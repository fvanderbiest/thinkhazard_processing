# -*- coding: utf-8 -*-

import transaction
import datetime
import numpy
import rasterio
import pyproj
from rasterio import features
from shapely.ops import (
    transform,
    cascaded_union
)
from shapely.geometry import Polygon
from functools import partial
from geoalchemy2.shape import to_shape
from sqlalchemy import func

from thinkhazard_common.models import (
    DBSession,
    AdministrativeDivision,
    AdminLevelType,
    HazardLevel,
    HazardType,
    HazardCategory,
    hazardcategory_administrativedivision_table,
    )
from .models import (
    HazardSet,
    Layer,
    Output,
    )
from . import settings


class ProcessException(Exception):
    def __init__(self, message):
        self.message = message


def process(hazardset_id=None, force=False):
    hazardsets = DBSession.query(HazardSet)
    hazardsets = hazardsets.filter(HazardSet.complete.is_(True))
    if hazardset_id is not None:
        hazardsets = hazardsets.filter(HazardSet.id == hazardset_id)
    if not force:
        hazardsets = hazardsets.filter(HazardSet.processed.is_(False))
    if hazardsets.count() == 0:
        print 'No hazardsets to process'
        return
    for hazardset in hazardsets:
        process_hazardset(hazardset, force=force)


def upscale_hazardcategories(target_adminlevel_mnemonic):
    # identify the admin divisions matching the given level:
    admindivs = DBSession.query(AdministrativeDivision)\
        .join(AdminLevelType) \
        .filter(AdminLevelType.mnemonic == target_adminlevel_mnemonic)
    hazardtypes = DBSession.query(HazardType)
    # for each of these admin divisions and hazard types,
    # identify the highest HazardCategory among their children:
    for admindiv in admindivs:
        # identify max(level) for each hazardtype across children
        for hazardtype in hazardtypes:
            hazardcategory = DBSession.query(HazardCategory) \
                .join((AdministrativeDivision, HazardCategory.administrativedivisions)) \
                .join(HazardType) \
                .filter(HazardType.id == hazardtype.id) \
                .filter(AdministrativeDivision.parent == admindiv) \
                .order_by(HazardCategory.hazardlevel_id.desc()).first()
            if hazardcategory:
                # find the highest hazardlevel for all children admindivs
                print '[upscaling] admindiv {} inherits hazardlevel {} for {}'\
                    .format(admindiv.code, hazardcategory.hazardlevel_id,
                            hazardcategory.hazardtype.mnemonic)
                admindiv.hazardcategories.append(hazardcategory)
                DBSession.add(admindiv)


def process_outputs():
    print "Decision Tree running..."
    # first of all, remove all records
    # in the datamart table linking admin divs with hazard categories:
    hazardcategory_administrativedivision_table.delete()
    # identify the admin level for which we run the decision tree:
    # (REG)ion aka admin level 2
    dt_level = DBSession.query(AdminLevelType)\
        .filter(AdminLevelType.mnemonic == u'REG').one()
    # then, identify the unique (admindiv, hazardtype) tuples
    # contained in the Output table:
    admindiv_hazardtype_tuples = (
        DBSession.query(AdministrativeDivision, HazardType).distinct()
        .join(Output)
        .join(HazardSet)
        .join(HazardType)
        # the following should not be necessary in production
        # because only the lowest admin levels should be inserted
        # in the Output table:
        .filter(AdministrativeDivision.leveltype_id == dt_level.id)
        # not necessary, but practical for debugging:
        .order_by(AdministrativeDivision.code)
    )
    # for each tuple, identify the most relevant HazardSet
    # in the light of the criteria that we all agreed on (cf Decision Tree):
    for (admindiv, hazardtype) in admindiv_hazardtype_tuples:
        (hazardset, output) = DBSession.query(HazardSet, Output) \
            .join(Output) \
            .filter(Output.admin_id == admindiv.id) \
            .filter(HazardSet.hazardtype_id == hazardtype.id) \
            .order_by(HazardSet.calculation_method_quality.desc(),
                      HazardSet.scientific_quality.desc(),
                      HazardSet.local.desc(),
                      HazardSet.data_lastupdated_date.desc()).first()
        print "[decision tree] admindiv {} gets hazardlevel {} from {} for {}"\
            .format(admindiv.code, output.hazardlevel_id, hazardset.id,
                    hazardtype.mnemonic)
        # find the relevant HazardCategory for the current hazardtype
        # and the hazardset's hazardlevel
        hazardcategory = DBSession.query(HazardCategory) \
            .filter(HazardCategory.hazardtype_id == hazardtype.id) \
            .filter(HazardCategory.hazardlevel_id == output.hazardlevel_id) \
            .one()
        # append new hazardcategory to current admin div:
        admindiv.hazardcategories.append(hazardcategory)
        DBSession.add(admindiv)

    # UpScaling level2 (REG)ion -> level1 (PRO)vince
    upscale_hazardcategories(u'PRO')
    # UpScaling level1 (PRO)vince -> level0 (COU)ntry
    upscale_hazardcategories(u'COU')

    transaction.commit()


def process_hazardset(hazardset, force=False):
    print hazardset.id
    chrono = datetime.datetime.now()
    last_percent = 0

    level_VLO = HazardLevel.get(u'VLO')

    if hazardset is None:
        raise ProcessException('HazardSet {} does not exist.'
                               .format(hazardset.id))

    if hazardset.processed:
        if force:
            hazardset.processed = False
        else:
            raise ProcessException('HazardSet {} has already been processed.'
                                   .format(hazardset.id))

    # clean previous outputs
    DBSession.query(Output) \
        .filter(Output.hazardset_id == hazardset.id) \
        .delete()
    DBSession.flush()

    hazardtype = hazardset.hazardtype
    hazardtype_settings = settings['hazard_types'][hazardtype.mnemonic]
    thresholds = hazardtype_settings['thresholds']

    project = partial(
        pyproj.transform,
        pyproj.Proj(init='epsg:3857'),
        pyproj.Proj(init='epsg:4326'))

    layers = {}
    for level in (u'HIG', u'MED', u'LOW'):
        hazardlevel = HazardLevel.get(level)
        layer = DBSession.query(Layer) \
            .filter(Layer.hazardset_id == hazardset.id) \
            .filter(Layer.hazardlevel_id == hazardlevel.id) \
            .one()
        layers[level] = layer

    with rasterio.drivers():
        with rasterio.open(layers['HIG'].path()) as src_hig, \
                rasterio.open(layers['MED'].path()) as src_med, \
                rasterio.open(layers['LOW'].path()) as src_low:
            readers = {}
            readers['HIG'] = src_hig
            readers['MED'] = src_med
            readers['LOW'] = src_low

            polygon_hig = polygonFromBounds(src_hig.bounds)
            polygon_med = polygonFromBounds(src_med.bounds)
            polygon_low = polygonFromBounds(src_low.bounds)
            polygon = cascaded_union((
                polygon_hig,
                polygon_med,
                polygon_low))

            adminlevel_REG = AdminLevelType.get(u'REG')

            admindivs = DBSession.query(AdministrativeDivision) \
                .filter(AdministrativeDivision.leveltype_id == adminlevel_REG.id) \

            if hazardset.local:
                admindivs = admindivs \
                    .filter(
                        func.ST_Transform(AdministrativeDivision.geom, 4326)
                        .intersects(
                            func.ST_GeomFromText(polygon.wkt, 4326))) \
                    .filter(func.ST_Intersects(
                        func.ST_Transform(AdministrativeDivision.geom, 4326),
                        func.ST_GeomFromText(polygon.wkt, 4326)))

            current = 0
            outputs = 0
            total = admindivs.count()
            for admindiv in admindivs:
                # print ' ', admindiv.id, admindiv.code, admindiv.name

                current += 1
                if admindiv.geom is None:
                    print '   ', ('{}-{} has null geometry'
                                  .format(admindiv.code, admindiv.name))
                    continue

                reprojected = transform(
                    project,
                    to_shape(admindiv.geom))

                output = Output()
                output.hazardset = hazardset
                output.administrativedivision = admindiv
                output.hazardlevel = None

                # TODO: calculate coverage ratio
                output.coverage_ratio = 100

                for level in (u'HIG', u'MED', u'LOW'):
                    layer = layers[level]
                    src = readers[level]

                    if not reprojected.intersects(polygon):
                        continue

                    window = src.window(*reprojected.bounds)
                    data = src.read(1, window=window, masked=True)
                    if data.shape[0] * data.shape[1] == 0:
                        continue

                    threshold = thresholds[layer.hazardunit]
                    positive_data = (data > threshold).astype(rasterio.uint8)

                    division = features.rasterize(
                        ((g, 1) for g in [reprojected]),
                        out_shape=data.shape,
                        transform=src.window_transform(window),
                        all_touched=True)

                    masked = numpy.ma.masked_array(positive_data,
                                                   mask=~division.astype(bool))

                    if str(numpy.max(masked)) == str(numpy.ma.masked):
                        break
                    else:
                        if output.hazardlevel is None:
                            output.hazardlevel = level_VLO

                    if numpy.max(masked) > 0:
                        output.hazardlevel = layer.hazardlevel
                        break

                if output.hazardlevel is not None:
                    # print '    hazardlevel :', output.hazardlevel.mnemonic
                    DBSession.add(output)
                    outputs += 1

                percent = int(100.0 * current / total)
                if percent % 10 == 0 and percent != last_percent:
                    print '  ... processed {}%'.format(percent)
                    last_percent = percent
                    pass

    hazardset.processed = True

    DBSession.flush()
    transaction.commit()

    print ('Successfully processed {} divisions, {} outputs generated in {}'
           .format(total, outputs, datetime.datetime.now() - chrono))


def polygonFromBounds(bounds):
    return Polygon([
        (bounds[0], bounds[1]),
        (bounds[0], bounds[3]),
        (bounds[2], bounds[3]),
        (bounds[2], bounds[1]),
        (bounds[0], bounds[1])])

# -*- coding: utf-8 -*-

import transaction
import datetime
import numpy
import rasterio
import pyproj
from rasterio import features
from shapely.ops import transform
from functools import partial
from geoalchemy2.shape import to_shape

from thinkhazard_common.models import (
    DBSession,
    AdministrativeDivision,
    HazardLevel,
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


def process_pendings():
    ids = DBSession.query(HazardSet.id) \
        .filter(HazardSet.complete.is_(True)) \
        .filter(HazardSet.processed.is_(False))
    for id in ids:
        process_hazardset(id)


def process_all():
    ids = DBSession.query(HazardSet.id) \
        .filter(HazardSet.complete.is_(True))
    for id in ids:
        process_hazardset(id, force=True)


def process_hazardset(hazardset_id, force=False):
    print hazardset_id
    chrono = datetime.datetime.now()

    hazardset = DBSession.query(HazardSet).get(hazardset_id)
    if hazardset is None:
        raise ProcessException('HazardSet {} does not exist.'
                               .format(hazardset_id))

    if hazardset.processed:
        if force:
            hazardset.processed = False
            DBSession.flush()
        else:
            raise ProcessException('HazardSet {} has already been processed.'
                                   .format(hazardset_id))

    # lean previous outputs
    DBSession.query(Output) \
        .filter(hazardset_id == hazardset_id) \
        .delete()

    hazardtype = hazardset.hazardtype
    hazardtype_settings = settings['hazard_types'][hazardtype.mnemonic]
    threshold = hazardtype_settings['threshold']

    project = partial(pyproj.transform,
                      pyproj.Proj(init='epsg:3857'),
                      pyproj.Proj(init='epsg:4326'))

    print 'Reading raster data'
    with rasterio.drivers():
        # Register GDAL format drivers and configuration options with a
        # context manager.
        layers = []
        for level in (u'HIG', u'MED', u'LOW'):
            hazardlevel = HazardLevel.get(level)
            layer = DBSession.query(Layer) \
                .filter(Layer.hazardset_id == hazardset.id) \
                .filter(Layer.hazardlevel_id == hazardlevel.id) \
                .one()

            with rasterio.open(layer.path()) as src:
                src_data = src.read()
                layer.shape = src.shape
                layer.transform = src.transform
            threshold_value = threshold[layer.hazardunit]
            layer.data = (src_data > threshold_value).astype(rasterio.uint8)

            layers.append(layer)

    print 'Reading admin divisions'
    admindivs = (
        DBSession.query(AdministrativeDivision)
        .filter(AdministrativeDivision.leveltype_id == 2)
    )

    print 'Processing'
    current = 0
    total = admindivs.count()
    for admindiv in admindivs:
        current += 1

        if admindiv.geom is None:
            print admindiv.id, admindiv.code, admindiv.name, ' null geometry'
            continue

        output = Output()
        output.hazardset = hazardset
        output.administrativedivision = admindiv
        output.hazardlevel = HazardLevel.get(u'NPR')

        for layer in layers:
            division = features.rasterize(
                ((g, 1) for g in [transform(project,
                                            to_shape(admindiv.geom))]),
                out_shape=layer.shape,
                transform=layer.transform,
                all_touched=True)

            masked = numpy.ma.masked_array(layer.data,
                                           mask=~division.astype(bool))
            if numpy.max(masked) > 0:
                output.hazardlevel = layer.hazardlevel

        # TODO: calculate coverage ratio
        output.coverage_ratio = 100

        DBSession.add(output)

        percent = int(100.0 * current / total)
        if percent % 1 == 0:
            print '... processed {}%'.format(percent)

    hazardset.processed = True
    DBSession.flush()
    transaction.commit()

    print ('Successfully processed {} divisions:'
           .format(current), datetime.datetime.now() - chrono)

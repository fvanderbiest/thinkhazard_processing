# -*- coding: utf-8 -*-

import sys
import argparse
import datetime
import numpy
import rasterio
import pyproj
from rasterio import features
from shapely.ops import transform
from functools import partial

from sqlalchemy import engine_from_config
from geoalchemy2.shape import to_shape


from .. import settings
from ..models import DBSession, AdministrativeDivision, Dataset, Layer, Output


class ProcessException(Exception):
    def __init__(self, message):
        self.message = message


def main(argv=sys.argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('hazard_set', help='The hazard set identifier')
    parser.add_argument(
        '--force', dest='force',
        action='store_const', const=True, default=False,
        help='Force execution even if dataset has already been processed')
    args = parser.parse_args(argv[1:])

    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)

    try:
        execute(DBSession, args.hazard_set, args.force)
    except ProcessException as e:
        print e.message


def execute(hazard_set_id, force=False):
    chrono = datetime.datetime.now()

    dataset = DBSession.query(Dataset).get(hazard_set_id)
    if dataset is None:
        raise ProcessException('Dataset {} does not exists.'
                               .format(hazard_set_id))

    if dataset.processed:
        if force:
            dataset.processed = False
            DBSession.flush()
        else:
            raise ProcessException('Dataset {} has already been processed.'
                                   .format(hazard_set_id))

    # lean previous outputs
    (
        DBSession.query(Output)
        .filter(hazard_set_id == hazard_set_id)
        .delete()
    )

    print 'Reading raster data'
    threshold = settings['threshold']
    rasters = []
    with rasterio.drivers():
        for return_period in settings['return_periods']:
            hazard_level = settings['return_periods'].index(return_period) + 1
            layer = (
                DBSession.query(Layer)
                .filter(Layer.hazard_set_id == hazard_set_id)
                .filter(Layer.return_period == return_period)
                .first()
            )
            if dataset is None:
                raise ProcessException('Layer {} {}) does not exists.'
                                       .format(hazard_set_id, return_period))

            # Register GDAL format drivers and configuration options with a
            # context manager.
            with rasterio.open(layer.path()) as src:
                src_data = src.read()

            dst_data = (src_data > threshold).astype(rasterio.uint8)
            rasters.append((dst_data, hazard_level))

    project = partial(pyproj.transform,
                      pyproj.Proj(init='epsg:3857'),
                      pyproj.Proj(init='epsg:4326'))

    print 'Reading admin divisions'
    query = (
        DBSession.query(AdministrativeDivision)
        .filter(AdministrativeDivision.leveltype_id == 2)
    )
    admindivs = query.all()

    print 'Processing'
    current = 0
    for admindiv in admindivs:
        current += 1

        if admindiv.geom is None:
            print admindiv.id, admindiv.code, admindiv.name, ' null geometry'
            continue

        division = features.rasterize(
            ((g, 1) for g in [transform(project, to_shape(admindiv.geom))]),
            out_shape=src.shape,
            transform=src.transform,
            all_touched=True
            )

        output = Output()
        output.admin_id = admindiv.id
        output.hazard_set_id = hazard_set_id
        output.hazard_level = 4
        for (raster, hazard_level) in rasters:
            masked = numpy.ma.masked_array(raster, mask=~division.astype(bool))
            if numpy.max(masked) > 0:
                output.hazard_level = hazard_level

        DBSession.add(output)

        if current % 100 == 0:
            print '... processed {} divisions'.format(current)

    dataset.processed = True
    print ('Successfully processed {} divisions:'
           .format(current), datetime.datetime.now() - chrono)

    print 'Committing transaction'
    DBSession.commit()

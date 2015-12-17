import logging
import transaction
import datetime
import rasterio
import pyproj
from rasterio import (
    features,
    window_shape)
from shapely.ops import transform
from shapely.geometry import box
from functools import partial
from geoalchemy2.shape import to_shape
from sqlalchemy import func

from thinkhazard_common.models import (
    DBSession,
    AdministrativeDivision,
    AdminLevelType,
    HazardLevel,
    )
from .models import (
    HazardSet,
    Layer,
    Output,
    )
from . import settings


logger = logging.getLogger(__name__)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

logger.setLevel(logging.DEBUG)


project = partial(
    pyproj.transform,
    pyproj.Proj(init='epsg:3857'),
    pyproj.Proj(init='epsg:4326'))


class ProcessException(Exception):
    def __init__(self, message):
        self.message = message


def process(hazardset_id=None, force=False, dry_run=False):
    ids = DBSession.query(HazardSet.id) \
        .filter(HazardSet.complete.is_(True))
    if hazardset_id is not None:
        ids = ids.filter(HazardSet.id == hazardset_id)
    if not force:
        ids = ids.filter(HazardSet.processed.is_(False))
    if ids.count() == 0:
        logger.info('No hazardsets to process')
        return
    for id in ids:
        logger.info(id[0])
        try:
            process_hazardset(id[0], force=force)
            if dry_run:
                logger.info('  Abording transaction')
                transaction.abort()
            else:
                logger.info('  Committing transaction')
                transaction.commit()
        except Exception as e:
            transaction.abort()
            logger.error(e.message)


def process_hazardset(hazardset_id, force=False):
    hazardset = DBSession.query(HazardSet).get(hazardset_id)
    if hazardset is None:
        raise ProcessException('HazardSet {} does not exist.'
                               .format(hazardset_id))

    chrono = datetime.datetime.now()

    if hazardset.processed:
        if force:
            hazardset.processed = False
        else:
            raise ProcessException('HazardSet {} has already been processed.'
                                   .format(hazardset.id))

    logger.info("  Cleaning previous outputs")
    DBSession.query(Output) \
        .filter(Output.hazardset_id == hazardset.id) \
        .delete()
    DBSession.flush()

    type_settings = settings['hazard_types'][hazardset.hazardtype.mnemonic]

    with rasterio.drivers():
        try:
            logger.info("  Openning raster files")
            # Open rasters
            layers = {}
            readers = {}
            if type_settings['preprocessed']:
                layer = DBSession.query(Layer) \
                    .filter(Layer.hazardset_id == hazardset.id) \
                    .one()
                reader = rasterio.open(layer.path())

                layers[0] = layer
                readers[0] = reader

            else:
                for level in (u'HIG', u'MED', u'LOW'):
                    hazardlevel = HazardLevel.get(level)
                    layer = DBSession.query(Layer) \
                        .filter(Layer.hazardset_id == hazardset.id) \
                        .filter(Layer.hazardlevel_id == hazardlevel.id) \
                        .one()
                    reader = rasterio.open(layer.path())

                    layers[level] = layer
                    readers[level] = reader
                if ('mask_return_period' in type_settings):
                    layer = DBSession.query(Layer) \
                        .filter(Layer.hazardset_id == hazardset.id) \
                        .filter(Layer.mask.is_(True)) \
                        .one()
                    reader = rasterio.open(layer.path())
                    layers['mask'] = layer
                    readers['mask'] = reader

            outputs = create_outputs(hazardset, layers, readers)
            if outputs:
                DBSession.add_all(outputs)

        finally:
            logger.info("  Closing raster files")
            for key, reader in readers.iteritems():
                if reader and not reader.closed:
                    reader.close()

    hazardset.processed = True
    DBSession.flush()

    logger.info('  Successfully processed {}, {} outputs generated in {}'
                .format(hazardset.id,
                        len(outputs),
                        datetime.datetime.now() - chrono))

    return True


def create_outputs(hazardset, layers, readers):
    type_settings = settings['hazard_types'][hazardset.hazardtype.mnemonic]
    adminlevel_REG = AdminLevelType.get(u'REG')

    bbox = None
    for reader in readers.itervalues():
        polygon = polygon_from_boundingbox(reader.bounds)
        if bbox is None:
            bbox = polygon
        else:
            bbox = bbox.intersection(polygon)

    admindivs = DBSession.query(AdministrativeDivision) \
        .filter(AdministrativeDivision.leveltype_id == adminlevel_REG.id)

    if hazardset.local:
        # TODO : this could be optimized (double reprojection)
        # Better to had a geom_4326 column
        admindivs = admindivs \
            .filter(
                func.ST_Transform(AdministrativeDivision.geom, 4326)
                .intersects(
                    func.ST_GeomFromText(bbox.wkt, 4326))) \
            .filter(func.ST_Intersects(
                func.ST_Transform(AdministrativeDivision.geom, 4326),
                func.ST_GeomFromText(bbox.wkt, 4326)))

    current = 0
    last_percent = 0
    outputs = []
    total = admindivs.count()
    logger.info('  Iterating over {} administrative divisions'.format(total))
    for admindiv in admindivs:
        # print ' ', admindiv.id, admindiv.code, admindiv.name

        current += 1
        if admindiv.geom is None:
            logger.warning('    {}-{} has null geometry'
                           .format(admindiv.code, admindiv.name))
            continue

        reprojected = transform(
            project,
            to_shape(admindiv.geom))

        if not reprojected.intersects(bbox):
            continue

        # Try block to include admindiv.code in exception message
        try:
            if type_settings['preprocessed']:
                hazardlevel = preprocessed_hazardlevel(hazardset,
                                                       layers[0], readers[0],
                                                       reprojected)
            else:
                hazardlevel = notpreprocessed_hazardlevel(hazardset,
                                                          layers, readers,
                                                          reprojected)

        except Exception as e:
            e.message = ("{}-{} raise an exception :\n{}"
                         .format(admindiv.code, admindiv.name, e.message))
            raise

        # Create output record
        if hazardlevel is not None:
            # print '    hazardlevel :', output.hazardlevel.mnemonic
            output = Output()
            output.hazardset = hazardset
            output.administrativedivision = admindiv
            output.hazardlevel = hazardlevel
            # TODO: calculate coverage ratio
            output.coverage_ratio = 100
            outputs.append(output)

        percent = int(100.0 * current / total)
        if percent % 10 == 0 and percent != last_percent:
            logger.info('  ... processed {}%'.format(percent))
            last_percent = percent

    return outputs


def shape_size_exceeds(reader, bounds):
    '''Check the size of the matrix to read from reader
    Some multipolygons crosses the dateline.
    This can result in a memory error with large raster files.
    We bypass this iterate through polygons.
    See admindiv.code = 28773 for example.
    '''
    window = reader.window(*bounds)
    shape = window_shape(window)
    if shape[0] * shape[1] * 4 > 100000000:
        logger.debug("    iterate through multipolygon parts")
        return True
    return False


def preprocessed_hazardlevel(hazardset, layer, reader, geometry):
    type_settings = settings['hazard_types'][hazardset.hazardtype.mnemonic]

    hazardlevel = None

    if shape_size_exceeds(reader, geometry.bounds):
        polygons = geometry.geoms
    else:
        polygons = geometry

    for polygon in polygons:
        window = reader.window(*polygon.bounds)
        data = reader.read(1, window=window, masked=True)
        if data.shape[0] * data.shape[1] == 0:
            continue
        if data.mask.all():
            continue

        division = features.rasterize(
            ((g, 1) for g in [polygon]),
            out_shape=data.shape,
            transform=reader.window_transform(window),
            all_touched=True)

        data.mask = data.mask | ~division.astype(bool)

        if data.mask.all():
            continue

        for level in (u'HIG', u'MED', u'LOW', u'VLO'):
            level_obj = HazardLevel.get(unicode(level))
            if level_obj <= hazardlevel:
                break

            if level in type_settings['values']:
                values = type_settings['values'][level]
                for value in values:
                    if value in data:
                        hazardlevel = level_obj
                        break

    return hazardlevel


def notpreprocessed_hazardlevel(hazardset, layers, readers, geometry):
    type_settings = settings['hazard_types'][hazardset.hazardtype.mnemonic]
    level_VLO = HazardLevel.get(u'VLO')

    hazardlevel = None

    for level in (u'HIG', u'MED', u'LOW'):
        layer = layers[level]
        reader = readers[level]

        threshold = get_threshold(hazardset.hazardtype.mnemonic,
                                  layer.local,
                                  layer.hazardlevel.mnemonic,
                                  layer.hazardunit)
        if threshold is None:
            raise ProcessException(
                'No threshold found for {} {} {} {}'
                .format(hazardset.hazardtype.mnemonic,
                        'local' if layer.local else 'global',
                        layer.hazardlevel.mnemonic,
                        layer.hazardunit))

        if shape_size_exceeds(reader, geometry.bounds):
            polygons = geometry.geoms
        else:
            polygons = geometry

        for polygon in polygons:
            window = reader.window(*polygon.bounds)
            data = reader.read(1, window=window, masked=True)
            if data.shape[0] * data.shape[1] == 0:
                continue
            if data.mask.all():
                continue

            division = features.rasterize(
                ((g, 1) for g in [polygon]),
                out_shape=data.shape,
                transform=reader.window_transform(window),
                all_touched=True)

            inverted_comparison = ('inverted_comparison' in type_settings and
                                   type_settings['inverted_comparison'])
            if inverted_comparison:
                data = data < threshold
            else:
                data = data > threshold

            if ('mask_return_period' in type_settings):
                mask = readers['mask'].read(1, window=window, masked=True)
                if inverted_comparison:
                    mask = mask < threshold
                else:
                    mask = mask > threshold

                data.mask = data.mask | mask

            data.mask = data.mask | ~division.astype(bool)

            if data.any():
                hazardlevel = layer.hazardlevel
                break

            if data.mask.all():
                continue

            if hazardlevel is None:
                hazardlevel = level_VLO

        if hazardlevel == layer.hazardlevel:
            break

    return hazardlevel


def polygon_from_boundingbox(boundingbox):
    return box(boundingbox[0],
               boundingbox[1],
               boundingbox[2],
               boundingbox[3])


def get_threshold(hazardtype, local, level, unit):
    mysettings = settings['hazard_types'][hazardtype]['thresholds']
    while type(mysettings) is dict:
        if 'local' in mysettings.keys():
            mysettings = mysettings['local'] if local else mysettings['global']
        elif 'HIG' in mysettings.keys():
            mysettings = mysettings[level]
        elif unit in mysettings.keys():
            mysettings = mysettings[unit]
    return float(mysettings)

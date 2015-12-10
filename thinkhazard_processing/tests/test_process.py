import unittest
import transaction
from datetime import datetime
from shapely.geometry import (
    MultiPolygon,
    Polygon,
    )
from geoalchemy2.shape import from_shape
import numpy as np
from mock import Mock, patch
from rasterio._io import RasterReader
from affine import Affine
from thinkhazard_common.models import (
    DBSession,
    AdminLevelType,
    AdministrativeDivision,
    HazardType,
    HazardLevel,
    )
from . import settings
from ..models import (
    HazardSet,
    Layer,
    Output,
    )
from ..processing import process


def populate():
    DBSession.query(Output).delete()
    DBSession.query(Layer).delete()
    DBSession.query(HazardSet).delete()
    DBSession.query(AdministrativeDivision).delete()
    populate_datamart()
    populate_processing()
    transaction.commit()


def rasterio_open(reader):
    mock = Mock()
    mock.__enter__ = Mock(return_value=reader)
    mock.__exit__ = Mock(return_value=False)
    return mock


def global_reader(value=None):
    array = np.empty(shape=(360, 720), dtype=np.float32, order='C')
    if value is not None:
        array.fill(value)
    transform = Affine(-180., 0.5, 0.0, 90., 0.0, -0.5)
    reader = Mock(spec=RasterReader)
    reader.read.return_value = array
    reader.shape = array.shape
    reader.transform = transform
    reader.bounds = (-180., -90., 180., 90.)
    reader.window.return_value = ((0, 359), (0, 719))
    reader.window_transform.return_value = transform
    return reader


class TestProcess(unittest.TestCase):

    def setUp(self):
        populate()

    @patch('rasterio.open')
    def test_process_nodata(self, open_mock):
        '''Test nodata everywhere'''
        open_mock.side_effect = [
            rasterio_open(global_reader()),
            rasterio_open(global_reader()),
            rasterio_open(global_reader())
        ]
        rasterio_open.return_period = None
        rasterio_open.value = None
        process(force=True)
        output = DBSession.query(Output).first()
        self.assertEqual(output.hazardlevel.mnemonic, 'VLO')

    @patch('rasterio.open')
    def test_process_low(self, open_mock):
        '''Test value > threshold in LOW layer'''
        open_mock.side_effect = [
            rasterio_open(global_reader()),
            rasterio_open(global_reader()),
            rasterio_open(global_reader(100.0))
        ]
        process(force=True)
        output = DBSession.query(Output).first()
        self.assertEqual(output.hazardlevel.mnemonic, 'LOW')

    @patch('rasterio.open')
    def test_process_medium(self, open_mock):
        '''Test value > threshold in MED layer'''
        open_mock.side_effect = [
            rasterio_open(global_reader()),
            rasterio_open(global_reader(100.0)),
            rasterio_open(global_reader())
        ]
        process(force=True)
        output = DBSession.query(Output).first()
        self.assertEqual(output.hazardlevel.mnemonic, 'MED')

    @patch('rasterio.open', side_effect=rasterio_open)
    def test_process_high(self, open_mock):
        '''Test value > threshold in HIG layer'''
        open_mock.side_effect = [
            rasterio_open(global_reader(100.0)),
            rasterio_open(global_reader()),
            rasterio_open(global_reader())
        ]
        process(force=True)
        output = DBSession.query(Output).first()
        self.assertEqual(output.hazardlevel.mnemonic, 'HIG')


def populate_datamart():
    print 'populate datamart'
    adminlevel_REG = AdminLevelType.get(u'REG')

    from functools import partial
    import pyproj
    from shapely.ops import transform

    project = partial(
        pyproj.transform,
        pyproj.Proj(init='epsg:4326'),
        pyproj.Proj(init='epsg:3857'))

    shape = MultiPolygon([
        Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])
    ])
    reprojected = transform(
        project,
        shape)
    geometry = from_shape(reprojected, 3857)

    div = AdministrativeDivision(**{
        'code': 30,
        'leveltype_id': adminlevel_REG.id,
        'name': u'Administrative division level 3'
    })
    div.geom = geometry
    div.hazardcategories = []
    DBSession.add(div)

    DBSession.flush()


def populate_processing():
    print 'populate processing'
    hazardset_id = u'test'
    hazardtype = HazardType.get(u'EQ')
    hazardtype_settings = settings['hazard_types'][hazardtype.mnemonic]

    print 'Populating hazardset {}'.format(hazardset_id)
    hazardset = HazardSet()
    hazardset.id = hazardset_id
    hazardset.hazardtype = hazardtype
    hazardset.local = False
    hazardset.data_lastupdated_date = datetime.now()
    hazardset.metadata_lastupdated_date = datetime.now()
    DBSession.add(hazardset)

    return_periods = hazardtype_settings['global']['return_periods']
    unit = hazardtype_settings['thresholds'].keys()[0]

    for level in (u'HIG', u'MED', u'LOW'):
        hazardlevel = HazardLevel.get(level)
        return_period = return_periods[level]

        layer = Layer()
        layer.title = "{}-{}".format(id, return_period)
        layer.hazardlevel = hazardlevel
        layer.return_period = return_period
        layer.hazardunit = unit
        layer.data_lastupdated_date = datetime.now()
        layer.metadata_lastupdated_date = datetime.now()
        layer.geonode_id = new_geonode_id()
        layer.download_url = 'test'
        layer.calculation_method_quality = 5
        layer.scientific_quality = 1
        layer.local = False
        layer.downloaded = True
        hazardset.layers.append(layer)
        DBSession.flush()

    hazardset.complete = True
    DBSession.flush()


def new_geonode_id():
    from sqlalchemy import func
    row = DBSession.query(func.max(Layer.geonode_id)).one_or_none()
    if row[0] is None:
        return 1
    return row[0] + 1

import unittest
import numpy as np
from mock import Mock, patch
from rasterio._io import RasterReader
from ..models import DBSession, Output
from ..scripts.process import execute
from . import hazard_set


def rasterio_open(reader):
    mock = Mock()
    mock.__enter__ = Mock(return_value=reader)
    mock.__exit__ = Mock(return_value=False)
    return mock


def global_reader(value=None):
    array = np.empty(shape=(361, 721), dtype=np.float32, order='C')
    if value is not None:
        array.fill(value)

    reader = Mock(spec=RasterReader)
    reader.read.return_value = array
    reader.shape = array.shape
    reader.transform = [-180.25, 0.5, 0.0, 90.25, 0.0, -0.5]
    return reader


class TestProcess(unittest.TestCase):

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

        execute(hazard_set, force=True)
        output = DBSession.query(Output).first()
        self.assertEqual(output.hazard_level, 4)

    @patch('rasterio.open')
    def test_process_low(self, open_mock):
        '''Test value > threshold in first layer'''
        open_mock.side_effect = [
            rasterio_open(global_reader(100.0)),
            rasterio_open(global_reader()),
            rasterio_open(global_reader())
        ]

        execute(hazard_set, force=True)
        output = DBSession.query(Output).first()
        self.assertEqual(output.hazard_level, 1)

    @patch('rasterio.open')
    def test_process_medium(self, open_mock):
        '''Test value > threshold in second layer'''
        open_mock.side_effect = [
            rasterio_open(global_reader()),
            rasterio_open(global_reader(100.0)),
            rasterio_open(global_reader())
        ]

        execute(hazard_set, force=True)
        output = DBSession.query(Output).first()
        self.assertEqual(output.hazard_level, 2)

    @patch('rasterio.open', side_effect=rasterio_open)
    def test_process_high(self, open_mock):
        '''Test value > threshold in third layer'''
        open_mock.side_effect = [
            rasterio_open(global_reader()),
            rasterio_open(global_reader()),
            rasterio_open(global_reader(100.0))
        ]

        execute(hazard_set, force=True)
        output = DBSession.query(Output).first()
        self.assertEqual(output.hazard_level, 3)

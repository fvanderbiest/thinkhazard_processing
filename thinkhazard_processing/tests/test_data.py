from shapely.geometry import (
    MultiPolygon,
    Polygon,
    )
from geoalchemy2.shape import from_shape

from ..models import DBSession, AdministrativeDivision, Dataset, Layer, Output
from .. import settings


def populate_admindiv():
    print 'Populating administrative divisions'
    shape = MultiPolygon([
        Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])
    ])
    geometry = from_shape(shape, 3857)

    div_level_1 = AdministrativeDivision(**{
        'code': 10,
        'leveltype_id': 1,
        'name': u'Division level 1'
    })
    div_level_1.geom = geometry
    DBSession.add(div_level_1)

    div_level_2 = AdministrativeDivision(**{
        'code': 20,
        'leveltype_id': 2,
        'name': u'Division level 2'
    })
    div_level_2.parent_code = div_level_1.code
    div_level_2.geom = geometry
    DBSession.add(div_level_2)

    div_level_3 = AdministrativeDivision(**{
        'code': 30,
        'leveltype_id': 3,
        'name': u'Division level 3'
    })
    div_level_3.parent_code = div_level_2.code
    div_level_3.geom = geometry
    div_level_3.hazardcategories = []
    DBSession.add(div_level_3)

    DBSession.flush()


def populate_dataset(hazard_set):
    print 'Populating dataset {}'.format(hazard_set)
    dataset = Dataset()
    dataset.hazard_set_id = hazard_set
    dataset.is_global = False
    DBSession.add(dataset)
    DBSession.flush()

    for return_period in settings['return_periods']:
        layer = Layer()
        layer.title = "{}-{}".format(hazard_set, return_period)
        layer.hazard_set_id = hazard_set
        layer.return_period = return_period
        layer.downloaded = True
        DBSession.add(layer)
        DBSession.flush()

    DBSession.commit()

from shapely.geometry import (
    MultiPolygon,
    Polygon,
    )
from geoalchemy2.shape import from_shape
from datetime import datetime
from uuid import uuid4

from thinkhazard_common.models import (
    DBSession,
    AdministrativeDivision,
    HazardType,
    HazardLevel,
    )
from ..models import (
    HazardSet,
    Layer,
    )
from .. import settings


hazardset_id = u'test'
geonode_layer_id = 0


def populate():
    populate_datamart()
    populate_processing()


def populate_processing():
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
    unit = hazardtype_settings['threshold'].keys()[0]

    for level in (u'HIG', u'MED', u'LOW'):
        hazardlevel = HazardLevel.get(level)
        return_period = return_periods[level]

        global geonode_layer_id
        geonode_layer_id += 1

        layer = Layer()
        layer.title = "{}-{}".format(id, return_period)
        layer.hazardlevel = hazardlevel
        layer.return_period = return_period
        layer.hazardunit = unit
        layer.data_lastupdated_date = datetime.now()
        layer.metadata_lastupdated_date = datetime.now()
        layer.geonode_id = geonode_layer_id
        layer.download_url = uuid4()
        layer.calculation_method_quality = 5
        layer.scientific_quality = 1
        layer.local = False
        layer.downloaded = True
        hazardset.layers.append(layer)

    hazardset.complete = True

    DBSession.flush()


def populate_datamart():
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

    shape = MultiPolygon([
        Polygon([(0, 0), (0, 1), (.5, 1), (.5, 0), (0, 0)])
    ])
    geometry = from_shape(shape, 3857)

    div_level_3_1 = AdministrativeDivision(**{
        'code': 30,
        'leveltype_id': 3,
        'name': u'Division level 3 - 1'
    })
    div_level_3_1.parent_code = div_level_2.code
    div_level_3_1.geom = geometry
    div_level_3_1.hazardcategories = []

    shape = MultiPolygon([
        Polygon([(.5, 0), (.5, 1), (1, 1), (1, 0), (.5, 0)])
    ])
    geometry = from_shape(shape, 3857)

    div_level_3_2 = AdministrativeDivision(**{
        'code': 31,
        'leveltype_id': 3,
        'name': u'Division level 3 - 2'
    })
    div_level_3_2.parent_code = div_level_2.code
    div_level_3_2.geom = geometry
    div_level_3_2.hazardcategories = []

    DBSession.flush()

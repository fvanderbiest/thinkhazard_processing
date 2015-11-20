import yaml
from sqlalchemy import engine_from_config

from .. import settings
from ..models import DBSession
from .test_data import populate_admindiv, populate_dataset


hazard_set = 'EQ-GLOBAL-GAR15'


local_settings_path = 'local.tests.yaml'

with open(local_settings_path, 'r') as f:
    settings.update(yaml.load(f.read()))


def populate_db():
    engine = engine_from_config(settings, 'sqlalchemy.')

    from ..scripts.initializedb import initdb
    initdb(engine, True)

    DBSession.configure(bind=engine)
    populate_admindiv()
    populate_dataset(hazard_set)
    DBSession.commit()

populate_db()

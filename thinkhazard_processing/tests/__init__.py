import yaml
from sqlalchemy import engine_from_config
import transaction

from .. import settings
from .test_data import populate


local_settings_path = 'local.tests.yaml'


with open(local_settings_path, 'r') as f:
    settings.update(yaml.load(f.read()))


def populate_db():
    engine = engine_from_config(settings, 'sqlalchemy.')

    from ..scripts.initializedb import initdb_processing
    initdb_processing(engine, True)

    with transaction.manager:
        populate()

populate_db()

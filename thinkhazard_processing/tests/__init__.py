import ConfigParser
from sqlalchemy import create_engine
from ..models import DBSession
from .test_data import populate_admindiv, populate_dataset


hazard_set = 'EQ-GLOBAL-GAR15'


local_settings_path = 'local.tests.ini'

# raise an error if the file doesn't exist
with open(local_settings_path):
    pass


def populate_db():
    config = ConfigParser.ConfigParser()
    config.read(local_settings_path)
    db_url = config.get('app:main', 'sqlalchemy.url')
    engine = create_engine(db_url)

    from ..scripts.initializedb import initdb
    initdb(engine, True)

    DBSession.configure(bind=engine)
    populate_admindiv()
    populate_dataset(hazard_set)
    DBSession.commit()

populate_db()

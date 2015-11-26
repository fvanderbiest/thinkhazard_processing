import sys
from sqlalchemy import engine_from_config

from .. import models  # NOQA
from .. import settings

from thinkhazard_common.scripts.initializedb import initdb, schema_exists


def initdb_processing(engine, drop_all=False):
    connection = engine.connect()
    trans = connection.begin()
    try:
        if not schema_exists(connection, 'processing'):
            connection.execute("CREATE SCHEMA processing;")
        initdb(connection, drop_all=drop_all)
        trans.commit()
    except:
        trans.rollback()
        raise


def main(argv=sys.argv):
    engine = engine_from_config(settings, 'sqlalchemy.')
    initdb_processing(engine)

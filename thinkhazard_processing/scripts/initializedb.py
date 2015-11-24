import sys
from sqlalchemy import engine_from_config

from .. import models  # NOQA
from .. import settings

from thinkhazard_common.scripts.initializedb import initdb, schema_exists


def initdb_processing(engine, drop_all=False):
    if not schema_exists(engine, 'processing'):
        engine.execute("CREATE SCHEMA processing;")
    initdb(engine, drop_all=drop_all)


def main(argv=sys.argv):
    engine = engine_from_config(settings, 'sqlalchemy.')
    initdb_processing(engine)

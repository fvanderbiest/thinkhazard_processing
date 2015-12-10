import sys
from sqlalchemy import engine_from_config

from thinkhazard_common.scripts.initializedb import (
    initdb,
    schema_exists,
    )

from ..models import Base  # NOQA
from .. import settings


def initdb_processing(engine, drop_all=False):
    if not schema_exists(engine, 'processing'):
        engine.execute("CREATE SCHEMA processing;")
    initdb(engine, drop_all=drop_all)


def main(argv=sys.argv):
    engine = engine_from_config(settings, 'sqlalchemy.')
    with engine.begin() as db:
        initdb_processing(db)

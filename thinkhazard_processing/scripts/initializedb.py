import sys
from sqlalchemy import engine_from_config

from ..models import Base
from ..settings import settings


def initdb(engine):
    engine.execute("CREATE SCHEMA processing;")
    Base.metadata.create_all(engine)


def main(argv=sys.argv):
    engine = engine_from_config(settings, 'sqlalchemy.')
    initdb(engine)

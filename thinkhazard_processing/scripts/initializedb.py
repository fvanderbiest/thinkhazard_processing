import sys
from sqlalchemy import engine_from_config

from ..models import Base
from .. import settings


def initdb(engine, drop_all=False):
    if drop_all:
        Base.metadata.drop_all(engine)
    if not schema_exists(engine, 'processing'):
        engine.execute("CREATE SCHEMA processing IF NOT EXISTS;")
    Base.metadata.create_all(engine)


def schema_exists(engine, schema_name):
    connection = engine.connect()
    sql = '''
SELECT count(*) AS count
FROM information_schema.schemata
WHERE schema_name = '{}';
'''.format(schema_name)
    result = connection.execute(sql)
    row = result.first()
    return row[0] == 1


def main(argv=sys.argv):
    engine = engine_from_config(settings, 'sqlalchemy.')
    initdb(engine)

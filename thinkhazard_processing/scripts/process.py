import sys
import argparse
from sqlalchemy import engine_from_config
from thinkhazard_common.models import DBSession
from .. import settings
from ..processing import process


def main(argv=sys.argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--hazardset_id',  dest='hazardset_id', action='store',
        help='The hazard set identifier')
    parser.add_argument(
        '--force', dest='force',
        action='store_const', const=True, default=False,
        help='Force execution even if hazardset has already been processed')
    args = parser.parse_args(argv[1:])

    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)

    process(
        hazardset_id=args.hazardset_id,
        force=args.force)

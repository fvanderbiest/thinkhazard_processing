import sys
import argparse
from sqlalchemy import engine_from_config

from thinkhazard_common.models import DBSession

from .. import settings
from ..decisiontree import apply_decision_tree


def main(argv=sys.argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dry-run', dest='dry_run',
        action='store_const', const=True, default=False,
        help='Perform a trial run that do not commit changes')
    args = parser.parse_args(argv[1:])

    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)

    apply_decision_tree(dry_run=args.dry_run)

# -*- coding: utf-8 -*-

import sys
import argparse
import transaction
from sqlalchemy import engine_from_config
from thinkhazard_common.models import DBSession
from .. import settings
from ..processing import (
    process_all,
    process_pendings,
    process_hazardset,
    )


def main(argv=sys.argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--hazard_set',  dest='hazard_set', action='store',
        help='The hazard set identifier')
    parser.add_argument(
        '--force', dest='force',
        action='store_const', const=True, default=False,
        help='Force execution even if dataset has already been processed')
    args = parser.parse_args(argv[1:])

    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)

    if args.hazard_set is not None:
        with transaction.manager:
            process_hazardset(args.hazard_set, args.force)
    else:
        if args.force:
            process_all()
        else:
            process_pendings()

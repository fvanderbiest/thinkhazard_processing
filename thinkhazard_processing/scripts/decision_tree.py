# coding: utf-8

import sys
from sqlalchemy import engine_from_config
from thinkhazard_common.models import DBSession
from .. import settings
from ..processing import (
    process_outputs,
    )


def main(argv=sys.argv):
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    process_outputs()

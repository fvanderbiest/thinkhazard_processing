import os
import yaml

from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    )
from zope.sqlalchemy import ZopeTransactionExtension

# Overwrite the DBSession class with option keep_session=True
# we don't want session to be closed on commit in the processing package.
from thinkhazard_common import models
models.DBSession = scoped_session(sessionmaker(
    extension=ZopeTransactionExtension(keep_session=True)))


def load_settings():
    root_folder = os.path.join(os.path.dirname(__file__), '..')
    main_settings_path = os.path.join(root_folder,
                                      'thinkhazard_processing.yaml')
    with open(main_settings_path, 'r') as f:
        settings = yaml.load(f.read())

    local_settings_path = os.path.join(root_folder,
                                       'local_settings.yaml')
    if os.path.exists(local_settings_path):
        with open(local_settings_path, 'r') as f:
            settings.update(yaml.load(f.read()))

    return settings

settings = load_settings()

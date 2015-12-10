from thinkhazard_common.models import DBSession
from ..models import Layer
from sqlalchemy import func


def new_geonode_id():
    row = DBSession.query(func.max(Layer.geonode_id)).one_or_none()
    if row[0] is None:
        return 1
    return row[0] + 1

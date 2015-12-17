from thinkhazard_common.models import (
    DBSession,
    AdminLevelType,
    )


def apply_decision_tree(dry_run=False):
    connection = DBSession.bind.connect()
    trans = connection.begin()
    try:
        print "Purging previous relations"
        connection.execute(clearall_query())
        print "Calculating level REG"
        connection.execute(level_REG_query())
        print "Upscaling to PRO"
        connection.execute(upscaling_query(u'PRO'))
        print "Upscaling to COU"
        connection.execute(upscaling_query(u'COU'))
        if dry_run:
            trans.rollback()
        else:
            trans.commit()
    except:
        trans.rollback()
        raise


def clearall_query():
    return '''
DELETE FROM datamart.rel_hazardcategory_administrativedivision;
'''


def level_REG_query():
    return '''
INSERT INTO datamart.rel_hazardcategory_administrativedivision (
    administrativedivision_id,
    hazardcategory_id,
    source
)
SELECT DISTINCT
    o.admin_id AS administrativedivision_id,
    first_value(hc.id) OVER w AS hazardcategory_id,
    first_value(hs.id) OVER w AS source
FROM
    processing.output AS o
    JOIN processing.hazardset AS hs
        ON hs.id = o.hazardset_id
    JOIN datamart.hazardcategory AS hc
        ON hc.hazardtype_id = hs.hazardtype_id
        AND hc.hazardlevel_id = o.hazardlevel_id
WINDOW w AS (
    PARTITION BY
        o.admin_id,
        hs.hazardtype_id
    ORDER BY
        hs.calculation_method_quality DESC,
        hs.scientific_quality DESC,
        hs.local DESC,
        hs.data_lastupdated_date DESC
)
ORDER BY
    o.admin_id;
'''


def upscaling_query(level):
    return '''
INSERT INTO datamart.rel_hazardcategory_administrativedivision (
    administrativedivision_id,
    hazardcategory_id,
    source
)
SELECT DISTINCT
    ad_parent.id AS administrativedivision_id,
    first_value(hc.id) OVER w AS hazardcategory_id,
    first_value(hc_ad.source) OVER w AS source
FROM
    datamart.rel_hazardcategory_administrativedivision AS hc_ad
    JOIN datamart.hazardcategory AS hc
        ON hc.id = hc_ad.hazardcategory_id
    JOIN datamart.enum_hazardlevel AS hl
        ON hl.id =  hc.hazardlevel_id
    JOIN datamart.administrativedivision AS ad_child
        ON ad_child.id = hc_ad.administrativedivision_id
    JOIN datamart.administrativedivision AS ad_parent
        ON ad_parent.code = ad_child.parent_code
WHERE ad_parent.leveltype_id = {}
WINDOW w AS (
    PARTITION BY
        ad_parent.id,
        hc.hazardtype_id
    ORDER BY
        hl.order
)
ORDER BY
    ad_parent.id;
'''.format(AdminLevelType.get(level).id)

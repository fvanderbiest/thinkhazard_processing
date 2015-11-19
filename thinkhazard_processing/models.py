# coding: utf-8
import os
from sqlalchemy import (Column, ForeignKey,
                        Boolean, Date, Integer, String)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
import geoalchemy2
from . import settings

from thinkhazard_common.models import Base


class HazardUnit(Base):
    __tablename__ = 'hazardunit'
    __table_args__ = {u'schema': 'processing'}
    id = Column(Integer, primary_key=True)
    # the code for the hazard unit
    # eg: cm, dm, m, km/h, PGA-g, PGA-gal, SA-g
    code = Column(String(7), nullable=False, unique=True)


class HazardSet(Base):
    __tablename__ = 'hazardset'
    __table_args__ = {u'schema': 'processing'}

    # id is the string id common to the 3 layers,
    # as reported by geonode ("hazard_set" field), eg: "EQ-PA"
    id = Column(String, primary_key=True)

    # a hazardset is related to a hazard type:
    hazardtype_id = Column(Integer,
                           ForeignKey('datamart.enum_hazardtype.id'),
                           nullable=False)

    # "local" is set to false when bounds = -180/-90/180/90
    # this value comes from the linked layers
    local = Column(Boolean)
    # date the data was last updated (defaults to created):
    # this value comes from the linked layers
    data_lastupdated_date = Column(Date, nullable=False)
    # date the metadata was last updated (defaults to created):
    # this value comes from the linked layers
    metadata_lastupdated_date = Column(Date, nullable=False)
    # quality rating for the hazard calculation method
    # ranges from 0 (bad) to 10 (excellent).
    # this value comes from the linked layers
    calculation_method_quality = Column(Integer)
    # quality rating for the study
    # ranges from 0 (bad) to 2 (excellent)
    # this value comes from the linked layers
    scientific_quality = Column(Integer)

    # processing steps:
    # a hazardset starts incomplete.
    # then it becomes complete, which means:
    #   * all layers have been downloaded
    #   * the date, quality, etc fields of the hazardset has been updated
    complete = Column(Boolean, nullable=False, default=False)
    # finally it is processed:
    processed = Column(Boolean, nullable=False, default=False)


class Layer(Base):
    __tablename__ = 'layer'
    __table_args__ = {u'schema': 'processing'}
    # a layer is identified by it's return_period and hazard_set:
    hazardset_id = Column(String, ForeignKey('processing.hazardset.id'),
                          primary_key=True)
    # the related hazard_level, inferred from return_period
    hazardlevel_id = Column(Integer,
                            ForeignKey('datamart.enum_hazardlevel.id'),
                            primary_key=True)
    # the return period is typically 100, 475, 2475 years but it can vary
    return_period = Column(Integer, nullable=False)

    # pixel values have a unit:
    hazardunit_id = Column(Integer,
                           ForeignKey('processing.hazardunit.id'),
                           nullable=False)

    # date the data was last updated (defaults to created):
    data_lastupdated_date = Column(Date, nullable=False)
    # date the metadata was last updated (defaults to created):
    metadata_lastupdated_date = Column(Date, nullable=False)

    # the layer is referenced in geonode with an id:
    geonode_id = Column(Integer, nullable=False, unique=True)
    # the data can be downloaded at this URL:
    download_url = Column(String, nullable=False)

    # quality rating for the hazard calculation method
    # ranges from 0 (bad) to 10 (excellent)
    calculation_method_quality = Column(Integer, nullable=False)
    # quality rating for the study
    # ranges from 0 (bad) to 2 (excellent)
    scientific_quality = Column(Integer, nullable=False)

    # "local" is set to false when bounds = -180/-90/180/90
    # true otherwise
    local = Column(Boolean, nullable=False)

    # "downloaded" is set to true
    # when the geotiff file has been downloaded
    downloaded = Column(Boolean, nullable=False, default=False)


class Output(Base):
    __tablename__ = 'output'
    __table_args__ = {u'schema': 'processing'}
    # processing results are identified by:
    #  * the hazardset they come from
    #  * the administrative division that they qualify
    hazardset_id = Column(String,
                          ForeignKey('processing.hazardset.id'),
                          primary_key=True)
    admin_id = Column(Integer,
                      ForeignKey('datamart.administrativedivision.id'),
                      primary_key=True)
    # the coverage_ratio ranges from 0 to 100
    # it represents the percentage of the admin division area
    # covered by the data in the hazardset
    # (NO-DATA values are not taken into account here)
    coverage_ratio = Column(Integer, nullable=False)
    # hazard_level_id is the processing result
    hazardlevel_id = Column(Integer,
                            ForeignKey('datamart.enum_hazardlevel.id'),
                            nullable=False)

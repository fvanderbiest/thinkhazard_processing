# coding: utf-8
from sqlalchemy import (Column, ForeignKey,
                        Boolean, Date, Integer, String)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
import geoalchemy2


DBSession = scoped_session(sessionmaker())
Base = declarative_base()


class AdministrativeDivision(Base):
    __tablename__ = 'administrativedivision'
    __table_args__ = {u'schema': 'processing'}
    id = Column(Integer, primary_key=True)
    code = Column(Integer, nullable=False, unique=True)
    leveltype_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    parent_code = Column(Integer,
                         ForeignKey('processing.administrativedivision.code'))
    geom = Column(geoalchemy2.Geometry('MULTIPOLYGON',
                                       3857,
                                       management=True))  # bbox ?


class Dataset(Base):
    __tablename__ = 'dataset'
    __table_args__ = {u'schema': 'processing'}

    # hazard_set is the ID common to the 3 layers,
    # as reported by geonode (hazard_set field)
    hazard_set_id = Column(String(1024), primary_key=True)  # eg: "EQ-PA"
    # rating 1 is the rating coming from the metadata
    rating1 = Column(Integer)
    # rating 2 is the rating coming from the data (quality of survey)
    rating2 = Column(Integer)
    # "is_global" is set to true when bounds = -180/-90/180/90
    # false otherwise
    is_global = Column(Boolean)
    # "processed" is set to true by the app
    # when all 3 datasets have been treated
    # it maintains the application state
    processed = Column(Boolean, default=False)


class Layer(Base):
    __tablename__ = 'layer'
    __table_args__ = {u'schema': 'processing'}

    id = Column(Integer, primary_key=True)
    # title is the layer title, as reported by geonode, eg: "EQ-PA-100"
    title = Column(String(1024))
    hazard_set_id = Column(String(1024),
                           ForeignKey('processing.dataset.hazard_set_id'))
    return_period = Column(Integer)  # 100, 475, 2475
    data_creation_date = Column(Date)
    md_creation_date = Column(Date)
    # possible that one of them will not be useful
    md_update_date = Column(Date)
    geom = Column(geoalchemy2.Geometry('POLYGON',
                                       4326,
                                       management=True))  # bbox ?

    # "downloaded" is set to true by the app
    # when the layer geotiff has been downloaded
    # it maintains the application state
    downloaded = Column(Boolean, default=False)


class Output(Base):
    __tablename__ = 'output'
    __table_args__ = {u'schema': 'processing'}
    hazard_set_id = Column(String(1024),
                           ForeignKey('processing.dataset.hazard_set_id'),
                           primary_key=True)
    admin_id = Column(Integer,
                      ForeignKey('processing.administrativedivision.id'),
                      primary_key=True)
    hazard_level = Column(Integer)  # 1, 2, 3, 4

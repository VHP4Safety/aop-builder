from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Float
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList
import datetime
import enum

Base = declarative_base()

class SessionStatusEnum(str, enum.Enum):
    queued = "queued"
    starting = "starting"
    chunking = "chunking"
    waiting = "waiting"
    extracting = "extracting"
    enriching = "enriching"
    finished = "finished"
    canceled = "canceled"

class CerSession(Base):
    __tablename__ = "cer_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    collection_id = Column(Integer, index=True, nullable=False)
    title = Column(String, nullable=False)
    key_events = Column(MutableList.as_mutable(ARRAY(String)), default=[])
    model_name = Column(String, nullable=False)
    relevance_score_threshold = Column(Float, nullable=False)
    status = Column(Enum(SessionStatusEnum, native_enum=False), default=SessionStatusEnum.queued, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    logs = relationship("CerSessionLog", back_populates="session", cascade="all, delete-orphan")

class CerSessionLog(Base):
    __tablename__ = "cer_session_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("cer_sessions.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(Enum(SessionStatusEnum, native_enum=False), nullable=False)

    session = relationship("CerSession", back_populates="logs")

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList
import datetime

Base = declarative_base()

class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)       # Het ID van de gebruiker waaraan deze collectie hangt
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    # Maak het array-veld mutable zodat in-place wijzigingen gedetecteerd worden:
    pdf_ids = Column(MutableList.as_mutable(ARRAY(String)), default=[])
    status = Column(String, default="unscanned", nullable=False)

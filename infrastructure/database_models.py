from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SystemStatus(Base):
    __tablename__ = "system_status"

    id = Column(Integer, primary_key=True, index=True)
    component = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)


class TicketRecord(Base):
    __tablename__ = "ticket_records"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String(50), unique=True, index=True, nullable=False)
    plate = Column(String(32), nullable=False)
    vehicle_id = Column(String(32), nullable=True)
    slot_id = Column(String(32), nullable=True)
    violation = Column(String(50), nullable=False)
    status = Column(String(20), default="printed")
    message = Column(String(255), nullable=True)
    image_url = Column(String(255), nullable=True)
    evidence_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
import enum
from .database import Base

class FlightStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    DELAYED = "delayed"
    LANDED = "landed"
    DIVERTED = "diverted"

class Flight(Base):
    __tablename__ = "flights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_number = Column(String(10), nullable=False, unique=True)
    departure_time = Column(DateTime, nullable=False)
    arrival_time = Column(DateTime, nullable=False)
    origin_airport = Column(String(3), nullable=False)
    destination_airport = Column(String(3), nullable=False)
    aircraft_id = Column(String(10), nullable=False)
    status = Column(SQLAlchemyEnum(FlightStatus), nullable=False, default=FlightStatus.SCHEDULED)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    crew_ids = Column(ARRAY(String), nullable=True)
    
    layovers = relationship("Layover", back_populates="flight", cascade="all, delete-orphan")

class Layover(Base):
    __tablename__ = "layovers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_id = Column(UUID(as_uuid=True), ForeignKey("flights.id", ondelete="CASCADE"), nullable=False)
    airport_code = Column(String(3), nullable=False)
    arrival_time = Column(DateTime, nullable=False)
    departure_time = Column(DateTime, nullable=False)
    
    flight = relationship("Flight", back_populates="layovers")

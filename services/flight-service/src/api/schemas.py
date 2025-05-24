from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from src.core.models import FlightStatus

class LayoverBase(BaseModel):
    airport_code: str
    arrival_time: datetime
    departure_time: datetime

class LayoverCreate(LayoverBase):
    pass

class Layover(LayoverBase):
    id: UUID
    flight_id: UUID

    class Config:
        orm_mode = True

class FlightBase(BaseModel):
    flight_number: str
    departure_time: datetime
    arrival_time: datetime
    origin_airport: str
    destination_airport: str
    aircraft_id: str

class FlightCreate(FlightBase):
    crew_ids: Optional[List[str]] = []
    layovers: Optional[List[LayoverCreate]] = []

class FlightUpdate(BaseModel):
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    origin_airport: Optional[str] = None
    destination_airport: Optional[str] = None
    aircraft_id: Optional[str] = None
    status: Optional[FlightStatus] = None
    crew_ids: Optional[List[str]] = None

class Flight(FlightBase):
    id: UUID
    status: FlightStatus
    created_at: datetime
    updated_at: datetime
    crew_ids: List[str] = []
    layovers: List[Layover] = []

    class Config:
        orm_mode = True

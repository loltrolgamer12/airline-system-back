from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.core.models import Flight, Layover, FlightStatus
from src.api.schemas import FlightCreate, FlightUpdate, LayoverCreate
from .event_publisher import EventPublisher

class FlightService:
    def __init__(self):
        self.event_publisher = EventPublisher()
    
    def get_flights(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        departure_after: Optional[str] = None,
        departure_before: Optional[str] = None,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Flight]:
        query = db.query(Flight)
        
        # Apply filters if provided
        if departure_after:
            query = query.filter(Flight.departure_time >= departure_after)
        if departure_before:
            query = query.filter(Flight.departure_time <= departure_before)
        if origin:
            query = query.filter(Flight.origin_airport == origin)
        if destination:
            query = query.filter(Flight.destination_airport == destination)
        if status:
            query = query.filter(Flight.status == status)
            
        return query.offset(skip).limit(limit).all()
    
    def get_flight(self, db: Session, flight_id: str) -> Optional[Flight]:
        return db.query(Flight).filter(Flight.id == flight_id).first()
    
    def get_flight_by_number(self, db: Session, flight_number: str) -> Optional[Flight]:
        return db.query(Flight).filter(Flight.flight_number == flight_number).first()
    
    def create_flight(self, db: Session, flight: FlightCreate) -> Flight:
        # Check if flight number already exists
        existing_flight = self.get_flight_by_number(db, flight.flight_number)
        if existing_flight:
            raise ValueError(f"Flight with number {flight.flight_number} already exists")
        
        # Create new flight
        db_flight = Flight(
            flight_number=flight.flight_number,
            departure_time=flight.departure_time,
            arrival_time=flight.arrival_time,
            origin_airport=flight.origin_airport,
            destination_airport=flight.destination_airport,
            aircraft_id=flight.aircraft_id,
            crew_ids=flight.crew_ids,
            status=FlightStatus.SCHEDULED
        )
        db.add(db_flight)
        db.commit()
        db.refresh(db_flight)
        
        # Add layovers if provided
        if flight.layovers:
            for layover_data in flight.layovers:
                self.add_layover(db, db_flight, layover_data)
        
        # Publish event
        self.event_publisher.publish("flight.created", {
            "flight_id": str(db_flight.id),
            "flight_number": db_flight.flight_number
        })
        
        return db_flight
    
    def update_flight(self, db: Session, flight: Flight, flight_update: FlightUpdate) -> Flight:
        # Update flight attributes if provided
        update_data = flight_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(flight, key, value)
        
        flight.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(flight)
        
        # Publish event
        self.event_publisher.publish("flight.updated", {
            "flight_id": str(flight.id),
            "flight_number": flight.flight_number,
            "status": flight.status.value if hasattr(flight.status, "value") else flight.status
        })
        
        return flight
    
    def delete_flight(self, db: Session, flight: Flight) -> None:
        flight_id = str(flight.id)
        flight_number = flight.flight_number
        
        db.delete(flight)
        db.commit()
        
        # Publish event
        self.event_publisher.publish("flight.deleted", {
            "flight_id": flight_id,
            "flight_number": flight_number
        })
    
    def add_layover(self, db: Session, flight: Flight, layover: LayoverCreate) -> Layover:
        db_layover = Layover(
            flight_id=flight.id,
            airport_code=layover.airport_code,
            arrival_time=layover.arrival_time,
            departure_time=layover.departure_time
        )
        db.add(db_layover)
        db.commit()
        db.refresh(db_layover)
        return db_layover

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from src.core.dependencies import get_db
from src.core.models import Flight as FlightModel, Layover as LayoverModel
from src.api.schemas import Flight, FlightCreate, FlightUpdate, Layover, LayoverCreate
from src.services.flight_service import FlightService

router = APIRouter()
flight_service = FlightService()

@router.get("/flights", response_model=List[Flight])
def get_flights(
    departure_after: Optional[str] = None, 
    departure_before: Optional[str] = None,
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    skip: int = 0, 
    limit: int = 100
):
    return flight_service.get_flights(
        db, 
        skip=skip, 
        limit=limit, 
        departure_after=departure_after,
        departure_before=departure_before,
        origin=origin,
        destination=destination,
        status=status
    )

@router.get("/flights/{flight_number}", response_model=Flight)
def get_flight(flight_number: str, db: Session = Depends(get_db)):
    flight = flight_service.get_flight_by_number(db, flight_number=flight_number)
    if flight is None:
        raise HTTPException(status_code=404, detail=f"Flight with number {flight_number} not found")
    return flight

@router.post("/flights", response_model=Flight, status_code=201)
def create_flight(flight: FlightCreate, db: Session = Depends(get_db)):
    return flight_service.create_flight(db, flight=flight)

@router.put("/flights/{flight_number}", response_model=Flight)
def update_flight(flight_number: str, flight_update: FlightUpdate, db: Session = Depends(get_db)):
    flight = flight_service.get_flight_by_number(db, flight_number=flight_number)
    if flight is None:
        raise HTTPException(status_code=404, detail=f"Flight with number {flight_number} not found")
    return flight_service.update_flight(db, flight=flight, flight_update=flight_update)

@router.delete("/flights/{flight_number}", status_code=204)
def delete_flight(flight_number: str, db: Session = Depends(get_db)):
    flight = flight_service.get_flight_by_number(db, flight_number=flight_number)
    if flight is None:
        raise HTTPException(status_code=404, detail=f"Flight with number {flight_number} not found")
    flight_service.delete_flight(db, flight=flight)
    return {"detail": "Flight deleted successfully"}

@router.get("/flights/{flight_number}/layovers", response_model=List[Layover])
def get_flight_layovers(flight_number: str, db: Session = Depends(get_db)):
    flight = flight_service.get_flight_by_number(db, flight_number=flight_number)
    if flight is None:
        raise HTTPException(status_code=404, detail=f"Flight with number {flight_number} not found")
    return flight.layovers

@router.post("/flights/{flight_number}/layovers", response_model=Layover, status_code=201)
def add_flight_layover(flight_number: str, layover: LayoverCreate, db: Session = Depends(get_db)):
    flight = flight_service.get_flight_by_number(db, flight_number=flight_number)
    if flight is None:
        raise HTTPException(status_code=404, detail=f"Flight with number {flight_number} not found")
    return flight_service.add_layover(db, flight=flight, layover=layover)

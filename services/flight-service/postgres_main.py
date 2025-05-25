from fastapi import FastAPI, HTTPException, Depends, Query
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Float, text, and_
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, date
from pydantic import BaseModel
from typing import List, Optional
import datetime as dt
import os
import time
from enum import Enum

# Configuración de base de datos
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "airline")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

print(f"🔗 Flight Service conectando a: {POSTGRES_HOST}:{POSTGRES_PORT}")

def create_engine_with_retry(database_url, max_retries=10, retry_delay=5):
    retries = 0
    while retries < max_retries:
        try:
            print(f"📡 Intento de conexión {retries + 1}/{max_retries}...")
            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ Flight Service conectado a PostgreSQL")
            return engine
        except Exception as e:
            retries += 1
            print(f"❌ Error conectando (intento {retries}): {e}")
            if retries < max_retries:
                print(f"⏳ Esperando {retry_delay} segundos...")
                time.sleep(retry_delay)
            else:
                print("💥 Flight Service: No se pudo conectar a PostgreSQL")
                raise e

engine = create_engine_with_retry(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class FlightStatus(str, Enum):
    SCHEDULED = "scheduled"
    BOARDING = "boarding"
    DEPARTED = "departed"
    ARRIVED = "arrived"
    DELAYED = "delayed"
    CANCELLED = "cancelled"

class Flight(Base):
    __tablename__ = "flights"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_number = Column(String(10), nullable=False, unique=True)
    departure_time = Column(DateTime, nullable=False)
    arrival_time = Column(DateTime, nullable=False)
    origin_airport = Column(String(3), nullable=False)
    destination_airport = Column(String(3), nullable=False)
    aircraft_id = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default=FlightStatus.SCHEDULED.value)
    price = Column(Float, nullable=False, default=299.99)
    total_seats = Column(Integer, nullable=False, default=180)
    available_seats = Column(Integer, nullable=False, default=180)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

print("🏗️ Creando/actualizando tablas...")
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas actualizadas exitosamente")
except Exception as e:
    print(f"❌ Error actualizando tablas: {e}")

class FlightCreate(BaseModel):
    flight_number: str
    departure_time: datetime
    arrival_time: datetime
    origin_airport: str
    destination_airport: str
    aircraft_id: str
    price: Optional[float] = 299.99
    total_seats: Optional[int] = 180

class FlightUpdate(BaseModel):
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    status: Optional[str] = None
    price: Optional[float] = None
    available_seats: Optional[int] = None

class FlightResponse(BaseModel):
    id: str
    flight_number: str
    departure_time: datetime
    arrival_time: datetime
    origin_airport: str
    destination_airport: str
    aircraft_id: str
    status: str
    price: float
    total_seats: int
    available_seats: int
    occupancy_rate: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def publish_event(event_type: str, data: dict):
    print(f"📤 FLIGHT EVENT: {event_type} - {data}")

app = FastAPI(title="Flight Service Enhanced", version="2.0.0")

@app.get("/health")
def health_check():
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT COUNT(*) as count FROM flights")).fetchone()
        db.close()
        return {
            "status": "healthy",
            "service": "flight-service",
            "database": "connected",
            "total_flights": result.count if result else 0,
            "database_url": f"{POSTGRES_HOST}:{POSTGRES_PORT}"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "flight-service",
            "database": "disconnected",
            "error": str(e)
        }

@app.get("/api/v1/flights", response_model=List[FlightResponse])
def search_flights(
    origin: Optional[str] = Query(None, description="Código del aeropuerto de origen"),
    destination: Optional[str] = Query(None, description="Código del aeropuerto de destino"),
    departure_date: Optional[date] = Query(None, description="Fecha de salida (YYYY-MM-DD)"),
    min_price: Optional[float] = Query(None, description="Precio mínimo"),
    max_price: Optional[float] = Query(None, description="Precio máximo"),
    status: Optional[str] = Query(None, description="Estado del vuelo"),
    available_only: Optional[bool] = Query(True, description="Solo vuelos con asientos disponibles"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    query = db.query(Flight)
    
    if origin:
        query = query.filter(Flight.origin_airport.ilike(f"%{origin}%"))
    
    if destination:
        query = query.filter(Flight.destination_airport.ilike(f"%{destination}%"))
    
    if departure_date:
        start_date = datetime.combine(departure_date, datetime.min.time())
        end_date = datetime.combine(departure_date, datetime.max.time())
        query = query.filter(and_(
            Flight.departure_time >= start_date,
            Flight.departure_time <= end_date
        ))
    
    if min_price is not None:
        query = query.filter(Flight.price >= min_price)
    
    if max_price is not None:
        query = query.filter(Flight.price <= max_price)
    
    if status:
        query = query.filter(Flight.status == status)
    
    if available_only:
        query = query.filter(Flight.available_seats > 0)
    
    query = query.order_by(Flight.departure_time)
    flights = query.offset(skip).limit(limit).all()
    
    return [FlightResponse(
        id=str(flight.id),
        flight_number=flight.flight_number,
        departure_time=flight.departure_time,
        arrival_time=flight.arrival_time,
        origin_airport=flight.origin_airport,
        destination_airport=flight.destination_airport,
        aircraft_id=flight.aircraft_id,
        status=flight.status,
        price=flight.price,
        total_seats=flight.total_seats,
        available_seats=flight.available_seats,
        occupancy_rate=round(((flight.total_seats - flight.available_seats) / flight.total_seats) * 100, 2),
        created_at=flight.created_at,
        updated_at=flight.updated_at
    ) for flight in flights]

@app.get("/api/v1/flights/{flight_number}", response_model=FlightResponse)
def get_flight(flight_number: str, db: Session = Depends(get_db)):
    flight = db.query(Flight).filter(Flight.flight_number == flight_number).first()
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    
    return FlightResponse(
        id=str(flight.id),
        flight_number=flight.flight_number,
        departure_time=flight.departure_time,
        arrival_time=flight.arrival_time,
        origin_airport=flight.origin_airport,
        destination_airport=flight.destination_airport,
        aircraft_id=flight.aircraft_id,
        status=flight.status,
        price=flight.price,
        total_seats=flight.total_seats,
        available_seats=flight.available_seats,
        occupancy_rate=round(((flight.total_seats - flight.available_seats) / flight.total_seats) * 100, 2),
        created_at=flight.created_at,
        updated_at=flight.updated_at
    )

@app.post("/api/v1/flights", response_model=FlightResponse, status_code=201)
def create_flight(flight_data: FlightCreate, db: Session = Depends(get_db)):
    existing = db.query(Flight).filter(Flight.flight_number == flight_data.flight_number).first()
    if existing:
        raise HTTPException(status_code=409, detail="Flight already exists")
    
    db_flight = Flight(
        flight_number=flight_data.flight_number,
        departure_time=flight_data.departure_time,
        arrival_time=flight_data.arrival_time,
        origin_airport=flight_data.origin_airport,
        destination_airport=flight_data.destination_airport,
        aircraft_id=flight_data.aircraft_id,
        price=flight_data.price,
        total_seats=flight_data.total_seats,
        available_seats=flight_data.total_seats,
        status=FlightStatus.SCHEDULED.value
    )
    
    db.add(db_flight)
    db.commit()
    db.refresh(db_flight)
    
    publish_event("flight.created", {
        "flight_id": str(db_flight.id),
        "flight_number": db_flight.flight_number,
        "route": f"{db_flight.origin_airport} → {db_flight.destination_airport}",
        "price": db_flight.price
    })
    
    return FlightResponse(
        id=str(db_flight.id),
        flight_number=db_flight.flight_number,
        departure_time=db_flight.departure_time,
        arrival_time=db_flight.arrival_time,
        origin_airport=db_flight.origin_airport,
        destination_airport=db_flight.destination_airport,
        aircraft_id=db_flight.aircraft_id,
        status=db_flight.status,
        price=db_flight.price,
        total_seats=db_flight.total_seats,
        available_seats=db_flight.available_seats,
        occupancy_rate=0.0,
        created_at=db_flight.created_at,
        updated_at=db_flight.updated_at
    )

@app.put("/api/v1/flights/{flight_number}", response_model=FlightResponse)
def update_flight(flight_number: str, flight_update: FlightUpdate, db: Session = Depends(get_db)):
    flight = db.query(Flight).filter(Flight.flight_number == flight_number).first()
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    
    update_data = flight_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(flight, key, value)
    
    flight.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(flight)
    
    publish_event("flight.updated", {
        "flight_id": str(flight.id),
        "flight_number": flight.flight_number,
        "updated_fields": list(update_data.keys())
    })
    
    return FlightResponse(
        id=str(flight.id),
        flight_number=flight.flight_number,
        departure_time=flight.departure_time,
        arrival_time=flight.arrival_time,
        origin_airport=flight.origin_airport,
        destination_airport=flight.destination_airport,
        aircraft_id=flight.aircraft_id,
        status=flight.status,
        price=flight.price,
        total_seats=flight.total_seats,
        available_seats=flight.available_seats,
        occupancy_rate=round(((flight.total_seats - flight.available_seats) / flight.total_seats) * 100, 2),
        created_at=flight.created_at,
        updated_at=flight.updated_at
    )

@app.patch("/api/v1/flights/{flight_number}/seats")
def update_seat_availability(flight_number: str, seats_change: int, db: Session = Depends(get_db)):
    flight = db.query(Flight).filter(Flight.flight_number == flight_number).first()
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    
    new_available = flight.available_seats + seats_change
    
    if new_available < 0:
        raise HTTPException(status_code=400, detail="Not enough available seats")
    
    if new_available > flight.total_seats:
        raise HTTPException(status_code=400, detail="Cannot exceed total seat capacity")
    
    flight.available_seats = new_available
    flight.updated_at = datetime.utcnow()
    db.commit()
    
    return {"flight_number": flight_number, "available_seats": new_available}

@app.get("/")
def root():
    return {
        "message": "Enhanced Flight Service v2.0",
        "status": "active",
        "features": ["advanced_search", "pricing", "seat_management", "status_tracking"],
        "database": f"{POSTGRES_HOST}:{POSTGRES_PORT}"
    }

def create_enhanced_sample_data():
    print("🎯 Creando datos de muestra mejorados...")
    db = SessionLocal()
    try:
        count = db.query(Flight).count()
        if count == 0:
            enhanced_flights = [
                Flight(flight_number="AV101", departure_time=dt.datetime(2025, 6, 15, 6, 0),
                       arrival_time=dt.datetime(2025, 6, 15, 7, 30), origin_airport="BOG",
                       destination_airport="MDE", aircraft_id="A320-001", status="scheduled",
                       price=180.99, total_seats=150, available_seats=120),
                
                Flight(flight_number="AV102", departure_time=dt.datetime(2025, 6, 15, 8, 15),
                       arrival_time=dt.datetime(2025, 6, 15, 9, 45), origin_airport="MDE",
                       destination_airport="BOG", aircraft_id="A320-002", status="scheduled",
                       price=185.50, total_seats=150, available_seats=95),
                
                Flight(flight_number="AV201", departure_time=dt.datetime(2025, 6, 15, 10, 30),
                       arrival_time=dt.datetime(2025, 6, 15, 12, 0), origin_airport="BOG",
                       destination_airport="CLO", aircraft_id="B737-001", status="boarding",
                       price=220.00, total_seats=180, available_seats=15),
                
                Flight(flight_number="AV301", departure_time=dt.datetime(2025, 6, 15, 14, 0),
                       arrival_time=dt.datetime(2025, 6, 15, 15, 15), origin_airport="BOG",
                       destination_airport="CTG", aircraft_id="A319-001", status="delayed",
                       price=275.75, total_seats=120, available_seats=8),
                
                Flight(flight_number="AV801", departure_time=dt.datetime(2025, 6, 16, 1, 30),
                       arrival_time=dt.datetime(2025, 6, 16, 7, 45), origin_airport="BOG",
                       destination_airport="MIA", aircraft_id="B787-001", status="scheduled",
                       price=890.00, total_seats=250, available_seats=180),
                
                Flight(flight_number="AV901", departure_time=dt.datetime(2025, 6, 17, 23, 15),
                       arrival_time=dt.datetime(2025, 6, 18, 14, 30), origin_airport="BOG",
                       destination_airport="MAD", aircraft_id="A350-001", status="scheduled",
                       price=1450.00, total_seats=300, available_seats=245),
                
                Flight(flight_number="AV999", departure_time=dt.datetime(2025, 6, 10, 12, 0),
                       arrival_time=dt.datetime(2025, 6, 10, 13, 30), origin_airport="BOG",
                       destination_airport="MDE", aircraft_id="A320-999", status="arrived",
                       price=199.99, total_seats=150, available_seats=0),
                
                Flight(flight_number="AV500", departure_time=dt.datetime(2025, 6, 20, 16, 30),
                       arrival_time=dt.datetime(2025, 6, 20, 18, 0), origin_airport="CLO",
                       destination_airport="BOG", aircraft_id="B737-002", status="cancelled",
                       price=210.00, total_seats=180, available_seats=180)
            ]
            
            for flight in enhanced_flights:
                db.add(flight)
            
            db.commit()
            print("✅ Datos de muestra mejorados creados")
        else:
            print(f"ℹ️ Ya existen {count} vuelos en la base de datos")
    except Exception as e:
        print(f"❌ Error creando datos de muestra: {e}")
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    create_enhanced_sample_data()

if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando Enhanced Flight Service...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

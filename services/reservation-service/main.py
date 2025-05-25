from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
import os
import time
import httpx
import random
import string
from enum import Enum
from circuit_breaker import database_circuit_breaker, http_circuit_breaker

# Configuración
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "airline")

FLIGHT_SERVICE_URL = os.getenv("FLIGHT_SERVICE_URL", "http://flight-service:8000")
PASSENGER_SERVICE_URL = os.getenv("PASSENGER_SERVICE_URL", "http://passenger-service:8000")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

print(f"🎫 Reservation Service Enhanced")
print(f"🔗 Flight Service: {FLIGHT_SERVICE_URL}")
print(f"🔗 Passenger Service: {PASSENGER_SERVICE_URL}")

def create_engine_with_circuit_breaker(database_url, max_retries=10, retry_delay=3):
    retries = 0
    while retries < max_retries:
        try:
            print(f"📡 Reservation Service - Conexión {retries + 1}/{max_retries}...")
            
            def create_engine_protected():
                engine = create_engine(database_url)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return engine
            
            engine = database_circuit_breaker.call(create_engine_protected)
            print("✅ Reservation Service conectado con Circuit Breaker")
            return engine
            
        except Exception as e:
            retries += 1
            print(f"❌ Error conectando (intento {retries}): {e}")
            if retries < max_retries:
                time.sleep(retry_delay)
            else:
                raise e

engine = create_engine_with_circuit_breaker(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ReservationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

class Reservation(Base):
    __tablename__ = "reservations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reservation_code = Column(String(10), nullable=False, unique=True)
    passenger_identification = Column(String(20), nullable=False)
    flight_number = Column(String(10), nullable=False)
    seat_number = Column(String(5), nullable=True)
    status = Column(String(20), nullable=False, default=ReservationStatus.PENDING.value)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    checked_in_at = Column(DateTime, nullable=True)

print("🏗️ Creando tablas de reservas...")
try:
    def create_tables():
        Base.metadata.create_all(bind=engine)
    database_circuit_breaker.call(create_tables)
    print("✅ Tablas creadas con Circuit Breaker")
except Exception as e:
    print(f"❌ Error creando tablas: {e}")

class ReservationCreate(BaseModel):
    passenger_identification: str
    flight_number: str
    seat_number: Optional[str] = None

class ReservationUpdate(BaseModel):
    status: Optional[str] = None
    seat_number: Optional[str] = None

class ReservationResponse(BaseModel):
    id: str
    reservation_code: str
    passenger_identification: str
    flight_number: str
    seat_number: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    checked_in_at: Optional[datetime]
    passenger_info: Optional[dict] = None
    flight_info: Optional[dict] = None

    class Config:
        from_attributes = True

def get_db():
    def get_session():
        return SessionLocal()
    
    db = database_circuit_breaker.call(get_session)
    try:
        yield db
    finally:
        db.close()

async def verify_flight_exists(flight_number: str) -> Optional[dict]:
    try:
        print(f"🔍 Verificando vuelo {flight_number}...")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{FLIGHT_SERVICE_URL}/api/v1/flights/{flight_number}")
            
            if response.status_code == 200:
                flight_info = response.json()
                print(f"✅ Vuelo encontrado: {flight_info['origin_airport']} → {flight_info['destination_airport']}")
                return flight_info
            else:
                print(f"❌ Vuelo {flight_number} no encontrado")
                return None
    except Exception as e:
        print(f"❌ Error verificando vuelo: {e}")
        return None

async def verify_passenger_exists(identification: str) -> Optional[dict]:
    try:
        print(f"🔍 Verificando pasajero {identification}...")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{PASSENGER_SERVICE_URL}/api/v1/passengers/{identification}")
            
            if response.status_code == 200:
                passenger_info = response.json()
                print(f"✅ Pasajero encontrado: {passenger_info['first_name']} {passenger_info['last_name']}")
                return passenger_info
            else:
                print(f"❌ Pasajero {identification} no encontrado")
                return None
    except Exception as e:
        print(f"❌ Error verificando pasajero: {e}")
        return None

async def update_flight_seats(flight_number: str, seats_change: int):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"{FLIGHT_SERVICE_URL}/api/v1/flights/{flight_number}/seats",
                params={"seats_change": seats_change}
            )
            return response.status_code == 200
    except Exception as e:
        print(f"❌ Error actualizando asientos: {e}")
        return False

def generate_reservation_code() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def assign_seat(flight_number: str, db: Session, preferred_seat: Optional[str] = None) -> str:
    if preferred_seat:
        def check_seat_availability():
            return db.query(Reservation).filter(
                Reservation.flight_number == flight_number,
                Reservation.seat_number == preferred_seat,
                Reservation.status.in_(["confirmed", "checked_in"])
            ).first()
        
        existing = database_circuit_breaker.call(check_seat_availability)
        if not existing:
            return preferred_seat
    
    def get_existing_seats():
        return db.query(Reservation).filter(
            Reservation.flight_number == flight_number,
            Reservation.status.in_(["confirmed", "checked_in"])
        ).count()
    
    existing_seats = database_circuit_breaker.call(get_existing_seats)
    row = (existing_seats // 6) + 1
    seat_letter = chr(65 + (existing_seats % 6))
    seat_number = f"{row}{seat_letter}"
    
    print(f"💺 Asiento asignado: {seat_number}")
    return seat_number

def publish_event(event_type: str, data: dict):
    print(f"📤 RESERVATION EVENT: {event_type} - {data}")

app = FastAPI(title="Reservation Service Enhanced", version="2.0.0")

@app.get("/health")
def health_check():
    try:
        def check_db():
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
        
        database_circuit_breaker.call(check_db)
        
        return {
            "status": "healthy", 
            "service": "reservation-service", 
            "database": "connected",
            "circuit_breakers": {
                "database": database_circuit_breaker.get_stats(),
                "http": http_circuit_breaker.get_stats()
            },
            "flight_service": FLIGHT_SERVICE_URL,
            "passenger_service": PASSENGER_SERVICE_URL
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "service": "reservation-service", 
            "database": "disconnected", 
            "error": str(e),
            "circuit_breakers": {
                "database": database_circuit_breaker.get_stats(),
                "http": http_circuit_breaker.get_stats()
            }
        }

@app.get("/api/v1/reservations", response_model=List[ReservationResponse])
def get_reservations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    def get_reservations_protected():
        return db.query(Reservation).offset(skip).limit(limit).all()
    
    reservations = database_circuit_breaker.call(get_reservations_protected)
    return [ReservationResponse(
        id=str(reservation.id),
        reservation_code=reservation.reservation_code,
        passenger_identification=reservation.passenger_identification,
        flight_number=reservation.flight_number,
        seat_number=reservation.seat_number,
        status=reservation.status,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
        checked_in_at=reservation.checked_in_at
    ) for reservation in reservations]

@app.get("/api/v1/reservations/{reservation_code}", response_model=ReservationResponse)
async def get_reservation(reservation_code: str, db: Session = Depends(get_db)):
    def get_reservation_protected():
        return db.query(Reservation).filter(
            Reservation.reservation_code == reservation_code
        ).first()
    
    reservation = database_circuit_breaker.call(get_reservation_protected)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    # Obtener información adicional
    passenger_info = await verify_passenger_exists(reservation.passenger_identification)
    flight_info = await verify_flight_exists(reservation.flight_number)
    
    return ReservationResponse(
        id=str(reservation.id),
        reservation_code=reservation.reservation_code,
        passenger_identification=reservation.passenger_identification,
        flight_number=reservation.flight_number,
        seat_number=reservation.seat_number,
        status=reservation.status,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
        checked_in_at=reservation.checked_in_at,
        passenger_info=passenger_info,
        flight_info=flight_info
    )

@app.post("/api/v1/reservations", response_model=ReservationResponse, status_code=201)
async def create_reservation(reservation_data: ReservationCreate, db: Session = Depends(get_db)):
    print(f"🎫 Creando reserva para pasajero {reservation_data.passenger_identification}")
    
    # Verificaciones
    flight_info = await verify_flight_exists(reservation_data.flight_number)
    if not flight_info:
        raise HTTPException(status_code=404, detail=f"Flight {reservation_data.flight_number} not found")
    
    passenger_info = await verify_passenger_exists(reservation_data.passenger_identification)
    if not passenger_info:
        raise HTTPException(status_code=404, detail=f"Passenger {reservation_data.passenger_identification} not found")
    
    # Verificar reserva existente
    def check_existing_reservation():
        return db.query(Reservation).filter(
            Reservation.passenger_identification == reservation_data.passenger_identification,
            Reservation.flight_number == reservation_data.flight_number,
            Reservation.status.in_(["confirmed", "checked_in"])
        ).first()
    
    existing_reservation = database_circuit_breaker.call(check_existing_reservation)
    if existing_reservation:
        raise HTTPException(status_code=409, detail="Passenger already has a reservation for this flight")
    
    # Generar código único
    reservation_code = generate_reservation_code()
    def check_code_uniqueness():
        return db.query(Reservation).filter(Reservation.reservation_code == reservation_code).first()
    
    while database_circuit_breaker.call(check_code_uniqueness):
        reservation_code = generate_reservation_code()
    
    # Asignar asiento
    seat_number = assign_seat(reservation_data.flight_number, db, reservation_data.seat_number)
    
    # Crear reserva
    def create_reservation_protected():
        db_reservation = Reservation(
            reservation_code=reservation_code,
            passenger_identification=reservation_data.passenger_identification,
            flight_number=reservation_data.flight_number,
            seat_number=seat_number,
            status=ReservationStatus.CONFIRMED.value
        )
        
        db.add(db_reservation)
        db.commit()
        db.refresh(db_reservation)
        return db_reservation
    
    db_reservation = database_circuit_breaker.call(create_reservation_protected)
    
    # Actualizar asientos disponibles en el vuelo
    await update_flight_seats(reservation_data.flight_number, -1)
    
    publish_event("reservation.created", {
        "reservation_id": str(db_reservation.id),
        "reservation_code": db_reservation.reservation_code,
        "passenger": f"{passenger_info['first_name']} {passenger_info['last_name']}",
        "flight": f"{flight_info['flight_number']} ({flight_info['origin_airport']} → {flight_info['destination_airport']})",
        "seat": seat_number
    })
    
    print(f"✅ Reserva creada: {reservation_code}")
    
    return ReservationResponse(
        id=str(db_reservation.id),
        reservation_code=db_reservation.reservation_code,
        passenger_identification=db_reservation.passenger_identification,
        flight_number=db_reservation.flight_number,
        seat_number=db_reservation.seat_number,
        status=db_reservation.status,
        created_at=db_reservation.created_at,
        updated_at=db_reservation.updated_at,
        checked_in_at=db_reservation.checked_in_at,
        passenger_info=passenger_info,
        flight_info=flight_info
    )

@app.put("/api/v1/reservations/{reservation_code}/status", response_model=ReservationResponse)
async def update_reservation_status(reservation_code: str, new_status: str, db: Session = Depends(get_db)):
    def get_reservation_protected():
        return db.query(Reservation).filter(
            Reservation.reservation_code == reservation_code
        ).first()
    
    reservation = database_circuit_breaker.call(get_reservation_protected)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    
    # Validar estado
    if new_status not in [status.value for status in ReservationStatus]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    old_status = reservation.status
    reservation.status = new_status
    reservation.updated_at = datetime.utcnow()
    
    if new_status == ReservationStatus.CHECKED_IN.value:
        reservation.checked_in_at = datetime.utcnow()
    
    db.commit()
    db.refresh(reservation)
    
    # Si cancela, liberar asiento
    if new_status == ReservationStatus.CANCELLED.value and old_status in ["confirmed", "checked_in"]:
        await update_flight_seats(reservation.flight_number, 1)
    
    publish_event("reservation.status_updated", {
        "reservation_code": reservation_code,
        "old_status": old_status,
        "new_status": new_status
    })
    
    return ReservationResponse(
        id=str(reservation.id),
        reservation_code=reservation.reservation_code,
        passenger_identification=reservation.passenger_identification,
        flight_number=reservation.flight_number,
        seat_number=reservation.seat_number,
        status=reservation.status,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
        checked_in_at=reservation.checked_in_at
    )

@app.get("/api/v1/circuit-breaker/stats")
def get_circuit_breaker_stats():
    return {
        "database_circuit_breaker": database_circuit_breaker.get_stats(),
        "http_circuit_breaker": http_circuit_breaker.get_stats(),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/")
def root():
    return {
        "message": "Reservation Service Enhanced v2.0", 
        "status": "active",
        "version": "2.0.0",
        "features": ["circuit_breakers", "status_management", "seat_assignment", "cross_service_validation"],
        "database": f"{POSTGRES_HOST}:{POSTGRES_PORT}",
        "circuit_breakers": {
            "database": database_circuit_breaker.get_stats(),
            "http": http_circuit_breaker.get_stats()
        }
    }

def create_sample_reservations():
    print("🎫 Creando reservas de muestra...")
    db = SessionLocal()
    try:
        count = db.query(Reservation).count()
        if count == 0:
            sample_reservations = [
                Reservation(
                    reservation_code="ABC123",
                    passenger_identification="12345678",
                    flight_number="AV101",
                    seat_number="1A",
                    status=ReservationStatus.CONFIRMED.value
                ),
                Reservation(
                    reservation_code="DEF456",
                    passenger_identification="87654321",
                    flight_number="AV102",
                    seat_number="15B",
                    status=ReservationStatus.CHECKED_IN.value,
                    checked_in_at=datetime.utcnow()
                ),
                Reservation(
                    reservation_code="GHI789",
                    passenger_identification="11223344",
                    flight_number="AV201",
                    seat_number="8C",
                    status=ReservationStatus.CONFIRMED.value
                )
            ]
            
            for reservation in sample_reservations:
                db.add(reservation)
            
            db.commit()
            print("✅ Reservas de muestra creadas")
        else:
            print(f"ℹ️ Ya existen {count} reservas")
    except Exception as e:
        print(f"❌ Error creando reservas de muestra: {e}")
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    create_sample_reservations()

if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando Enhanced Reservation Service...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

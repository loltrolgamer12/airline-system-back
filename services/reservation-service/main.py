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
from circuit_breaker import database_circuit_breaker, http_circuit_breaker

# Configuración de base de datos
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "airline")

# URLs de otros microservicios
FLIGHT_SERVICE_URL = os.getenv("FLIGHT_SERVICE_URL", "http://flight-service:8000")
PASSENGER_SERVICE_URL = os.getenv("PASSENGER_SERVICE_URL", "http://passenger-service:8000")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

print(f"🎫 Reservation Service with Circuit Breakers")
print(f"🔗 Flight Service URL: {FLIGHT_SERVICE_URL}")
print(f"🔗 Passenger Service URL: {PASSENGER_SERVICE_URL}")

# Función de retry para conexión a BD con Circuit Breaker
def create_engine_with_circuit_breaker(database_url, max_retries=10, retry_delay=3):
    retries = 0
    while retries < max_retries:
        try:
            print(f"📡 Reservation Service - Intento conexión {retries + 1}/{max_retries}...")
            
            def create_engine_protected():
                engine = create_engine(database_url)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return engine
            
            engine = database_circuit_breaker.call(create_engine_protected)
            print("✅ Reservation Service conectado a PostgreSQL con Circuit Breaker")
            return engine
            
        except Exception as e:
            retries += 1
            print(f"❌ Error conectando (intento {retries}): {e}")
            if retries < max_retries:
                print(f"⏳ Esperando {retry_delay} segundos...")
                time.sleep(retry_delay)
            else:
                print("💥 Reservation Service: No se pudo conectar a PostgreSQL")
                raise e

# Crear engine con circuit breaker
engine = create_engine_with_circuit_breaker(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelo de base de datos
class Reservation(Base):
    __tablename__ = "reservations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reservation_code = Column(String(10), nullable=False, unique=True)
    passenger_identification = Column(String(20), nullable=False)
    flight_number = Column(String(10), nullable=False)
    seat_number = Column(String(5), nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

# Crear tablas con circuit breaker
print("🏗️ Creando tablas de reservas con Circuit Breaker...")
try:
    def create_tables():
        Base.metadata.create_all(bind=engine)
    
    database_circuit_breaker.call(create_tables)
    print("✅ Tablas de reservas creadas con Circuit Breaker")
except Exception as e:
    print(f"❌ Error creando tablas: {e}")

# Schemas Pydantic
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
    passenger_info: Optional[dict] = None
    flight_info: Optional[dict] = None

    class Config:
        from_attributes = True

# Dependencia para obtener sesión de DB con Circuit Breaker
def get_db():
    def get_session():
        return SessionLocal()
    
    db = database_circuit_breaker.call(get_session)
    try:
        yield db
    finally:
        db.close()

# Funciones para comunicarse con otros microservicios usando Circuit Breaker
async def verify_flight_exists(flight_number: str) -> Optional[dict]:
    """Verificar que el vuelo existe en Flight Service con Circuit Breaker"""
    try:
        print(f"🔍 Verificando vuelo {flight_number} con Circuit Breaker...")
        response = await http_circuit_breaker.http_request(
            "GET", 
            f"{FLIGHT_SERVICE_URL}/api/v1/flights/{flight_number}"
        )
        
        if response.status_code == 200:
            flight_info = response.json()
            print(f"✅ Vuelo {flight_number} encontrado: {flight_info['origin_airport']} → {flight_info['destination_airport']}")
            return flight_info
        else:
            print(f"❌ Vuelo {flight_number} no encontrado")
            return None
            
    except Exception as e:
        print(f"❌ Circuit Breaker: Error verificando vuelo {flight_number}: {e}")
        return None

async def verify_passenger_exists(identification: str) -> Optional[dict]:
    """Verificar que el pasajero existe en Passenger Service con Circuit Breaker"""
    try:
        print(f"🔍 Verificando pasajero {identification} con Circuit Breaker...")
        response = await http_circuit_breaker.http_request(
            "GET", 
            f"{PASSENGER_SERVICE_URL}/api/v1/passengers/{identification}"
        )
        
        if response.status_code == 200:
            passenger_info = response.json()
            print(f"✅ Pasajero {identification} encontrado: {passenger_info['first_name']} {passenger_info['last_name']}")
            return passenger_info
        else:
            print(f"❌ Pasajero {identification} no encontrado")
            return None
            
    except Exception as e:
        print(f"❌ Circuit Breaker: Error verificando pasajero {identification}: {e}")
        return None

def generate_reservation_code() -> str:
    """Generar código de reserva único de 6 caracteres"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def assign_seat(flight_number: str, db: Session, preferred_seat: Optional[str] = None) -> str:
    """Asignar asiento automáticamente o usar el preferido con Circuit Breaker"""
    def get_existing_seats():
        return db.query(Reservation).filter(
            Reservation.flight_number == flight_number,
            Reservation.status.in_(["confirmed", "pending"])
        ).count()
    
    if preferred_seat:
        def check_seat_availability():
            return db.query(Reservation).filter(
                Reservation.flight_number == flight_number,
                Reservation.seat_number == preferred_seat,
                Reservation.status.in_(["confirmed", "pending"])
            ).first()
        
        existing = database_circuit_breaker.call(check_seat_availability)
        if not existing:
            return preferred_seat
        else:
            print(f"⚠️ Asiento {preferred_seat} no disponible, asignando automáticamente...")
    
    # Asignación automática con circuit breaker
    existing_seats = database_circuit_breaker.call(get_existing_seats)
    
    row = (existing_seats // 6) + 1
    seat_letter = chr(65 + (existing_seats % 6))  # A, B, C, D, E, F
    seat_number = f"{row}{seat_letter}"
    
    print(f"💺 Asiento asignado automáticamente: {seat_number}")
    return seat_number

# Función para publicar eventos
def publish_event(event_type: str, data: dict):
    print(f"📤 RESERVATION EVENT: {event_type} - {data}")

# FastAPI App
app = FastAPI(title="Reservation Service with Circuit Breakers", version="2.0.0")

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
        updated_at=reservation.updated_at
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
    
    # Obtener información adicional con circuit breaker
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
        passenger_info=passenger_info,
        flight_info=flight_info
    )

@app.post("/api/v1/reservations", response_model=ReservationResponse, status_code=201)
async def create_reservation(reservation_data: ReservationCreate, db: Session = Depends(get_db)):
    print(f"🎫 Creando reserva con Circuit Breakers para pasajero {reservation_data.passenger_identification}")
    
    # Verificaciones con circuit breaker
    flight_info = await verify_flight_exists(reservation_data.flight_number)
    if not flight_info:
        raise HTTPException(status_code=404, detail=f"Flight {reservation_data.flight_number} not found or service unavailable")
    
    passenger_info = await verify_passenger_exists(reservation_data.passenger_identification)
    if not passenger_info:
        raise HTTPException(status_code=404, detail=f"Passenger {reservation_data.passenger_identification} not found or service unavailable")
    
    # Verificar reserva existente con circuit breaker
    def check_existing_reservation():
        return db.query(Reservation).filter(
            Reservation.passenger_identification == reservation_data.passenger_identification,
            Reservation.flight_number == reservation_data.flight_number,
            Reservation.status.in_(["confirmed", "pending"])
        ).first()
    
    existing_reservation = database_circuit_breaker.call(check_existing_reservation)
    if existing_reservation:
        raise HTTPException(
            status_code=409, 
            detail=f"Passenger already has a reservation for flight {reservation_data.flight_number}"
        )
    
    # Generar código único con circuit breaker
    reservation_code = generate_reservation_code()
    def check_code_uniqueness():
        return db.query(Reservation).filter(Reservation.reservation_code == reservation_code).first()
    
    while database_circuit_breaker.call(check_code_uniqueness):
        reservation_code = generate_reservation_code()
    
    # Asignar asiento con circuit breaker
    seat_number = assign_seat(reservation_data.flight_number, db, reservation_data.seat_number)
    
    # Crear reserva con circuit breaker
    def create_reservation_protected():
        db_reservation = Reservation(
            reservation_code=reservation_code,
            passenger_identification=reservation_data.passenger_identification,
            flight_number=reservation_data.flight_number,
            seat_number=seat_number,
            status="confirmed"
        )
        
        db.add(db_reservation)
        db.commit()
        db.refresh(db_reservation)
        return db_reservation
    
    db_reservation = database_circuit_breaker.call(create_reservation_protected)
    
    # Publicar evento
    publish_event("reservation.created", {
        "reservation_id": str(db_reservation.id),
        "reservation_code": db_reservation.reservation_code,
        "passenger": f"{passenger_info['first_name']} {passenger_info['last_name']}",
        "flight": f"{flight_info['flight_number']} ({flight_info['origin_airport']} → {flight_info['destination_airport']})",
        "seat": seat_number
    })
    
    print(f"✅ Reserva creada exitosamente con Circuit Breakers: {reservation_code}")
    
    return ReservationResponse(
        id=str(db_reservation.id),
        reservation_code=db_reservation.reservation_code,
        passenger_identification=db_reservation.passenger_identification,
        flight_number=db_reservation.flight_number,
        seat_number=db_reservation.seat_number,
        status=db_reservation.status,
        created_at=db_reservation.created_at,
        updated_at=db_reservation.updated_at,
        passenger_info=passenger_info,
        flight_info=flight_info
    )

@app.get("/api/v1/circuit-breaker/stats")
def get_circuit_breaker_stats():
    """Endpoint para monitorear el estado de los circuit breakers"""
    return {
        "database_circuit_breaker": database_circuit_breaker.get_stats(),
        "http_circuit_breaker": http_circuit_breaker.get_stats(),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/")
def root():
    return {
        "message": "Reservation Service with Advanced Circuit Breakers", 
        "status": "active",
        "version": "2.0.0",
        "features": ["circuit_breakers", "resilience", "monitoring"],
        "database": f"{POSTGRES_HOST}:{POSTGRES_PORT}",
        "circuit_breakers": {
            "database": database_circuit_breaker.get_stats(),
            "http": http_circuit_breaker.get_stats()
        }
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando Reservation Service with Circuit Breakers...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

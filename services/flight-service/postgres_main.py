from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
import datetime as dt
import os
import time

# Configuración de base de datos
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "airline")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

print(f"🔗 Intentando conectar a: {POSTGRES_HOST}:{POSTGRES_PORT} como {POSTGRES_USER}")

# Función de retry para conexión a BD
def create_engine_with_retry(database_url, max_retries=10, retry_delay=5):
    retries = 0
    while retries < max_retries:
        try:
            print(f"📡 Intento de conexión {retries + 1}/{max_retries}...")
            engine = create_engine(database_url)
            # Probar conexión
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ Conexión a PostgreSQL exitosa")
            return engine
        except Exception as e:
            retries += 1
            print(f"❌ Error conectando a PostgreSQL (intento {retries}): {e}")
            if retries < max_retries:
                print(f"⏳ Esperando {retry_delay} segundos antes del siguiente intento...")
                time.sleep(retry_delay)
            else:
                print("💥 No se pudo conectar a PostgreSQL después de todos los intentos")
                raise e

# Crear engine con retry
engine = create_engine_with_retry(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelo de base de datos
class Flight(Base):
    __tablename__ = "flights"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_number = Column(String(10), nullable=False, unique=True)
    departure_time = Column(DateTime, nullable=False)
    arrival_time = Column(DateTime, nullable=False)  
    origin_airport = Column(String(3), nullable=False)
    destination_airport = Column(String(3), nullable=False)
    aircraft_id = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default="scheduled")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

# Crear tablas con retry
print("🏗️ Creando tablas...")
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas creadas exitosamente")
except Exception as e:
    print(f"❌ Error creando tablas: {e}")

# Schemas Pydantic
class FlightCreate(BaseModel):
    flight_number: str
    departure_time: datetime
    arrival_time: datetime
    origin_airport: str
    destination_airport: str
    aircraft_id: str

class FlightResponse(BaseModel):
    id: str
    flight_number: str
    departure_time: datetime
    arrival_time: datetime
    origin_airport: str
    destination_airport: str
    aircraft_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Dependencia para obtener sesión de DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Simulación de eventos (por ahora)
def publish_event(event_type: str, data: dict):
    print(f"📤 EVENT: {event_type} - {data}")

# FastAPI App
app = FastAPI(title="Flight Service with Retry Logic", version="1.0.0")

@app.get("/health")
def health_check():
    try:
        # Verificar conexión a DB
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {
            "status": "healthy", 
            "service": "flight-service", 
            "database": "connected",
            "database_url": f"{POSTGRES_HOST}:{POSTGRES_PORT}"
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "service": "flight-service", 
            "database": "disconnected", 
            "error": str(e),
            "database_url": f"{POSTGRES_HOST}:{POSTGRES_PORT}"
        }

@app.get("/api/v1/flights", response_model=List[FlightResponse])
def get_flights(db: Session = Depends(get_db)):
    flights = db.query(Flight).all()
    return [FlightResponse(
        id=str(flight.id),
        flight_number=flight.flight_number,
        departure_time=flight.departure_time,
        arrival_time=flight.arrival_time,
        origin_airport=flight.origin_airport,
        destination_airport=flight.destination_airport,
        aircraft_id=flight.aircraft_id,
        status=flight.status,
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
        created_at=flight.created_at,
        updated_at=flight.updated_at
    )

@app.post("/api/v1/flights", response_model=FlightResponse, status_code=201)
def create_flight(flight_data: FlightCreate, db: Session = Depends(get_db)):
    # Verificar si ya existe
    existing = db.query(Flight).filter(Flight.flight_number == flight_data.flight_number).first()
    if existing:
        raise HTTPException(status_code=409, detail="Flight already exists")
    
    # Crear nuevo vuelo
    db_flight = Flight(
        flight_number=flight_data.flight_number,
        departure_time=flight_data.departure_time,
        arrival_time=flight_data.arrival_time,
        origin_airport=flight_data.origin_airport,
        destination_airport=flight_data.destination_airport,
        aircraft_id=flight_data.aircraft_id,
        status="scheduled"
    )
    
    db.add(db_flight)
    db.commit()
    db.refresh(db_flight)
    
    # Publicar evento
    publish_event("flight.created", {
        "flight_id": str(db_flight.id),
        "flight_number": db_flight.flight_number,
        "origin": db_flight.origin_airport,
        "destination": db_flight.destination_airport
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
        created_at=db_flight.created_at,
        updated_at=db_flight.updated_at
    )

@app.delete("/api/v1/flights/{flight_number}", status_code=204)
def delete_flight(flight_number: str, db: Session = Depends(get_db)):
    flight = db.query(Flight).filter(Flight.flight_number == flight_number).first()
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    
    flight_id = str(flight.id)
    db.delete(flight)
    db.commit()
    
    # Publicar evento
    publish_event("flight.deleted", {
        "flight_id": flight_id,
        "flight_number": flight_number
    })

@app.get("/")
def root():
    return {
        "message": "Flight Service with Retry Logic", 
        "status": "active",
        "database": f"{POSTGRES_HOST}:{POSTGRES_PORT}"
    }

# Crear datos de muestra al iniciar
def create_sample_data():
    print("🎯 Creando datos de muestra...")
    db = SessionLocal()
    try:
        # Verificar si ya hay datos
        count = db.query(Flight).count()
        if count == 0:
            # Crear vuelos de muestra
            sample_flights = [
                Flight(
                    flight_number="AA123",
                    departure_time=dt.datetime(2025, 6, 15, 10, 0),
                    arrival_time=dt.datetime(2025, 6, 15, 12, 0),
                    origin_airport="JFK",
                    destination_airport="LAX",
                    aircraft_id="N12345",
                    status="scheduled"
                ),
                Flight(
                    flight_number="UA456", 
                    departure_time=dt.datetime(2025, 6, 15, 14, 0),
                    arrival_time=dt.datetime(2025, 6, 15, 18, 30),
                    origin_airport="LAX",
                    destination_airport="MIA", 
                    aircraft_id="N67890",
                    status="active"
                )
            ]
            
            for flight in sample_flights:
                db.add(flight)
            
            db.commit()
            print("✅ Datos de muestra creados")
        else:
            print(f"ℹ️ Ya existen {count} vuelos en la base de datos")
    except Exception as e:
        print(f"❌ Error creando datos de muestra: {e}")
    finally:
        db.close()

# Inicializar datos cuando la app inicie
@app.on_event("startup")
def startup_event():
    create_sample_data()

if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando Flight Service...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

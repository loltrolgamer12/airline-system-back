from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, DateTime, Date, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, date
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import os
import time

# Configuración de base de datos
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "airline")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

print(f"👥 Passenger Service conectando a: {POSTGRES_HOST}:{POSTGRES_PORT}")

# Función de retry para conexión a BD
def create_engine_with_retry(database_url, max_retries=10, retry_delay=3):
    retries = 0
    while retries < max_retries:
        try:
            print(f"📡 Passenger Service - Intento conexión {retries + 1}/{max_retries}...")
            engine = create_engine(database_url)
            # Probar conexión
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ Passenger Service conectado a PostgreSQL")
            return engine
        except Exception as e:
            retries += 1
            print(f"❌ Error conectando (intento {retries}): {e}")
            if retries < max_retries:
                print(f"⏳ Esperando {retry_delay} segundos...")
                time.sleep(retry_delay)
            else:
                print("💥 Passenger Service: No se pudo conectar a PostgreSQL")
                raise e

# Crear engine con retry
engine = create_engine_with_retry(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelo de base de datos
class Passenger(Base):
    __tablename__ = "passengers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identification_number = Column(String(20), nullable=False, unique=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    nationality = Column(String(50), nullable=False)
    passport_number = Column(String(20), nullable=True)
    birth_date = Column(Date, nullable=False)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

# Crear tablas
print("🏗️ Creando tablas de pasajeros...")
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas de pasajeros creadas")
except Exception as e:
    print(f"❌ Error creando tablas: {e}")

# Schemas Pydantic
class PassengerCreate(BaseModel):
    identification_number: str
    first_name: str
    last_name: str
    nationality: str
    passport_number: Optional[str] = None
    birth_date: date
    email: Optional[str] = None
    phone: Optional[str] = None

class PassengerUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nationality: Optional[str] = None
    passport_number: Optional[str] = None
    birth_date: Optional[date] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class PassengerResponse(BaseModel):
    id: str
    identification_number: str
    first_name: str
    last_name: str
    nationality: str
    passport_number: Optional[str]
    birth_date: date
    email: Optional[str]
    phone: Optional[str]
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

# Función para publicar eventos
def publish_event(event_type: str, data: dict):
    print(f"📤 PASSENGER EVENT: {event_type} - {data}")

# FastAPI App
app = FastAPI(title="Passenger Service", version="1.0.0")

@app.get("/health")
def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {
            "status": "healthy", 
            "service": "passenger-service", 
            "database": "connected",
            "database_url": f"{POSTGRES_HOST}:{POSTGRES_PORT}"
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "service": "passenger-service", 
            "database": "disconnected", 
            "error": str(e)
        }

@app.get("/api/v1/passengers", response_model=List[PassengerResponse])
def get_passengers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    passengers = db.query(Passenger).offset(skip).limit(limit).all()
    return [PassengerResponse(
        id=str(passenger.id),
        identification_number=passenger.identification_number,
        first_name=passenger.first_name,
        last_name=passenger.last_name,
        nationality=passenger.nationality,
        passport_number=passenger.passport_number,
        birth_date=passenger.birth_date,
        email=passenger.email,
        phone=passenger.phone,
        created_at=passenger.created_at,
        updated_at=passenger.updated_at
    ) for passenger in passengers]

@app.get("/api/v1/passengers/{identification}", response_model=PassengerResponse)
def get_passenger(identification: str, db: Session = Depends(get_db)):
    passenger = db.query(Passenger).filter(
        Passenger.identification_number == identification
    ).first()
    if not passenger:
        raise HTTPException(status_code=404, detail="Passenger not found")
    
    return PassengerResponse(
        id=str(passenger.id),
        identification_number=passenger.identification_number,
        first_name=passenger.first_name,
        last_name=passenger.last_name,
        nationality=passenger.nationality,
        passport_number=passenger.passport_number,
        birth_date=passenger.birth_date,
        email=passenger.email,
        phone=passenger.phone,
        created_at=passenger.created_at,
        updated_at=passenger.updated_at
    )

@app.post("/api/v1/passengers", response_model=PassengerResponse, status_code=201)
def create_passenger(passenger_data: PassengerCreate, db: Session = Depends(get_db)):
    # Verificar si ya existe
    existing = db.query(Passenger).filter(
        Passenger.identification_number == passenger_data.identification_number
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Passenger already exists")
    
    # Crear nuevo pasajero
    db_passenger = Passenger(
        identification_number=passenger_data.identification_number,
        first_name=passenger_data.first_name,
        last_name=passenger_data.last_name,
        nationality=passenger_data.nationality,
        passport_number=passenger_data.passport_number,
        birth_date=passenger_data.birth_date,
        email=passenger_data.email,
        phone=passenger_data.phone
    )
    
    db.add(db_passenger)
    db.commit()
    db.refresh(db_passenger)
    
    # Publicar evento
    publish_event("passenger.created", {
        "passenger_id": str(db_passenger.id),
        "identification_number": db_passenger.identification_number,
        "full_name": f"{db_passenger.first_name} {db_passenger.last_name}",
        "nationality": db_passenger.nationality
    })
    
    return PassengerResponse(
        id=str(db_passenger.id),
        identification_number=db_passenger.identification_number,
        first_name=db_passenger.first_name,
        last_name=db_passenger.last_name,
        nationality=db_passenger.nationality,
        passport_number=db_passenger.passport_number,
        birth_date=db_passenger.birth_date,
        email=db_passenger.email,
        phone=db_passenger.phone,
        created_at=db_passenger.created_at,
        updated_at=db_passenger.updated_at
    )

@app.put("/api/v1/passengers/{identification}", response_model=PassengerResponse)
def update_passenger(identification: str, passenger_update: PassengerUpdate, db: Session = Depends(get_db)):
    passenger = db.query(Passenger).filter(
        Passenger.identification_number == identification
    ).first()
    if not passenger:
        raise HTTPException(status_code=404, detail="Passenger not found")
    
    # Actualizar campos proporcionados
    update_data = passenger_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(passenger, key, value)
    
    passenger.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(passenger)
    
    # Publicar evento
    publish_event("passenger.updated", {
        "passenger_id": str(passenger.id),
        "identification_number": passenger.identification_number,
        "updated_fields": list(update_data.keys())
    })
    
    return PassengerResponse(
        id=str(passenger.id),
        identification_number=passenger.identification_number,
        first_name=passenger.first_name,
        last_name=passenger.last_name,
        nationality=passenger.nationality,
        passport_number=passenger.passport_number,
        birth_date=passenger.birth_date,
        email=passenger.email,
        phone=passenger.phone,
        created_at=passenger.created_at,
        updated_at=passenger.updated_at
    )

@app.delete("/api/v1/passengers/{identification}", status_code=204)
def delete_passenger(identification: str, db: Session = Depends(get_db)):
    passenger = db.query(Passenger).filter(
        Passenger.identification_number == identification
    ).first()
    if not passenger:
        raise HTTPException(status_code=404, detail="Passenger not found")
    
    passenger_id = str(passenger.id)
    full_name = f"{passenger.first_name} {passenger.last_name}"
    
    db.delete(passenger)
    db.commit()
    
    # Publicar evento
    publish_event("passenger.deleted", {
        "passenger_id": passenger_id,
        "identification_number": identification,
        "full_name": full_name
    })

@app.get("/")
def root():
    return {
        "message": "Passenger Service", 
        "status": "active",
        "database": f"{POSTGRES_HOST}:{POSTGRES_PORT}"
    }

# Crear datos de muestra
def create_sample_passengers():
    print("👥 Creando pasajeros de muestra...")
    db = SessionLocal()
    try:
        count = db.query(Passenger).count()
        if count == 0:
            sample_passengers = [
                Passenger(
                    identification_number="12345678",
                    first_name="Juan",
                    last_name="Pérez",
                    nationality="Colombian",
                    passport_number="AB123456",
                    birth_date=date(1985, 5, 15),
                    email="juan.perez@email.com",
                    phone="+57300123456"
                ),
                Passenger(
                    identification_number="87654321",
                    first_name="María",
                    last_name="García",
                    nationality="Colombian", 
                    passport_number="CD789012",
                    birth_date=date(1992, 8, 22),
                    email="maria.garcia@email.com",
                    phone="+57301987654"
                ),
                Passenger(
                    identification_number="11223344",
                    first_name="Carlos",
                    last_name="Rodríguez",
                    nationality="Colombian",
                    passport_number="EF345678",
                    birth_date=date(1988, 12, 3),
                    email="carlos.rodriguez@email.com",
                    phone="+57302555444"
                )
            ]
            
            for passenger in sample_passengers:
                db.add(passenger)
            
            db.commit()
            print("✅ Pasajeros de muestra creados")
        else:
            print(f"ℹ️ Ya existen {count} pasajeros en la base de datos")
    except Exception as e:
        print(f"❌ Error creando pasajeros de muestra: {e}")
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    create_sample_passengers()

if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando Passenger Service...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, Integer, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import uuid
from pydantic import BaseModel
from typing import List
import os
import time

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "airline")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

def create_engine_with_retry(database_url, max_retries=10, retry_delay=3):
    retries = 0
    while retries < max_retries:
        try:
            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ Aircraft Service conectado")
            return engine
        except Exception as e:
            retries += 1
            if retries < max_retries:
                time.sleep(retry_delay)
            else:
                raise e

engine = create_engine_with_retry(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Aircraft(Base):
    __tablename__ = "aircraft"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration = Column(String(10), nullable=False, unique=True)
    model = Column(String(50), nullable=False)
    manufacturer = Column(String(50), nullable=False)
    total_seats = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="available")

try:
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas de aviones creadas")
except Exception as e:
    print(f"❌ Error: {e}")

class AircraftResponse(BaseModel):
    id: str
    registration: str
    model: str
    manufacturer: str
    total_seats: int
    status: str
    class Config:
        from_attributes = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="Aircraft Service", version="1.0.0")

@app.get("/health")
def health_check():
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT COUNT(*) as count FROM aircraft")).fetchone()
        available = db.execute(text("SELECT COUNT(*) as count FROM aircraft WHERE status = 'available'")).fetchone()
        db.close()
        return {
            "status": "healthy",
            "service": "aircraft-service",
            "database": "connected",
            "total_aircraft": result.count if result else 0,
            "available_aircraft": available.count if available else 0
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "aircraft-service",
            "error": str(e)
        }

@app.get("/api/v1/aircraft", response_model=List[AircraftResponse])
def get_aircraft(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    aircraft_list = db.query(Aircraft).offset(skip).limit(limit).all()
    return [AircraftResponse(
        id=str(aircraft.id),
        registration=aircraft.registration,
        model=aircraft.model,
        manufacturer=aircraft.manufacturer,
        total_seats=aircraft.total_seats,
        status=aircraft.status
    ) for aircraft in aircraft_list]

@app.get("/api/v1/aircraft/available/count")
def get_available_count(db: Session = Depends(get_db)):
    count = db.query(Aircraft).filter(Aircraft.status == "available").count()
    return {"available_aircraft": count}

@app.get("/")
def root():
    return {"message": "Aircraft Service", "status": "active"}

def create_sample_data():
    db = SessionLocal()
    try:
        count = db.query(Aircraft).count()
        if count == 0:
            aircraft_list = [
                Aircraft(registration="HK-001", model="A320-200", manufacturer="Airbus", total_seats=150),
                Aircraft(registration="HK-002", model="B737-800", manufacturer="Boeing", total_seats=180),
                Aircraft(registration="HK-787", model="B787-9", manufacturer="Boeing", total_seats=250)
            ]
            for aircraft in aircraft_list:
                db.add(aircraft)
            db.commit()
            print("✅ Aviones creados")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    create_sample_data()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

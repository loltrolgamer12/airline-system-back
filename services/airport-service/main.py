from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, Integer, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import uuid
from pydantic import BaseModel
from typing import List, Optional
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
            print("✅ Airport Service conectado")
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

class Airport(Base):
    __tablename__ = "airports"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iata_code = Column(String(3), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    city = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)

try:
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas de aeropuertos creadas")
except Exception as e:
    print(f"❌ Error: {e}")

class AirportResponse(BaseModel):
    id: str
    iata_code: str
    name: str
    city: str
    country: str
    class Config:
        from_attributes = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="Airport Service", version="1.0.0")

@app.get("/health")
def health_check():
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT COUNT(*) as count FROM airports")).fetchone()
        db.close()
        return {
            "status": "healthy",
            "service": "airport-service",
            "database": "connected",
            "total_airports": result.count if result else 0
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "airport-service",
            "error": str(e)
        }

@app.get("/api/v1/airports", response_model=List[AirportResponse])
def get_airports(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    airports = db.query(Airport).offset(skip).limit(limit).all()
    return [AirportResponse(
        id=str(airport.id),
        iata_code=airport.iata_code,
        name=airport.name,
        city=airport.city,
        country=airport.country
    ) for airport in airports]

@app.get("/")
def root():
    return {"message": "Airport Service", "status": "active"}

def create_sample_data():
    db = SessionLocal()
    try:
        count = db.query(Airport).count()
        if count == 0:
            airports = [
                Airport(iata_code="BOG", name="El Dorado", city="Bogotá", country="Colombia"),
                Airport(iata_code="MDE", name="José María Córdova", city="Medellín", country="Colombia"),
                Airport(iata_code="CLO", name="Alfonso Bonilla Aragón", city="Cali", country="Colombia")
            ]
            for airport in airports:
                db.add(airport)
            db.commit()
            print("✅ Aeropuertos creados")
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

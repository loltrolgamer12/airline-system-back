from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, String, Integer, Date, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import uuid
from pydantic import BaseModel
from typing import List
from datetime import date
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
            print("✅ Crew Service conectado")
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

class CrewMember(Base):
    __tablename__ = "crew_members"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(String(10), nullable=False, unique=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    position = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="available")
    base_airport = Column(String(3), nullable=False)

try:
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas de tripulación creadas")
except Exception as e:
    print(f"❌ Error: {e}")

class CrewResponse(BaseModel):
    id: str
    employee_id: str
    first_name: str
    last_name: str
    position: str
    status: str
    base_airport: str
    class Config:
        from_attributes = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="Crew Service", version="1.0.0")

@app.get("/health")
def health_check():
    try:
        db = SessionLocal()
        total = db.execute(text("SELECT COUNT(*) as count FROM crew_members")).fetchone()
        available = db.execute(text("SELECT COUNT(*) as count FROM crew_members WHERE status = 'available'")).fetchone()
        db.close()
        return {
            "status": "healthy",
            "service": "crew-service",
            "database": "connected",
            "total_crew": total.count if total else 0,
            "available_crew": available.count if available else 0
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "crew-service",
            "error": str(e)
        }

@app.get("/api/v1/crew", response_model=List[CrewResponse])
def get_crew(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    crew_list = db.query(CrewMember).offset(skip).limit(limit).all()
    return [CrewResponse(
        id=str(member.id),
        employee_id=member.employee_id,
        first_name=member.first_name,
        last_name=member.last_name,
        position=member.position,
        status=member.status,
        base_airport=member.base_airport
    ) for member in crew_list]

@app.get("/api/v1/crew/available/by-position")
def get_available_by_position(db: Session = Depends(get_db)):
    members = db.query(CrewMember).filter(CrewMember.status == "available").all()
    by_position = {}
    for member in members:
        if member.position not in by_position:
            by_position[member.position] = []
        by_position[member.position].append({
            "employee_id": member.employee_id,
            "name": f"{member.first_name} {member.last_name}"
        })
    return {"available_crew_by_position": by_position}

@app.get("/")
def root():
    return {"message": "Crew Service", "status": "active"}

def create_sample_data():
    db = SessionLocal()
    try:
        count = db.query(CrewMember).count()
        if count == 0:
            crew_list = [
                CrewMember(employee_id="CP001", first_name="Carlos", last_name="Rodríguez", position="captain", base_airport="BOG"),
                CrewMember(employee_id="FO001", first_name="María", last_name="González", position="first_officer", base_airport="BOG"),
                CrewMember(employee_id="FA001", first_name="Ana", last_name="López", position="flight_attendant", base_airport="BOG")
            ]
            for member in crew_list:
                db.add(member)
            db.commit()
            print("✅ Tripulación creada")
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

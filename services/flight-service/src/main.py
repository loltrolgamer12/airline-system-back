import os
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from .api import routes
from .core.database import engine, Base
from .core.config import settings
from .core.dependencies import get_db

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Flight Service API",
    description="API for managing flights in the Airline System",
    version="1.0.0",
)

# Include routers
app.include_router(routes.router, prefix="/api/v1", tags=["flights"])

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "flight-service"}

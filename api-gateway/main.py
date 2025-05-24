from fastapi import FastAPI

app = FastAPI(
    title="Airline System API Gateway",
    description="API Gateway for the Airline Management System",
    version="1.0.0",
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api-gateway"}

@app.get("/")
async def root():
    return {"message": "Welcome to the Airline Management System API"}

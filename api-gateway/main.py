from fastapi import FastAPI
import uvicorn

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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

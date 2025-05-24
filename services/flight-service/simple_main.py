from fastapi import FastAPI

app = FastAPI(title="Flight Service", version="1.0.0")

# Lista en memoria para pruebas
flights_db = [
    {
        "id": "1",
        "flight_number": "AA123",
        "origin_airport": "JFK", 
        "destination_airport": "LAX",
        "status": "scheduled",
        "departure_time": "2025-06-15T10:00:00Z",
        "arrival_time": "2025-06-15T12:00:00Z"
    },
    {
        "id": "2", 
        "flight_number": "UA456",
        "origin_airport": "LAX",
        "destination_airport": "MIA", 
        "status": "active",
        "departure_time": "2025-06-15T14:00:00Z",
        "arrival_time": "2025-06-15T18:30:00Z"
    }
]

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "flight-service"}

@app.get("/api/v1/flights")
def get_flights():
    return flights_db

@app.get("/api/v1/flights/{flight_number}")
def get_flight(flight_number: str):
    for flight in flights_db:
        if flight["flight_number"] == flight_number:
            return flight
    return {"error": "Flight not found"}

@app.get("/")
def root():
    return {"message": "Flight Service is running", "total_flights": len(flights_db)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# main.py - API Gateway Completo (BACKEND)
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import os
import logging
from datetime import datetime
import uvicorn

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URLs de los microservicios
SERVICES = {
    "flight": os.getenv("FLIGHT_SERVICE_URL", "http://flight-service:8000"),
    "passenger": os.getenv("PASSENGER_SERVICE_URL", "http://passenger-service:8000"), 
    "reservation": os.getenv("RESERVATION_SERVICE_URL", "http://reservation-service:8000")
}

app = FastAPI(
    title="Airline System API Gateway",
    description="Gateway for Airline Management System",
    version="2.0.0",
)

# Configurar CORS para permitir frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000", 
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "*"  # Para desarrollo - remover en producción
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Cliente HTTP global
http_client = httpx.AsyncClient(timeout=30.0)

async def proxy_request(service_name: str, path: str, method: str, request: Request):
    """Proxy request to microservice"""
    service_url = SERVICES.get(service_name)
    if not service_url:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    # Construir URL completa
    target_url = f"{service_url}{path}"
    
    # Obtener body si existe
    body = None
    if method in ["POST", "PUT", "PATCH"]:
        body = await request.body()
    
    # Obtener query parameters
    query_params = dict(request.query_params)
    
    # Headers (filtrar algunos headers problemáticos)
    headers = {
        k: v for k, v in request.headers.items() 
        if k.lower() not in ['host', 'content-length']
    }
    
    try:
        logger.info(f"Proxying {method} {target_url}")
        
        # Hacer request al microservicio
        response = await http_client.request(
            method=method,
            url=target_url,
            params=query_params,
            headers=headers,
            content=body
        )
        
        # Retornar respuesta
        try:
            content = response.json()
        except:
            content = response.text
            
        return JSONResponse(
            content=content,
            status_code=response.status_code
        )
        
    except httpx.RequestError as e:
        logger.error(f"Request error to {target_url}: {e}")
        raise HTTPException(status_code=503, detail=f"Service {service_name} unavailable")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Health check del gateway
@app.get("/health")
async def gateway_health():
    """Health check del gateway y servicios"""
    health_status = {
        "gateway": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    # Verificar cada microservicio
    for service_name, service_url in SERVICES.items():
        try:
            response = await http_client.get(f"{service_url}/health", timeout=5.0)
            health_status["services"][service_name] = {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "url": service_url,
                "response_time": f"{response.elapsed.total_seconds():.3f}s"
            }
        except Exception as e:
            health_status["services"][service_name] = {
                "status": "unhealthy",
                "url": service_url,
                "error": str(e)
            }
    
    return health_status

@app.get("/")
async def root():
    return {
        "message": "Airline System API Gateway v2.0",
        "status": "active",
        "services": list(SERVICES.keys()),
        "endpoints": {
            "flights": "/api/v1/flights",
            "passengers": "/api/v1/passengers",
            "reservations": "/api/v1/reservations",
            "health": "/health"
        }
    }

# ============================================================================
# RUTAS PROXY PARA MICROSERVICIOS
# ============================================================================

# Flight Service routes
@app.api_route("/api/v1/flights/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def flight_proxy(path: str, request: Request):
    full_path = f"/api/v1/flights/{path}" if path else "/api/v1/flights"
    return await proxy_request("flight", full_path, request.method, request)

@app.api_route("/api/v1/flights", methods=["GET", "POST"])
async def flight_proxy_root(request: Request):
    return await proxy_request("flight", "/api/v1/flights", request.method, request)

# Passenger Service routes  
@app.api_route("/api/v1/passengers/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def passenger_proxy(path: str, request: Request):
    full_path = f"/api/v1/passengers/{path}" if path else "/api/v1/passengers"
    return await proxy_request("passenger", full_path, request.method, request)

@app.api_route("/api/v1/passengers", methods=["GET", "POST"])
async def passenger_proxy_root(request: Request):
    return await proxy_request("passenger", "/api/v1/passengers", request.method, request)

# Reservation Service routes
@app.api_route("/api/v1/reservations/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def reservation_proxy(path: str, request: Request):
    full_path = f"/api/v1/reservations/{path}" if path else "/api/v1/reservations"
    return await proxy_request("reservation", full_path, request.method, request)

@app.api_route("/api/v1/reservations", methods=["GET", "POST"])
async def reservation_proxy_root(request: Request):
    return await proxy_request("reservation", "/api/v1/reservations", request.method, request)

# Circuit breaker stats (para monitoreo)
@app.get("/api/v1/circuit-breaker/stats")
async def circuit_breaker_stats(request: Request):
    return await proxy_request("reservation", "/api/v1/circuit-breaker/stats", "GET", request)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

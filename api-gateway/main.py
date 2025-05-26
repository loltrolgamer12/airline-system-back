from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import os
import logging
from datetime import datetime
import uvicorn
import jwt

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "airline-secret-key-2025")
JWT_ALGORITHM = "HS256"

# URLs de los microservicios
SERVICES = {
    "flight": os.getenv("FLIGHT_SERVICE_URL", "http://flight-service:8000"),
    "passenger": os.getenv("PASSENGER_SERVICE_URL", "http://passenger-service:8000"), 
    "reservation": os.getenv("RESERVATION_SERVICE_URL", "http://reservation-service:8000"),
    "user": os.getenv("USER_SERVICE_URL", "http://user-service:8000")
}

app = FastAPI(
    title="Enhanced Airline System API Gateway",
    description="Gateway with Authentication for Airline Management System",
    version="3.0.0",
)

# Configurar CORS mejorado para Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js development
        "http://localhost:3001",  # Next.js production
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "https://airline-frontend.vercel.app",  # Vercel deployment
        "*"  # Para desarrollo - REMOVER EN PRODUCCIÓN
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

# Cliente HTTP global
http_client = httpx.AsyncClient(timeout=30.0)

def verify_token(token: str) -> dict:
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from token"""
    if not credentials:
        return None
    
    try:
        return verify_token(credentials.credentials)
    except HTTPException:
        return None

# Protected routes configuration
PROTECTED_ROUTES = {
    "/api/v1/users": ["admin"],
    "/api/v1/flights": {"POST": ["admin", "operator"], "PUT": ["admin", "operator"], "DELETE": ["admin"]},
    "/api/v1/passengers": {"POST": ["admin", "agent"], "PUT": ["admin", "agent"], "DELETE": ["admin"]},
    "/api/v1/reservations": {"POST": ["admin", "agent"], "PUT": ["admin", "agent"], "DELETE": ["admin"]}
}

def check_route_permission(path: str, method: str, user_data: dict = None):
    """Check if user has permission for route"""
    # Public routes (no authentication needed)
    public_routes = ["/health", "/", "/api/v1/auth/login"]
    
    if any(path.startswith(route) for route in public_routes):
        return True
    
    # GET requests for flights are public (search functionality)
    if path.startswith("/api/v1/flights") and method == "GET":
        return True
    
    if not user_data:
        return False
    
    user_role = user_data.get("role")
    
    # Admin has access to everything
    if user_role == "admin":
        return True
    
    # Check specific route permissions
    for route_pattern, permissions in PROTECTED_ROUTES.items():
        if path.startswith(route_pattern):
            if isinstance(permissions, dict):
                method_roles = permissions.get(method, permissions.get("GET", []))
                return user_role in method_roles
            return user_role in permissions
    
    return True

async def proxy_request(service_name: str, path: str, method: str, request: Request):
    """Enhanced proxy request with authentication"""
    service_url = SERVICES.get(service_name)
    if not service_url:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")
    
    # Check authentication for protected routes
    auth_header = request.headers.get("Authorization")
    user_data = None
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            user_data = verify_token(token)
        except HTTPException:
            pass
    
    # Check permissions for protected routes
    if not check_route_permission(path, method, user_data):
        if not user_data:
            raise HTTPException(status_code=401, detail="Authentication required")
        else:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    
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
        "message": "Enhanced Airline System API Gateway v3.0",
        "status": "active",
        "services": list(SERVICES.keys()),
        "features": ["authentication", "authorization", "role_based_access"],
        "endpoints": {
            "auth": "/api/v1/auth/*",
            "users": "/api/v1/users",
            "flights": "/api/v1/flights",
            "passengers": "/api/v1/passengers",
            "reservations": "/api/v1/reservations",
            "health": "/health"
        }
    }

# ============================================================================
# RUTAS PROXY PARA MICROSERVICIOS CON AUTENTICACIÓN
# ============================================================================

# Authentication routes (User Service)
@app.api_route("/api/v1/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def auth_proxy(path: str, request: Request):
    full_path = f"/api/v1/auth/{path}" if path else "/api/v1/auth"
    return await proxy_request("user", full_path, request.method, request)

@app.api_route("/api/v1/auth/login", methods=["POST"])
async def auth_login_proxy(request: Request):
    return await proxy_request("user", "/api/v1/auth/login", request.method, request)

@app.api_route("/api/v1/auth/logout", methods=["POST"])
async def auth_logout_proxy(request: Request):
    return await proxy_request("user", "/api/v1/auth/logout", request.method, request)

@app.api_route("/api/v1/auth/me", methods=["GET"])
async def auth_me_proxy(request: Request):
    return await proxy_request("user", "/api/v1/auth/me", request.method, request)

# User management routes (User Service)
@app.api_route("/api/v1/users/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def user_proxy(path: str, request: Request):
    full_path = f"/api/v1/users/{path}" if path else "/api/v1/users"
    return await proxy_request("user", full_path, request.method, request)

@app.api_route("/api/v1/users", methods=["GET", "POST"])
async def user_proxy_root(request: Request):
    return await proxy_request("user", "/api/v1/users", request.method, request)

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


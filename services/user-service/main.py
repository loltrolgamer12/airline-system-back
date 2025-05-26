from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, Column, String, DateTime, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import os
import time
import jwt
import bcrypt
from enum import Enum

# Configuración
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres123")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "airline")

JWT_SECRET = os.getenv("JWT_SECRET", "airline-secret-key-2025")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

print(f"👤 User Service conectando a: {POSTGRES_HOST}:{POSTGRES_PORT}")

def create_engine_with_retry(database_url, max_retries=10, retry_delay=3):
    retries = 0
    while retries < max_retries:
        try:
            print(f"📡 User Service - Conexión {retries + 1}/{max_retries}...")
            engine = create_engine(database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("✅ User Service conectado a PostgreSQL")
            return engine
        except Exception as e:
            retries += 1
            print(f"❌ Error conectando (intento {retries}): {e}")
            if retries < max_retries:
                time.sleep(retry_delay)
            else:
                raise e

engine = create_engine_with_retry(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    AGENT = "agent"
    PASSENGER = "passenger"

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(100), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default=UserRole.PASSENGER.value)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

print("🏗️ Creando tablas de usuarios...")
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Tablas de usuarios creadas")
except Exception as e:
    print(f"❌ Error creando tablas: {e}")

# Schemas
class UserLogin(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse

# Security
security = HTTPBearer()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(user_data: dict) -> str:
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub": user_data["id"],
        "email": user_data["email"],
        "name": user_data["name"],
        "role": user_data["role"],
        "exp": expire
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(token_data: dict = Depends(verify_token), db: Session = Depends(lambda: SessionLocal())):
    user = db.query(User).filter(User.id == token_data["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI App
app = FastAPI(title="User Authentication Service", version="1.0.0")

@app.get("/health")
def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {
            "status": "healthy",
            "service": "user-service",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "user-service",
            "database": "disconnected",
            "error": str(e)
        }

@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Create token
    user_data = {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role
    }
    
    access_token = create_access_token(user_data)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=JWT_EXPIRE_HOURS * 3600,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login
        )
    )

@app.post("/api/v1/auth/logout")
def logout(current_user: User = Depends(get_current_user)):
    return {"message": "Logged out successfully"}

@app.get("/api/v1/auth/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )

@app.get("/api/v1/users", response_model=List[UserResponse])
def get_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    users = db.query(User).offset(skip).limit(limit).all()
    return [UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login
    ) for user in users]

@app.post("/api/v1/users", response_model=UserResponse, status_code=201)
def create_user(
    user_data: UserCreate, 
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    # Check if user exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    
    # Create new user
    db_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        name=user_data.name,
        role=user_data.role.value
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse(
        id=str(db_user.id),
        email=db_user.email,
        name=db_user.name,
        role=db_user.role,
        is_active=db_user.is_active,
        created_at=db_user.created_at,
        last_login=db_user.last_login
    )

@app.put("/api/v1/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        if key == "role" and value:
            setattr(user, key, value.value)
        else:
            setattr(user, key, value)
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login
    )

@app.delete("/api/v1/users/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()

@app.get("/")
def root():
    return {
        "message": "User Authentication Service",
        "status": "active",
        "version": "1.0.0",
        "features": ["JWT_auth", "role_management", "user_CRUD"]
    }

def create_default_admin():
    print("👤 Creando usuario administrador por defecto...")
    db = SessionLocal()
    try:
        admin_count = db.query(User).filter(User.role == UserRole.ADMIN.value).count()
        if admin_count == 0:
            admin_user = User(
                email="admin@aeroadmin.com",
                password_hash=hash_password("admin123"),
                name="Administrador Principal",
                role=UserRole.ADMIN.value
            )
            
            # Crear otros usuarios de prueba
            operator_user = User(
                email="operador@aeroadmin.com",
                password_hash=hash_password("operador123"),
                name="Operador de Vuelos",
                role=UserRole.OPERATOR.value
            )
            
            agent_user = User(
                email="agente@aeroadmin.com",
                password_hash=hash_password("agente123"),
                name="Agente de Reservas",
                role=UserRole.AGENT.value
            )
            
            db.add_all([admin_user, operator_user, agent_user])
            db.commit()
            print("✅ Usuarios por defecto creados")
        else:
            print(f"ℹ️ Ya existen {admin_count} administradores")
    except Exception as e:
        print(f"❌ Error creando usuarios por defecto: {e}")
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    create_default_admin()


@app.post("/api/v1/auth/register", response_model=UserResponse, status_code=201)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Endpoint público para registro de usuarios (solo pasajeros)"""
    # Verificar si ya existe
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    
    # Solo permitir registro como pasajero
    if user_data.role != UserRole.PASSENGER:
        user_data.role = UserRole.PASSENGER
    
    # Crear nuevo usuario
    db_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        name=user_data.name,
        role=user_data.role.value
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse(
        id=str(db_user.id),
        email=db_user.email,
        name=db_user.name,
        role=db_user.role,
        is_active=db_user.is_active,
        created_at=db_user.created_at,
        last_login=db_user.last_login
    )

if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando User Authentication Service...")
    uvicorn.run(app, host="0.0.0.0", port=8000)


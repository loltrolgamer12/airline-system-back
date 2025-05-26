# ========================================
# SCRIPT COMPLETO - CONFIGURACIÓN AUTOMÁTICA DEL BACKEND (CORREGIDO)
# ========================================

# setup-backend.ps1 - Configuración automática del Backend
param(
    [switch]$Force,
    [switch]$SkipDocker,
    [switch]$Clean,
    [switch]$Verbose
)

# Configuración de colores
$Host.UI.RawUI.WindowTitle = "🛫 Airline System - Backend Setup"

function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    else {
        $input | Write-Output
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Write-Success { Write-ColorOutput Green $args }
function Write-Warning { Write-ColorOutput Yellow $args }
function Write-Error { Write-ColorOutput Red $args }
function Write-Info { Write-ColorOutput Cyan $args }
function Write-Debug { if ($Verbose) { Write-ColorOutput Magenta $args } }

# Variables globales
$global:DockerComposeCmd = "docker compose"

# Función para verificar si Docker está corriendo
function Test-Docker {
    try {
        $dockerInfo = docker info 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Docker está corriendo"
            return $true
        }
        else {
            Write-Error "❌ Docker no está corriendo"
            Write-Info "💡 Por favor, inicia Docker Desktop y vuelve a ejecutar este script"
            return $false
        }
    }
    catch {
        Write-Error "❌ Docker no está instalado o no está disponible"
        Write-Info "💡 Instala Docker Desktop desde https://docker.com/products/docker-desktop"
        return $false
    }
}

# Función para verificar Docker Compose
function Test-DockerCompose {
    try {
        docker compose version 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✅ Docker Compose (v2) disponible"
            $global:DockerComposeCmd = "docker compose"
            return $true
        }
        else {
            Write-Warning "⚠️ Probando con 'docker-compose'..."
            docker-compose --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Success "✅ Docker Compose (v1) disponible"
                $global:DockerComposeCmd = "docker-compose"
                return $true
            }
        }
    }
    catch {
        Write-Error "❌ Docker Compose no está disponible"
        return $false
    }
}

# Función para crear archivos de configuración necesarios
function Create-ConfigFiles {
    Write-Info "📄 Creando archivos de configuración..."
    
    # Crear .env si no existe
    if (-not (Test-Path ".env")) {
        Write-Info "📝 Creando archivo .env..."
        @"
# Configuración del Backend
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=airline

RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

JWT_SECRET=airline-secret-key-2025
JWT_ALGORITHM=HS256
JWT_EXPIRES_IN=86400

# URLs de servicios
FLIGHT_SERVICE_URL=http://flight-service:8000
PASSENGER_SERVICE_URL=http://passenger-service:8000
RESERVATION_SERVICE_URL=http://reservation-service:8000
USER_SERVICE_URL=http://user-service:8000
"@ | Out-File -FilePath ".env" -Encoding UTF8
        Write-Success "✅ Archivo .env creado"
    }
    
    # Crear healthcheck script con sintaxis corregida
    if (-not (Test-Path "healthcheck.ps1")) {
        Write-Info "📝 Creando script de diagnóstico..."
        
        # Crear contenido del script de diagnóstico por separado para evitar problemas de escape
        $healthcheckContent = @'
# healthcheck.ps1 - Script de diagnóstico
param([switch]$Detailed)

function Test-ServiceHealth {
    param([string]$Name, [string]$Url, [int]$Port)
    
    try {
        $response = Invoke-RestMethod -Uri $Url -TimeoutSec 5 -ErrorAction Stop
        Write-Host "✅ $Name está funcionando" -ForegroundColor Green
        if ($Detailed) {
            Write-Host "   URL: $Url" -ForegroundColor Gray
            Write-Host "   Status: $($response.status)" -ForegroundColor Gray
        }
        return $true
    }
    catch {
        Write-Host "❌ $Name no responde" -ForegroundColor Red
        if ($Detailed) {
            Write-Host "   URL: $Url" -ForegroundColor Gray
            Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
        }
        return $false
    }
}

Write-Host "🔍 DIAGNÓSTICO DEL SISTEMA" -ForegroundColor Cyan
Write-Host "============================" -ForegroundColor Cyan

$services = @(
    @{Name="API Gateway"; Url="http://localhost:8000/health"},
    @{Name="User Service"; Url="http://localhost:8004/health"},
    @{Name="Flight Service"; Url="http://localhost:8001/health"},
    @{Name="Passenger Service"; Url="http://localhost:8002/health"},
    @{Name="Reservation Service"; Url="http://localhost:8003/health"},
    @{Name="Monitoring"; Url="http://localhost:9090"}
)

$healthyCount = 0
foreach ($service in $services) {
    if (Test-ServiceHealth -Name $service.Name -Url $service.Url) {
        $healthyCount++
    }
}

$totalServices = $services.Count
$statusColor = if ($healthyCount -eq $totalServices) { "Green" } else { "Yellow" }
Write-Host "`n📊 Resumen: $healthyCount/$totalServices servicios funcionando" -ForegroundColor $statusColor

if ($healthyCount -lt $totalServices) {
    Write-Host "`n💡 Soluciones sugeridas:" -ForegroundColor Yellow
    Write-Host "  • Verificar que Docker esté corriendo: docker ps"
    Write-Host "  • Ver logs: docker compose logs -f"
    Write-Host "  • Reiniciar servicios: docker compose restart"
}
'@
        
        Set-Content -Path "healthcheck.ps1" -Value $healthcheckContent -Encoding UTF8
        Write-Success "✅ Script de diagnóstico creado"
    }
    
    # Crear script de documentación de API
    if (-not (Test-Path "api-docs.ps1")) {
        Write-Info "📝 Creando script de documentación de API..."
        
        $apiDocsContent = @'
# api-docs.ps1 - Generador de documentación de API
param([switch]$Export)

Write-Host "📚 DOCUMENTACIÓN DE LA API - SISTEMA DE AEROLÍNEAS" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

$apiInfo = @{
    "Gateway" = @{
        "URL" = "http://localhost:8000"
        "Docs" = "http://localhost:8000/docs"
        "Health" = "http://localhost:8000/health"
    }
    "Servicios" = @{
        "User Service" = "http://localhost:8004"
        "Flight Service" = "http://localhost:8001"
        "Passenger Service" = "http://localhost:8002"
        "Reservation Service" = "http://localhost:8003"
    }
    "Infraestructura" = @{
        "PostgreSQL" = "localhost:5432"
        "RabbitMQ" = "localhost:5672"
        "RabbitMQ Admin" = "http://localhost:15672"
        "Monitoring" = "http://localhost:9090"
    }
}

foreach ($category in $apiInfo.Keys) {
    Write-Host "`n🔹 $category" -ForegroundColor Green
    foreach ($service in $apiInfo[$category].Keys) {
        $url = $apiInfo[$category][$service]
        Write-Host "  • $service : $url" -ForegroundColor White
    }
}

Write-Host "`n🔑 CREDENCIALES DE PRUEBA:" -ForegroundColor Yellow
Write-Host "  • Administrador: admin@aeroadmin.com / admin123"
Write-Host "  • Operador: operador@aeroadmin.com / operador123"
Write-Host "  • Agente: agente@aeroadmin.com / agente123"

Write-Host "`n📖 ENDPOINTS PRINCIPALES:" -ForegroundColor Magenta
$endpoints = @(
    "POST /api/v1/auth/login - Autenticación",
    "POST /api/v1/auth/register - Registro",
    "GET  /api/v1/auth/me - Perfil del usuario",
    "GET  /api/v1/flights - Listar vuelos",
    "POST /api/v1/flights - Crear vuelo",
    "GET  /api/v1/passengers - Listar pasajeros",
    "POST /api/v1/passengers - Crear pasajero",
    "GET  /api/v1/reservations - Listar reservas",
    "POST /api/v1/reservations - Crear reserva"
)

foreach ($endpoint in $endpoints) {
    Write-Host "  • $endpoint" -ForegroundColor White
}

if ($Export) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $exportFile = "api-documentation-$timestamp.txt"
    $this | Out-File -FilePath $exportFile
    Write-Host "`n💾 Documentación exportada a: $exportFile" -ForegroundColor Green
}
'@
        
        Set-Content -Path "api-docs.ps1" -Value $apiDocsContent -Encoding UTF8
        Write-Success "✅ Script de documentación de API creado"
    }
}

# Función para aplicar correcciones al código
function Apply-BackendFixes {
    Write-Info "🔧 Aplicando correcciones al backend..."
    
    # Corregir user-service/main.py - Agregar endpoint de registro
    $userServicePath = "services/user-service/main.py"
    if (Test-Path $userServicePath) {
        $content = Get-Content $userServicePath -Raw
        
        if ($content -notmatch "auth/register") {
            Write-Info "📝 Agregando endpoint de registro al user-service..."
            
            $registerEndpoint = @'

@app.post("/api/v1/auth/register", response_model=UserResponse, status_code=201)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Endpoint público para registro de usuarios (solo pasajeros)"""
    # Verificar si ya existe
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    
    # Solo permitir registro como pasajero para endpoint público
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
'@
            
            # Insertar antes de la función main
            $content = $content -replace "if __name__ == `"__main__`":", "$registerEndpoint`n`nif __name__ == `"__main__`":"
            Set-Content $userServicePath -Value $content -Encoding UTF8
            Write-Success "✅ Endpoint de registro agregado al user-service"
        }
    }
    
    # Corregir api-gateway/main.py - Agregar ruta de registro
    $gatewayPath = "api-gateway/main.py"
    if (Test-Path $gatewayPath) {
        $content = Get-Content $gatewayPath -Raw
        
        if ($content -notmatch "auth/register.*proxy") {
            Write-Info "📝 Agregando ruta de registro al API Gateway..."
            
            $registerRoute = @'

@app.api_route("/api/v1/auth/register", methods=["POST"])
async def auth_register_proxy(request: Request):
    """Proxy para registro de usuarios"""
    return await proxy_request("user", "/api/v1/auth/register", request.method, request)
'@
            
            # Insertar después de las otras rutas de auth
            $insertPoint = $content.IndexOf("@app.api_route(`"/api/v1/auth/me`", methods=[`"GET`"])")
            if ($insertPoint -gt 0) {
                $content = $content.Insert($insertPoint, $registerRoute + "`n`n")
                Set-Content $gatewayPath -Value $content -Encoding UTF8
                Write-Success "✅ Ruta de registro agregada al API Gateway"
            }
        }
    }
    
    # Verificar y corregir CORS en API Gateway
    $content = Get-Content $gatewayPath -Raw
    if ($content -notmatch "http://localhost:3000") {
        Write-Info "📝 Actualizando configuración CORS..."
        $content = $content -replace "allow_origins=\[([^\]]+)\]", 'allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "*"]'
        Set-Content $gatewayPath -Value $content -Encoding UTF8
        Write-Success "✅ CORS actualizado para frontend"
    }
    
    # Agregar middleware de logging mejorado
    $loggingMiddleware = @'

# Middleware de logging mejorado
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Log de request
    logger.info(f"🔍 {request.method} {request.url.path} - IP: {request.client.host}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log de response
        status_emoji = "✅" if response.status_code < 400 else "❌"
        logger.info(f"{status_emoji} {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
        
        response.headers["X-Process-Time"] = str(process_time)
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"💥 {request.method} {request.url.path} - ERROR - {process_time:.3f}s: {str(e)}")
        raise
'@
    
    if ($content -notmatch "logging_middleware") {
        $content = $content -replace "import uvicorn", "import uvicorn`nimport time"
        $content = $content -replace "app = FastAPI\(", "$loggingMiddleware`n`napp = FastAPI("
        Set-Content $gatewayPath -Value $content -Encoding UTF8
        Write-Success "✅ Middleware de logging agregado"
    }
}

# Función para limpiar Docker
function Clean-Docker {
    if ($Clean -or $Force) {
        Write-Warning "🧹 Limpiando contenedores y volúmenes Docker..."
        
        # Detener y eliminar contenedores
        docker compose down --remove-orphans --volumes 2>$null
        
        # Limpiar imágenes no utilizadas
        docker system prune -f 2>$null
        
        # Limpiar volúmenes no utilizados
        docker volume prune -f 2>$null
        
        Write-Success "✅ Limpieza completada"
    }
}

# Función para iniciar servicios Docker
function Start-DockerServices {
    Write-Info "🐳 Iniciando servicios Docker..."
    
    # Usar docker-compose.working.yml si existe
    if (Test-Path "docker-compose.working.yml") {
        Write-Info "📄 Usando docker-compose.working.yml"
        Copy-Item "docker-compose.working.yml" "docker-compose.yml" -Force
    }
    
    # Detener servicios existentes
    Write-Info "🛑 Deteniendo servicios existentes..."
    docker compose down --remove-orphans 2>$null
    
    # Construir e iniciar servicios
    Write-Info "🔨 Construyendo e iniciando servicios..."
    Write-Debug "Ejecutando: docker compose up -d --build"
    
    $startTime = Get-Date
    docker compose up -d --build
    $endTime = Get-Date
    $duration = ($endTime - $startTime).TotalSeconds
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "✅ Servicios Docker iniciados correctamente en $([math]::Round($duration, 1)) segundos"
        return $true
    }
    else {
        Write-Error "❌ Error al iniciar servicios Docker"
        Write-Info "💡 Ver logs con: docker compose logs"
        return $false
    }
}

# Función para verificar servicios con reintentos inteligentes
function Test-Services {
    Write-Info "🔍 Verificando servicios..."
    
    $services = @(
        @{Name="API Gateway"; URL="http://localhost:8000/health"; Critical=$true},
        @{Name="User Service"; URL="http://localhost:8004/health"; Critical=$true},
        @{Name="Flight Service"; URL="http://localhost:8001/health"; Critical=$true},
        @{Name="Passenger Service"; URL="http://localhost:8002/health"; Critical=$true},
        @{Name="Reservation Service"; URL="http://localhost:8003/health"; Critical=$true},
        @{Name="Monitoring"; URL="http://localhost:9090"; Critical=$false}
    )
    
    $maxAttempts = 15
    $attempt = 1
    $allCriticalHealthy = $false
    
    while ($attempt -le $maxAttempts -and -not $allCriticalHealthy) {
        Write-Info "🔄 Verificación $attempt/$maxAttempts..."
        $healthyCount = 0
        $criticalHealthyCount = 0
        
        foreach ($service in $services) {
            try {
                $response = Invoke-RestMethod -Uri $service.URL -TimeoutSec 3 -ErrorAction Stop
                Write-Success "✅ $($service.Name) está funcionando"
                $healthyCount++
                if ($service.Critical) { $criticalHealthyCount++ }
            }
            catch {
                if ($service.Critical) {
                    Write-Warning "⏳ $($service.Name) aún no está listo..."
                } else {
                    Write-Debug "⚠️ $($service.Name) no está disponible (no crítico)"
                }
            }
        }
        
        $criticalServices = ($services | Where-Object {$_.Critical}).Count
        if ($criticalHealthyCount -eq $criticalServices) {
            $allCriticalHealthy = $true
            Write-Success "🎉 ¡Todos los servicios críticos están funcionando!"
            if ($healthyCount -lt $services.Count) {
                Write-Warning "⚠️ Algunos servicios no críticos aún no están listos"
            }
        }
        else {
            if ($attempt -lt $maxAttempts) {
                $waitTime = [math]::Min(10, $attempt * 2)  # Aumentar tiempo de espera gradualmente
                Write-Info "⏳ Esperando $waitTime segundos antes del siguiente intento... ($criticalHealthyCount/$criticalServices servicios críticos listos)"
                Start-Sleep -Seconds $waitTime
            }
            $attempt++
        }
    }
    
    return $allCriticalHealthy
}

# Función para probar autenticación completa
function Test-Authentication {
    Write-Info "🔐 Probando autenticación completa..."
    
    $testUsers = @(
        @{Email="admin@aeroadmin.com"; Password="admin123"; Role="admin"},
        @{Email="operador@aeroadmin.com"; Password="operador123"; Role="operator"},
        @{Email="agente@aeroadmin.com"; Password="agente123"; Role="agent"}
    )
    
    $successCount = 0
    
    foreach ($user in $testUsers) {
        try {
            $loginData = @{
                email = $user.Email
                password = $user.Password
            } | ConvertTo-Json
            
            $response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" -Method Post -Body $loginData -ContentType "application/json" -TimeoutSec 10
            
            if ($response.access_token) {
                Write-Success "✅ Login exitoso - $($response.user.name) ($($response.user.role))"
                
                # Probar endpoint protegido
                $headers = @{
                    "Authorization" = "Bearer $($response.access_token)"
                    "Content-Type" = "application/json"
                }
                
                $userResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/me" -Headers $headers -TimeoutSec 5
                Write-Debug "Endpoint /auth/me funcionando para $($user.Role)"
                $successCount++
            }
        }
        catch {
            Write-Warning "⚠️ Error autenticando usuario $($user.Role): $($_.Exception.Message)"
        }
    }
    
    if ($successCount -gt 0) {
        Write-Success "✅ Autenticación funcionando ($successCount/$($testUsers.Count) usuarios probados)"
        return $true
    } else {
        Write-Error "❌ Error en sistema de autenticación"
        return $false
    }
}

# Función para probar endpoints de la API
function Test-ApiEndpoints {
    Write-Info "🔌 Probando endpoints principales..."
    
    $endpoints = @(
        @{Name="Health Check"; URL="http://localhost:8000/health"; Method="GET"},
        @{Name="Flights List"; URL="http://localhost:8000/api/v1/flights"; Method="GET"},
        @{Name="Passengers List"; URL="http://localhost:8000/api/v1/passengers"; Method="GET"},
        @{Name="Reservations List"; URL="http://localhost:8000/api/v1/reservations"; Method="GET"}
    )
    
    $successCount = 0
    
    foreach ($endpoint in $endpoints) {
        try {
            $response = Invoke-RestMethod -Uri $endpoint.URL -Method $endpoint.Method -TimeoutSec 5
            Write-Success "✅ $($endpoint.Name) responde correctamente"
            $successCount++
        }
        catch {
            Write-Warning "⚠️ $($endpoint.Name) no responde: $($_.Exception.Message)"
        }
    }
    
    Write-Info "📊 Endpoints funcionando: $successCount/$($endpoints.Count)"
    return $successCount -ge ($endpoints.Count * 0.8)  # 80% de éxito mínimo
}

# Función para generar documentación automática
function Generate-Documentation {
    Write-Info "📚 Generando documentación automática..."
    
    $docContent = @"
# DOCUMENTACIÓN DEL SISTEMA DE AEROLÍNEAS

## Arquitectura de Microservicios

### Servicios Principales:
- **API Gateway** (Puerto 8000): Punto de entrada único, manejo de autenticación y enrutamiento
- **User Service** (Puerto 8004): Gestión de usuarios y autenticación JWT
- **Flight Service** (Puerto 8001): Gestión de vuelos y horarios
- **Passenger Service** (Puerto 8002): Gestión de información de pasajeros
- **Reservation Service** (Puerto 8003): Gestión de reservas y asignación de asientos

### Infraestructura:
- **PostgreSQL** (Puerto 5432): Base de datos principal
- **RabbitMQ** (Puerto 5672): Comunicación asíncrona entre servicios
- **Monitoring** (Puerto 9090): Dashboard de monitoreo

## Patrones Implementados:
- **API Gateway Pattern**: Punto de entrada único
- **Database per Service**: Cada servicio tiene su esquema
- **Circuit Breaker**: Tolerancia a fallos en Reservation Service
- **Event-Driven Architecture**: Comunicación asíncrona con RabbitMQ
- **JWT Authentication**: Autenticación stateless
- **Health Checks**: Monitoreo de servicios

## Endpoints Principales:

### Autenticación:
- POST /api/v1/auth/login - Iniciar sesión
- POST /api/v1/auth/register - Registro de usuarios
- GET /api/v1/auth/me - Perfil del usuario actual

### Vuelos:
- GET /api/v1/flights - Listar vuelos (con filtros)
- POST /api/v1/flights - Crear vuelo (admin/operator)
- GET /api/v1/flights/{flight_number} - Detalles de vuelo
- PUT /api/v1/flights/{flight_number} - Actualizar vuelo

### Pasajeros:
- GET /api/v1/passengers - Listar pasajeros
- POST /api/v1/passengers - Crear pasajero
- GET /api/v1/passengers/{identification} - Detalles de pasajero

### Reservas:
- GET /api/v1/reservations - Listar reservas
- POST /api/v1/reservations - Crear reserva
- GET /api/v1/reservations/{reservation_code} - Detalles de reserva

## Credenciales de Prueba:
- **Administrador**: admin@aeroadmin.com / admin123
- **Operador**: operador@aeroadmin.com / operador123
- **Agente**: agente@aeroadmin.com / agente123

## Comandos de Mantenimiento:
- ``docker compose ps`` - Ver estado de servicios
- ``docker compose logs -f [servicio]`` - Ver logs
- ``.\healthcheck.ps1`` - Diagnóstico del sistema
- ``.\api-docs.ps1`` - Ver documentación de API

Generado automáticamente el $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
"@
    
    Set-Content -Path "README-Backend.md" -Value $docContent -Encoding UTF8
    Write-Success "✅ Documentación generada en README-Backend.md"
}

# Función para mostrar información del sistema
function Show-SystemInfo {
    Write-Info "📊 INFORMACIÓN DEL SISTEMA"
    Write-Info "=" * 50
    
    Write-Success "🌐 URLs de acceso:"
    Write-Output "  • API Gateway:      http://localhost:8000"
    Write-Output "  • API Docs:         http://localhost:8000/docs"
    Write-Output "  • Health Check:     http://localhost:8000/health"
    Write-Output "  • Monitoring:       http://localhost:9090"
    Write-Output "  • RabbitMQ Admin:   http://localhost:15672 (guest/guest)"
    Write-Output "  • PostgreSQL:       localhost:5432 (postgres/postgres123)"
    
    Write-Success "`n🔑 Credenciales de prueba:"
    Write-Output "  • Admin:            admin@aeroadmin.com / admin123"
    Write-Output "  • Operador:         operador@aeroadmin.com / operador123"
    Write-Output "  • Agente:           agente@aeroadmin.com / agente123"
    
    Write-Success "`n🐳 Comandos útiles de Docker:"
    Write-Output "  • Ver estado:       docker compose ps"
    Write-Output "  • Ver logs:         docker compose logs -f"
    Write-Output "  • Ver logs específico: docker compose logs -f [servicio]"
    Write-Output "  • Reiniciar:        docker compose restart"
    Write-Output "  • Detener todo:     docker compose down"
    Write-Output "  • Reconstruir:      docker compose up -d --build"
    
    Write-Success "`n🔧 Scripts de mantenimiento:"
    Write-Output "  • Diagnóstico:      .\healthcheck.ps1"
    Write-Output "  • Diagnóstico detallado: .\healthcheck.ps1 -Detailed"
    Write-Output "  • Documentación API: .\api-docs.ps1"
    Write-Output "  • Reconfigurar:     .\setup-backend.ps1 -Force"
    Write-Output "  • Limpiar todo:     .\setup-backend.ps1 -Clean"
    
    Write-Success "`n📱 Próximos pasos:"
    Write-Output "  1. El backend está listo para recibir conexiones del frontend"
    Write-Output "  2. Configura el frontend para usar http://localhost:8000 como API_URL"
    Write-Output "  3. Prueba la autenticación con las credenciales proporcionadas"
    Write-Output "  4. Usa el script de diagnóstico para verificar el estado regularmente"
}

# Función para mostrar logs en tiempo real
function Show-LiveLogs {
    Write-Info "📋 Mostrando logs en tiempo real (Ctrl+C para salir)..."
    docker compose logs -f
}

# Función principal
function Main {
    $startTime = Get-Date
    
    Write-Info "🛫 CONFIGURACIÓN AUTOMÁTICA DEL BACKEND - AIRLINE SYSTEM"
    Write-Info "=" * 60
    Write-Info "Iniciado: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    
    # Verificar directorio
    if (-not (Test-Path "docker-compose.yml") -and -not (Test-Path "docker-compose.working.yml")) {
        Write-Error "❌ No se encontró docker-compose.yml en el directorio actual"
        Write-Info "📁 Por favor, ejecuta este script desde la carpeta del backend:"
        Write-Info "   cd loltrolgamer12-airline-system-back"
        Write-Info "   .\setup-backend.ps1"
        exit 1
    }
    
    Write-Success "✅ Directorio correcto detectado"
    
    # Verificar Docker
    if (-not $SkipDocker) {
        if (-not (Test-Docker)) {
            exit 1
        }
        
        if (-not (Test-DockerCompose)) {
            Write-Error "❌ Docker Compose no está disponible"
            Write-Info "💡 Instala Docker Desktop que incluye Docker Compose"
            exit 1
        }
    }
    
    # Crear archivos de configuración
    Create-ConfigFiles
    
    # Limpiar si se solicita
    Clean-Docker
    
    # Aplicar correcciones
    Apply-BackendFixes
    
    # Generar documentación
    Generate-Documentation
    
    # Iniciar servicios Docker
    if (-not $SkipDocker) {
        if (-not (Start-DockerServices)) {
            Write-Error "❌ Error al iniciar los servicios"
            Write-Info "💡 Revisa los logs con: docker compose logs"
            exit 1
        }
        
        # Verificar servicios
        Write-Info "⏳ Esperando que los servicios estén listos (puede tomar 1-3 minutos)..."
        Start-Sleep -Seconds 20
        
        if (Test-Services) {
            Write-Success "`n🎉 ¡Servicios iniciados correctamente!"
            
            # Probar autenticación
            if (Test-Authentication) {
                Write-Success "🔐 Sistema de autenticación verificado"
            }
            
            # Probar endpoints principales
            if (Test-ApiEndpoints) {
                Write-Success "🔌 Endpoints principales verificados"
            }
            
            # Mostrar información
            Show-SystemInfo
            
            $endTime = Get-Date
            $totalTime = ($endTime - $startTime).TotalMinutes
            Write-Success "`n✅ ¡CONFIGURACIÓN COMPLETADA EN $([math]::Round($totalTime, 1)) MINUTOS!"
            Write-Success "🚀 El backend está listo para conectar con el frontend"
            
        }
        else {
            Write-Warning "⚠️ Algunos servicios pueden tardar más en iniciarse"
            Write-Info "💡 Usa el script de diagnóstico para verificar: .\healthcheck.ps1"
            Write-Info "💡 Ver logs: docker compose logs -f"
        }
    }
    else {
        Write-Success "✅ Correcciones aplicadas. Inicia Docker manualmente con:"
        Write-Info "docker compose up -d --build"
    }
}

# Manejo de errores
trap {
    Write-Error "❌ Error inesperado: $($_.Exception.Message)"
    Write-Info "🔍 Información de debug:"
    Write-Info "  - Línea: $($_.InvocationInfo.ScriptLineNumber)"
    Write-Info "  - Comando: $($_.InvocationInfo.Line.Trim())"
    Write-Info "`n💡 Soluciones sugeridas:"
    Write-Info "  - Ejecutar con parámetro -Force: .\setup-backend.ps1 -Force"
    Write-Info "  - Ejecutar con parámetro -Clean: .\setup-backend.ps1 -Clean"
    Write-Info "  - Verificar que Docker Desktop esté corriendo"
    Write-Info "  - Verificar puertos disponibles (8000-8004, 5432, 5672, 15672)"
    exit 1
}

# Ejecutar función principal
Main

# Preguntar si mostrar logs
if (-not $SkipDocker -and -not $Verbose) {
    $showLogs = Read-Host "`n¿Deseas ver los logs en tiempo real? (y/N)"
    if ($showLogs -eq 'y' -or $showLogs -eq 'Y') {
        Show-LiveLogs
    }
}
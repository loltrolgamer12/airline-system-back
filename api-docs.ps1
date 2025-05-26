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

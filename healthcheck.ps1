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

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
- `docker compose ps` - Ver estado de servicios
- `docker compose logs -f [servicio]` - Ver logs
- `.\healthcheck.ps1` - Diagnóstico del sistema
- `.\api-docs.ps1` - Ver documentación de API

Generado automáticamente el 2025-05-26 02:11:27

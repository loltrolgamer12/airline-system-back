-- Crear extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Crear esquemas para cada servicio si es necesario
CREATE SCHEMA IF NOT EXISTS flights;
CREATE SCHEMA IF NOT EXISTS passengers;
CREATE SCHEMA IF NOT EXISTS reservations;
CREATE SCHEMA IF NOT EXISTS crew;

-- Otorgar permisos al usuario de la aplicación
GRANT ALL PRIVILEGES ON SCHEMA flights TO admin_airline;
GRANT ALL PRIVILEGES ON SCHEMA passengers TO admin_airline;
GRANT ALL PRIVILEGES ON SCHEMA reservations TO admin_airline;
GRANT ALL PRIVILEGES ON SCHEMA crew TO admin_airline;

-- Mensaje de confirmación
SELECT 'Base de datos inicializada correctamente' as status;

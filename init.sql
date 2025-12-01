CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    usuario VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    contrasena VARCHAR(255) NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS predicciones (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    aerolinea VARCHAR(100) NOT NULL,
    origen VARCHAR(10) NOT NULL,
    destino VARCHAR(10) NOT NULL,
    fecha_viaje DATE NOT NULL,
    hora_salida VARCHAR(10) NOT NULL,
    duracion FLOAT NOT NULL,
    escalas INTEGER NOT NULL,
    informacion VARCHAR(100) NOT NULL,
    precio_predicho FLOAT NOT NULL,
    fecha_prediccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

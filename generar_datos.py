import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

def generar_datos_vuelos_peru(cantidad=10000):
    """
    Genera datos simulados pero realistas de vuelos nacionales en Perú 🇵🇪
    """

    # ✈️ Aerolíneas nacionales más comunes
    aerolineas = [
        'LATAM Perú', 'Sky Airline Perú', 'JetSMART Perú',
        'VIVA Air Perú', 'Avianca Perú'
    ]
    
    # 🏙️ Principales aeropuertos del Perú (códigos IATA)
    ciudades = {
        'LIM': 'Lima',
        'AQP': 'Arequipa',
        'CUZ': 'Cusco',
        'TRU': 'Trujillo',
        'PIU': 'Piura',
        'IQT': 'Iquitos',
        'TCQ': 'Tacna',
        'JUL': 'Juliaca',
        'PCL': 'Pucallpa',
        'TPP': 'Tarapoto',
        'AYP': 'Ayacucho',
        'CIX': 'Chiclayo'
    }

    # 🍽️ Información adicional común en vuelos nacionales
    informacion = [
        'Solo equipaje de mano',
        'Incluye equipaje',
        'Asiento preferente',
        'Clase económica',
        'Clase business',
        'Incluye snack',
        'WiFi incluido',
        'Cancelación gratuita'
    ]

    datos = []
    fecha_inicio = datetime(2024, 1, 1)

    # ✈️ Rutas posibles (reales entre ciudades grandes)
    rutas_posibles = [
        ('LIM', 'AQP'), ('LIM', 'CUZ'), ('LIM', 'TRU'), ('LIM', 'PIU'), ('LIM', 'IQT'),
        ('LIM', 'TCQ'), ('LIM', 'JUL'), ('LIM', 'PCL'), ('LIM', 'TPP'), ('LIM', 'CIX'),
        ('CUZ', 'AQP'), ('CUZ', 'JUL'), ('TRU', 'PIU'), ('TRU', 'CIX'),
        ('AQP', 'TCQ'), ('AQP', 'JUL')
    ]

    for _ in range(cantidad):
        origen, destino = rutas_posibles[np.random.randint(0, len(rutas_posibles))]
        ruta = f"{origen}-{destino}"

        aerolinea = np.random.choice(aerolineas)
        info = np.random.choice(informacion)
        fecha = fecha_inicio + timedelta(days=np.random.randint(0, 365))

        hora_salida_h = np.random.randint(5, 22)
        hora_salida_m = np.random.choice([0, 15, 30, 45])
        hora_salida = f"{hora_salida_h:02d}:{hora_salida_m:02d}"

        duraciones_promedio = {
            'LIM-AQP': 1.3, 'LIM-CUZ': 1.2, 'LIM-TRU': 1.1, 'LIM-PIU': 1.5,
            'LIM-IQT': 1.9, 'LIM-TCQ': 1.6, 'LIM-JUL': 1.4, 'LIM-PCL': 1.2,
            'LIM-TPP': 1.4, 'LIM-CIX': 1.2, 'CUZ-AQP': 1.0, 'CUZ-JUL': 0.8,
            'TRU-PIU': 1.0, 'TRU-CIX': 0.8, 'AQP-TCQ': 0.9, 'AQP-JUL': 0.9
        }
        duracion = round(duraciones_promedio.get(ruta, np.random.uniform(1.0, 2.0)) + np.random.normal(0, 0.1), 1)

        escalas = np.random.choice([0, 0, 1], p=[0.85, 0.10, 0.05])

        hora_llegada_total = hora_salida_h + int(np.floor(duracion))
        hora_llegada_h = hora_llegada_total % 24
        hora_llegada_m = np.random.choice([0, 15, 30, 45])
        hora_llegada = f"{hora_llegada_h:02d}:{hora_llegada_m:02d}"

        precio_base = 150 + duracion * 80

        ajuste_aerolinea = {
            'LATAM Perú': 1.00,
            'Sky Airline Perú': 0.80,
            'JetSMART Perú': 0.75,
            'VIVA Air Perú': 0.70,
            'Avianca Perú': 0.95
        }
        precio_base *= ajuste_aerolinea[aerolinea]

        multiplicadores_info = {
            'Solo equipaje de mano': 0.85,
            'Incluye equipaje': 1.0,
            'Asiento preferente': 1.2,
            'Clase económica': 0.9,
            'Clase business': 2.3,
            'Incluye snack': 1.1,
            'WiFi incluido': 1.15,
            'Cancelación gratuita': 1.3
        }
        precio_base *= multiplicadores_info[info]

        dia_semana = fecha.weekday()
        if dia_semana in [4, 5, 6]:  # Viernes a domingo
            precio_base *= 1.2

        if fecha.month in [7, 12]:  # Temporada alta
            precio_base *= 1.25

        precio_final = max(120, round(precio_base + np.random.normal(0, 20), 2))

        datos.append({
            'Aerolínea': aerolinea,
            'Fecha_del_viaje': fecha.strftime('%Y-%m-%d'),
            'Origen': origen,
            'Destino': destino,
            'Ruta': ruta,
            'Hora_de_salida': hora_salida,
            'Hora_de_llegada': hora_llegada,
            'Duración': duracion,
            'Total_de_escalas': escalas,
            'Información_adicional': info,
            'Precio (S/)': precio_final
        })

    df = pd.DataFrame(datos)
    return df
def main():
    print("🇵🇪 Generando datos realistas de vuelos nacionales en Perú...")
    df = generar_datos_vuelos_peru(10000)
    archivo_excel = 'datos_vuelos.xlsx'
    df.to_excel(archivo_excel, index=False)
    print(f"✅ Datos guardados en: {archivo_excel}")

if __name__ == "__main__":
    main()


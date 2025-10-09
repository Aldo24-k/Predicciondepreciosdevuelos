import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file
from sklearn.preprocessing import StandardScaler, LabelEncoder
import joblib
import os
from datetime import datetime
import io

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# Variables globales para el modelo
modelo = None
scaler = None
label_encoders = None
features = None
datos_cache = None

def cargar_modelo():
    """Carga el modelo entrenado"""
    global modelo, scaler, label_encoders, features
    
    if os.path.exists('modelo_vuelos.pkl'):
        modelo = joblib.load('modelo_vuelos.pkl')
        scaler = joblib.load('scaler.pkl')
        label_encoders = joblib.load('label_encoders.pkl')
        features = joblib.load('features.pkl')
        return True
    return False

def cargar_datos_cache():
    """Carga los datos en caché"""
    global datos_cache
    
    if os.path.exists('datos_vuelos_peru.xlsx'):
        datos_cache = pd.read_excel('datos_vuelos_peru.xlsx')
    
    
    
    return datos_cache is not None

@app.route('/')
def index():
    """Página principal"""
    if modelo is None:
        return '''
        <html>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>⚠️ Modelo no cargado</h1>
                <p>Por favor ejecuta primero:</p>
                <code>python generar_datos.py</code><br>
                <code>python training.py</code>
            </body>
        </html>
        '''
    return render_template('index.html')

@app.route('/api/datos', methods=['GET'])
def obtener_datos():
    """Obtiene los datos únicos para los selectores"""
    if datos_cache is None:
        return jsonify({'error': 'Datos no disponibles'}), 500
    
    try:
        return jsonify({
            'aerolineas': sorted(datos_cache['Aerolínea'].unique().tolist()),
            'origenes': sorted(datos_cache['Origen'].unique().tolist()),
            'destinos': sorted(datos_cache['Destino'].unique().tolist()),
            'duraciones': sorted(datos_cache['Duración'].unique().tolist()),
            'escalas': sorted(datos_cache['Total_de_escalas'].unique().tolist()),
            'informaciones': sorted(datos_cache['Información_adicional'].unique().tolist())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/predecir', methods=['POST'])
def predecir():
    """Realiza la predicción del precio"""
    if modelo is None:
        return jsonify({'error': 'Modelo no cargado'}), 500
    
    try:
        datos = request.json

        # ✅ Validación: origen y destino no pueden ser iguales
        if datos['origen'] == datos['destino']:
            return jsonify({
                'exito': False,
                'error': 'El origen y el destino no pueden ser iguales.'
            }), 400
        
        # Procesar fecha
        fecha = pd.to_datetime(datos['fecha'])
        fecha_min = pd.to_datetime(datos_cache['Fecha_del_viaje'].min())
        
        dias_desde_inicio = (fecha - fecha_min).days
        
        # Crear DataFrame de entrada
        entrada = pd.DataFrame({
            'Aerolínea': [label_encoders['Aerolínea'].transform([datos['aerolinea']])[0]],
            'Día_semana': [fecha.dayofweek],
            'Mes': [fecha.month],
            'Trimestre': [fecha.quarter],
            'Es_fin_de_semana': [1 if fecha.weekday() >= 5 else 0],
            'Origen': [label_encoders['Origen'].transform([datos['origen']])[0]],
            'Destino': [label_encoders['Destino'].transform([datos['destino']])[0]],
            'Duración': [int(datos['duracion'])],
            'Total_de_escalas': [int(datos['escalas'])],
            'Información_adicional': [label_encoders['Información_adicional'].transform([datos['informacion']])[0]],
            'Hora_salida_num': [int(datos['hora_salida'].split(':')[0])],
            'Minuto_salida': [int(datos['hora_salida'].split(':')[1])],
            'Días_desde_inicio': [dias_desde_inicio],
            'Longitud_ruta': [len(f"{datos['origen']}-{datos['destino']}")]
        })
        
        # Escalar y predecir
        entrada_scaled = scaler.transform(entrada[features])
        precio_predicho = modelo.predict(entrada_scaled)[0]
        precio_predicho = max(150, round(precio_predicho, 2))
        
        return jsonify({
            'exito': True,
            'precio': precio_predicho,
            'fecha': datos['fecha'],
            'aerolinea': datos['aerolinea'],
            'ruta': f"{datos['origen']} → {datos['destino']}"
        })
    
    except Exception as e:
        return jsonify({'exito': False, 'error': str(e)}), 400

@app.route('/api/estadisticas', methods=['GET'])
def estadisticas():
    """Obtiene estadísticas de los datos"""
    if datos_cache is None:
        return jsonify({'error': 'Datos no disponibles'}), 500
    
    try:
        return jsonify({
            'total_registros': len(datos_cache),
            'precio_min': float(datos_cache['Precio (S/)'].min()),
            'precio_max': float(datos_cache['Precio (S/)'].max()),
            'precio_promedio': float(datos_cache['Precio (S/)'].mean()),
            'precio_mediana': float(datos_cache['Precio (S/)'].median()),
            'desviacion_estandar': float(datos_cache['Precio (S/)'].std()),
            'duracion_promedio': float(datos_cache['Duración'].mean()),
            'escalas_promedio': float(datos_cache['Total_de_escalas'].mean())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/descargar-datos', methods=['GET'])
def descargar_datos():
    """Descarga los datos en Excel"""
    if datos_cache is None:
        return jsonify({'error': 'Datos no disponibles'}), 500
    
    try:
        output = io.BytesIO()
        datos_cache.to_excel(output, index=False, sheet_name='Vuelos')
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='datos_vuelos.xlsx'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cargar-datos', methods=['POST'])
def cargar_datos_usuario():
    """Carga datos desde archivo Excel/CSV del usuario"""
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se envió archivo'}), 400
    
    archivo = request.files['archivo']
    
    try:
        if archivo.filename.endswith('.xlsx'):
            df = pd.read_excel(archivo)
        elif archivo.filename.endswith('.csv'):
            df = pd.read_csv(archivo)
        else:
            return jsonify({'error': 'Formato no soportado'}), 400
        
        # Validar columnas requeridas
        columnas_requeridas = ['Aerolínea', 'Fecha_del_viaje', 'Origen', 'Destino', 
                              'Hora_de_salida', 'Duración', 'Total_de_escalas', 
                              'Información_adicional', 'Precio (S/)']
        
        if not all(col in df.columns for col in columnas_requeridas):
            return jsonify({'error': 'Columnas faltantes en el archivo'}), 400
        
        
        

        # Guardar datos
        df.to_excel('datos_vuelos.xlsx', index=False)
        
        # Recargar caché
        global datos_cache
        datos_cache = df
        
        return jsonify({
            'exito': True,
            'mensaje': f'Datos cargados: {len(df)} registros'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Iniciando aplicación Flask...")
    
    if cargar_modelo():
        print("✓ Modelo cargado exitosamente")
    else:
        print("⚠️  Modelo no encontrado. Ejecuta training.py primero")
    
    if cargar_datos_cache():
        print("✓ Datos cargados en caché")
    else:
        print("⚠️  Datos no encontrados")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
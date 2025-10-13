import pandas as pd
import numpy as np
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.preprocessing import StandardScaler, LabelEncoder
import joblib
import os
from datetime import datetime
import io
from functools import wraps

# ========== CONFIGURACIÓN DE FLASK ==========
app = Flask(__name__)
app.secret_key = "clave_super_segura_2025_mejorada"
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# ========== CONFIGURACIÓN DE POSTGRESQL ==========
# Cambia estos valores según tu base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://vuelos_user:270225@localhost:5432/predictor_vuelos'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ========== MODELOS DE BASE DE DATOS ==========
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    contrasena = db.Column(db.String(255), nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.now)
    activo = db.Column(db.Boolean, default=True)
    
    # Relación con historial
    predicciones = db.relationship('Prediccion', backref='usuario_ref', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, contrasena):
        self.contrasena = generate_password_hash(contrasena)
    
    def check_password(self, contrasena):
        return check_password_hash(self.contrasena, contrasena)

class Prediccion(db.Model):
    __tablename__ = 'predicciones'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    aerolinea = db.Column(db.String(100), nullable=False)
    origen = db.Column(db.String(10), nullable=False)
    destino = db.Column(db.String(10), nullable=False)
    fecha_viaje = db.Column(db.Date, nullable=False)
    hora_salida = db.Column(db.String(10), nullable=False)
    duracion = db.Column(db.Float, nullable=False)
    escalas = db.Column(db.Integer, nullable=False)
    informacion = db.Column(db.String(100), nullable=False)
    precio_predicho = db.Column(db.Float, nullable=False)
    fecha_prediccion = db.Column(db.DateTime, default=datetime.now)

# ========== VARIABLES GLOBALES ==========
modelo = None
scaler = None
label_encoders = None
features = None
datos_cache = None

# ========== DECORADORES ==========
def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ========== CARGA DE MODELO ==========
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
    
    if os.path.exists('datos_vuelos.xlsx'):
        datos_cache = pd.read_excel('datos_vuelos.xlsx')
    elif os.path.exists('datos_vuelos_peru.xlsx'):
        datos_cache = pd.read_excel('datos_vuelos_peru.xlsx')
    
    return datos_cache is not None

# ========== RUTAS DE AUTENTICACIÓN ==========
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        email = request.form.get('email')
        contrasena = request.form.get('contrasena')
        confirmar_contrasena = request.form.get('confirmar_contrasena')
        
        # Validaciones
        if not usuario or not email or not contrasena:
            flash('Todos los campos son obligatorios', 'danger')
            return redirect(url_for('registro'))
        
        if len(contrasena) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'danger')
            return redirect(url_for('registro'))
        
        if contrasena != confirmar_contrasena:
            flash('Las contraseñas no coinciden', 'danger')
            return redirect(url_for('registro'))
        
        # Verificar si usuario existe
        if Usuario.query.filter_by(usuario=usuario).first():
            flash('El usuario ya existe', 'warning')
            return redirect(url_for('registro'))
        
        if Usuario.query.filter_by(email=email).first():
            flash('El email ya está registrado', 'warning')
            return redirect(url_for('registro'))
        
        # Crear nuevo usuario
        nuevo_usuario = Usuario(usuario=usuario, email=email)
        nuevo_usuario.set_password(contrasena)
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        flash('¡Registro exitoso! Ahora puedes iniciar sesión', 'success')
        return redirect(url_for('login'))
    
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        contrasena = request.form.get('contrasena')
        
        usuario_obj = Usuario.query.filter_by(usuario=usuario).first()
        
        if usuario_obj and usuario_obj.check_password(contrasena) and usuario_obj.activo:
            session['usuario_id'] = usuario_obj.id
            session['usuario'] = usuario_obj.usuario
            session['email'] = usuario_obj.email
            flash(f'¡Bienvenido {usuario}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente', 'info')
    return redirect(url_for('login'))

# ========== RUTAS PRINCIPALES ==========
@app.route('/')
@login_requerido
def index():
    if modelo is None:
        return render_template('error.html', 
                             mensaje='Modelo no cargado',
                             detalle='Por favor ejecuta: python training.py')
    
    return render_template('index.html')

@app.route('/dashboard')
@login_requerido
def dashboard():
    usuario_id = session.get('usuario_id')
    predicciones = Prediccion.query.filter_by(usuario_id=usuario_id).all()
    
    # Estadísticas
    total_predicciones = len(predicciones)
    if predicciones:
        precios = [p.precio_predicho for p in predicciones]
        precio_promedio = np.mean(precios)
        precio_min = min(precios)
        precio_max = max(precios)
        
        # Rutas más consultadas
        rutas = {}
        for p in predicciones:
            ruta = f"{p.origen}-{p.destino}"
            rutas[ruta] = rutas.get(ruta, 0) + 1
    else:
        precio_promedio = precio_min = precio_max = 0
        rutas = {}
    
    return render_template('dashboard.html',
                         total_predicciones=total_predicciones,
                         precio_promedio=precio_promedio,
                         precio_min=precio_min,
                         precio_max=precio_max,
                         rutas_top=dict(sorted(rutas.items(), 
                                             key=lambda x: x[1], 
                                             reverse=True)[:5]))

@app.route('/historial')
@login_requerido
def historial():
    usuario_id = session.get('usuario_id')
    predicciones = Prediccion.query.filter_by(usuario_id=usuario_id)\
                                   .order_by(Prediccion.fecha_prediccion.desc())\
                                   .all()
    return render_template('historial.html', predicciones=predicciones)

# ========== RUTAS DE API ==========
@app.route('/api/datos', methods=['GET'])
@login_requerido
def obtener_datos():
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
@login_requerido
def predecir():
    if modelo is None:
        return jsonify({'error': 'Modelo no cargado'}), 500
    
    try:
        datos = request.json
        usuario_id = session.get('usuario_id')
        
        # Validación
        if datos['origen'] == datos['destino']:
            return jsonify({
                'exito': False,
                'error': 'El origen y destino no pueden ser iguales'
            }), 400
        
        # Procesar fecha
        fecha = pd.to_datetime(datos['fecha'])
        fecha_min = pd.to_datetime(datos_cache['Fecha_del_viaje'].min())
        dias_desde_inicio = (fecha - fecha_min).days
        
        # Crear entrada
        entrada = pd.DataFrame({
            'Aerolínea': [label_encoders['Aerolínea'].transform([datos['aerolinea']])[0]],
            'Día_semana': [fecha.dayofweek],
            'Mes': [fecha.month],
            'Trimestre': [fecha.quarter],
            'Es_fin_de_semana': [1 if fecha.weekday() >= 5 else 0],
            'Origen': [label_encoders['Origen'].transform([datos['origen']])[0]],
            'Destino': [label_encoders['Destino'].transform([datos['destino']])[0]],
            'Duración': [float(datos['duracion'])],
            'Total_de_escalas': [int(datos['escalas'])],
            'Información_adicional': [label_encoders['Información_adicional'].transform([datos['informacion']])[0]],
            'Hora_salida_num': [int(datos['hora_salida'].split(':')[0])],
            'Minuto_salida': [int(datos['hora_salida'].split(':')[1])],
            'Días_desde_inicio': [dias_desde_inicio],
            'Longitud_ruta': [len(f"{datos['origen']}-{datos['destino']}")]
        })
        
        # Predicción
        entrada_scaled = scaler.transform(entrada[features])
        precio_predicho = float(modelo.predict(entrada_scaled)[0])
        precio_predicho = max(150, round(precio_predicho, 2))
        
        # Guardar en base de datos
        prediccion = Prediccion(
            usuario_id=usuario_id,
            aerolinea=datos['aerolinea'],
            origen=datos['origen'],
            destino=datos['destino'],
            fecha_viaje=fecha.date(),
            hora_salida=datos['hora_salida'],
            duracion=float(datos['duracion']),
            escalas=int(datos['escalas']),
            informacion=datos['informacion'],
            precio_predicho=precio_predicho
        )
        
        db.session.add(prediccion)
        db.session.commit()
        
        return jsonify({
            'exito': True,
            'precio': precio_predicho,
            'fecha': datos['fecha'],
            'aerolinea': datos['aerolinea'],
            'ruta': f"{datos['origen']} → {datos['destino']}"
        })
    
    except Exception as e:
        return jsonify({'exito': False, 'error': str(e)}), 400

@app.route('/api/historial-json', methods=['GET'])
@login_requerido
def historial_json():
    usuario_id = session.get('usuario_id')
    predicciones = Prediccion.query.filter_by(usuario_id=usuario_id)\
                                   .order_by(Prediccion.fecha_prediccion.desc())\
                                   .limit(10).all()
    
    return jsonify([{
        'id': p.id,
        'aerolinea': p.aerolinea,
        'ruta': f"{p.origen}-{p.destino}",
        'fecha': p.fecha_viaje.strftime('%Y-%m-%d'),
        'precio': p.precio_predicho,
        'hora': p.fecha_prediccion.strftime('%H:%M:%S')
    } for p in predicciones])

@app.route('/api/estadisticas', methods=['GET'])
@login_requerido
def estadisticas():
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

@app.route('/api/perfil', methods=['GET'])
@login_requerido
def perfil():
    usuario_id = session.get('usuario_id')
    usuario = Usuario.query.get(usuario_id)
    predicciones = Prediccion.query.filter_by(usuario_id=usuario_id).count()
    
    return jsonify({
        'usuario': usuario.usuario,
        'email': usuario.email,
        'fecha_creacion': usuario.fecha_creacion.strftime('%Y-%m-%d'),
        'total_predicciones': predicciones
    })

# ========== MANEJO DE ERRORES ==========
@app.errorhandler(404)
def no_encontrado(error):
    return render_template('error.html',
                         mensaje='Página no encontrada',
                         detalle='La página que buscas no existe'), 404

@app.errorhandler(500)
def error_interno(error):
    return render_template('error.html',
                         mensaje='Error interno',
                         detalle='Ocurrió un error en el servidor'), 500

# ========== INICIALIZACIÓN ==========
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Crear tablas si no existen
    
    print("🚀 Iniciando aplicación Flask...")
    
    if cargar_modelo():
        print("✓ Modelo cargado exitosamente")
    else:
        print("⚠️  Modelo no encontrado")
    
    if cargar_datos_cache():
        print("✓ Datos cargados en caché")
    else:
        print("⚠️  Datos no encontrados")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
    

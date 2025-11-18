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
from flask import send_file
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side



# ========== CONFIGURACIÓN DE FLASK ==========
app = Flask(__name__)
app.secret_key = "clave_super_segura_2025_mejorada"
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# ========== CONFIGURACIÓN DE POSTGRESQL ==========
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


@app.route('/api/perfil/actualizar', methods=['PUT'])
@login_requerido
def actualizar_perfil():
    """Actualiza los datos del perfil del usuario"""
    usuario_id = session.get('usuario_id')
    usuario = Usuario.query.get(usuario_id)
    
    try:
        datos = request.json
        
        # Validar datos
        nuevo_usuario = datos.get('usuario', '').strip()
        nuevo_email = datos.get('email', '').strip()
        
        if not nuevo_usuario or not nuevo_email:
            return jsonify({'exito': False, 'error': 'Todos los campos son obligatorios'}), 400
        
        # Verificar si el nuevo usuario ya existe (excepto el actual)
        if nuevo_usuario != usuario.usuario:
            existe_usuario = Usuario.query.filter_by(usuario=nuevo_usuario).first()
            if existe_usuario:
                return jsonify({'exito': False, 'error': 'El nombre de usuario ya está en uso'}), 400
        
        # Verificar si el nuevo email ya existe (excepto el actual)
        if nuevo_email != usuario.email:
            existe_email = Usuario.query.filter_by(email=nuevo_email).first()
            if existe_email:
                return jsonify({'exito': False, 'error': 'El email ya está registrado'}), 400
        
        # Actualizar datos
        usuario.usuario = nuevo_usuario
        usuario.email = nuevo_email
        
        db.session.commit()
        
        # Actualizar sesión
        session['usuario'] = nuevo_usuario
        session['email'] = nuevo_email
        
        return jsonify({
            'exito': True,
            'mensaje': 'Perfil actualizado exitosamente',
            'usuario': nuevo_usuario,
            'email': nuevo_email
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'exito': False, 'error': str(e)}), 500

@app.route('/api/perfil/cambiar-contrasena', methods=['PUT'])
@login_requerido
def cambiar_contrasena():
    """Cambia la contraseña del usuario"""
    usuario_id = session.get('usuario_id')
    usuario = Usuario.query.get(usuario_id)
    
    try:
        datos = request.json
        
        contrasena_actual = datos.get('contrasena_actual', '')
        nueva_contrasena = datos.get('nueva_contrasena', '')
        confirmar_contrasena = datos.get('confirmar_contrasena', '')
        
        # Validaciones
        if not contrasena_actual or not nueva_contrasena or not confirmar_contrasena:
            return jsonify({'exito': False, 'error': 'Todos los campos son obligatorios'}), 400
        
        # Verificar contraseña actual
        if not usuario.check_password(contrasena_actual):
            return jsonify({'exito': False, 'error': 'La contraseña actual es incorrecta'}), 400
        
        # Verificar longitud de nueva contraseña
        if len(nueva_contrasena) < 6:
            return jsonify({'exito': False, 'error': 'La nueva contraseña debe tener al menos 6 caracteres'}), 400
        
        # Verificar que las contraseñas coincidan
        if nueva_contrasena != confirmar_contrasena:
            return jsonify({'exito': False, 'error': 'Las contraseñas no coinciden'}), 400
        
        # Actualizar contraseña
        usuario.set_password(nueva_contrasena)
        db.session.commit()
        
        return jsonify({
            'exito': True,
            'mensaje': 'Contraseña cambiada exitosamente'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'exito': False, 'error': str(e)}), 500
        # ========== RUTAS DE EXPORTACIÓN ==========

@app.route('/api/historial/exportar-excel', methods=['GET'])
@login_requerido
def exportar_excel():
    """Exporta el historial de predicciones a Excel"""
    usuario_id = session.get('usuario_id')
    usuario = Usuario.query.get(usuario_id)
    predicciones = Prediccion.query.filter_by(usuario_id=usuario_id)\
                                   .order_by(Prediccion.fecha_prediccion.desc())\
                                   .all()
    
    if not predicciones:
        return jsonify({'error': 'No hay predicciones para exportar'}), 404
    
    try:
        # Crear workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Historial de Predicciones"
        
        # Estilos
        header_fill = PatternFill(start_color="667EEA", end_color="667EEA", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=12)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Título
        ws.merge_cells('A1:H1')
        titulo = ws['A1']
        titulo.value = f"Historial de Predicciones - {usuario.usuario}"
        titulo.font = Font(bold=True, size=16, color="667EEA")
        titulo.alignment = Alignment(horizontal='center', vertical='center')
        
        # Información del usuario
        ws.merge_cells('A2:H2')
        info = ws['A2']
        info.value = f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total: {len(predicciones)} predicciones"
        info.font = Font(size=10, italic=True)
        info.alignment = Alignment(horizontal='center')
        
        # Espacio
        ws.append([])
        
        # Encabezados
        headers = ['#', 'Fecha Viaje', 'Aerolínea', 'Origen', 'Destino', 'Duración (h)', 'Escalas', 'Precio (S/)']
        ws.append(headers)
        
        # Aplicar estilo a encabezados
        for cell in ws[4]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border
        
        # Datos
        for idx, pred in enumerate(predicciones, 1):
            ws.append([
                idx,
                pred.fecha_viaje.strftime('%Y-%m-%d'),
                pred.aerolinea,
                pred.origen,
                pred.destino,
                pred.duracion,
                pred.escalas,
                pred.precio_predicho
            ])
            
            # Aplicar bordes a todas las celdas
            for cell in ws[ws.max_row]:
                cell.border = border
                cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # Ajustar anchos de columna
        column_widths = [5, 15, 20, 10, 10, 12, 10, 12]
        for i, width in enumerate(column_widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width
        
        # Estadísticas al final
        ws.append([])
        precios = [p.precio_predicho for p in predicciones]
        ws.append(['ESTADÍSTICAS', '', '', '', '', '', '', ''])
        ws.append(['Precio Promedio:', '', '', '', '', '', '', f"S/ {sum(precios)/len(precios):.2f}"])
        ws.append(['Precio Mínimo:', '', '', '', '', '', '', f"S/ {min(precios):.2f}"])
        ws.append(['Precio Máximo:', '', '', '', '', '', '', f"S/ {max(precios):.2f}"])
        
        # Estilo para estadísticas
        for row in range(ws.max_row - 3, ws.max_row + 1):
            ws[f'A{row}'].font = Font(bold=True)
            ws[f'H{row}'].font = Font(bold=True, color="667EEA")
        
        # Guardar en memoria
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        # Nombre del archivo
        filename = f"historial_{usuario.usuario}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/historial/exportar-pdf', methods=['GET'])
@login_requerido
def exportar_pdf():
    """Exporta el historial de predicciones a PDF"""
    usuario_id = session.get('usuario_id')
    usuario = Usuario.query.get(usuario_id)
    predicciones = Prediccion.query.filter_by(usuario_id=usuario_id)\
                                   .order_by(Prediccion.fecha_prediccion.desc())\
                                   .all()
    
    if not predicciones:
        return jsonify({'error': 'No hay predicciones para exportar'}), 404
    
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#667EEA'),
            spaceAfter=12,
            alignment=1  # Centrado
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.grey,
            spaceAfter=20,
            alignment=1
        )
        
        # Título
        titulo = Paragraph(f"<b>Historial de Predicciones</b><br/>{usuario.usuario}", title_style)
        elements.append(titulo)
        
        # Información
        info_text = f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total: {len(predicciones)} predicciones"
        info = Paragraph(info_text, subtitle_style)
        elements.append(info)
        elements.append(Spacer(1, 0.2*inch))
        
        # Tabla de datos
        data = [['#', 'Fecha', 'Aerolínea', 'Ruta', 'Duración', 'Escalas', 'Precio']]
        
        for idx, pred in enumerate(predicciones, 1):
            data.append([
                str(idx),
                pred.fecha_viaje.strftime('%Y-%m-%d'),
                pred.aerolinea[:15],  # Truncar si es muy largo
                f"{pred.origen}-{pred.destino}",
                f"{pred.duracion}h",
                str(pred.escalas),
                f"S/ {pred.precio_predicho:.2f}"
            ])
        
        # Crear tabla
        table = Table(data, colWidths=[0.5*inch, 1*inch, 1.5*inch, 1*inch, 0.8*inch, 0.7*inch, 1*inch])
        
        # Estilo de tabla
        table.setStyle(TableStyle([
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667EEA')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            
            # Contenido
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7F7F7')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Estadísticas
        precios = [p.precio_predicho for p in predicciones]
        stats_data = [
            ['ESTADÍSTICAS', ''],
            ['Precio Promedio:', f"S/ {sum(precios)/len(precios):.2f}"],
            ['Precio Mínimo:', f"S/ {min(precios):.2f}"],
            ['Precio Máximo:', f"S/ {max(precios):.2f}"],
            ['Duración Promedio:', f"{sum(p.duracion for p in predicciones)/len(predicciones):.1f}h"],
            ['Total de Escalas:', f"{sum(p.escalas for p in predicciones)}"]
        ]
        
        stats_table = Table(stats_data, colWidths=[2.5*inch, 1.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667EEA')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(stats_table)
        
        # Pie de página
        elements.append(Spacer(1, 0.3*inch))
        footer = Paragraph(
            f"<i>Documento generado por AeroPredict © {datetime.now().year}</i>",
            ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=1)
        )
        elements.append(footer)
        
        # Construir PDF
        doc.build(elements)
        buffer.seek(0)
        
        # Nombre del archivo
        filename = f"historial_{usuario.usuario}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    

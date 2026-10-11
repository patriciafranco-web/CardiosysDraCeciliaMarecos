import os
import sys
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from threading import Timer
import webbrowser
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Configuración de rutas apuntando al Disco Persistente en Render
if getattr(sys, 'frozen', False):
  base_dir = os.path.dirname(sys.executable)
else:
  base_dir = os.path.dirname(os.path.abspath(__file__))

data_dir = os.path.join(base_dir, 'data')
os.makedirs(data_dir, exist_ok=True)

db_path = os.path.join(data_dir, 'cardiologia_elite.db')
upload_folder = os.path.join(data_dir, 'uploads')
backup_folder = os.path.join(data_dir, 'Backups_Automaticos')
os.makedirs(upload_folder, exist_ok=True)
os.makedirs(backup_folder, exist_ok=True)

app = Flask(__name__)
app.secret_key = 'cardio_elite_seguro_2026'


def hacer_backup_automatico():
  if os.path.exists(db_path):
    fecha_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_file = os.path.join(
        backup_folder, f'backup_cardiologia_{fecha_str}.db'
    )
    try:
      with open(db_path, 'rb') as src, open(backup_file, 'wb') as dst:
        dst.write(src.read())
    except Exception as e:
      print('Error al generar auto-backup:', e)


def init_db():
  conn = sqlite3.connect(db_path)
  cursor = conn.cursor()

  # Tabla de Usuarios y contraseñas cifradas
  cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

  pass_hash = generate_password_hash('cardiopy')
  cursor.execute(
      '''
        INSERT INTO usuarios (username, password_hash) 
        VALUES ('draceciliamarecos', ?) 
        ON CONFLICT(username) DO UPDATE SET password_hash = ?
    ''',
      (pass_hash, pass_hash),
  )

  cursor.execute('''
        CREATE TABLE IF NOT EXISTS pacientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cedula TEXT NOT NULL,
            nombre TEXT NOT NULL,
            nacimiento TEXT,
            sexo TEXT,
            telefono TEXT,
            profesion TEXT,
            direccion TEXT,
            alergias TEXT,
            antecedentes TEXT,
            fecha_cita TEXT,
            es_estudio INTEGER DEFAULT 0
        )
    ''')

  # Migración segura para columna es_estudio en pacientes
  try:
    cursor.execute(
        'ALTER TABLE pacientes ADD COLUMN es_estudio INTEGER DEFAULT 0'
    )
  except sqlite3.OperationalError:
    pass

  cursor.execute('''
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER,
            fecha TEXT,
            antecedentes_consulta TEXT,
            motivo TEXT,
            consulta_actual TEXT,
            pa TEXT,
            fc TEXT,
            peso TEXT,
            talla TEXT,
            imc TEXT,
            cintura TEXT,
            estudios_historial TEXT,
            medicacion_actual TEXT,
            framingham TEXT,
            cha2ds2 TEXT,
            funcion_renal TEXT,
            rel_alb_crea TEXT,
            scag TEXT,
            asa TEXT,
            lee TEXT,
            examen_fisico_notas TEXT,
            FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
        )
    ''')

  # Migración segura para columnas nuevas en historial
  for col, tipo in [
      ('framingham', 'TEXT'),
      ('cha2ds2', 'TEXT'),
      ('funcion_renal', 'TEXT'),
      ('rel_alb_crea', 'TEXT'),
      ('scag', 'TEXT'),
      ('asa', 'TEXT'),
      ('lee', 'TEXT'),
      ('examen_fisico_notas', 'TEXT'),
  ]:
    try:
      cursor.execute(f'ALTER TABLE historial ADD COLUMN {col} {tipo}')
    except sqlite3.OperationalError:
      pass

  cursor.execute('''
        CREATE TABLE IF NOT EXISTS estudios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER,
            nombre_estudio TEXT,
            archivo TEXT,
            fecha TEXT,
            sanatorio TEXT,
            tipo_plantilla TEXT,
            contenido_editable TEXT,
            FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
        )
    ''')

  cursor.execute('SELECT COUNT(*) FROM pacientes')
  if cursor.fetchone()[0] == 0:
    hoy_str = datetime.today().strftime('%Y-%m-%d')
    cursor.execute(
        '''
            INSERT INTO pacientes (cedula, nombre, nacimiento, sexo, telefono, profesion, direccion, alergias, antecedentes, fecha_cita, es_estudio) 
            VALUES ('3789170', 'Paciente Ejemplo', '1986-05-22', 'Femenino', '0987546321', 'Médico', 'Asunción', 'Ninguna', 'HTA, Dislipidemia', ?, 0)
        ''',
        (hoy_str,),
    )

  conn.commit()
  conn.close()
  hacer_backup_automatico()


# Inicializar la base de datos y tablas globalmente para Render/Gunicorn
init_db()


@app.before_request
def hacer_sesion_no_permanente():
  session.permanent = False


def calcular_edad(nacimiento_str):
  if not nacimiento_str:
    return 0
  try:
    nac = datetime.strptime(nacimiento_str, '%Y-%m-%d')
    hoy = datetime.today()
    edad = (
        hoy.year
        - nac.year
        - ((hoy.month, hoy.day) < (nac.month, nac.day))
    )
    return edad
  except:
    return 0


def calcular_edad_texto(nacimiento_str):
  edad = calcular_edad(nacimiento_str)
  return f'{edad} años' if edad else 'N/D'


def dibujar_membrete(c, sanatorio, width, height):
  logo_file = (
      'logo_ovelar.png' if 'Ovelar' in sanatorio else 'logo_carlos.png'
  )
  if not os.path.exists(logo_file):
    alternativos = (
        ['logo_san_carlos.png', 'SanCarlos.png', 'san_carlos.png']
        if 'Carlos' in sanatorio
        else ['logo_san_ovelar.png', 'Ovelar.png']
    )
    for alt in alternativos:
      if os.path.exists(alt):
        logo_file = alt
        break

  if os.path.exists(logo_file):
    try:
      c.drawImage(
          logo_file,
          50,
          height - 60,
          width=160,
          height=45,
          preserveAspectRatio=True,
          mask='auto',
      )
    except Exception as e:
      print('Error al cargar logo:', e)
  else:
    c.setFillColorRGB(0.1, 0.3, 0.5)
    c.setFont('Helvetica-Bold', 14)
    c.drawString(50, height - 40, sanatorio)

  c.setFillColorRGB(0.85, 0.87, 0.9)
  c.rect(50, height - 85, width - 100, 18, fill=1, stroke=0)
  c.setFillColorRGB(0.1, 0.1, 0.1)
  c.setFont('Helvetica-Bold', 10)
  c.drawCentredString(width / 2.0, height - 78, 'SERVICIO DE CARDIOLOGÍA IMÁGENES')

  c.setFont('Helvetica-Bold', 12)
  c.drawCentredString(
      width / 2.0, height - 105, 'Informe de Ecocardiografía-Doppler-Color'
  )


def generar_pdf_ecocardiograma(
    sanatorio,
    cedula,
    nombre,
    edad,
    sexo,
    motivo,
    pestaña,
    dims,
    doppler,
    desc,
    conc,
):
  nombre_limpio = nombre.replace(' ', '_')
  sanatorio_limpio = sanatorio.replace(' ', '_')
  filename = f'Informe_{nombre_limpio}_{sanatorio_limpio}.pdf'
  filepath = os.path.join(upload_folder, filename)

  c = canvas.Canvas(filepath, pagesize=letter)
  width, height = letter

  # PÁGINA 1
  dibujar_membrete(c, sanatorio, width, height)

  # Datos del paciente
  y = height - 128
  c.setFont('Helvetica-Bold', 10)
  c.drawString(50, y, 'Nombre:')
  c.setFont('Helvetica', 10)
  c.drawString(105, y, f'{nombre}')

  c.setFont('Helvetica-Bold', 10)
  c.drawString(450, y, 'Fecha:')
  c.setFont('Helvetica', 10)
  c.drawString(490, y, f"{datetime.today().strftime('%d/%m/%Y')}")
  y -= 16

  c.setFont('Helvetica-Bold', 10)
  c.drawString(50, y, 'Edad (años):')
  c.setFont('Helvetica', 10)
  c.drawString(125, y, f'{edad}')

  c.setFont('Helvetica-Bold', 10)
  c.drawString(240, y, 'Sexo:')
  c.setFont('Helvetica', 10)
  c.drawString(280, y, f'{sexo}')
  y -= 16

  c.setFont('Helvetica-Bold', 10)
  c.drawString(50, y, 'Motivo del estudio:')
  c.setFont('Helvetica', 10)
  c.drawString(150, y, f'{motivo}')
  y -= 16

  c.setFont('Helvetica-Bold', 10)
  c.drawString(50, y, 'C.I. nº:')
  c.setFont('Helvetica', 10)
  c.drawString(100, y, f'{cedula}')
  y -= 8
  c.line(50, y, width - 50, y)
  y -= 15

  # Sección Dimensiones
  c.setFont('Helvetica-Bold', 10)
  c.drawString(50, y, 'Dimensiones')
  y -= 3
  c.line(50, y, width - 50, y)
  y -= 15

  lista_dims = [
      ('Aorta (AO):', dims.get('ao', ''), 'v.n.: 20 - 37', 'mm'),
      ('Aurícula izquierda (AI):', dims.get('ai', ''), 'v.n.: 20 - 40', 'mm'),
      ('Volumen aurícula izquierda:', dims.get('vol_ai', ''), '', 'ml'),
      (
          'Volumen aurícula izquierda/SC:',
          dims.get('vol_ai_sc', ''),
          'v.n.: 16 - 34',
          'ml/m2',
      ),
      ('Ventrículo derecho:', dims.get('vd', ''), 'v.n.: 09 - 26', 'mm'),
      (
          'Ventrículo izquierdo Diástole:',
          dims.get('vi_diastole', ''),
          'v.n.: 37 - 56',
          'mm',
      ),
      (
          'Ventrículo izquierdo Sístole:',
          dims.get('vi_sistole', ''),
          'v.n.: 27 - 37',
          'mm',
      ),
      (
          'Volumen de fin de Diástole del VI:',
          dims.get('vol_diastole_vi', ''),
          '',
          'ml/m2',
      ),
      (
          'Volumen de fin de Sístole del VI:',
          dims.get('vol_sistole_vi', ''),
          '',
          'ml/m2',
      ),
      (
          'Fracción de acortamiento:',
          dims.get('facortamiento', ''),
          'v.n.: 28 - 40 %',
          '',
      ),
      (
          'Fracción de eyección:',
          dims.get('feyeccion', ''),
          'v.n.: 55 - 70 %',
          '',
      ),
      (
          'Espesor del tabique interventricular:',
          dims.get('siv', ''),
          'v.n.: 7 - 11',
          'mm',
      ),
      (
          'Espesor de la pared posterior del VI:',
          dims.get('ppvi', ''),
          'v.n.: 7 - 11',
          'mm',
      ),
      ('Espesor parietal relativo:', dims.get('epr', ''), '', ''),
      ('Masa del VI (g):', dims.get('masavi', ''), '', 'g'),
      (
          'Índice de Masa del VI (g/m2):',
          dims.get('imasa_vi', ''),
          'v.n.: <115 g/m2 (hombres) - <95 g/m2 (mujeres)',
          '',
      ),
  ]

  c.setFont('Helvetica', 9)
  for label, val, vn, unit in lista_dims:
    if y < 80:
      c.showPage()
      dibujar_membrete(c, sanatorio, width, height)
      y = height - 130
    c.drawString(50, y, label)
    if val:
      c.setFont('Helvetica-Bold', 9)
      c.drawString(280, y, str(val))
      c.setFont('Helvetica', 9)
    c.drawString(340, y, vn)
    c.drawString(480, y, unit)
    y -= 13

  y -= 5
  c.line(50, y, width - 50, y)
  y -= 15

  # Sección Descripción
  if y < 120:
    c.showPage()
    dibujar_membrete(c, sanatorio, width, height)
    y = height - 130

  c.setFont('Helvetica-Bold', 10)
  c.drawString(50, y, 'Descripción')
  y -= 3
  c.line(50, y, width - 50, y)
  y -= 15

  c.setFont('Helvetica', 9)
  for line in desc.split('\n'):
    clean_line = line.replace('■', '').replace('', '').strip()
    if clean_line:
      if y < 70:
        c.showPage()
        dibujar_membrete(c, sanatorio, width, height)
        y = height - 130
      c.drawString(50, y, clean_line)
      y -= 12

  y -= 10

  # Sección Examen Doppler Completo
  if y < 180:
    c.showPage()
    dibujar_membrete(c, sanatorio, width, height)
    y = height - 130

  c.setFont('Helvetica-Bold', 10)
  c.drawString(50, y, 'Examen Doppler')
  y -= 3
  c.line(50, y, width - 50, y)
  y -= 15

  lista_doppler = [
      ('Flujo mitral:', doppler.get('flujo_mitral', ''), ''),
      ('Onda E:', doppler.get('onda_e', ''), 'm/seg'),
      ('Onda A:', doppler.get('onda_a', ''), 'm/seg'),
      (
          'E/A:',
          doppler.get('ea', ''),
          (
              'v.n.: < 40 años:1,5±0,40 ms; <60 años:1,3±0,25 ms; >60'
              ' años:0,96±0,18 ms'
          ),
      ),
      ('TDE:', doppler.get('tde', ''), 'v.n.: 188±28 ms'),
      ('Flujo aórtico:', doppler.get('flujo_aortico', ''), ''),
      ('Velocidad máxima:', doppler.get('vel_max', ''), 'm/seg'),
      ('Gradiente pico:', doppler.get('grad_pico', ''), 'mm/Hg'),
      ('Gradiente medio:', doppler.get('grad_medio', ''), 'mm/Hg'),
      ('Área aórtica:', doppler.get('area_aortica', ''), 'cm2'),
      ('THP:', doppler.get('thp', ''), 'ms'),
      ('Flujo tricuspídeo:', doppler.get('flujo_tricuspideo', ''), ''),
      ('Gradiente VD/AD:', doppler.get('grad_vd_ad', ''), 'mmHg'),
      ('Flujo pulmonar:', doppler.get('flujo_pulmonar', ''), ''),
      (
          'PA pulmonar sistólica:',
          doppler.get('pa_sistolica', ''),
          'mmHg    v.n.: <36 mm/Hg',
      ),
  ]

  c.setFont('Helvetica', 9)
  for label, val, unit in lista_doppler:
    if val or label in [
        'Flujo mitral:',
        'Flujo aórtico:',
        'Flujo tricuspídeo:',
        'Flujo pulmonar:',
    ]:
      if y < 70:
        c.showPage()
        dibujar_membrete(c, sanatorio, width, height)
        y = height - 130
      c.drawString(50, y, label)
      if val:
        c.setFont('Helvetica-Bold', 9)
        c.drawString(180, y, str(val))
        c.setFont('Helvetica', 9)
      if unit:
        c.drawString(260, y, unit)
      y -= 13

  y -= 5
  c.line(50, y, width - 50, y)
  y -= 15

  # Sección Conclusión
  if y < 150:
    c.showPage()
    dibujar_membrete(c, sanatorio, width, height)
    y = height - 130

  c.setFont('Helvetica-Bold', 10)
  c.setFillColorRGB(0.1, 0.1, 0.1)
  c.drawString(50, y, 'Conclusión')
  y -= 3
  c.line(50, y, width - 50, y)
  y -= 15

  c.setFont('Helvetica-Bold', 9)
  c.setFillColorRGB(0.05, 0.3, 0.15)
  for line in conc.split('\n'):
    clean_line = line.replace('■', '').replace('', '').strip()
    if clean_line:
      if y < 70:
        c.showPage()
        dibujar_membrete(c, sanatorio, width, height)
        y = height - 130
      c.drawString(50, y, clean_line)
      y -= 13

  # Firma al pie
  c.setFont('Helvetica-Bold', 10)
  c.setFillColorRGB(0.1, 0.1, 0.1)
  c.drawString(width - 250, 70, 'Dra. Cecilia Marecos Viana')
  c.setFont('Helvetica', 9)
  c.drawString(width - 250, 57, 'Reg. Prof. 13943')
  c.drawString(width - 250, 44, 'Esp. Cardiología Clínica y Diagnóstica')

  c.save()
  return filename


@app.route('/login', methods=['GET', 'POST'])
def login():
  error = None
  if request.method == 'POST':
    username = request.form.get('username')
    password = request.form.get('password')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT password_hash FROM usuarios WHERE username = ?', (username,)
    )
    row = cursor.fetchone()
    conn.close()

    if row and check_password_hash(row[0], password):
      session['logged_in'] = True
      session['username'] = username
      return redirect(url_for('index'))
    else:
      error = 'Usuario o contraseña incorrectos'

  err_html = (
      f'<p style="color:red; font-size:13px; text-align:center;">{error}</p>'
      if error
      else ''
  )
  return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Acceso - CardioSys</title></head>
    <body style="font-family:Segoe UI; background:#f4f7f6; display:flex; justify-content:center; align-items:center; height:100vh; margin:0;">
        <div style="background:white; padding:30px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.1); width:350px; text-align:center;">
            <h2 style="color:#2c3e50; margin-top:0;">CardioSys 1.0</h2>
            <p style="color:#2980b9; font-size:16px; font-weight:bold; margin-bottom:20px;">Dra. Cecilia Marecos Viana</p>
            {err_html}
            <form method="POST">
                <label style="display:block; text-align:left; font-size:13px; font-weight:bold;">Usuario:</label>
                <input type="text" name="username" required style="width:100%; padding:10px; margin:8px 0 15px 0; box-sizing:border-box; border:1px solid #ccc; border-radius:4px;">
                
                <label style="display:block; text-align:left; font-size:13px; font-weight:bold;">Contraseña:</label>
                <input type="password" name="password" required style="width:100%; padding:10px; margin:8px 0 20px 0; box-sizing:border-box; border:1px solid #ccc; border-radius:4px;">
                
                <button type="submit" style="width:100%; padding:10px; background:#2980b9; color:white; border:none; border-radius:4px; font-weight:bold; cursor:pointer;">Ingresar</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.route('/cambiar-contrasena', methods=['GET', 'POST'])
def cambiar_contrasena():
  if not session.get('logged_in'):
    return redirect(url_for('login'))

  error = None
  exito = None
  username = session.get('username', 'draceciliamarecos')

  if request.method == 'POST':
    actual = request.form.get('password_actual', '')
    nueva = request.form.get('password_nueva', '')
    repetir = request.form.get('password_repetir', '')

    if not actual or not nueva or not repetir:
      error = 'Por favor, complete todos los campos.'
    elif nueva != repetir:
      error = 'Las nuevas contraseñas no coinciden.'
    else:
      conn = sqlite3.connect(db_path)
      cursor = conn.cursor()
      cursor.execute(
          'SELECT password_hash FROM usuarios WHERE username = ?', (username,)
      )
      row = cursor.fetchone()

      if row and check_password_hash(row[0], actual):
        nuevo_hash = generate_password_hash(nueva)
        cursor.execute(
            'UPDATE usuarios SET password_hash = ? WHERE username = ?',
            (nuevo_hash, username),
        )
        conn.commit()
        exito = '¡Contraseña actualizada con éxito!'
      else:
        error = 'La contraseña actual es incorrecta.'
      conn.close()

  msg_html = (
      f'<p style="color:green; font-weight:bold; text-align:center;">{exito}</p>'
      if exito
      else (
          f'<p style="color:red; font-size:13px; text-align:center;">{error}</p>'
          if error
          else ''
      )
  )

  return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Cambiar Contraseña - CardioSys</title></head>
    <body style="font-family:Segoe UI; background:#f4f7f6; margin:0; display:flex; height:100vh;">
        <div style="width:260px; background:#1e293b; color:white; padding:20px; box-sizing:border-box; display:flex; flex-direction:column;">
            <h2 style="color:white; margin-top:0; margin-bottom:5px;">CardioSys 1.0</h2>
            <p style="color:#38bdf8; font-size:16px; font-weight:bold; margin-top:0; margin-bottom:25px; line-height:1.3;">Dra. Cecilia Marecos</p>
            <ul style="list-style:none; padding:0; margin-top:0; flex:1;">
                <li style="margin:15px 0;"><a href="/" style="color:white; text-decoration:none;">📋 Agenda Diaria</a></li>
                <li style="margin:15px 0;"><a href="/nuevo" style="color:white; text-decoration:none;">➕ Nuevo Ingreso</a></li>
                <li style="margin:15px 0;"><a href="/lista-pacientes" style="color:white; text-decoration:none;">👥 Lista de Pacientes</a></li>
                <li style="margin:15px 0;"><a href="/plantilla-ovelar" style="color:white; text-decoration:none;">🏥 Plantilla Ovelar</a></li>
                <li style="margin:15px 0;"><a href="/plantilla-san-carlos" style="color:white; text-decoration:none;">🏥 Plantilla San Carlos</a></li>
                <li style="margin:15px 0;"><a href="/estudios-recientes" style="color:white; text-decoration:none;">📁 Lista de Estudios</a></li>
                <li style="margin:15px 0;"><a href="/cambiar-contrasena" style="color:#38bdf8; text-decoration:none; font-weight:bold;">🔑 Cambiar Contraseña</a></li>
            </ul>
            <div style="margin-bottom:20px;">
                <a href="/backup" style="display:block; background:#e67e22; color:white; padding:12px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold;">💾 Backup Manual</a>
                <a href="/logout" style="display:block; background:#ef4444; color:white; padding:8px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold; margin-top:10px; font-size:13px;">🚪 Cerrar Sesión</a>
            </div>
        </div>
        <div style="flex:1; padding:40px; overflow-y:auto;">
            <a href="/" style="display:inline-block; margin-bottom:15px; color:#3498db; text-decoration:none; font-weight:bold;">⬅ Volver al Panel</a>
            <div style="background:white; padding:30px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.05); max-width:450px;">
                <h2 style="color:#2c3e50; margin-top:0;">🔑 Cambiar Contraseña de Acceso</h2>
                {msg_html}
                <form method="POST">
                    <label style="font-weight:bold; font-size:13px; display:block; margin-bottom:6px;">Contraseña Actual:</label>
                    <input type="password" name="password_actual" required style="width:100%; padding:10px; margin-bottom:15px; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;">
                    
                    <label style="font-weight:bold; font-size:13px; display:block; margin-bottom:6px;">Nueva Contraseña:</label>
                    <input type="password" name="password_nueva" required style="width:100%; padding:10px; margin-bottom:15px; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;">
                    
                    <label style="font-weight:bold; font-size:13px; display:block; margin-bottom:6px;">Confirmar Nueva Contraseña:</label>
                    <input type="password" name="password_repetir" required style="width:100%; padding:10px; margin-bottom:20px; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;">
                    
                    <button type="submit" style="background:#2980b9; color:white; border:none; padding:12px 20px; border-radius:4px; font-weight:bold; cursor:pointer; width:100%;">Actualizar Contraseña</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """


@app.route('/lista-pacientes')
def lista_pacientes():
  if not session.get('logged_in'):
    return redirect(url_for('login'))

  conn = sqlite3.connect(db_path)
  cursor = conn.cursor()
  cursor.execute(
      'SELECT id, cedula, nombre, nacimiento, profesion, direccion, telefono'
      ' FROM pacientes WHERE es_estudio = 0 ORDER BY nombre ASC'
  )
  pacientes = cursor.fetchall()
  conn.close()

  filas_html = ''
  for p in pacientes:
    edad_txt = calcular_edad_texto(p[3])
    filas_html += f"""
        <tr>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{p[1]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd; font-weight:bold;">{p[2]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{edad_txt}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{p[4] or 'N/D'}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{p[5] or 'N/D'}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{p[6] or 'N/D'}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">
                <a href="/ficha/{p[0]}" style="background:#3498db; color:white; padding:6px 12px; text-decoration:none; border-radius:4px; font-size:14px; margin-right:5px;">Ver Ficha</a>
            </td>
        </tr>
        """
  if not filas_html:
    filas_html = (
        "<tr><td colspan='7' style='padding:15px;"
        " text-align:center;'>No hay pacientes habituales registrados.</td></tr>"
    )

  return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Lista de Pacientes - CardioSys</title></head>
    <body style="font-family:Segoe UI; background:#f4f7f6; margin:0; display:flex; height:100vh;">
        <div style="width:260px; background:#1e293b; color:white; padding:20px; box-sizing:border-box; display:flex; flex-direction:column;">
            <h2 style="color:white; margin-top:0; margin-bottom:5px;">CardioSys 1.0</h2>
            <p style="color:#38bdf8; font-size:16px; font-weight:bold; margin-top:0; margin-bottom:25px; line-height:1.3;">Dra. Cecilia Marecos</p>
            <ul style="list-style:none; padding:0; margin-top:0; flex:1;">
                <li style="margin:15px 0;"><a href="/" style="color:white; text-decoration:none;">📋 Agenda Diaria</a></li>
                <li style="margin:15px 0;"><a href="/nuevo" style="color:white; text-decoration:none;">➕ Nuevo Ingreso</a></li>
                <li style="margin:15px 0;"><a href="/lista-pacientes" style="color:#38bdf8; text-decoration:none; font-weight:bold;">👥 Lista de Pacientes</a></li>
                <li style="margin:15px 0;"><a href="/plantilla-ovelar" style="color:white; text-decoration:none;">🏥 Plantilla Ovelar</a></li>
                <li style="margin:15px 0;"><a href="/plantilla-san-carlos" style="color:white; text-decoration:none;">🏥 Plantilla San Carlos</a></li>
                <li style="margin:15px 0;"><a href="/estudios-recientes" style="color:white; text-decoration:none;">📁 Lista de Estudios</a></li>
                <li style="margin:15px 0;"><a href="/cambiar-contrasena" style="color:white; text-decoration:none;">🔑 Cambiar Contraseña</a></li>
            </ul>
            <div style="margin-bottom:20px;">
                <a href="/backup" style="display:block; background:#e67e22; color:white; padding:12px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold;">💾 Backup Manual</a>
                <a href="/logout" style="display:block; background:#ef4444; color:white; padding:8px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold; margin-top:10px; font-size:13px;">🚪 Cerrar Sesión</a>
            </div>
        </div>
        <div style="flex:1; padding:40px; overflow-y:auto;">
            <h1>👥 Directorio General de Pacientes Habituales</h1>
            <div style="background:white; padding:25px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.05); margin-top:20px;">
                <table style="width:100%; border-collapse:collapse; margin-top:15px;">
                    <tr style="background:#1e293b; color:white;">
                        <th style="padding:12px; text-align:left;">Cédula (C.I.)</th>
                        <th style="padding:12px; text-align:left;">Nombre y Apellido</th>
                        <th style="padding:12px; text-align:left;">Edad</th>
                        <th style="padding:12px; text-align:left;">Profesión</th>
                        <th style="padding:12px; text-align:left;">Procedencia</th>
                        <th style="padding:12px; text-align:left;">Teléfono</th>
                        <th style="padding:12px; text-align:left;">Acción</th>
                    </tr>
                    {filas_html}
                </table>
            </div>
        </div>
    </body>
    </html>
    """


@app.route('/')
def index():
  if not session.get('logged_in'):
    return redirect(url_for('login'))

  fecha_agenda = request.args.get(
      'fecha', datetime.today().strftime('%Y-%m-%d')
  )
  busqueda = request.args.get('q', '').strip()
  conn = sqlite3.connect(db_path)
  cursor = conn.cursor()

  if busqueda:
    cursor.execute(
        'SELECT id, cedula, nombre, nacimiento, profesion, direccion,'
        ' fecha_cita FROM pacientes WHERE es_estudio = 0 AND (nombre LIKE ? OR'
        ' cedula LIKE ?)',
        (f'%{busqueda}%', f'%{busqueda}%'),
    )
  else:
    cursor.execute(
        'SELECT id, cedula, nombre, nacimiento, profesion, direccion,'
        ' fecha_cita FROM pacientes WHERE es_estudio = 0 AND fecha_cita = ?',
        (fecha_agenda,),
    )

  pacientes = cursor.fetchall()
  conn.close()

  filas_html = ''
  for p in pacientes:
    edad_txt = calcular_edad_texto(p[3])
    profesion_txt = p[4] or 'N/D'
    procedencia_txt = p[5] or 'N/D'
    filas_html += f"""
        <tr>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{p[1]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd; font-weight:bold;">{p[2]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{edad_txt}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{profesion_txt}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{procedencia_txt}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">
                <a href="/ficha/{p[0]}" style="background:#2ecc71; color:white; padding:6px 12px; text-decoration:none; border-radius:4px; font-size:14px;">Abrir Ficha</a>
            </td>
        </tr>
        """
  if not filas_html:
    filas_html = (
        "<tr><td colspan='6' style='padding:15px;"
        " text-align:center;'>No hay pacientes agendados para esta"
        ' fecha.</td></tr>'
    )

  return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Panel Principal - CardioSys</title></head>
    <body style="font-family:Segoe UI; background:#f4f7f6; margin:0; display:flex; height:100vh;">
        <div style="width:260px; background:#1e293b; color:white; padding:20px; box-sizing:border-box; display:flex; flex-direction:column;">
            <h2 style="color:white; margin-top:0; margin-bottom:5px;">CardioSys 1.0</h2>
            <p style="color:#38bdf8; font-size:16px; font-weight:bold; margin-top:0; margin-bottom:25px; line-height:1.3;">Dra. Cecilia Marecos</p>
            <ul style="list-style:none; padding:0; margin-top:0; flex:1;">
                <li style="margin:15px 0;"><a href="/" style="color:#38bdf8; text-decoration:none; font-weight:bold;">📋 Agenda Diaria</a></li>
                <li style="margin:15px 0;"><a href="/nuevo" style="color:white; text-decoration:none;">➕ Nuevo Ingreso</a></li>
                <li style="margin:15px 0;"><a href="/lista-pacientes" style="color:white; text-decoration:none;">👥 Lista de Pacientes</a></li>
                <li style="margin:15px 0;"><a href="/plantilla-ovelar" style="color:white; text-decoration:none;">🏥 Plantilla Ovelar</a></li>
                <li style="margin:15px 0;"><a href="/plantilla-san-carlos" style="color:white; text-decoration:none;">🏥 Plantilla San Carlos</a></li>
                <li style="margin:15px 0;"><a href="/estudios-recientes" style="color:white; text-decoration:none;">📁 Lista de Estudios</a></li>
                <li style="margin:15px 0;"><a href="/cambiar-contrasena" style="color:white; text-decoration:none;">🔑 Cambiar Contraseña</a></li>
            </ul>
            <div style="margin-bottom:20px;">
                <a href="/backup" style="display:block; background:#e67e22; color:white; padding:12px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold;">💾 Backup Manual</a>
                <a href="/logout" style="display:block; background:#ef4444; color:white; padding:8px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold; margin-top:10px; font-size:13px;">🚪 Cerrar Sesión</a>
            </div>
        </div>
        <div style="flex:1; padding:40px; overflow-y:auto;">
            <h1>Panel de Control / Agenda Diaria</h1>
            
            <div style="background:white; padding:20px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.05); margin-bottom:20px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:15px;">
                <form method="GET" action="/" style="display:flex; gap:10px; align-items:center; margin:0;">
                    <label style="font-weight:bold; font-size:13px; color:#2c3e50;">📅 Seleccionar Fecha:</label>
                    <input type="date" name="fecha" value="{fecha_agenda}" onchange="this.form.submit()" style="padding:8px; border:1px solid #ccc; border-radius:4px; font-weight:bold;">
                </form>
                <form method="GET" action="/" style="display:flex; gap:10px; margin:0; flex:1; max-width:400px;">
                    <input type="hidden" name="fecha" value="{fecha_agenda}">
                    <input type="text" name="q" value="{busqueda}" placeholder="Buscar por nombre o cédula..." style="flex:1; padding:8px; border:1px solid #ccc; border-radius:4px;">
                    <button type="submit" style="background:#3498db; color:white; border:none; padding:8px 15px; border-radius:4px; cursor:pointer; font-weight:bold;">Buscar</button>
                    <a href="/" style="background:#95a5a6; color:white; padding:8px 12px; text-decoration:none; border-radius:4px; font-weight:bold; display:inline-block; text-align:center;">Hoy</a>
                </form>
            </div>

            <div style="background:white; padding:25px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.05);">
                <h3>Pacientes para el día: {fecha_agenda}</h3>
                <table style="width:100%; border-collapse:collapse; margin-top:15px;">
                    <tr style="background:#3498db; color:white;">
                        <th style="padding:12px; text-align:left;">Cédula (C.I.)</th>
                        <th style="padding:12px; text-align:left;">Nombre y Apellido</th>
                        <th style="padding:12px; text-align:left;">Edad</th>
                        <th style="padding:12px; text-align:left;">Profesión</th>
                        <th style="padding:12px; text-align:left;">Procedencia</th>
                        <th style="padding:12px; text-align:left;">Acción</th>
                    </tr>
                    {filas_html}
                </table>
            </div>
        </div>
    </body>
    </html>
    """


@app.route('/nuevo', methods=['GET', 'POST'])
def nuevo():
  if not session.get('logged_in'):
    return redirect(url_for('login'))

  if request.method == 'POST':
    cedula = request.form.get('cedula')
    nombre = request.form.get('nombre')
    nacimiento = request.form.get('nacimiento')
    sexo = request.form.get('sexo')
    telefono = request.form.get('telefono')
    profesion = request.form.get('profesion')
    direccion = request.form.get('direccion')
    alergias = request.form.get('alergias', 'Ninguna')
    antecedentes_list = request.form.getlist('antecedentes')
    antecedentes_str = ', '.join(antecedentes_list)
    fecha_cita = request.form.get(
        'fecha_cita', datetime.today().strftime('%Y-%m-%d')
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO pacientes (cedula, nombre, nacimiento, sexo, telefono,'
        ' profesion, direccion, alergias, antecedentes, fecha_cita, es_estudio)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)',
        (
            cedula,
            nombre,
            nacimiento,
            sexo,
            telefono,
            profesion,
            direccion,
            alergias,
            antecedentes_str,
            fecha_cita,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for('index', fecha=fecha_cita))

  return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Nuevo Ingreso - CardioSys</title></head>
    <body style="font-family:Segoe UI; background:#f4f7f6; margin:0; display:flex; height:100vh;">
        <div style="width:260px; background:#1e293b; color:white; padding:20px; box-sizing:border-box; display:flex; flex-direction:column;">
            <h2 style="color:white; margin-top:0; margin-bottom:5px;">CardioSys 1.0</h2>
            <p style="color:#38bdf8; font-size:16px; font-weight:bold; margin-top:0; margin-bottom:25px; line-height:1.3;">Dra. Cecilia Marecos</p>
            <ul style="list-style:none; padding:0; margin-top:0; flex:1;">
                <li style="margin:15px 0;"><a href="/" style="color:white; text-decoration:none;">📋 Agenda Diaria</a></li>
                <li style="margin:15px 0;"><a href="/nuevo" style="color:#38bdf8; text-decoration:none; font-weight:bold;">➕ Nuevo Ingreso</a></li>
                <li style="margin:15px 0;"><a href="/lista-pacientes" style="color:white; text-decoration:none;">👥 Lista de Pacientes</a></li>
                <li style="margin:15px 0;"><a href="/plantilla-ovelar" style="color:white; text-decoration:none;">🏥 Plantilla Ovelar</a></li>
                <li style="margin:15px 0;"><a href="/plantilla-san-carlos" style="color:white; text-decoration:none;">🏥 Plantilla San Carlos</a></li>
                <li style="margin:15px 0;"><a href="/estudios-recientes" style="color:white; text-decoration:none;">📁 Lista de Estudios</a></li>
                <li style="margin:15px 0;"><a href="/cambiar-contrasena" style="color:white; text-decoration:none;">🔑 Cambiar Contraseña</a></li>
            </ul>
            <div style="margin-bottom:20px;">
                <a href="/backup" style="display:block; background:#e67e22; color:white; padding:12px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold;">💾 Backup Manual</a>
                <a href="/logout" style="display:block; background:#ef4444; color:white; padding:8px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold; margin-top:10px; font-size:13px;">🚪 Cerrar Sesión</a>
            </div>
        </div>
        <div style="flex:1; padding:40px; overflow-y:auto;">
            <a href="/" style="display:inline-block; margin-bottom:15px; color:#3498db; text-decoration:none; font-weight:bold;">⬅ Volver al Panel</a>
            <div style="background:white; padding:30px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.05); max-width:700px;">
                <h2 style="color:#2c3e50; margin-top:0;">Ficha de Nuevo Ingreso y Factores de Riesgo</h2>
                <form method="POST">
                    <div style="display:flex; gap:15px;">
                        <div style="flex:1;"><label style="font-weight:bold; font-size:13px;">Fecha de Cita (Agenda):</label><input type="date" name="fecha_cita" value="{datetime.today().strftime('%Y-%m-%d')}" required style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></div>
                        <div style="flex:1;"><label style="font-weight:bold; font-size:13px;">Cédula / C.I.:</label><input type="text" name="cedula" placeholder="Ej: 1321854" required style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></div>
                    </div>
                    <div style="display:flex; gap:15px;">
                        <div style="flex:2;"><label style="font-weight:bold; font-size:13px;">Nombre Completo:</label><input type="text" name="nombre" placeholder="Nombre y Apellido" required style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></div>
                        <div style="flex:1;"><label style="font-weight:bold; font-size:13px;">Fecha de Nacimiento:</label><input type="date" name="nacimiento" required style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></div>
                    </div>
                    <div style="display:flex; gap:15px;">
                        <div style="flex:1;">
                            <label style="font-weight:bold; font-size:13px;">Sexo Biológico:</label>
                            <select name="sexo" required style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;">
                                <option value="">Seleccionar...</option>
                                <option value="Hombre">Hombre</option>
                                <option value="Mujer">Mujer</option>
                            </select>
                        </div>
                        <div style="flex:1;"><label style="font-weight:bold; font-size:13px;">Teléfono:</label><input type="text" name="telefono" placeholder="Ej: 0987546321" style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></div>
                        <div style="flex:1;"><label style="font-weight:bold; font-size:13px;">Profesión:</label><input type="text" name="profesion" placeholder="Ej: Docente..." style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></div>
                    </div>
                    <label style="font-weight:bold; font-size:13px;">Dirección / Procedencia:</label>
                    <input type="text" name="direccion" placeholder="Ej: Ciudad del Este" style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;">
                    
                    <label style="font-weight:bold; font-size:13px; color:#c0392b;">⚠️ Alergias Medicamentosas:</label>
                    <input type="text" name="alergias" placeholder="Ej: Alergia a la Aspirina (Dejar en blanco si no tiene)" style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #e74c3c; border-radius:4px; box-sizing:border-box;">

                    <label style="font-weight:bold; font-size:13px; display:block; margin-bottom:8px;">Antecedentes y Factores de Riesgo Cardiovascular:</label>
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px; background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #e2e8f0; margin-bottom:20px;">
                        <label><input type="checkbox" name="antecedentes" value="HTA"> Hipertensión Arterial (HTA)</label>
                        <label><input type="checkbox" name="antecedentes" value="Diabetes"> Diabetes Mellitus (DBM)</label>
                        <label><input type="checkbox" name="antecedentes" value="Dislipidemia"> Dislipidemia</label>
                        <label><input type="checkbox" name="antecedentes" value="Tabaquismo"> Tabaquismo Activo</label>
                        <label><input type="checkbox" name="antecedentes" value="Enf. Coronaria"> Enfermedad Coronaria Previa</label>
                        <label><input type="checkbox" name="antecedentes" value="IAM previo"> IAM previo</label>
                        <label><input type="checkbox" name="antecedentes" value="Angioplastia"> Angioplastia / Stent</label>
                        <label><input type="checkbox" name="antecedentes" value="CRM"> Cirugía de Revascularización (CRM)</label>
                    </div>

                    <button type="submit" style="background:#2ecc71; color:white; border:none; padding:12px 20px; border-radius:4px; font-weight:bold; cursor:pointer; width:100%;">Guardar Paciente y Agendar</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """


PLANTILLAS_DATOS = {
    'NORMAL': {
        'descripcion': (
            'Ventrículo izquierdo de dimensiones conservadas. Espesor parietal'
            ' aumentado.\nFunción sistólica ventricular izquierda,'
            ' conservada.\nMotilidad segmentaria normal en reposo.\nVálvula'
            ' aórtica, apertura y movilidad normal.\nVálvula mitral, apertura y'
            ' movilidad normal.\nAurícula izquierda dilatación leve. Cavidades'
            ' derechas de dimensiones normales.\nSeptum interauricular e'
            ' interventricular íntegrros.\nAorta ascendente y cayado de'
            ' diámetros normales.\nVena cava inferior, no dilatada, con colapso'
            ' inspiratorio > 50%.\nPericardio, normal.'
        ),
        'conclusion': (
            'Dimensiones conservadas del ventriculo izquierdo. Función'
            ' sistolica conservada.\nContractilidad normal en reposo. Cavidades'
            ' derechas conservadas.\nAuricula izquierda no dilatada.\nFunción'
            ' diastólica normal, sin aumento de presiones de'
            ' llenado.\nVálvulas sin alteraciones de consideración. Escape'
            ' tricuspideo leve.\nPresiones pulmonares estimadas normales.\nVCI'
            ' no dilatada con colapso inspiratorio mayor al 50%.'
        ),
    },
    'AI-HVI': {
        'descripcion': (
            'Ventrículo izquierdo de dimensiones conservadas. Espesor parietal'
            ' aumentado.\nFunción sistólica ventricular izquierda,'
            ' conservada.\nMotilidad segmentaria, normal en reposo.\nVálvula'
            ' aórtica, esclerosis, apertura conservada.\nVálvula mitral,'
            ' esclerosis, apertura conservada.\nAurícula izquierda dilatación'
            ' leve. Cavidades derechas de dimensiones normales.\nSeptum'
            ' interauricular e interventricular íntegrros.\nAorta ascendente y'
            ' cayado de diámetros normales.\nVena cava inferior, no dilatada,'
            ' con colapso inspiratorio > 50%.\nPericardio, normal.'
        ),
        'conclusion': (
            'Hipertrofia concéntrica leve del ventriculo izquierdo. Función'
            ' sistolica conservada.\nContractilidad conservada en'
            ' reposo.\nAuricula izquierda con dilatación leve.\nDisfunción'
            ' diastólica tipo 1, sin aumento de presiones de'
            ' llenado.\nInsuficiencia mitral leve. Escape tricuspideo'
            ' leve.\nPresiones pulmonares estimadas normales.\nVCI no dilatada'
            ' con colapso inspiratorio mayor al 50%.'
        ),
    },
    'ESCLERO': {
        'descripcion': (
            'Ventrículo izquierdo de dimensiones conservadas. Espesor parietal'
            ' aumentado.\nFunción sistólica ventricular izquierda,'
            ' conservada.\nMotilidad segmentaria, normal en reposo.\nVálvula'
            ' aórtica, esclerosis, apertura conservada.\nVálvula mitral,'
            ' esclerosis, apertura conservada.\nAurícula izquierda dilatación'
            ' leve. Cavidades derechas de dimensiones normales.\nSeptum'
            ' interauricular e interventricular íntegrros.\nAorta ascendente y'
            ' cayado de diámetros normales.\nVena cava inferior, no dilatada,'
            ' con colapso inspiratorio > 50%.\nPericardio, normal.'
        ),
        'conclusion': (
            'Hipertrofia concéntrica leve del ventriculo izquierdo. Función'
            ' sistolica conservada.\nContractilidad conservada en'
            ' reposo.\nAuricula izquierda con dilatación leve.\nDisfunción'
            ' diastólica tipo 1, sin aumento de presiones de'
            ' llenado.\nEsclerosis mitroaortica degenerativa. Insuficiencia'
            ' tricuspidea leve.\nPresiones pulmonares estimadas normales.\nVCI'
            ' no dilatada con colapso inspiratorio mayor al 50%.'
        ),
    },
    'FA': {
        'descripcion': (
            'Ventrículo izquierdo de dimensiones conservadas. Espesor parietal'
            ' aumentado.\nFunción sistólica ventricular izquierda,'
            ' conservada.\nMotilidad segmentaria, normal en reposo.\nVálvula'
            ' aórtica, esclerosis, apertura conservada.\nVálvula mitral,'
            ' esclerosis, apertura conservada.\nAurícula izquierda dilatación'
            ' leve. Cavidades derechas de dimensiones normales.\nSeptum'
            ' interauricular e interventricular íntegrros.\nAorta ascendente y'
            ' cayado de diámetros normales.\nVena cava inferior, no dilatada,'
            ' con colapso inspiratorio > 50%.\nPericardio, normal.'
        ),
        'conclusion': (
            'Hipertrofia concéntrica leve del ventriculo izquierdo. Función'
            ' sistolica conservada.\nContractilidad conservada en'
            ' reposo.\nAuricula izquierda con dilatación leve.\nLlenado del VI'
            ' de onda única por arritmia.\nEsclerosis mitroaortica'
            ' degenerativa. Insuficiencia tricuspidea leve.\nPresiones'
            ' pulmonares estimadas normales.\nVCI no dilatada con colapcol'
            ' inspiratorio mayor al 50%.'
        ),
    },
    'DILATADA': {
        'descripcion': (
            'Ventrículo izquierdo de dimensiones aumentadas. Espesor parietal'
            ' conservado.\nFunción sistólica ventricular izquierda,'
            ' deteriorada.\nMotilidad segmentaria, hipoquinesia difusa.\nVálvula'
            ' aórtica, apertura y movilidad conservada.\nVálvula mitral, apertura'
            ' y movilidad conservada.\nAurícula izquierda dilatación severa.'
            ' Cavidades derechas de dimensiones normales.\nSeptum interauricular'
            ' e interventricular íntegrros.\nAorta ascendente y cayado de'
            ' diámetros aumentados.\nVena cava inferior, no dilatada, con'
            ' colapso inspiratorio > 50%.\nPericardio, normal.'
        ),
        'conclusion': (
            'Dilatación excéntrica del ventriculo izquierdo. Función sistolica'
            ' con deterioro severo.\nHipoquinesia difusa.\nDilatación severa de'
            ' ambas auriculas.\nDisfunción diastólica tipo 3, con aumento de'
            ' presiones de llenado.\nInsuficiencia mitral y tricuspidea ambas'
            ' de grado moderado.\nHipertensión pulmonar leve.\nVCI no dilatada'
            ' con colapso inspiratorio disminuido.'
        ),
    },
    'EST AORT': {
        'descripcion': (
            'Ventrículo izquierdo de dimensiones conservadas. Espesor parietal'
            ' aumentado.\nFunción sistólica ventricular izquierda,'
            ' conservada.\nMotilidad segmentaria, normal en reposo.\nVálvula'
            ' aórtica, esclerocalcificada, apertura reducida.\nVálvula mitral,'
            ' esclerosis, apertura conservada.\nAurícula izquierda dilatación'
            ' leve. Cavidades derechas de dimensiones normales.\nSeptum'
            ' interauricular e interventricular íntegrros.\nAorta ascendente y'
            ' cayado de diámetros normales.\nVena cava inferior, no dilatada,'
            ' con colapso inspiratorio > 50%.\nPericardio, normal.'
        ),
        'conclusion': (
            'Hipertrofia concéntrica leve del ventriculo izquierdo. Función'
            ' sistolica conservada.\nContractilidad conservada en'
            ' reposo.\nAuricula izquierda con dilatación leve.\nDisfunción'
            ' diastólica tipo 1, sin aumento de presiones de'
            ' llenado.\nEsclerosis mitroaortica degenerativa. Estenosis'
            ' aórtica moderada. Insuficiencia tricuspidea leve.\nPresiones'
            ' pulmonares estimadas normales.\nVCI no dilatada con colapso'
            ' inspiratorio mayor al 50%.'
        ),
    },
    'COMPLETO': {
        'descripcion': (
            'Ventrículo izquierdo de dimensiones conservadas. Espesor parietal'
            ' aumentado.\nFunción sistólica ventricular izquierda,'
            ' conservada.\nMotilidad segmentaria normal en reposo.\nVálvula'
            ' aórtica, apertura y movilidad normal.\nVálvula mitral, apertura y'
            ' movilidad normal.\nAurícula izquierda dilatación leve. Cavidades'
            ' derechas de dimensiones normales.\nSeptum interauricular e'
            ' interventricular íntegrros.\nAorta ascendente y cayado de'
            ' diámetros normales.\nVena cava inferior, no dilatada, con colapso'
            ' inspiratorio > 50%.\nPericardio, normal.'
        ),
        'conclusion': (
            'Hipertrofia concéntrica leve del ventriculo izquierdo. Función'
            ' sistolica conservada.\nContractilidad normal en reposo. Cavidades'
            ' derechas conservadas.\nAuricula izquierda no dilatada.\nFunción'
            ' diastólica normal, sin aumento de presiones de'
            ' llenado.\nVálvulas sin alteraciones de consideración. Escape'
            ' tricuspideo leve.\nPresiones pulmonares estimadas normales.\nVCI'
            ' no dilatada con colapso inspiratorio mayor al 50%.'
        ),
    },
}


@app.route('/plantilla-ovelar', methods=['GET', 'POST'])
def plantilla_ovelar():
  if not session.get('logged_in'):
    return redirect(url_for('login'))

  if request.method == 'POST':
    cedula = request.form.get('cedula', 'S/N')
    nombre = request.form.get('nombre_apellido', 'Paciente')
    edad = request.form.get('edad', '0')
    sexo = request.form.get('sexo', 'Femenino')
    motivo = request.form.get('motivo', 'Control')
    pestaña_activa = request.form.get('pestana_activa', 'NORMAL')

    dims = {
        'ao': request.form.get(f'{pestaña_activa}_ao', ''),
        'ai': request.form.get(f'{pestaña_activa}_ai', ''),
        'vol_ai': request.form.get(f'{pestaña_activa}_vol_ai', ''),
        'vol_ai_sc': request.form.get(f'{pestaña_activa}_vol_ai_sc', ''),
        'vd': request.form.get(f'{pestaña_activa}_vd', ''),
        'vi_diastole': request.form.get(f'{pestaña_activa}_vi_diastole', ''),
        'vi_sistole': request.form.get(f'{pestaña_activa}_vi_sistole', ''),
        'vol_diastole_vi': request.form.get(
            f'{pestaña_activa}_vol_diastole_vi', ''
        ),
        'vol_sistole_vi': request.form.get(
            f'{pestaña_activa}_vol_sistole_vi', ''
        ),
        'facortamiento': request.form.get(
            f'{pestaña_activa}_facortamiento', ''
        ),
        'feyeccion': request.form.get(f'{pestaña_activa}_feyeccion', ''),
        'siv': request.form.get(f'{pestaña_activa}_siv', ''),
        'ppvi': request.form.get(f'{pestaña_activa}_ppvi', ''),
        'epr': request.form.get(f'{pestaña_activa}_epr', ''),
        'masavi': request.form.get(f'{pestaña_activa}_masavi', ''),
        'imasa_vi': request.form.get(f'{pestaña_activa}_imasa_vi', ''),
    }

    doppler = {
        'flujo_mitral': request.form.get(f'{pestaña_activa}_flujo_mitral', ''),
        'onda_e': request.form.get(f'{pestaña_activa}_onda_e', ''),
        'onda_a': request.form.get(f'{pestaña_activa}_onda_a', ''),
        'ea': request.form.get(f'{pestaña_activa}_ea', ''),
        'tde': request.form.get(f'{pestaña_activa}_tde', ''),
        'flujo_aortico': request.form.get(f'{pestaña_activa}_flujo_aortico', ''),
        'vel_max': request.form.get(f'{pestaña_activa}_vel_max', ''),
        'grad_pico': request.form.get(f'{pestaña_activa}_grad_pico', ''),
        'grad_medio': request.form.get(f'{pestaña_activa}_grad_medio', ''),
        'area_aortica': request.form.get(f'{pestaña_activa}_area_aortica', ''),
        'thp': request.form.get(f'{pestaña_activa}_thp', ''),
        'flujo_tricuspideo': request.form.get(
            f'{pestaña_activa}_flujo_tricuspideo', ''
        ),
        'grad_vd_ad': request.form.get(f'{pestaña_activa}_grad_vd_ad', ''),
        'flujo_pulmonar': request.form.get(
            f'{pestaña_activa}_flujo_pulmonar', ''
        ),
        'pa_sistolica': request.form.get(f'{pestaña_activa}_pa_sistolica', ''),
    }

    desc = request.form.get(f'{pestaña_activa}_desc', '')
    conc = request.form.get(f'{pestaña_activa}_conc', '')

    pdf_filename = generar_pdf_ecocardiograma(
        'Sanatorio Ovelar',
        cedula,
        nombre,
        edad,
        sexo,
        motivo,
        pestaña_activa,
        dims,
        doppler,
        desc,
        conc,
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, es_estudio FROM pacientes WHERE cedula = ?', (cedula,))
    p_row = cursor.fetchone()
    if p_row:
      p_id = p_row[0]
    else:
      cursor.execute(
          'INSERT INTO pacientes (cedula, nombre, sexo, fecha_cita, es_estudio)'
          ' VALUES (?, ?, ?, ?, 1)',
          (cedula, nombre, sexo, datetime.today().strftime('%Y-%m-%d')),
      )
      p_id = cursor.lastrowid

    cursor.execute(
        'INSERT INTO estudios (paciente_id, nombre_estudio, archivo, fecha,'
        ' sanatorio, tipo_plantilla, contenido_editable) VALUES (?, ?, ?, ?,'
        ' ?, ?, ?)',
        (
            p_id,
            f'Ecocardiograma ({pestaña_activa})',
            pdf_filename,
            datetime.today().strftime('%Y-%m-%d %H:%M'),
            'Sanatorio Ovelar',
            pestaña_activa,
            conc,
        ),
    )
    conn.commit()
    conn.close()

    return redirect(url_for('imprimir_pdf', filename=pdf_filename))

  return renderizar_plantilla_html('Sanatorio Ovelar')


@app.route('/plantilla-san-carlos', methods=['GET', 'POST'])
def plantilla_san_carlos():
  if not session.get('logged_in'):
    return redirect(url_for('login'))

  if request.method == 'POST':
    cedula = request.form.get('cedula', 'S/N')
    nombre = request.form.get('nombre_apellido', 'Paciente')
    edad = request.form.get('edad', '0')
    sexo = request.form.get('sexo', 'Femenino')
    motivo = request.form.get('motivo', 'Control')
    pestaña_activa = request.form.get('pestana_activa', 'NORMAL')

    dims = {
        'ao': request.form.get(f'{pestaña_activa}_ao', ''),
        'ai': request.form.get(f'{pestaña_activa}_ai', ''),
        'vol_ai': request.form.get(f'{pestaña_activa}_vol_ai', ''),
        'vol_ai_sc': request.form.get(f'{pestaña_activa}_vol_ai_sc', ''),
        'vd': request.form.get(f'{pestaña_activa}_vd', ''),
        'vi_diastole': request.form.get(f'{pestaña_activa}_vi_diastole', ''),
        'vi_sistole': request.form.get(f'{pestaña_activa}_vi_sistole', ''),
        'vol_diastole_vi': request.form.get(
            f'{pestaña_activa}_vol_diastole_vi', ''
        ),
        'vol_sistole_vi': request.form.get(
            f'{pestaña_activa}_vol_sistole_vi', ''
        ),
        'facortamiento': request.form.get(
            f'{pestaña_activa}_facortamiento', ''
        ),
        'feyeccion': request.form.get(f'{pestaña_activa}_feyeccion', ''),
        'siv': request.form.get(f'{pestaña_activa}_siv', ''),
        'ppvi': request.form.get(f'{pestaña_activa}_ppvi', ''),
        'epr': request.form.get(f'{pestaña_activa}_epr', ''),
        'masavi': request.form.get(f'{pestaña_activa}_masavi', ''),
        'imasa_vi': request.form.get(f'{pestaña_activa}_imasa_vi', ''),
    }

    doppler = {
        'flujo_mitral': request.form.get(f'{pestaña_activa}_flujo_mitral', ''),
        'onda_e': request.form.get(f'{pestaña_activa}_onda_e', ''),
        'onda_a': request.form.get(f'{pestaña_activa}_onda_a', ''),
        'ea': request.form.get(f'{pestaña_activa}_ea', ''),
        'tde': request.form.get(f'{pestaña_activa}_tde', ''),
        'flujo_aortico': request.form.get(f'{pestaña_activa}_flujo_aortico', ''),
        'vel_max': request.form.get(f'{pestaña_activa}_vel_max', ''),
        'grad_pico': request.form.get(f'{pestaña_activa}_grad_pico', ''),
        'grad_medio': request.form.get(f'{pestaña_activa}_grad_medio', ''),
        'area_aortica': request.form.get(f'{pestaña_activa}_area_aortica', ''),
        'thp': request.form.get(f'{pestaña_activa}_thp', ''),
        'flujo_tricuspideo': request.form.get(
            f'{pestaña_activa}_flujo_tricuspideo', ''
        ),
        'grad_vd_ad': request.form.get(f'{pestaña_activa}_grad_vd_ad', ''),
        'flujo_pulmonar': request.form.get(
            f'{pestaña_activa}_flujo_pulmonar', ''
        ),
        'pa_sistolica': request.form.get(f'{pestaña_activa}_pa_sistolica', ''),
    }

    desc = request.form.get(f'{pestaña_activa}_desc', '')
    conc = request.form.get(f'{pestaña_activa}_conc', '')

    pdf_filename = generar_pdf_ecocardiograma(
        'Sanatorio San Carlos',
        cedula,
        nombre,
        edad,
        sexo,
        motivo,
        pestaña_activa,
        dims,
        doppler,
        desc,
        conc,
    )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, es_estudio FROM pacientes WHERE cedula = ?', (cedula,))
    p_row = cursor.fetchone()
    if p_row:
      p_id = p_row[0]
    else:
      cursor.execute(
          'INSERT INTO pacientes (cedula, nombre, sexo, fecha_cita, es_estudio)'
          ' VALUES (?, ?, ?, ?, 1)',
          (cedula, nombre, sexo, datetime.today().strftime('%Y-%m-%d')),
      )
      p_id = cursor.lastrowid

    cursor.execute(
        'INSERT INTO estudios (paciente_id, nombre_estudio, archivo, fecha,'
        ' sanatorio, tipo_plantilla, contenido_editable) VALUES (?, ?, ?, ?,'
        ' ?, ?, ?)',
        (
            p_id,
            f'Ecocardiograma ({pestaña_activa})',
            pdf_filename,
            datetime.today().strftime('%Y-%m-%d %H:%M'),
            'Sanatorio San Carlos',
            pestaña_activa,
            conc,
        ),
    )
    conn.commit()
    conn.close()

    return redirect(url_for('imprimir_pdf', filename=pdf_filename))

  return renderizar_plantilla_html('Sanatorio San Carlos')


@app.route('/imprimir/<filename>')
def imprimir_pdf(filename):
  if not session.get('logged_in'):
    return redirect(url_for('login'))
  return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Imprimir Informe</title></head>
    <body style="font-family:Segoe UI; text-align:center; padding:50px; background:#f4f7f6;">
        <div style="background:white; padding:30px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.1); display:inline-block;">
            <h2 style="color:#107c41;">✅ ¡Informe Guardado e Impreso con Éxito!</h2>
            <p>El PDF ha sido generado y enviado a imprimir automáticamente.</p>
            <div style="margin-top:20px; display:flex; gap:15px; justify-content:center;">
                <a href="/uploads/{filename}" target="_blank" style="background:#3498db; color:white; padding:10px 20px; text-decoration:none; border-radius:4px; font-weight:bold;">📄 Ver / Imprimir PDF</a>
                <a href="/" style="background:#64748b; color:white; padding:10px 20px; text-decoration:none; border-radius:4px; font-weight:bold;">🏠 Volver al Panel</a>
            </div>
        </div>
        <script>
            let win = window.open('/uploads/{filename}', '_blank');
            win.onload = function() {{
                win.print();
            }};
        </script>
    </body>
    </html>
    """


def renderizar_plantilla_html(nombre_sanatorio):
  sheets = list(PLANTILLAS_DATOS.keys())
  tabs_html = ''
  pages_html = ''

  for idx, sheetname in enumerate(sheets):
    active_cls = 'active' if idx == 0 else ''
    tabs_html += f'<button type="button" class="excel-tab {active_cls}" onclick="cambiarPestana(event, \'{sheetname}\')">{sheetname}</button>'

    data = PLANTILLAS_DATOS[sheetname]

    pages_html += f"""
        <div id="{sheetname}" class="sheet-page {active_cls}">
            <div style="background:#f8fafc; padding:8px 12px; border:1px solid #cbd5e1; border-bottom:none; font-weight:bold; color:#107c41; font-size:13px;">
                📑 Pestaña Activa: {sheetname} (Plantilla oficial integrada con valores de referencia)
            </div>
            <div style="padding:15px; border:2px solid #107c41; background:#fff; border-radius:4px;">
                
                <!-- 1. DIMENSIONES -->
                <h3 style="color:#1e3a8a; margin-top:0; border-bottom:2px solid #e2e8f0; padding-bottom:5px;">1. Dimensiones</h3>
                <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; margin-bottom:20px;">
                    <div><label style="font-size:11px; font-weight:bold;">Aorta (AO) [v.n.: 20-37 mm]:</label><input type="text" name="{sheetname}_ao" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Aurícula Izquierda (AI) [v.n.: 20-40 mm]:</label><input type="text" name="{sheetname}_ai" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Volumen AI [ml]:</label><input type="text" name="{sheetname}_vol_ai" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Volumen AI/SC [v.n.: 16-34 ml/m²]:</label><input type="text" name="{sheetname}_vol_ai_sc" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    
                    <div><label style="font-size:11px; font-weight:bold;">Ventrículo Derecho [v.n.: 09-26 mm]:</label><input type="text" name="{sheetname}_vd" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">VI Diástole [v.n.: 37-56 mm]:</label><input type="text" name="{sheetname}_vi_diastole" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">VI Sístole [v.n.: 27-37 mm]:</label><input type="text" name="{sheetname}_vi_sistole" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Vol. Fin Diástole VI [ml/m²]:</label><input type="text" name="{sheetname}_vol_diastole_vi" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>

                    <div><label style="font-size:11px; font-weight:bold;">Vol. Fin Sístole VI [ml/m²]:</label><input type="text" name="{sheetname}_vol_sistole_vi" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Fracción Acortamiento [v.n.: 28-40%]:</label><input type="text" name="{sheetname}_facortamiento" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Fracción Eyección [v.n.: 55-70%]:</label><input type="text" name="{sheetname}_feyeccion" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Tabique SIV [v.n.: 7-11 mm]:</label><input type="text" name="{sheetname}_siv" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>

                    <div><label style="font-size:11px; font-weight:bold;">Pared Posterior [v.n.: 7-11 mm]:</label><input type="text" name="{sheetname}_ppvi" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Espesor Parietal Relativo:</label><input type="text" name="{sheetname}_epr" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Masa del VI [g]:</label><input type="text" name="{sheetname}_masavi" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Índice Masa VI [v.n.: <115/<95]:</label><input type="text" name="{sheetname}_imasa_vi" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                </div>

                <!-- 2. DESCRIPCIÓN -->
                <h3 style="color:#1e3a8a; margin-top:20px; border-bottom:2px solid #e2e8f0; padding-bottom:5px;">2. Descripción ({sheetname}):</h3>
                <textarea name="{sheetname}_desc" rows="10" style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:4px; font-family:Segoe UI; font-size:13px; box-sizing:border-box;">{data['descripcion']}</textarea>

                <!-- 3. EXAMEN DOPPLER -->
                <h3 style="color:#1e3a8a; margin-top:20px; border-bottom:2px solid #e2e8f0; padding-bottom:5px;">3. Examen Doppler</h3>
                <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; margin-bottom:20px;">
                    <div><label style="font-size:11px; font-weight:bold;">Flujo Mitral:</label><input type="text" name="{sheetname}_flujo_mitral" value="" placeholder="Ej: Insuficiencia leve." style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Onda E [m/seg]:</label><input type="text" name="{sheetname}_onda_e" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Onda A [m/seg]:</label><input type="text" name="{sheetname}_onda_a" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Relación E/A:</label><input type="text" name="{sheetname}_ea" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>

                    <div><label style="font-size:11px; font-weight:bold;">TDE [ms]:</label><input type="text" name="{sheetname}_tde" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Flujo Aórtico:</label><input type="text" name="{sheetname}_flujo_aortico" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Velocidad Máxima [m/seg]:</label><input type="text" name="{sheetname}_vel_max" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Gradiente Pico AO [mmHg]:</label><input type="text" name="{sheetname}_grad_pico" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>

                    <div><label style="font-size:11px; font-weight:bold;">Gradiente Medio [mmHg]:</label><input type="text" name="{sheetname}_grad_medio" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Área Aórtica [cm2]:</label><input type="text" name="{sheetname}_area_aortica" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">THP [ms]:</label><input type="text" name="{sheetname}_thp" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Flujo Tricuspídeo:</label><input type="text" name="{sheetname}_flujo_tricuspideo" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>

                    <div><label style="font-size:11px; font-weight:bold;">Gradiente VD/AD [mmHg]:</label><input type="text" name="{sheetname}_grad_vd_ad" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">Flujo Pulmonar:</label><input type="text" name="{sheetname}_flujo_pulmonar" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                    <div><label style="font-size:11px; font-weight:bold;">PA Pulmonar Sistólica [mmHg]:</label><input type="text" name="{sheetname}_pa_sistolica" value="" style="width:100%; padding:6px; border:1px solid #ccc; border-radius:4px;"></div>
                </div>

                <!-- 4. CONCLUSIÓN -->
                <h3 style="color:#1e3a8a; margin-top:20px; border-bottom:2px solid #e2e8f0; padding-bottom:5px;">4. Conclusión ({sheetname}):</h3>
                <textarea name="{sheetname}_conc" rows="8" style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:4px; font-family:Segoe UI; font-size:13px; box-sizing:border-box;">{data['conclusion']}</textarea>
            </div>
        </div>
        """

  return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Plantilla {nombre_sanatorio} - CardioSys</title>
        <style>
            .excel-window {{
                background: #ffffff;
                border: 2px solid #107c41;
                border-radius: 4px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                display: flex;
                flex-direction: column;
                height: 84vh;
                max-width: 1150px;
            }}
            .excel-topbar {{
                background: #f8fafc;
                padding: 12px 20px;
                border-bottom: 1px solid #cbd5e1;
                display: flex;
                align-items: center;
                gap: 15px;
                flex-wrap: wrap;
            }}
            .excel-content {{
                flex: 1;
                padding: 15px;
                overflow-y: auto;
                background: #ffffff;
            }}
            .tab-bar {{
                background: #f3f4f6;
                display: flex;
                gap: 1px;
                padding: 8px 10px 0 10px;
                border-top: 1px solid #d1d5db;
                overflow-x: auto;
            }}
            .excel-tab {{
                background: #e5e7eb;
                color: #374151;
                border: 1px solid #d1d5db;
                border-bottom: none;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 12px;
                cursor: pointer;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            .excel-tab.active {{
                background: #ffffff;
                color: #107c41;
                border-bottom: 2px solid #ffffff;
                position: relative;
                top: 1px;
            }}
            .sheet-page {{
                display: none;
            }}
            .sheet-page.active {{
                display: block;
            }}
        </style>
        <script>
            let pestanaActual = 'NORMAL';
            function cambiarPestana(evt, sheetId) {{
                let pages = document.getElementsByClassName('sheet-page');
                for (let p of pages) {{ p.classList.remove('active'); }}
                let tabs = document.getElementsByClassName('excel-tab');
                for (let t of tabs) {{ t.classList.remove('active'); }}
                document.getElementById(sheetId).classList.add('active');
                evt.currentTarget.classList.add('active');
                pestanaActual = sheetId;
                document.getElementById('input_pestana_activa').value = sheetId;
            }}
        </script>
    </head>
    <body style="font-family:Segoe UI; background:#f4f7f6; margin:0; display:flex; height:100vh;">
        <div style="width:260px; background:#1e293b; color:white; padding:20px; box-sizing:border-box; display:flex; flex-direction:column;">
            <h2 style="color:white; margin-top:0; margin-bottom:5px;">CardioSys 1.0</h2>
            <p style="color:#38bdf8; font-size:16px; font-weight:bold; margin-top:0; margin-bottom:25px; line-height:1.3;">Dra. Cecilia Marecos</p>
            <ul style="list-style:none; padding:0; margin-top:0; flex:1;">
                <li style="margin:15px 0;"><a href="/" style="color:white; text-decoration:none;">📋 Agenda Diaria</a></li>
                <li style="margin:15px 0;"><a href="/nuevo" style="color:white; text-decoration:none;">➕ Nuevo Ingreso</a></li>
                <li style="margin:15px 0;"><a href="/lista-pacientes" style="color:white; text-decoration:none;">👥 Lista de Pacientes</a></li>
                <li style="margin:15px 0;"><a href="/plantilla-ovelar" style="color:{'#38bdf8' if 'Ovelar' in nombre_sanatorio else 'white'}; text-decoration:none; {'font-weight:bold;' if 'Ovelar' in nombre_sanatorio else ''}">🏥 Plantilla Ovelar</a></li>
                <li style="margin:15px 0;"><a href="/plantilla-san-carlos" style="color:{'#38bdf8' if 'Carlos' in nombre_sanatorio else 'white'}; text-decoration:none; {'font-weight:bold;' if 'Carlos' in nombre_sanatorio else ''}">🏥 Plantilla San Carlos</a></li>
                <li style="margin:15px 0;"><a href="/estudios-recientes" style="color:white; text-decoration:none;">📁 Lista de Estudios</a></li>
                <li style="margin:15px 0;"><a href="/cambiar-contrasena" style="color:white; text-decoration:none;">🔑 Cambiar Contraseña</a></li>
            </ul>
            <div style="margin-bottom:20px;">
                <a href="/backup" style="display:block; background:#e67e22; color:white; padding:12px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold;">💾 Backup Manual</a>
                <a href="/logout" style="display:block; background:#ef4444; color:white; padding:8px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold; margin-top:10px; font-size:13px;">🚪 Cerrar Sesión</a>
            </div>
        </div>
        <div style="flex:1; padding:30px; overflow-y:auto;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <h1 style="margin:0;">🏥 Plantilla Ecocardiograma - {nombre_sanatorio}</h1>
                <div style="background:{'#107c41' if 'Ovelar' in nombre_sanatorio else '#0284c7'}; color:white; padding:8px 15px; border-radius:6px; font-weight:bold; font-size:14px;">
                    {nombre_sanatorio}
                </div>
            </div>
            
            <form method="POST">
                <input type="hidden" id="input_pestana_activa" name="pestana_activa" value="NORMAL">
                <div class="excel-window">
                    <!-- ENCABEZADO SUPERIOR EXACTO: Cédula, Nombre y Apellido, Edad, Sexo, Motivo -->
                    <div class="excel-topbar">
                        <div style="flex: 1; min-width: 120px;">
                            <label style="font-weight: bold; font-size: 11px; color: #334155;">Cédula (C.I.):</label>
                            <input type="text" name="cedula" placeholder="Ej: 3789170" required style="width: 100%; padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 12px;">
                        </div>
                        <div style="flex: 2; min-width: 220px;">
                            <label style="font-weight: bold; font-size: 11px; color: #334155;">Nombre y Apellido:</label>
                            <input type="text" name="nombre_apellido" placeholder="Nombre completo del paciente" required style="width: 100%; padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 12px;">
                        </div>
                        <div style="flex: 0.8; min-width: 70px;">
                            <label style="font-weight: bold; font-size: 11px; color: #334155;">Edad:</label>
                            <input type="number" name="edad" placeholder="40" required style="width: 100%; padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 12px;">
                        </div>
                        <div style="flex: 1; min-width: 110px;">
                            <label style="font-weight: bold; font-size: 11px; color: #334155;">Sexo:</label>
                            <select name="sexo" required style="width: 100%; padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 12px;">
                                <option value="Femenino">Femenino</option>
                                <option value="Masculino">Masculino</option>
                            </select>
                        </div>
                        <div style="flex: 1.8; min-width: 200px;">
                            <label style="font-weight: bold; font-size: 11px; color: #334155;">Motivo:</label>
                            <input type="text" name="motivo" value="CONTROL CARDIOVASCULAR" required style="width: 100%; padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 12px;">
                        </div>
                        <div style="flex: 1; min-width: 150px; padding-top: 16px;">
                            <button type="submit" style="background:#107c41; color:white; border:none; padding:8px 15px; border-radius:4px; font-weight:bold; cursor:pointer; width:100%;">💾 Generar PDF & Imprimir</button>
                        </div>
                    </div>

                    <!-- CONTENIDO DE LAS PESTAÑAS -->
                    <div class="excel-content">
                        {pages_html}
                    </div>

                    <!-- BARRA DE PESTAÑAS INFERIOR -->
                    <div class="tab-bar">
                        {tabs_html}
                    </div>
                </div>
            </form>
        </div>
    </body>
    </html>
    """


@app.route('/estudios-recientes')
def estudios_recientes():
  if not session.get('logged_in'):
    return redirect(url_for('login'))

  conn = sqlite3.connect(db_path)
  cursor = conn.cursor()
  cursor.execute("""
        SELECT e.id, p.cedula, p.nombre, e.nombre_estudio, e.archivo, e.fecha, e.sanatorio, p.id, e.contenido_editable 
        FROM estudios e 
        JOIN pacientes p ON e.paciente_id = p.id 
        ORDER BY e.id DESC
    """)
  estudios = cursor.fetchall()
  conn.close()

  filas_estudios = ''
  for est in estudios:
    sanatorio_badge = est[6] or 'No especificado'
    badge_color = (
        '#107c41'
        if 'Ovelar' in sanatorio_badge
        else '#0284c7' if 'Carlos' in sanatorio_badge else '#64748b'
    )
    pdf_link = f'/uploads/{est[4]}' if est[4] else '#'

    filas_estudios += f"""
        <tr>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{est[5]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{est[1]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd; font-weight:bold;">{est[2]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{est[3]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;"><span style="background:{badge_color}; color:white; padding:4px 8px; border-radius:4px; font-size:12px; font-weight:bold;">{sanatorio_badge}</span></td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">
                <a href="{pdf_link}" target="_blank" style="background:#9b59b6; color:white; padding:5px 10px; text-decoration:none; border-radius:4px; font-size:12px; font-weight:bold; margin-right:5px;">📄 Ver PDF</a>
                <a href="/ficha/{est[7]}" style="background:#3498db; color:white; padding:5px 10px; text-decoration:none; border-radius:4px; font-size:12px;">Ver Ficha</a>
            </td>
        </tr>
        """
  if not filas_estudios:
    filas_estudios = (
        "<tr><td colspan='6' style='padding:15px;"
        " text-align:center;'>No hay estudios recientes registrados.</td></tr>"
    )

  return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Lista de Estudios - CardioSys</title></head>
    <body style="font-family:Segoe UI; background:#f4f7f6; margin:0; display:flex; height:100vh;">
        <div style="width:260px; background:#1e293b; color:white; padding:20px; box-sizing:border-box; display:flex; flex-direction:column;">
            <h2 style="color:white; margin-top:0; margin-bottom:5px;">CardioSys 1.0</h2>
            <p style="color:#38bdf8; font-size:16px; font-weight:bold; margin-top:0; margin-bottom:25px; line-height:1.3;">Dra. Cecilia Marecos</p>
            <ul style="list-style:none; padding:0; margin-top:0; flex:1;">
                <li style="margin:15px 0;"><a href="/" style="color:white; text-decoration:none;">📋 Agenda Diaria</a></li>
                <li style="margin:15px 0;"><a href="/nuevo" style="color:white; text-decoration:none;">➕ Nuevo Ingreso</a></li>
                <li style="margin:15px 0;"><a href="/lista-pacientes" style="color:white; text-decoration:none;">👥 Lista de Pacientes</a></li>
                <li style="margin:15px 0;"><a href="/plantilla-ovelar" style="color:white; text-decoration:none;">🏥 Plantilla Ovelar</a></li>
                <li style="margin:15px 0;"><a href="/plantilla-san-carlos" style="color:white; text-decoration:none;">🏥 Plantilla San Carlos</a></li>
                <li style="margin:15px 0;"><a href="/estudios-recientes" style="color:#38bdf8; text-decoration:none; font-weight:bold;">📁 Lista de Estudios</a></li>
                <li style="margin:15px 0;"><a href="/cambiar-contrasena" style="color:white; text-decoration:none;">🔑 Cambiar Contraseña</a></li>
            </ul>
            <div style="margin-bottom:20px;">
                <a href="/backup" style="display:block; background:#e67e22; color:white; padding:12px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold;">💾 Backup Manual</a>
                <a href="/logout" style="display:block; background:#ef4444; color:white; padding:8px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold; margin-top:10px; font-size:13px;">🚪 Cerrar Sesión</a>
            </div>
        </div>
        <div style="flex:1; padding:40px; overflow-y:auto;">
            <h1>📁 Lista General de Estudios Complementarios y PDFs</h1>
            <div style="background:white; padding:25px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.05); margin-top:20px;">
                <h3>Estudios Registrados con Identificación de Sanatorio</h3>
                <table style="width:100%; border-collapse:collapse; margin-top:15px;">
                    <tr style="background:#107c41; color:white;">
                        <th style="padding:12px; text-align:left;">Fecha de Carga</th>
                        <th style="padding:12px; text-align:left;">Cédula</th>
                        <th style="padding:12px; text-align:left;">Paciente</th>
                        <th style="padding:12px; text-align:left;">Nombre del Estudio</th>
                        <th style="padding:12px; text-align:left;">Sanatorio</th>
                        <th style="padding:12px; text-align:left;">Acción</th>
                    </tr>
                    {filas_estudios}
                </table>
            </div>
        </div>
    </body>
    </html>
    """


@app.route('/uploads/<filename>')
def uploaded_file(filename):
  if not session.get('logged_in'):
    return redirect(url_for('login'))
  return send_file(os.path.join(upload_folder, filename))


@app.route('/ficha/<int:id>', methods=['GET', 'POST'])
def ficha(id):
  if not session.get('logged_in'):
    return redirect(url_for('login'))

  conn = sqlite3.connect(db_path)
  cursor = conn.cursor()

  if request.method == 'POST':
    accion = request.form.get('accion')
    if accion == 'guardar_antecedentes':
      nuevo_ant = request.form.get('antecedentes_base', '')
      cursor.execute(
          'UPDATE pacientes SET antecedentes = ? WHERE id = ?', (nuevo_ant, id)
      )
      conn.commit()
    elif accion == 'nueva_consulta':
      fecha_cons = datetime.today().strftime('%Y-%m-%d %H:%M')
      ant_cons = request.form.get('antecedentes_consulta', '')
      motivo = request.form.get('motivo', '')
      consulta_actual = request.form.get('consulta_actual', '')
      pa = request.form.get('pa', '')
      fc = request.form.get('fc', '')
      peso = request.form.get('peso', '')
      talla = request.form.get('talla', '')
      imc = request.form.get('imc', '')
      cintura = request.form.get('cintura', '')
      estudios_h = request.form.get('estudios_historial', '')
      med = request.form.get('medicacion_actual', '')

      framingham = request.form.get('framingham', '')
      cha2ds2 = request.form.get('cha2ds2', '')
      funcion_renal = request.form.get('funcion_renal', '')
      rel_alb_crea = request.form.get('rel_alb_crea', '')
      scag = request.form.get('scag', '')
      asa = request.form.get('asa', '')
      lee = request.form.get('lee', '')
      examen_fisico_notas = request.form.get('examen_fisico_notas', '')

      cursor.execute(
          '''
                INSERT INTO historial (paciente_id, fecha, antecedentes_consulta, motivo, consulta_actual, pa, fc, peso, talla, imc, cintura, estudios_historial, medicacion_actual, framingham, cha2ds2, funcion_renal, rel_alb_crea, scag, asa, lee, examen_fisico_notas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
          (
              id,
              fecha_cons,
              ant_cons,
              motivo,
              consulta_actual,
              pa,
              fc,
              peso,
              talla,
              imc,
              cintura,
              estudios_h,
              med,
              framingham,
              cha2ds2,
              funcion_renal,
              rel_alb_crea,
              scag,
              asa,
              lee,
              examen_fisico_notas,
          ),
      )
      conn.commit()
    elif accion == 'subir_archivo':
      nombre_estudio = request.form.get('nombre_estudio', 'Estudio')
      archivo_obj = request.files.get('archivo_estudio')
      if archivo_obj and archivo_obj.filename:
        filename = f'Estudio_{id}_{int(datetime.now().timestamp())}_{archivo_obj.filename}'
        filepath = os.path.join(upload_folder, filename)
        archivo_obj.save(filepath)
        cursor.execute(
            'INSERT INTO estudios (paciente_id, nombre_estudio, archivo, fecha,'
            ' sanatorio) VALUES (?, ?, ?, ?, ?)',
            (
                id,
                nombre_estudio,
                filename,
                datetime.today().strftime('%Y-%m-%d %H:%M'),
                'Adjunto Consultorio',
            ),
        )
        conn.commit()

  cursor.execute(
      'SELECT id, cedula, nombre, nacimiento, sexo, telefono, profesion,'
      ' direccion, alergias, antecedentes FROM pacientes WHERE id = ?',
      (id,),
  )
  paciente = cursor.fetchone()

  cursor.execute(
      'SELECT fecha, antecedentes_consulta, motivo, consulta_actual, pa, fc,'
      ' peso, talla, imc, cintura, estudios_historial, medicacion_actual,'
      ' framingham, cha2ds2, funcion_renal, rel_alb_crea, scag, asa, lee,'
      ' examen_fisico_notas FROM historial WHERE paciente_id = ? ORDER BY id'
      ' DESC',
      (id,),
  )
  historiales = cursor.fetchall()

  cursor.execute(
      'SELECT id, nombre_estudio, archivo, fecha FROM estudios WHERE'
      ' paciente_id = ? ORDER BY id DESC',
      (id,),
  )
  archivos_paciente = cursor.fetchall()

  conn.close()

  if not paciente:
    return 'Paciente no encontrado', 404

  edad_num = calcular_edad(paciente[3])
  edad_txt = f'{edad_num} años' if edad_num else 'N/D'
  sexo_paciente = paciente[4] or 'Femenino'

  # Resumen de la consulta anterior
  ultima_consulta_html = ''
  if len(historiales) > 0:
    ult = historiales[0]
    notas_ant = f'<p><b>Notas Ex. Físico:</b> {ult[19]}</p>' if ult[19] else ''
    ultima_consulta_html = f"""
        <div style="background:#334155; color:#f8fafc; padding:20px; border-radius:8px; margin-bottom:20px; border:1px solid #475569; box-shadow:0 4px 10px rgba(0,0,0,0.1);">
            <div style="display:flex; justify-content:space-between; border-bottom:1px solid #475569; padding-bottom:6px; margin-bottom:12px; font-weight:bold; color:#38bdf8; font-size:14px;">
                <span>📅 Fecha de última consulta: {ult[0]}</span>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; font-size:13px; color:#e2e8f0;">
                <div><b>Motivo:</b> {ult[2] or 'N/D'}</div>
                <div><b>Antecedentes:</b> {ult[1] or 'N/D'}</div>
                <div><b>Estudios:</b> {ult[10] or 'Ninguno'}</div>
                <div><b>Medicación Actual:</b> {ult[11] or 'Ninguna'}</div>
            </div>
            {notas_ant}
        </div>
        """
  else:
    ultima_consulta_html = (
        "<p style='color:#64748b; font-style:italic; font-size:13px;"
        " margin-bottom:15px;'>No hay consultas anteriores registradas.</p>"
    )

  # Listado completo de historiales
  historial_completo_html = ''
  for h in historiales:
    scores_previo = ''
    if h[12] or h[13] or h[14] or h[15] or h[16]:
      scores_previo += f"""
            <div style="background:#e0f2fe; padding:8px 12px; border-radius:6px; margin:8px 0; font-size:12px; color:#0369a1;">
                <b>📊 Scores:</b> Framingham: {h[12] or '-'} | CHA2DS2: {h[13] or '-'} | F. Renal: {h[14] or '-'} | Rel. Alb/Crea: {h[15] or '-'} | SCag: {h[16] or '-'}
            </div>
            """
    if h[17] or h[18]:
      scores_previo += f"""
            <div style="background:#fef3c7; padding:8px 12px; border-radius:6px; margin:8px 0; font-size:12px; color:#b45309;">
                <b>🏥 Prequirúrgico:</b> ASA: {h[17] or '-'} | Índice de Lee: {h[18] or '-'}
            </div>
            """
    notas_hist = f'<p><b>Notas Ex. Físico:</b> {h[19]}</p>' if h[19] else ''

    historial_completo_html += f"""
        <div style="background:white; padding:20px; border-radius:8px; margin-bottom:15px; border:1px solid #cbd5e1;">
            <div style="display:flex; justify-content:space-between; border-bottom:1px solid #e2e8f0; padding-bottom:8px; margin-bottom:10px; font-weight:bold; color:#1e3a8a;">
                <span>📅 Fecha: {h[0]}</span>
            </div>
            <p><b>Motivo:</b> {h[2] or 'N/D'}</p>
            <p><b>Antecedentes:</b> {h[1] or 'N/D'}</p>
            <p><b>Consulta Actual / Plan:</b> {h[3] or 'N/D'}</p>
            <div style="background:#f8fafc; padding:10px; border-radius:6px; margin:10px 0; font-size:13px; display:grid; grid-template-columns: repeat(3, 1fr); gap:10px;">
                <span><b>PA:</b> {h[4] or '-'} mmHg</span>
                <span><b>FC:</b> {h[5] or '-'} lpm</span>
                <span><b>Peso:</b> {h[6] or '-'} kg</span>
                <span><b>Talla:</b> {h[7] or '-'} m</span>
                <span><b>IMC:</b> {h[8] or '-'}</span>
                <span><b>Cintura:</b> {h[9] or '-'} cm</span>
            </div>
            {notas_hist}
            {scores_previo}
            <p><b>Estudios:</b> {h[10] or 'Ninguno'}</p>
            <p><b>Medicación Actual:</b> {h[11] or 'Ninguna'}</p>
        </div>
        """
  if not historial_completo_html:
    historial_completo_html = (
        "<p style='color:#64748b; font-style:italic;'>No hay consultas"
        ' registradas aún.</p>'
    )

  archivos_html = ''
  for ar in archivos_paciente:
    archivos_html += f"""
        <div style="background:white; padding:12px 15px; border-radius:6px; margin-bottom:8px; border:1px solid #d8b4fe; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <b style="color:#6b21a8; font-size:14px;">{ar[1]}</b>
                <span style="font-size:12px; color:#64748b; margin-left:10px;">({ar[3]})</span>
            </div>
            <a href="/uploads/{ar[2]}" target="_blank" style="background:#7c3aed; color:white; padding:6px 14px; text-decoration:none; border-radius:4px; font-weight:bold; font-size:12px;">Ver Archivo</a>
        </div>
        """
  if not archivos_html:
    archivos_html = (
        "<p style='color:#64748b; font-style:italic;'>No hay archivos adjuntos"
        ' aún.</p>'
    )

  # Datos para gráfico (JSON seguros)
  fechas_graf = json.dumps([h[0].split(' ')[0] for h in reversed(historiales)])
  pesos_graf = json.dumps(
      [float(h[6]) if h[6] else None for h in reversed(historiales)]
  )

  sistolica_list = []
  diastolica_list = []
  for h in reversed(historiales):
    pa_val = h[4] or ''
    if '/' in pa_val:
      try:
        parts = pa_val.split('/')
        sistolica_list.append(float(parts[0].strip()))
        diastolica_list.append(float(parts[1].strip()))
      except:
        sistolica_list.append(None)
        diastolica_list.append(None)
    else:
      sistolica_list.append(None)
      diastolica_list.append(None)

  sistolica_graf = json.dumps(sistolica_list)
  diastolica_graf = json.dumps(diastolica_list)

  sexo_js = (
      'Femenino'
      if 'Femenino' in sexo_paciente or 'Mujer' in sexo_paciente
      else 'Masculino'
  )

  return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Ficha Clínica - CardioSys</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            const sexoPaciente = "{sexo_js}";
            const edadPaciente = {edad_num};

            function calcularIMC() {{
                let peso = parseFloat(document.getElementById('peso').value);
                let talla = parseFloat(document.getElementById('talla').value);
                let imcTxt = document.getElementById('imc_txt');
                if (peso > 0 && talla > 0) {{
                    if (talla > 3) talla = talla / 100;
                    let imc = peso / (talla * talla);
                    let val = imc.toFixed(2);
                    document.getElementById('imc').value = val;
                    
                    let estado = "";
                    let color = "";
                    if (imc < 18.5) {{ estado = "Bajo peso"; color = "#0284c7"; }}
                    else if (imc < 25) {{ estado = "Peso normal (Eutrófico)"; color = "#107c41"; }}
                    else if (imc < 30) {{ estado = "Sobrepeso"; color = "#d97706"; }}
                    else if (imc < 35) {{ estado = "Obesidad Grado I (Moderada)"; color = "#dc2626"; }}
                    else if (imc < 40) {{ estado = "Obesidad Grado II (Severa)"; color = "#b91c1c"; }}
                    else {{ estado = "Obesidad Grado III (Mórbida)"; color = "#7f1d1d"; }}
                    
                    imcTxt.innerHTML = "IMC: " + val + " — <b>" + estado + "</b>";
                    imcTxt.style.color = color;
                }} else {{
                    document.getElementById('imc').value = '';
                    imcTxt.innerHTML = "";
                }}
            }}

            function evaluarCintura() {{
                let cintura = parseFloat(document.getElementById('cintura').value);
                let cinturaTxt = document.getElementById('cintura_txt');
                if (cintura > 0) {{
                    let riesgo = "";
                    let color = "";
                    if (sexoPaciente === "Femenino") {{
                        if (cintura >= 88) {{ riesgo = "Riesgo Cardiovascular Muy Alto (≥ 88 cm)"; color = "#b91c1c"; }}
                        else if (cintura >= 80) {{ riesgo = "Riesgo Cardiovascular Aumentado (≥ 80 cm)"; color = "#d97706"; }}
                        else {{ riesgo = "Riesgo Normal (< 80 cm)"; color = "#107c41"; }}
                    }} else {{
                        if (cintura >= 102) {{ riesgo = "Riesgo Cardiovascular Muy Alto (≥ 102 cm)"; color = "#b91c1c"; }}
                        else if (cintura >= 94) {{ riesgo = "Riesgo Cardiovascular Aumentado (≥ 94 cm)"; color = "#d97706"; }}
                        else {{ riesgo = "Riesgo Normal (< 94 cm)"; color = "#107c41"; }}
                    }}
                    cinturaTxt.innerHTML = "<b>" + riesgo + "</b>";
                    cinturaTxt.style.color = color;
                }} else {{
                    cinturaTxt.innerHTML = "";
                }}
            }}

            function calcularTFG() {{
                let scr = parseFloat(document.getElementById('tfg_scr').value);
                if (!scr || scr <= 0) {{
                    alert("Ingrese un valor válido de Creatinina Sérica");
                    return;
                }}
                let kappa = (sexoPaciente === "Femenino") ? 0.7 : 0.9;
                let alfa = (sexoPaciente === "Femenino") ? -0.241 : -0.329;
                let factorSexo = (sexoPaciente === "Femenino") ? 1.012 : 1.0;
                
                let minVal = Math.min(scr / kappa, 1.0);
                let maxVal = Math.max(scr / kappa, 1.0);
                
                let tfg = 142 * Math.pow(minVal, alfa) * Math.pow(maxVal, -1.200) * Math.pow(0.9938, edadPaciente) * factorSexo;
                let val = tfg.toFixed(1);
                
                let estadio = "";
                if (tfg >= 90) estadio = "G1 (Normal o alta)";
                else if (tfg >= 60) estadio = "G2 (Levemente disminuida)";
                else if (tfg >= 45) estadio = "G3a (Leve a moderadamente)";
                else if (tfg >= 30) estadio = "G3b (Moderada a gravemente)";
                else if (tfg >= 15) estadio = "G4 (Gravemente disminuida)";
                else estadio = "G5 (Falla renal)";

                let res = "TFG: " + val + " mL/min (" + estadio + ")";
                document.getElementById('tfg_resultado').value = res;
            }}

            function pasarTFG() {{
                let val = document.getElementById('tfg_resultado').value;
                if (!val) {{ alert("Calcule primero la TFG"); return; }}
                let actual = document.getElementById('resumen_scores').value;
                document.getElementById('resumen_scores').value = actual + (actual ? "\\n" : "") + val;
            }}

            function calcularRAC() {{
                let alb = parseFloat(document.getElementById('rac_alb').value);
                let crea = parseFloat(document.getElementById('rac_crea').value);
                if (!alb || !crea || crea <= 0) {{
                    alert("Ingrese valores válidos para albúmina y creatinina en orina");
                    return;
                }}
                let rac = (alb / crea) * 1000;
                let val = rac.toFixed(1);
                
                let categoria = "";
                if (rac < 30) categoria = "A1 (Normal a leve)";
                else if (rac <= 300) categoria = "A2 (Moderada)";
                else categoria = "A3 (Grave)";

                let res = "Relación Alb/Crea: " + val + " mg/g (" + categoria + ")";
                document.getElementById('rac_resultado').value = res;
            }}

            function pasarRAC() {{
                let val = document.getElementById('rac_resultado').value;
                if (!val) {{ alert("Calcule primero la Relación Alb/Crea"); return; }}
                let actual = document.getElementById('resumen_scores').value;
                document.getElementById('resumen_scores').value = actual + (actual ? "\\n" : "") + val;
            }}

            function calcularFramingham() {{
                let col = document.getElementById('f_col').value;
                let hdl = document.getElementById('f_hdl').value;
                let pas = document.getElementById('f_pas').value;
                let fum = document.getElementById('f_fum').checked ? "Fumador" : "No fumador";
                let res = "Col: " + (col||'-') + ", HDL: " + (hdl||'-') + ", PAS: " + (pas||'-') + " | " + fum;
                document.getElementById('framingham_input').value = res;
            }}

            function pasarFramingham() {{
                let val = document.getElementById('framingham_input').value;
                let actual = document.getElementById('resumen_scores').value;
                document.getElementById('resumen_scores').value = actual + (actual ? "\\n" : "") + "Framingham: " + val;
            }}

            function calcularCHA2DS2() {{
                let score = 0;
                if (document.getElementById('chf').checked) score += 1;
                if (document.getElementById('htn').checked) score += 1;
                if (document.getElementById('age75').checked) score += 2;
                if (document.getElementById('dm').checked) score += 1;
                if (document.getElementById('stroke').checked) score += 2;
                if (document.getElementById('vasc').checked) score += 1;
                if (document.getElementById('age65').checked) score += 1;
                if (document.getElementById('female').checked) score += 1;
                document.getElementById('cha2ds2_input').value = "CHA2DS2-VASc: " + score + " puntos";
            }}

            function pasarCHA2DS2() {{
                let val = document.getElementById('cha2ds2_input').value;
                let actual = document.getElementById('resumen_scores').value;
                document.getElementById('resumen_scores').value = actual + (actual ? "\\n" : "") + val;
            }}

            function calcularLee() {{
                let score = 0;
                if (document.getElementById('lee_surg').checked) score += 1;
                if (document.getElementById('lee_isqu_hd').checked) score += 1;
                if (document.getElementById('lee_chf').checked) score += 1;
                if (document.getElementById('lee_cvd').checked) score += 1;
                if (document.getElementById('lee_dm_ins').checked) score += 1;
                if (document.getElementById('lee_creat').checked) score += 1;
                
                let riesgo = "Clase I (Riesgo muy bajo - 0.4%)";
                if (score === 1) riesgo = "Clase II (Riesgo bajo - 0.9%)";
                else if (score === 3) riesgo = "Clase III (Riesgo moderado - 7%)";
                else if (score >= 4) riesgo = "Clase IV (Riesgo alto - >11%)";

                document.getElementById('lee_input').value = "Índice de Lee: " + score + " puntos (" + riesgo + ")";
            }}

            function pasarPreOp() {{
                let asa = document.getElementById('asa_select').value;
                let lee = document.getElementById('lee_input').value;
                let res = "Prequirúrgico -> " + (asa ? asa + " | " : "") + lee;
                let actual = document.getElementById('resumen_scores').value;
                document.getElementById('resumen_scores').value = actual + (actual ? "\\n" : "") + res;
            }}
        </script>
    </head>
    <body style="font-family:Segoe UI; background:#f4f7f6; padding:40px;">
        <div style="max-width: 1350px; margin: auto;">
            <a href="/" style="color:#3498db; text-decoration:none; font-weight:bold; display:inline-block; margin-bottom:15px; font-size:15px;">⬅ Volver al Panel</a>
            
            <!-- Tarjeta Principal del Paciente -->
            <div style="background:#1e293b; color:white; padding:25px 30px; border-radius:12px; box-shadow:0 6px 20px rgba(0,0,0,0.15); margin-bottom:25px; display:grid; grid-template-columns: 1fr 1.2fr; gap:25px; align-items:start;">
                <div>
                    <h2 style="margin:0 0 12px 0; font-size:24px; color:#ffffff;">{paciente[2]}</h2>
                    <div style="display:flex; gap:20px; font-size:14px; color:#cbd5e1; margin-bottom:15px; flex-wrap:wrap;">
                        <span><b>C.I.:</b> {paciente[1]}</span>
                        <span><b>Edad:</b> {edad_txt}</span>
                        <span><b>Profesión:</b> {paciente[6] or 'N/D'}</span>
                        <span><b>Procedencia:</b> {paciente[7] or 'N/D'}</span>
                    </div>
                    <div style="background:#334155; padding:10px 14px; border-radius:6px; border:1px solid #475569;">
                        <span style="font-weight:bold; color:#f87171;">Alergias:</span> <span style="color:#fca5a5;">{paciente[8] or 'Ninguna'}</span>
                    </div>
                </div>
                <div>
                    <form method="POST" style="background:#334155; padding:12px 18px; border-radius:6px; border:1px solid #475569; height:100%; box-sizing:border-box; display:flex; flex-direction:column;">
                        <input type="hidden" name="accion" value="guardar_antecedentes">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <label style="font-weight:bold; font-size:13px; color:#38bdf8;">Antecedentes Principales (Editable):</label>
                            <button type="submit" style="background:#107c41; color:white; border:none; padding:4px 12px; border-radius:4px; font-weight:bold; cursor:pointer; font-size:12px;">💾 Guardar</button>
                        </div>
                        <textarea name="antecedentes_base" rows="3" style="width:100%; background:transparent; border:none; color:white; font-family:Segoe UI; font-size:13px; outline:none; resize:vertical; flex:1;">{paciente[9] or ''}</textarea>
                    </form>
                </div>
            </div>

            <!-- Resumen de Consulta Anterior -->
            <h4 style="color:#1e293b; font-size:15px; margin-bottom:8px;">📌 Resumen de Consulta Anterior:</h4>
            {ultima_consulta_html}

            <!-- Panel Deslizable Superior: Scores y Prequirúrgico -->
            <details style="margin-bottom:25px;">
                <summary style="background:#0284c7; color:white; padding:12px 20px; border-radius:6px; font-weight:bold; cursor:pointer; font-size:14px; list-style:none; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.1); outline:none;">
                    📊 Abrir / Cerrar Panel de Scores y Prequirúrgico
                </summary>
                <div style="background:#f8fafc; border:2px solid #cbd5e1; border-top:none; border-bottom-left-radius:8px; border-bottom-right-radius:8px; padding:20px; display:flex; flex-direction:column; gap:20px;">
                    
                    <!-- Framingham -->
                    <div style="background:white; padding:15px; border-radius:6px; border:1px solid #e2e8f0;">
                        <label style="font-weight:bold; color:#b91c1c; display:block; margin-bottom:8px;">Framingham:</label>
                        <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:10px;">
                            <input type="text" id="f_col" placeholder="Col. Total" style="flex:1; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:13px; min-width:120px;">
                            <input type="text" id="f_hdl" placeholder="HDL" style="flex:1; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:13px; min-width:120px;">
                            <input type="text" id="f_pas" placeholder="PA Sist." style="flex:1; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:13px; min-width:120px;">
                            <label style="font-size:13px; font-weight:bold; color:#334155;"><input type="checkbox" id="f_fum"> Fumador</label>
                        </div>
                        <div style="display:flex; gap:10px; align-items:center;">
                            <button type="button" onclick="calcularFramingham()" style="background:#b91c1c; color:white; border:none; padding:8px 16px; border-radius:4px; font-weight:bold; cursor:pointer; font-size:13px;">Calcular</button>
                            <input type="text" id="framingham_input" placeholder="Resultado..." style="flex:2; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:13px; background:#f8fafc;">
                            <button type="button" onclick="pasarFramingham()" style="background:#1e293b; color:white; border:none; padding:8px 14px; border-radius:4px; font-weight:bold; cursor:pointer; font-size:12px;">📥 Copiar al Cuadro</button>
                        </div>
                    </div>

                    <!-- CHA2DS2-VASc -->
                    <div style="background:white; padding:15px; border-radius:6px; border:1px solid #e2e8f0;">
                        <label style="font-weight:bold; color:#b91c1c; display:block; margin-bottom:8px;">CHA2DS2-VASc:</label>
                        <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; font-size:12px; margin-bottom:10px;">
                            <label><input type="checkbox" id="chf" onchange="calcularCHA2DS2()"> Insuf. Cardíaca (+1)</label>
                            <label><input type="checkbox" id="htn" onchange="calcularCHA2DS2()"> HTA (+1)</label>
                            <label><input type="checkbox" id="age75" onchange="calcularCHA2DS2()"> Edad ≥ 75 (+2)</label>
                            <label><input type="checkbox" id="dm" onchange="calcularCHA2DS2()"> Diabetes (+1)</label>
                            <label><input type="checkbox" id="stroke" onchange="calcularCHA2DS2()"> ACV / AIT (+2)</label>
                            <label><input type="checkbox" id="vasc" onchange="calcularCHA2DS2()"> Enf. Vascular (+1)</label>
                            <label><input type="checkbox" id="age65" onchange="calcularCHA2DS2()"> Edad 65-74 (+1)</label>
                            <label><input type="checkbox" id="female" onchange="calcularCHA2DS2()"> Sexo Femenino (+1)</label>
                        </div>
                        <div style="display:flex; gap:10px; align-items:center;">
                            <input type="text" id="cha2ds2_input" placeholder="Seleccione factores arriba..." readonly style="flex:1; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:13px; background:#f1f5f9; font-weight:bold;">
                            <button type="button" onclick="pasarCHA2DS2()" style="background:#1e293b; color:white; border:none; padding:8px 14px; border-radius:4px; font-weight:bold; cursor:pointer; font-size:12px;">📥 Copiar al Cuadro</button>
                        </div>
                    </div>

                    <!-- Función Renal: TFG y RAC (Calculadoras Reales) -->
                    <div style="background:white; padding:15px; border-radius:6px; border:1px solid #e2e8f0;">
                        <label style="font-weight:bold; color:#7e22ce; display:block; margin-bottom:8px;">Función Renal (TFG y RAC):</label>
                        
                        <!-- TFG Calculator -->
                        <div style="margin-bottom:12px; border-bottom:1px solid #e2e8f0; padding-bottom:10px;">
                            <label style="font-size:12px; font-weight:bold; display:block; margin-bottom:4px;">Tasa de Filtración Glomerular (TFG - CKD-EPI):</label>
                            <div style="display:flex; gap:10px; align-items:center; margin-bottom:6px; flex-wrap:wrap;">
                                <input type="number" step="0.01" id="tfg_scr" placeholder="Creatinina Sérica (mg/dL)" style="flex:1; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:13px; min-width:180px;">
                                <button type="button" onclick="calcularTFG()" style="background:#7e22ce; color:white; border:none; padding:8px 16px; border-radius:4px; font-weight:bold; cursor:pointer; font-size:13px;">Calcular TFG</button>
                            </div>
                            <div style="display:flex; gap:10px; align-items:center;">
                                <input type="text" id="tfg_resultado" placeholder="Resultado TFG..." readonly style="flex:2; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:13px; background:#f8fafc; font-weight:bold;">
                                <button type="button" onclick="pasarTFG()" style="background:#1e293b; color:white; border:none; padding:8px 14px; border-radius:4px; font-weight:bold; cursor:pointer; font-size:12px;">📥 Copiar TFG</button>
                            </div>
                        </div>

                        <!-- RAC Calculator -->
                        <div>
                            <label style="font-size:12px; font-weight:bold; display:block; margin-bottom:4px;">Relación Albúmina / Creatinina (RAC):</label>
                            <div style="display:flex; gap:10px; align-items:center; margin-bottom:6px; flex-wrap:wrap;">
                                <input type="number" step="0.1" id="rac_alb" placeholder="Albúmina urinaria (mg/L)" style="flex:1; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:13px; min-width:160px;">
                                <input type="number" step="0.1" id="rac_crea" placeholder="Creatinina urinaria (mg/dL)" style="flex:1; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:13px; min-width:160px;">
                                <button type="button" onclick="calcularRAC()" style="background:#7e22ce; color:white; border:none; padding:8px 16px; border-radius:4px; font-weight:bold; cursor:pointer; font-size:13px;">Calcular RAC</button>
                            </div>
                            <div style="display:flex; gap:10px; align-items:center;">
                                <input type="text" id="rac_resultado" placeholder="Resultado RAC..." readonly style="flex:2; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:13px; background:#f8fafc; font-weight:bold;">
                                <button type="button" onclick="pasarRAC()" style="background:#1e293b; color:white; border:none; padding:8px 14px; border-radius:4px; font-weight:bold; cursor:pointer; font-size:12px;">📥 Copiar Alb/Crea</button>
                            </div>
                        </div>
                    </div>

                    <!-- Prequirúrgico -->
                    <div style="background:white; padding:15px; border-radius:6px; border:1px solid #e2e8f0;">
                        <label style="font-weight:bold; color:#b45309; display:block; margin-bottom:8px;">Prequirúrgico (ASA + Lee/RCRI):</label>
                        <div style="margin-bottom:10px;">
                            <select id="asa_select" style="width:100%; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:13px; margin-bottom:8px;">
                                <option value="">Seleccionar ASA...</option>
                                <option value="ASA I (Sano normal)">ASA I - Sano normal</option>
                                <option value="ASA II (Enf. sistémica leve)">ASA II - Enfermedad sistémica leve</option>
                                <option value="ASA III (Enf. sistémica grave)">ASA III - Enfermedad sistémica grave</option>
                                <option value="ASA IV (Enf. grave que amenaza la vida)">ASA IV - Enfermedad grave que amenaza la vida</option>
                            </select>
                        </div>
                        <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap:6px; font-size:12px; margin-bottom:10px;">
                            <label><input type="checkbox" id="lee_surg" onchange="calcularLee()"> Cirugía de alto riesgo</label>
                            <label><input type="checkbox" id="lee_isqu_hd" onchange="calcularLee()"> Cardiopatía isquémica</label>
                            <label><input type="checkbox" id="lee_chf" onchange="calcularLee()"> Insuficiencia cardíaca</label>
                            <label><input type="checkbox" id="lee_cvd" onchange="calcularLee()"> ACV / AIT previo</label>
                            <label><input type="checkbox" id="lee_dm_ins" onchange="calcularLee()"> Diabetes insulino-dep.</label>
                            <label><input type="checkbox" id="lee_creat" onchange="calcularLee()"> Creatinina > 2.0</label>
                        </div>
                        <div style="display:flex; gap:10px; align-items:center;">
                            <input type="text" id="lee_input" placeholder="Seleccione factores..." readonly style="flex:1; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:13px; background:#fef9c3; font-weight:bold;">
                            <button type="button" onclick="pasarPreOp()" style="background:#1e293b; color:white; border:none; padding:8px 14px; border-radius:4px; font-weight:bold; cursor:pointer; font-size:12px;">📥 Copiar al Cuadro</button>
                        </div>
                    </div>

                </div>
            </details>

            <!-- Formulario Nueva Consulta / Evolución Ancho -->
            <div style="background:white; padding:35px; border-radius:10px; box-shadow:0 4px 15px rgba(0,0,0,0.05); margin-bottom:30px; border:1px solid #e2e8f0;">
                <h3 style="color:#1e3a8a; margin-top:0; border-bottom:2px solid #e2e8f0; padding-bottom:8px;">🩺 Registrar Nueva Consulta / Evolución</h3>
                
                <form method="POST">
                    <input type="hidden" name="accion" value="nueva_consulta">
                    
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom:15px;">
                        <div>
                            <label style="display:block; font-weight:bold; font-size:13px; color:#334155; margin-bottom:4px;">Motivo:</label>
                            <input type="text" name="motivo" placeholder="Ej: Control cardiológico..." required style="width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:4px; box-sizing:border-box; font-size:14px;">
                        </div>
                        <div>
                            <label style="display:block; font-weight:bold; font-size:13px; color:#334155; margin-bottom:4px;">Antecedentes:</label>
                            <textarea name="antecedentes_consulta" rows="3" placeholder="Ej: Refiere mejoría..." style="width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:4px; font-family:Segoe UI; box-sizing:border-box; font-size:14px;"></textarea>
                        </div>
                    </div>

                    <div style="margin-bottom:15px;">
                        <label style="display:block; font-weight:bold; font-size:13px; color:#334155; margin-bottom:4px;">Consulta Actual / Plan:</label>
                        <textarea name="consulta_actual" rows="4" placeholder="Detalles de la evaluación y plan médico..." style="width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:4px; font-family:Segoe UI; box-sizing:border-box; font-size:14px;"></textarea>
                    </div>

                    <!-- NUEVO CUADRO EXCLUSIVO PARA COPIAR LOS SCORES -->
                    <div style="background:#f1f5f9; padding:15px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:15px;">
                        <label style="display:block; font-weight:bold; font-size:13px; color:#1e3a8a; margin-bottom:4px;">📊 Cuadro de Scores y Prequirúrgico (Resultados copiados desde el panel superior):</label>
                        <textarea id="resumen_scores" name="framingham" rows="3" placeholder="Aquí puede copiar o pegar los resultados de los scores..." style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:4px; font-family:Segoe UI; box-sizing:border-box; font-size:13px; background:white;"></textarea>
                    </div>

                    <!-- EXAMEN FÍSICO CON EVALUACIÓN DE IMC Y CINTURA + ESPACIO PARA ESCRIBIR -->
                    <div style="background:#f8fafc; padding:20px; border-radius:6px; border:1px solid #cbd5e1; margin-bottom:20px;">
                        <h4 style="margin:0 0 12px 0; color:#1e293b; font-size:15px;">Examen Físico</h4>
                        <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:15px; margin-bottom:12px;">
                            <div>
                                <label style="font-size:12px; font-weight:bold; display:block; margin-bottom:4px;">PA [mmHg]:</label>
                                <input type="text" name="pa" placeholder="120/80" style="width:100%; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:14px;">
                            </div>
                            <div>
                                <label style="font-size:12px; font-weight:bold; display:block; margin-bottom:4px;">FC [lpm]:</label>
                                <input type="text" name="fc" placeholder="72" style="width:100%; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:14px;">
                            </div>
                            <div>
                                <label style="font-size:12px; font-weight:bold; display:block; margin-bottom:4px;">Peso [kg]:</label>
                                <input type="number" step="0.1" id="peso" name="peso" oninput="calcularIMC()" placeholder="70" style="width:100%; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:14px;">
                            </div>
                            <div>
                                <label style="font-size:12px; font-weight:bold; display:block; margin-bottom:4px;">Talla [m o cm]:</label>
                                <input type="number" step="0.01" id="talla" name="talla" oninput="calcularIMC()" placeholder="1.75" style="width:100%; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:14px;">
                            </div>
                            <div>
                                <label style="font-size:12px; font-weight:bold; display:block; margin-bottom:4px;">IMC Calculado:</label>
                                <input type="text" id="imc" name="imc" readonly style="width:100%; padding:8px; border:1px solid #ccc; border-radius:4px; background:#e2e8f0; font-weight:bold; font-size:14px;">
                            </div>
                            <div>
                                <label style="font-size:12px; font-weight:bold; display:block; margin-bottom:4px;">Perímetro Cintura [cm]:</label>
                                <input type="text" id="cintura" name="cintura" oninput="evaluarCintura()" placeholder="85" style="width:100%; padding:8px; border:1px solid #ccc; border-radius:4px; font-size:14px;">
                            </div>
                        </div>
                        
                        <!-- Textos dinámicos de IMC y Cintura -->
                        <div style="margin-top:10px; border-top:1px solid #e2e8f0; padding-top:10px; margin-bottom:12px;">
                            <span id="imc_txt" style="font-size:13px; font-weight:bold; color:#64748b; display:block; margin-bottom:2px;"></span>
                            <span id="cintura_txt" style="font-size:13px; font-weight:bold; color:#64748b; display:block;"></span>
                        </div>

                        <!-- Espacio para escribir notas del examen físico -->
                        <div>
                            <label style="display:block; font-weight:bold; font-size:12px; color:#334155; margin-bottom:4px;">Observaciones / Hallazgos del Examen Físico:</label>
                            <textarea name="examen_fisico_notas" rows="2" placeholder="Ej: Ruidos cardíacos normofonéticos, sin soplos. Edemas leves en miembros inferiores..." style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:4px; font-family:Segoe UI; box-sizing:border-box; font-size:13px; background:white;"></textarea>
                        </div>
                    </div>

                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-bottom:20px;">
                        <div>
                            <label style="display:block; font-weight:bold; font-size:13px; color:#334155; margin-bottom:4px;">Estudios:</label>
                            <textarea name="estudios_historial" rows="2" placeholder="Estudios solicitados o evaluados..." style="width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:4px; font-family:Segoe UI; box-sizing:border-box; font-size:14px;"></textarea>
                        </div>
                        <div>
                            <label style="display:block; font-weight:bold; font-size:13px; color:#334155; margin-bottom:4px;">Medicación Actual:</label>
                            <textarea name="medicacion_actual" rows="2" placeholder="Fármacos y dosis..." style="width:100%; padding:10px; border:1px solid #cbd5e1; border-radius:4px; font-family:Segoe UI; box-sizing:border-box; font-size:14px;"></textarea>
                        </div>
                    </div>

                    <button type="submit" style="background:#107c41; color:white; border:none; padding:14px 20px; border-radius:6px; font-weight:bold; cursor:pointer; width:100%; font-size:16px;">💾 Guardar Consulta en el Historial</button>
                </form>
            </div>

            <!-- BOTONES DESLIZANTES AL FINAL DE LA PÁGINA -->
            
            <!-- 1. Gráfico de Evolución Clínica -->
            <details style="margin-bottom:20px;">
                <summary style="background:#0284c7; color:white; padding:12px 20px; border-radius:6px; font-weight:bold; cursor:pointer; font-size:14px; list-style:none; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.1); outline:none;">
                    📈 Gráfico de Evolución Clínica (Presión y Peso)
                </summary>
                <div style="background:white; border:2px solid #cbd5e1; border-top:none; border-bottom-left-radius:8px; border-bottom-right-radius:8px; padding:25px;">
                    <h3 style="margin-top:0; color:#1e293b; font-size:18px;">Evolución Clínica (Presión y Peso)</h3>
                    <div style="width: 100%; height: 320px;">
                        <canvas id="graficoEvolucion"></canvas>
                    </div>
                </div>
            </details>

            <!-- 2. Archivos y Estudios -->
            <details style="margin-bottom:20px;">
                <summary style="background:#7c3aed; color:white; padding:12px 20px; border-radius:6px; font-weight:bold; cursor:pointer; font-size:14px; list-style:none; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.1); outline:none;">
                    📁 Archivos y Estudios (Adjuntar)
                </summary>
                <div style="background:white; border:2px solid #d8b4fe; border-top:none; border-bottom-left-radius:8px; border-bottom-right-radius:8px; padding:25px;">
                    <h3 style="margin-top:0; color:#6b21a8; font-size:18px; margin-bottom:15px;">Archivos y Estudios</h3>
                    
                    <form method="POST" enctype="multipart/form-data" style="margin-bottom:25px; background:#f8fafc; padding:20px; border-radius:8px; border:1px solid #e2e8f0;">
                        <input type="hidden" name="accion" value="subir_archivo">
                        <div style="margin-bottom:12px;">
                            <label style="display:block; font-weight:bold; font-size:13px; color:#334155; margin-bottom:4px;">Nombre del Estudio / Archivo:</label>
                            <input type="text" name="nombre_estudio" placeholder="Ej: Ecocardiograma, ECG, Laboratorio..." required style="width:100%; padding:8px; border:1px solid #cbd5e1; border-radius:4px; font-size:14px;">
                        </div>
                        <div style="margin-bottom:15px;">
                            <label style="display:block; font-weight:bold; font-size:13px; color:#334155; margin-bottom:4px;">Seleccionar Archivo:</label>
                            <input type="file" name="archivo_estudio" required style="font-size:13px;">
                        </div>
                        <button type="submit" style="background:#7c3aed; color:white; border:none; padding:10px 20px; border-radius:6px; font-weight:bold; cursor:pointer; width:100%; font-size:14px;">📁 Subir Estudio</button>
                    </form>

                    <h4 style="color:#1e293b; margin-bottom:10px;">Archivos Adjuntos Registrados:</h4>
                    {archivos_html}
                </div>
            </details>

            <!-- 3. Historial Completo -->
            <details style="margin-bottom:40px;">
                <summary style="background:#334155; color:white; padding:12px 20px; border-radius:6px; font-weight:bold; cursor:pointer; font-size:14px; list-style:none; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.1); outline:none;">
                    📂 Historial Completo de Consultas Anteriores
                </summary>
                <div style="background:#f8fafc; border:2px solid #cbd5e1; border-top:none; border-bottom-left-radius:8px; border-bottom-right-radius:8px; padding:25px;">
                    <h3 style="margin-top:0; color:#1e293b; font-size:18px; margin-bottom:15px;">Historial Completo de Consultas</h3>
                    {historial_completo_html}
                </div>
            </details>
        </div>

        <script>
            const ctx = document.getElementById('graficoEvolucion').getContext('2d');
            const grafico = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: {fechas_graf},
                    datasets: [
                        {{
                            label: 'PA Sistólica (mmHg)',
                            data: {sistolica_graf},
                            borderColor: '#ef4444',
                            backgroundColor: '#ef4444',
                            tension: 0.1
                        }},
                        {{
                            label: 'PA Diastólica (mmHg)',
                            data: {diastolica_graf},
                            borderColor: '#3b82f6',
                            backgroundColor: '#3b82f6',
                            tension: 0.1
                        }},
                        {{
                            label: 'Peso (Kg)',
                            data: {pesos_graf},
                            borderColor: '#10b981',
                            backgroundColor: '#10b981',
                            tension: 0.1,
                            yAxisID: 'y1'
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {{ display: true, text: 'Presión Arterial (mmHg)' }}
                        }},
                        y1: {{
                            type: 'linear',
                            display: true,
                            position: 'right',
                            grid: {{ drawOnChartArea: false }},
                            title: {{ display: true, text: 'Peso (Kg)' }}
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """


@app.route('/backup')
def backup():
  if not session.get('logged_in'):
    return redirect(url_for('login'))
  if os.path.exists(db_path):
    return send_file(db_path, as_attachment=True)
  return 'Base de datos no encontrada', 404


@app.route('/logout')
def logout():
  session.clear()
  return redirect(url_for('login'))


if __name__ == '__main__':
  port = int(os.environ.get('PORT', 5002))
  app.run(host='0.0.0.0', port=port, debug=False)

import os
import sys
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, send_file, render_template
from werkzeug.security import generate_password_hash, check_password_hash

# Configuración de rutas apuntando al Disco Persistente en Render o entorno local
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

data_dir = '/data' if os.path.exists('/data') else os.path.join(base_dir, 'data')
os.makedirs(data_dir, exist_ok=True)

db_path = os.path.join(data_dir, 'cardiologia_elite.db')
upload_folder = os.path.join(data_dir, 'uploads')
backup_folder = os.path.join(data_dir, 'Backups_Automaticos')
os.makedirs(upload_folder, exist_ok=True)
os.makedirs(backup_folder, exist_ok=True)

# Ruta absoluta exacta para que Render encuentre los templates
template_dir = os.path.join(base_dir, 'templates')
app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'cardio_elite_seguro_2026'

def hacer_backup_automatico():
    if os.path.exists(db_path):
        fecha_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_file = os.path.join(backup_folder, f'backup_cardiologia_{fecha_str}.db')
        try:
            with open(db_path, 'rb') as src, open(backup_file, 'wb') as dst:
                dst.write(src.read())
        except Exception as e:
            print('Error al generar auto-backup:', e)

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

    pass_hash = generate_password_hash('cardiopy')
    cursor.execute('''
        INSERT INTO usuarios (username, password_hash) 
        VALUES ('draceciliamarecos', ?) 
        ON CONFLICT(username) DO UPDATE SET password_hash = ?
    ''', (pass_hash, pass_hash))

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
            medicacion_actual TEXT,
            fecha_cita TEXT,
            es_estudio INTEGER DEFAULT 0
        )
    ''')

    for col, tipo in [('es_estudio', 'INTEGER DEFAULT 0'), ('medicacion_actual', 'TEXT')]:
        try:
            cursor.execute(f'ALTER TABLE pacientes ADD COLUMN {col} {tipo}')
        except sqlite3.OperationalError:
            pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER,
            fecha TEXT,
            motivo TEXT,
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

    conn.commit()
    conn.close()
    hacer_backup_automatico()

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
        edad = hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))
        return edad
    except:
        return 0

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT password_hash FROM usuarios WHERE username = ?', (username,))
        row = cursor.fetchone()
        conn.close()

        if row and check_password_hash(row[0], password):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        else:
            error = 'Usuario o contraseña incorrectos'
    return render_template('login.html', error=error)

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    fecha_agenda = request.args.get('fecha', datetime.today().strftime('%Y-%m-%d'))
    busqueda = request.args.get('q', '').strip()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if busqueda:
        cursor.execute('SELECT * FROM pacientes WHERE es_estudio = 0 AND (nombre LIKE ? OR cedula LIKE ?)', (f'%{busqueda}%', f'%{busqueda}%'))
    else:
        cursor.execute('SELECT * FROM pacientes WHERE es_estudio = 0 AND fecha_cita = ?', (fecha_agenda,))
    
    pacientes = cursor.fetchall()
    conn.close()
    return render_template('dashboard.html', pacientes=pacientes, fecha_agenda=fecha_agenda, busqueda=busqueda, calcular_edad=calcular_edad)

@app.route('/lista-pacientes')
def lista_pacientes():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    q = request.args.get('q', '').strip()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if q:
        cursor.execute('SELECT * FROM pacientes WHERE es_estudio = 0 AND (nombre LIKE ? OR cedula LIKE ?) ORDER BY nombre ASC', (f'%{q}%', f'%{q}%'))
    else:
        cursor.execute('SELECT * FROM pacientes WHERE es_estudio = 0 ORDER BY nombre ASC')
        
    pacientes = cursor.fetchall()
    conn.close()
    return render_template('lista_pacientes.html', pacientes=pacientes, q=q, calcular_edad=calcular_edad)

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
        alergias = request.form.get('alergias', '')
        antecedentes_str = ', '.join(request.form.getlist('antecedentes'))
        fecha_cita = request.form.get('fecha_cita', datetime.today().strftime('%Y-%m-%d'))

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO pacientes (cedula, nombre, nacimiento, sexo, telefono, profesion, direccion, alergias, antecedentes, fecha_cita, es_estudio) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (cedula, nombre, nacimiento, sexo, telefono, profesion, direccion, alergias, antecedentes_str, fecha_cita))
        conn.commit()
        conn.close()
        return redirect(url_for('index', fecha=fecha_cita))
        
    return render_template('nuevo_paciente.html')

@app.route('/lista-estudios')
def lista_estudios():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.*, p.cedula, p.nombre as nombre_paciente 
        FROM estudios e 
        JOIN pacientes p ON e.paciente_id = p.id 
        ORDER BY e.id DESC
    """)
    estudios = cursor.fetchall()
    conn.close()
    return render_template('estudios_recientes.html', estudios=estudios)

@app.route('/cambiar-contrasena', methods=['GET', 'POST'])
def cambiar_contrasena():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    error, exito = None, None
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
            cursor.execute('SELECT password_hash FROM usuarios WHERE username = ?', (username,))
            row = cursor.fetchone()

            if row and check_password_hash(row[0], actual):
                nuevo_hash = generate_password_hash(nueva)
                cursor.execute('UPDATE usuarios SET password_hash = ? WHERE username = ?', (nuevo_hash, username))
                conn.commit()
                exito = '¡Contraseña actualizada con éxito!'
            else:
                error = 'La contraseña actual es incorrecta.'
            conn.close()
            
    return render_template('cambiar_contrasena.html', error=error, exito=exito)

@app.route('/ficha/<int:id>', methods=['GET', 'POST'])
def ficha(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        accion = request.form.get('accion')
        if accion == 'guardar_antecedentes':
            nuevo_ant = request.form.get('antecedentes_base', '')
            cursor.execute('UPDATE pacientes SET antecedentes = ? WHERE id = ?', (nuevo_ant, id))
            conn.commit()
        elif accion == 'guardar_medicacion':
            nueva_med = request.form.get('medicacion_actual_base', '')
            cursor.execute('UPDATE pacientes SET medicacion_actual = ? WHERE id = ?', (nueva_med, id))
            conn.commit()
        elif accion == 'guardar_datos_paciente':
            nombre = request.form.get('nombre', '')
            cedula = request.form.get('cedula', '')
            profesion = request.form.get('profesion', '')
            direccion = request.form.get('direccion', '')
            telefono = request.form.get('telefono', '')
            alergias = request.form.get('alergias', '')
            cursor.execute('''
                UPDATE pacientes 
                SET nombre = ?, cedula = ?, profesion = ?, direccion = ?, telefono = ?, alergias = ? 
                WHERE id = ?
            ''', (nombre, cedula, profesion, direccion, telefono, alergias, id))
            conn.commit()
        elif accion == 'nueva_consulta':
            fecha_cons = datetime.today().strftime('%Y-%m-%d %H:%M')
            motivo_evolucion = request.form.get('motivo_evolucion', '')
            pa = request.form.get('pa', '')
            fc = request.form.get('fc', '')
            peso = request.form.get('peso', '')
            talla = request.form.get('talla', '')
            imc = request.form.get('imc', '')
            cintura = request.form.get('cintura', '')
            estudios_h = request.form.get('estudios_historial', '')
            med = request.form.get('medicacion_actual', '')
            examen_fisico_notas = request.form.get('examen_fisico_notas', '')

            cursor.execute('''
                INSERT INTO historial (paciente_id, fecha, motivo, pa, fc, peso, talla, imc, cintura, estudios_historial, medicacion_actual, examen_fisico_notas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (id, fecha_cons, motivo_evolucion, pa, fc, peso, talla, imc, cintura, estudios_h, med, examen_fisico_notas))
            conn.commit()
        elif accion == 'subir_archivo':
            nombre_estudio = request.form.get('nombre_estudio', 'Estudio')
            archivo_obj = request.files.get('archivo_estudio')
            if archivo_obj and archivo_obj.filename:
                filename = f'Estudio_{id}_{int(datetime.now().timestamp())}_{archivo_obj.filename}'
                filepath = os.path.join(upload_folder, filename)
                archivo_obj.save(filepath)
                cursor.execute('INSERT INTO estudios (paciente_id, nombre_estudio, archivo, fecha, sanatorio) VALUES (?, ?, ?, ?, ?)',
                               (id, nombre_estudio, filename, datetime.today().strftime('%Y-%m-%d %H:%M'), 'Adjunto Consultorio'))
                conn.commit()

    cursor.execute('SELECT * FROM pacientes WHERE id = ?', (id,))
    paciente = cursor.fetchone()

    cursor.execute('SELECT * FROM historial WHERE paciente_id = ? ORDER BY id DESC', (id,))
    historiales = cursor.fetchall()

    cursor.execute('SELECT * FROM estudios WHERE paciente_id = ? ORDER BY id DESC', (id,))
    archivos_paciente = cursor.fetchall()

    conn.close()

    if not paciente:
        return 'Paciente no encontrado', 404

    return render_template('ficha.html', paciente=paciente, historiales=historiales, archivos_paciente=archivos_paciente, calcular_edad=calcular_edad)

@app.route('/receta/<int:id>', methods=['POST'])
def receta(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    diagnostico = request.form.get('diagnostico_receta', 'Control Cardiológico')
    medicamentos = request.form.get('receta', '')
    indicaciones = request.form.get('indicaciones', '')
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pacientes WHERE id = ?', (id,))
    p = cursor.fetchone()
    conn.close()
    
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Receta Médica - {p['nombre']}</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 40px; color: #333; max-width: 800px; margin: auto; }}
            .header {{ border-bottom: 2px solid #2c3e50; padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }}
            .footer {{ margin-top: 60px; border-top: 1px solid #ccc; padding-top: 20px; text-align: center; font-size: 14px; color: #555; }}
            .section {{ margin-bottom: 25px; }}
            .label {{ font-weight: bold; color: #2c3e50; margin-bottom: 5px; display: block; }}
            .content {{ background: #f8fafc; padding: 15px; border-radius: 6px; border: 1px solid #e2e8f0; white-space: pre-wrap; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div>
                <h2 style="margin:0; color:#2c3e50;">Dra. Cecilia Marecos Viana</h2>
                <p style="margin:5px 0 0 0; color:#7f8c8d; font-size:14px;">Especialista en Cardiología Clínica | Reg. Prof. 13943</p>
            </div>
            <div style="text-align:right;">
                <p style="margin:0; font-size:14px;">Fecha: {datetime.today().strftime('%d/%m/%Y')}</p>
            </div>
        </div>
        
        <div style="background: #e2e8f0; padding: 12px 15px; border-radius: 6px; margin-bottom: 25px; font-size: 15px;">
            <strong>Paciente:</strong> {p['nombre']} &nbsp;&nbsp;|&nbsp;&nbsp; <strong>C.I.:</strong> {p['cedula']}
        </div>
        
        <div class="section">
            <span class="label">Diagnóstico / Motivo:</span>
            <div class="content">{diagnostico}</div>
        </div>
        
        <div class="section">
            <span class="label">Rx (Medicamentos):</span>
            <div class="content">{medicamentos}</div>
        </div>
        
        <div class="section">
            <span class="label">Indicaciones de Uso:</span>
            <div class="content">{indicaciones}</div>
        </div>
        
        <div class="footer">
            <p style="margin:0;">_________________________________________</p>
            <p style="margin:5px 0 0 0; font-weight:bold;">Firma y Sello</p>
        </div>
        
        <script>
            window.onload = function() {{ window.print(); }}
        </script>
    </body>
    </html>
    """

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return send_file(os.path.join(upload_folder, filename))

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

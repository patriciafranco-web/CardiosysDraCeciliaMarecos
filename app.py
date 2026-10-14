import os
import sys
import sqlite3
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

# Ruta absoluta exacta para que Render encuentre los templates sin errores
template_dir = os.path.join(base_dir, 'templates')
app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'cardio_elite_seguro_2026'

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
            FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
        )
    ''')

    conn.commit()
    conn.close()

init_db()

@app.before_request
def hacer_sesion_no_permanente():
    session.permanent = False

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
    
    busqueda = request.args.get('q', '').strip()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if busqueda:
        cursor.execute('SELECT * FROM pacientes WHERE es_estudio = 0 AND (nombre LIKE ? OR cedula LIKE ?)', (f'%{busqueda}%', f'%{busqueda}%'))
    else:
        cursor.execute('SELECT * FROM pacientes WHERE es_estudio = 0', ())
    
    pacientes = cursor.fetchall()
    conn.close()
    return render_template('dashboard.html', pacientes=pacientes, busqueda=busqueda)

@app.route('/nuevo_paciente', methods=['GET', 'POST'])
def nuevo_paciente():
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
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO pacientes (cedula, nombre, nacimiento, sexo, telefono, profesion, direccion, alergias, es_estudio) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (cedula, nombre, nacimiento, sexo, telefono, profesion, direccion, alergias))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('nuevo_paciente.html')

@app.route('/calculadoras')
def calculadoras():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('calculadoras.html')

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

    cursor.execute('SELECT * FROM pacientes WHERE id = ?', (id,))
    paciente = cursor.fetchone()
    
    cursor.execute('SELECT * FROM historial WHERE paciente_id = ? ORDER BY id DESC', (id,))
    historiales = cursor.fetchall()

    cursor.execute('SELECT * FROM estudios WHERE paciente_id = ? ORDER BY id DESC', (id,))
    archivos_paciente = cursor.fetchall()
    conn.close()

    if not paciente:
        return 'Paciente no encontrado', 404

    return render_template('ficha.html', paciente=paciente, historiales=historiales, archivos_paciente=archivos_paciente)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=False)

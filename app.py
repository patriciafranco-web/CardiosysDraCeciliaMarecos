import os
import sys
import sqlite3
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, send_file
from threading import Timer
import webbrowser
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Configuración de rutas
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

db_path = os.path.join(base_dir, 'cardiologia_elite.db')
upload_folder = os.path.join(base_dir, 'uploads')
backup_folder = os.path.join(base_dir, 'Backups_Automaticos')
os.makedirs(upload_folder, exist_ok=True)
os.makedirs(backup_folder, exist_ok=True)

app = Flask(__name__)
app.secret_key = 'cardio_elite_seguro_2026'

def hacer_backup_automatico():
    if os.path.exists(db_path):
        fecha_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_file = os.path.join(backup_folder, f'backup_cardiologia_{fecha_str}.db')
        try:
            with open(db_path, 'rb') as src, open(backup_file, 'wb') as dst:
                dst.write(src.read())
        except Exception as e:
            print("Error al generar auto-backup:", e)

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pacientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cedula TEXT NOT NULL,
            nombre TEXT NOT NULL,
            nacimiento TEXT,
            sexo TEXT,
            telefono TEXT,
            profesion TEXT,
            sanatorio TEXT,
            direccion TEXT,
            alergias TEXT,
            antecedentes TEXT
        )
    ''')
    
    # Migración segura para columnas adicionales en pacientes
    cursor.execute("PRAGMA table_info(pacientes)")
    cols_pacientes = [col[1] for col in cursor.fetchall()]
    if 'profesion' not in cols_pacientes:
        try:
            cursor.execute("ALTER TABLE pacientes ADD COLUMN profesion TEXT")
        except:
            pass
    if 'sanatorio' not in cols_pacientes:
        try:
            cursor.execute("ALTER TABLE pacientes ADD COLUMN sanatorio TEXT")
        except:
            pass

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER,
            fecha TEXT,
            motivo TEXT,
            antecedentes_evo TEXT,
            peso TEXT,
            talla TEXT,
            cintura TEXT,
            imc TEXT,
            bsa TEXT,
            pas TEXT,
            pad TEXT,
            score_fa TEXT,
            score_renal TEXT,
            score_preop TEXT,
            score_sca TEXT,
            score_ic TEXT,
            score_ecg TEXT,
            examen TEXT,
            diagnostico TEXT,
            tratamiento TEXT,
            receta TEXT,
            indicaciones TEXT,
            mapa_diurno TEXT,
            mapa_nocturno TEXT,
            patron TEXT,
            holter TEXT,
            FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
        )
    ''')
    
    cursor.execute("PRAGMA table_info(historial)")
    columnas_existentes = [col[1] for col in cursor.fetchall()]
    nuevas_columnas = [
        ('antecedentes_evo', 'TEXT'),
        ('talla', 'TEXT'),
        ('cintura', 'TEXT'),
        ('imc', 'TEXT'),
        ('bsa', 'TEXT'),
        ('score_fa', 'TEXT'),
        ('score_renal', 'TEXT'),
        ('score_preop', 'TEXT'),
        ('score_sca', 'TEXT'),
        ('score_ic', 'TEXT'),
        ('score_ecg', 'TEXT')
    ]
    for col_name, col_type in nuevas_columnas:
        if col_name not in columnas_existentes:
            try:
                cursor.execute(f"ALTER TABLE historial ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                print(f"Error al agregar columna {col_name}:", e)

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS estudios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER,
            nombre_estudio TEXT,
            archivo TEXT,
            fecha TEXT,
            FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vademecum (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            nombre TEXT NOT NULL
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM vademecum")
    if cursor.fetchone()[0] == 0:
        defaults = [
            ("IECA / ARA II", "Enalapril 10mg - 1 comp c/12h"),
            ("IECA / ARA II", "Losartán 50mg - 1 comp c/12h"),
            ("IECA / ARA II", "Valsartán 160mg - 1 comp c/24h"),
            ("Betabloqueantes", "Bisoprolol 5mg - 1 comp c/24h"),
            ("Betabloqueantes", "Carvedilol 12.5mg - 1 comp c/12h"),
            ("Betabloqueantes", "Nebivolol 5mg - 1 comp día"),
            ("Estatinas", "Atorvastatina 40mg - 1 comp noche"),
            ("Estatinas", "Rosuvastatina 20mg - 1 comp noche"),
            ("Antagonistas del Calcio", "Amlodipina 5mg - 1 comp día"),
            ("Diuréticos", "Hidroclorotiazida 25mg - 1 comp mañana"),
            ("Diuréticos", "Espironolactona 25mg - 1 comp día"),
            ("Diuréticos", "Furosemida 40mg - 1 comp día"),
            ("Antiagregantes / Anticoagulantes", "Ácido Acetilsalicílico 100mg - 1 comp día"),
            ("Antiagregantes / Anticoagulantes", "Clopidogrel 75mg - 1 comp día"),
            ("Antiagregantes / Anticoagulantes", "Rivaroxabán 20mg - 1 comp día")
        ]
        cursor.executemany("INSERT INTO vademecum (categoria, nombre) VALUES (?, ?)", defaults)
    
    conn.commit()
    conn.close()
    hacer_backup_automatico()

def calcular_edad(nacimiento_str):
    if not nacimiento_str:
        return "N/D"
    try:
        nac = datetime.strptime(nacimiento_str, "%Y-%m-%d")
        hoy = datetime.today()
        edad = hoy.year - nac.year - ((hoy.month, hoy.day) < (nac.month, nac.day))
        return f"{edad} años"
    except:
        return "N/D"

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'admin123':
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            error = "Contraseña incorrecta (es admin123)"
    
    err_html = f'<p style="color:red;">{error}</p>' if error else ''
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Acceso - CardioSys</title></head>
    <body style="font-family:Segoe UI; background:#f4f7f6; display:flex; justify-content:center; align-items:center; height:100vh; margin:0;">
        <div style="background:white; padding:30px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.1); width:350px; text-align:center;">
            <h2 style="color:#2c3e50; margin-top:0;">CardioSys 1.0</h2>
            <p style="color:#2980b9; font-size:16px; font-weight:bold; margin-bottom:20px;">Dr. Herve Benitez</p>
            {err_html}
            <form method="POST">
                <label style="display:block; text-align:left; font-size:13px; font-weight:bold;">Contraseña de Acceso:</label>
                <input type="password" name="password" required style="width:100%; padding:10px; margin:10px 0; box-sizing:border-box; border:1px solid #ccc; border-radius:4px;">
                <button type="submit" style="width:100%; padding:10px; background:#2980b9; color:white; border:none; border-radius:4px; font-weight:bold; cursor:pointer;">Ingresar</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    busqueda = request.args.get('q', '').strip()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if busqueda:
        cursor.execute("SELECT id, cedula, nombre, nacimiento, telefono FROM pacientes WHERE nombre LIKE ? OR cedula LIKE ?", (f'%{busqueda}%', f'%{busqueda}%'))
    else:
        cursor.execute("SELECT id, cedula, nombre, nacimiento, telefono FROM pacientes")
    
    pacientes = cursor.fetchall()
    conn.close()
    
    filas_html = ""
    for p in pacientes:
        edad_txt = calcular_edad(p[3])
        filas_html += f"""
        <tr>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{p[1]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd; font-weight:bold;">{p[2]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{p[3]} ({edad_txt})</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{p[4]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">
                <a href="/ficha/{p[0]}" style="background:#2ecc71; color:white; padding:6px 12px; text-decoration:none; border-radius:4px; font-size:14px;">Abrir Ficha</a>
            </td>
        </tr>
        """
    if not filas_html:
        filas_html = "<tr><td colspan='5' style='padding:15px; text-align:center;'>No se encontraron pacientes.</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Panel Principal - CardioSys</title></head>
    <body style="font-family:Segoe UI; background:#f4f7f6; margin:0; display:flex; height:100vh;">
        <div style="width:260px; background:#1e293b; color:white; padding:20px; box-sizing:border-box; display:flex; flex-direction:column;">
            <h2 style="color:white; margin-top:0; margin-bottom:5px;">CardioSys 1.0</h2>
            <p style="color:#38bdf8; font-size:15px; font-weight:bold; margin-top:0; margin-bottom:25px; line-height:1.3;">Dr. Herve Benitez</p>
            <ul style="list-style:none; padding:0; margin-top:0; flex:1;">
                <li style="margin:15px 0;"><a href="/" style="color:#38bdf8; text-decoration:none; font-weight:bold;">📋 Agenda de Hoy</a></li>
                <li style="margin:15px 0;"><a href="/nuevo" style="color:white; text-decoration:none;">➕ Nuevo Ingreso</a></li>
                <li style="margin:15px 0;"><a href="/estudios-recientes" style="color:white; text-decoration:none;">📁 Estudios Recientes</a></li>
            </ul>
            <div style="margin-bottom:20px;">
                <a href="/backup" style="display:block; background:#e67e22; color:white; padding:12px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold;">💾 Backup Manual</a>
            </div>
        </div>
        <div style="flex:1; padding:40px; overflow-y:auto;">
            <h1>Panel de Control / Agenda de Hoy</h1>
            
            <div style="background:white; padding:20px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.05); margin-bottom:20px;">
                <form method="GET" action="/" style="display:flex; gap:10px;">
                    <input type="text" name="q" value="{busqueda}" placeholder="Buscar por nombre o cédula..." style="flex:1; padding:10px; border:1px solid #ccc; border-radius:4px;">
                    <button type="submit" style="background:#3498db; color:white; border:none; padding:10px 20px; border-radius:4px; cursor:pointer; font-weight:bold;">Buscar</button>
                    <a href="/" style="background:#95a5a6; color:white; padding:10px 15px; text-decoration:none; border-radius:4px; font-weight:bold; display:inline-block; text-align:center;">Limpiar</a>
                </form>
            </div>

            <div style="background:white; padding:25px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.05);">
                <h3>Lista de Pacientes</h3>
                <table style="width:100%; border-collapse:collapse; margin-top:15px;">
                    <tr style="background:#3498db; color:white;">
                        <th style="padding:12px; text-align:left;">Cédula (C.I.)</th>
                        <th style="padding:12px; text-align:left;">Nombre del Paciente</th>
                        <th style="padding:12px; text-align:left;">Nacimiento / Edad</th>
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
        sanatorio = request.form.get('sanatorio')
        direccion = request.form.get('direccion')
        alergias = request.form.get('alergias', 'Ninguna')
        antecedentes_list = request.form.getlist('antecedentes')
        antecedentes_str = ", ".join(antecedentes_list)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO pacientes (cedula, nombre, nacimiento, sexo, telefono, profesion, sanatorio, direccion, alergias, antecedentes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                       (cedula, nombre, nacimiento, sexo, telefono, profesion, sanatorio, direccion, alergias, antecedentes_str))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    return """
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Nuevo Ingreso - CardioSys</title></head>
    <body style="font-family:Segoe UI; background:#f4f7f6; margin:0; display:flex; height:100vh;">
        <div style="width:260px; background:#1e293b; color:white; padding:20px; box-sizing:border-box; display:flex; flex-direction:column;">
            <h2 style="color:white; margin-top:0; margin-bottom:5px;">CardioSys 1.0</h2>
            <p style="color:#38bdf8; font-size:15px; font-weight:bold; margin-top:0; margin-bottom:25px; line-height:1.3;">Dr. Herve Benitez</p>
            <ul style="list-style:none; padding:0; margin-top:0; flex:1;">
                <li style="margin:15px 0;"><a href="/" style="color:white; text-decoration:none;">📋 Agenda de Hoy</a></li>
                <li style="margin:15px 0;"><a href="/nuevo" style="color:#38bdf8; text-decoration:none; font-weight:bold;">➕ Nuevo Ingreso</a></li>
                <li style="margin:15px 0;"><a href="/estudios-recientes" style="color:white; text-decoration:none;">📁 Estudios Recientes</a></li>
            </ul>
            <div style="margin-bottom:20px;">
                <a href="/backup" style="display:block; background:#e67e22; color:white; padding:12px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold;">💾 Backup Manual</a>
            </div>
        </div>
        <div style="flex:1; padding:40px; overflow-y:auto;">
            <a href="/" style="display:inline-block; margin-bottom:15px; color:#3498db; text-decoration:none; font-weight:bold;">⬅ Volver al Panel</a>
            <div style="background:white; padding:30px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.05); max-width:700px;">
                <h2 style="color:#2c3e50; margin-top:0;">Ficha de Nuevo Ingreso y Factores de Riesgo</h2>
                <form method="POST">
                    <div style="display:flex; gap:15px;">
                        <div style="flex:1;"><label style="font-weight:bold; font-size:13px;">Cédula / C.I.:</label><input type="text" name="cedula" placeholder="Ej: 1321854" required style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></div>
                        <div style="flex:2;"><label style="font-weight:bold; font-size:13px;">Nombre Completo:</label><input type="text" name="nombre" placeholder="Nombre y Apellido" required style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></div>
                    </div>
                    <div style="display:flex; gap:15px;">
                        <div style="flex:1;"><label style="font-weight:bold; font-size:13px;">Fecha de Nacimiento:</label><input type="date" name="nacimiento" required style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></div>
                        <div style="flex:1;">
                            <label style="font-weight:bold; font-size:13px;">Sexo Biológico:</label>
                            <select name="sexo" required style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;">
                                <option value="">Seleccionar...</option>
                                <option value="Hombre">Hombre</option>
                                <option value="Mujer">Mujer</option>
                            </select>
                        </div>
                    </div>
                    <div style="display:flex; gap:15px;">
                        <div style="flex:1;"><label style="font-weight:bold; font-size:13px;">Teléfono:</label><input type="text" name="telefono" placeholder="Ej: 0987546321" style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></div>
                        <div style="flex:1;"><label style="font-weight:bold; font-size:13px;">Profesión / Ocupación:</label><input type="text" name="profesion" placeholder="Ej: Docente..." style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></div>
                        <div style="flex:1;"><label style="font-weight:bold; font-size:13px;">Sanatorio / Hospital:</label><input type="text" name="sanatorio" placeholder="Ej: Sanatorio..." style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></div>
                    </div>
                    <label style="font-weight:bold; font-size:13px;">Dirección / Ciudad:</label>
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

                    <button type="submit" style="background:#2ecc71; color:white; border:none; padding:12px 20px; border-radius:4px; font-weight:bold; cursor:pointer; width:100%;">Guardar Paciente</button>
                </form>
            </div>
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
        SELECT e.id, p.cedula, p.nombre, e.nombre_estudio, e.archivo, e.fecha, p.id 
        FROM estudios e 
        JOIN pacientes p ON e.paciente_id = p.id 
        ORDER BY e.id DESC
    """)
    estudios = cursor.fetchall()
    conn.close()

    filas_estudios = ""
    for est in estudios:
        filas_estudios += f"""
        <tr>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{est[5]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{est[1]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd; font-weight:bold;">{est[2]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">{est[3]}</td>
            <td style="padding:12px; border-bottom:1px solid #ddd;">
                <a href="/uploads/{est[4]}" target="_blank" style="background:#9b59b6; color:white; padding:6px 12px; text-decoration:none; border-radius:4px; font-size:13px; font-weight:bold;">Ver Archivo</a>
                <a href="/ficha/{est[6]}" style="background:#3498db; color:white; padding:6px 12px; text-decoration:none; border-radius:4px; font-size:13px; margin-left:5px;">Ver Ficha</a>
            </td>
        </tr>
        """
    if not filas_estudios:
        filas_estudios = "<tr><td colspan='5' style='padding:15px; text-align:center;'>No hay estudios recientes registrados.</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Estudios Recientes - CardioSys</title></head>
    <body style="font-family:Segoe UI; background:#f4f7f6; margin:0; display:flex; height:100vh;">
        <div style="width:260px; background:#1e293b; color:white; padding:20px; box-sizing:border-box; display:flex; flex-direction:column;">
            <h2 style="color:white; margin-top:0; margin-bottom:5px;">CardioSys 1.0</h2>
            <p style="color:#38bdf8; font-size:15px; font-weight:bold; margin-top:0; margin-bottom:25px; line-height:1.3;">Dr. Herve Benitez</p>
            <ul style="list-style:none; padding:0; margin-top:0; flex:1;">
                <li style="margin:15px 0;"><a href="/" style="color:white; text-decoration:none;">📋 Agenda de Hoy</a></li>
                <li style="margin:15px 0;"><a href="/nuevo" style="color:white; text-decoration:none;">➕ Nuevo Ingreso</a></li>
                <li style="margin:15px 0;"><a href="/estudios-recientes" style="color:#38bdf8; text-decoration:none; font-weight:bold;">📁 Estudios Recientes</a></li>
            </ul>
            <div style="margin-bottom:20px;">
                <a href="/backup" style="display:block; background:#e67e22; color:white; padding:12px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold;">💾 Backup Manual</a>
            </div>
        </div>
        <div style="flex:1; padding:40px; overflow-y:auto;">
            <h1>📁 Repositorio Global de Estudios Recientes</h1>
            <div style="background:white; padding:25px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.05); margin-top:20px;">
                <h3>Últimos Estudios Complementarios Subidos</h3>
                <table style="width:100%; border-collapse:collapse; margin-top:15px;">
                    <tr style="background:#9b59b6; color:white;">
                        <th style="padding:12px; text-align:left;">Fecha de Carga</th>
                        <th style="padding:12px; text-align:left;">Cédula</th>
                        <th style="padding:12px; text-align:left;">Paciente</th>
                        <th style="padding:12px; text-align:left;">Nombre del Estudio</th>
                        <th style="padding:12px; text-align:left;">Acción</th>
                    </tr>
                    {filas_estudios}
                </table>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/agregar_vademecum/<int:paciente_id>', methods=['POST'])
def agregar_vademecum(paciente_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    categoria = request.form.get('cat_vademecum', 'Personalizados')
    nombre = request.form.get('nuevo_farmaco')
    if nombre and nombre.strip():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO vademecum (categoria, nombre) VALUES (?, ?)", (categoria.strip(), nombre.strip()))
        conn.commit()
        conn.close()
    return redirect(url_for('ficha', id=paciente_id))

@app.route('/ficha/<int:id>', methods=['GET', 'POST'])
def ficha(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, cedula, nombre, nacimiento, sexo, telefono, profesion, sanatorio, direccion, alergias, antecedentes FROM pacientes WHERE id = ?", (id,))
    paciente = cursor.fetchone()
    
    if not paciente:
        conn.close()
        return "Paciente no encontrado", 404

    edad_paciente_num = 55
    if paciente[3]:
        try:
            nac_dt = datetime.strptime(paciente[3], "%Y-%m-%d")
            edad_paciente_num = datetime.today().year - nac_dt.year
        except:
            pass

    sexo_paciente = paciente[4] or 'Hombre'

    mensaje_guardado = ""
    if request.method == 'POST':
        accion = request.form.get('accion')
        
        if accion == 'subir_estudio':
            nombre_estudio = request.form.get('nombre_estudio', 'Estudio Cardiológico')
            archivo = request.files.get('archivo_estudio')
            if archivo and archivo.filename:
                filename = f"{id}_{int(datetime.now().timestamp())}_{archivo.filename}"
                filepath = os.path.join(upload_folder, filename)
                archivo.save(filepath)
                cursor.execute("INSERT INTO estudios (paciente_id, nombre_estudio, archivo, fecha) VALUES (?, ?, ?, ?)",
                               (id, nombre_estudio, filename, datetime.today().strftime('%Y-%m-%d %H:%M')))
                conn.commit()
                mensaje_guardado = '<div style="background:#d4edda; color:#155724; padding:10px; border-radius:4px; margin-bottom:15px;">¡Estudio subido correctamente!</div>'
        else:
            fecha_actual = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
            motivo = request.form.get('motivo')
            antecedentes_evo = request.form.get('antecedentes_evo')
            peso = request.form.get('peso')
            talla = request.form.get('talla')
            cintura = request.form.get('cintura')
            imc = request.form.get('imc')
            bsa = request.form.get('bsa')
            pas = request.form.get('pas')
            pad = request.form.get('pad')
            score_fa = request.form.get('score_fa')
            score_renal = request.form.get('score_renal')
            score_preop = request.form.get('score_preop')
            score_sca = request.form.get('score_sca')
            score_ic = request.form.get('score_ic')
            score_ecg = request.form.get('score_ecg')
            examen = request.form.get('examen')
            diagnostico = request.form.get('diagnostico')
            tratamiento = request.form.get('tratamiento')
            receta = request.form.get('receta')
            indicaciones = request.form.get('indicaciones')
            mapa_diurno = request.form.get('mapa_diurno')
            mapa_nocturno = request.form.get('mapa_nocturno')
            patron = request.form.get('patron')
            holter = request.form.get('holter')
            
            cursor.execute('''
                INSERT INTO historial (paciente_id, fecha, motivo, antecedentes_evo, peso, talla, cintura, imc, bsa, pas, pad, score_fa, score_renal, score_preop, score_sca, score_ic, score_ecg, examen, diagnostico, tratamiento, receta, indicaciones, mapa_diurno, mapa_nocturno, patron, holter)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (id, fecha_actual, motivo, antecedentes_evo, peso, talla, cintura, imc, bsa, pas, pad, score_fa, score_renal, score_preop, score_sca, score_ic, score_ecg, examen, diagnostico, tratamiento, receta, indicaciones, mapa_diurno, mapa_nocturno, patron, holter))
            conn.commit()
            mensaje_guardado = '<div style="background:#d4edda; color:#155724; padding:10px; border-radius:4px; margin-bottom:15px;">¡Consulta guardada correctamente en el historial!</div>'

    cursor.execute("SELECT fecha, motivo, antecedentes_evo, diagnostico, tratamiento, pas, pad, peso, score_fa, score_renal, score_preop, score_sca, score_ic, score_ecg FROM historial WHERE paciente_id = ? ORDER BY id ASC", (id,))
    historiales = cursor.fetchall()
    
    cursor.execute("SELECT id, nombre_estudio, archivo, fecha FROM estudios WHERE paciente_id = ? ORDER BY id DESC", (id,))
    estudios = cursor.fetchall()

    # Cargar vademécum dinámico desde la BD
    cursor.execute("SELECT categoria, nombre FROM vademecum ORDER BY categoria, nombre")
    vademecum_rows = cursor.fetchall()
    conn.close()

    vademecum_dict = {}
    for cat, nom in vademecum_rows:
        if cat not in vademecum_dict:
            vademecum_dict[cat] = []
        vademecum_dict[cat].append(nom)

    vademecum_options_html = '<option value="">-- Seleccionar Fármaco --</option>'
    for cat, meds in vademecum_dict.items():
        vademecum_options_html += f'<optgroup label="{cat}">'
        for m in meds:
            vademecum_options_html += f'<option value="{m}">{m}</option>'
        vademecum_options_html += '</optgroup>'

    edad_actual = calcular_edad(paciente[3])
    
    fechas_js = [h[0].split()[0] for h in historiales]
    pas_js = [int(h[5]) if h[5] and h[5].isdigit() else 0 for h in historiales]
    pad_js = [int(h[6]) if h[6] and h[6].isdigit() else 0 for h in historiales]
    peso_js = [float(h[7]) if h[7] and h[7].replace('.','',1).isdigit() else 0 for h in historiales]

    historial_html = ""
    for h in reversed(historiales):
        scores_extras = ""
        if h[8]: scores_extras += f"<br>• <b>Fibrilación Auricular:</b> {h[8]}"
        if h[9]: scores_extras += f"<br>• <b>Función Renal:</b> {h[9]}"
        if h[10]: scores_extras += f"<br>• <b>Prequirúrgico:</b> {h[10]}"
        if h[11]: scores_extras += f"<br>• <b>SCA (GRACE/TIMI):</b> {h[11]}"
        if h[12]: scores_extras += f"<br>• <b>Insuficiencia Cardíaca:</b> {h[12]}"
        if h[13]: scores_extras += f"<br>• <b>Electrocardiograma (QTc):</b> {h[13]}"

        extra_div = f"""<div style="font-size:11px; color:#2563eb; margin-top:4px; background:#eff6ff; padding:5px; border-radius:4px;">
            <b>Scores y Parámetros:</b> {scores_extras}
        </div>""" if scores_extras else ""

        ant_evo = f"<br><b>Antecedentes:</b> {h[2]}" if h[2] else ""

        historial_html += f"""
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-left:4px solid #3498db; padding:12px; border-radius:6px; margin-bottom:12px;">
            <span style="font-size:11px; color:#64748b;">{h[0]}</span><br>
            <b>Motivo:</b> {h[1] or '-'}{ant_evo}<br>
            <b>Dx:</b> {h[3] or '-'}<br>
            <b>Plan / Tratamiento:</b> {h[4] or '-'}
            {extra_div}
        </div>
        """
    if not historial_html:
        historial_html = "<p style='color:#7f8c8d; font-size:14px;'>No hay consultas previas registradas para este paciente.</p>"

    estudios_html = ""
    for est in estudios:
        estudios_html += f"""
        <div style="background:#fdfefe; border:1px solid #e2e8f0; padding:8px 12px; border-radius:4px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <b>{est[1]}</b><br><span style="font-size:11px; color:#666;">{est[3]}</span>
            </div>
            <a href="/uploads/{est[2]}" target="_blank" style="background:#9b59b6; color:white; padding:5px 10px; text-decoration:none; border-radius:4px; font-size:12px; font-weight:bold;">Ver Archivo</a>
        </div>
        """
    if not estudios_html:
        estudios_html = "<p style='color:#7f8c8d; font-size:13px;'>No hay estudios adjuntos.</p>"

    alerta_alergia = ""
    if paciente[9] and paciente[9].lower() != "ninguna":
        alerta_alergia = f"<div style='background:#e74c3c; color:white; padding:8px 12px; border-radius:4px; font-weight:bold; margin-top:10px; font-size:13px;'>🚨 ALERTA DE ALERGIA: {paciente[9]}</div>"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Ficha del Paciente - CardioSys</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
        let edadPacienteNum = {edad_paciente_num};
        let sexoPacienteStr = "{sexo_paciente}";

        function seleccionarFarmaco(selectObj) {{
            let recetaInput = document.getElementById('receta_input');
            if (selectObj.value) {{
                recetaInput.value += (recetaInput.value ? " | " : "") + selectObj.value;
                selectObj.value = "";
            }}
        }}
        function agregarTexto(texto) {{
            let campo = document.getElementById('tratamiento_evolucion');
            campo.value += (campo.value ? " " : "") + texto;
        }}
        function toggleCalc(id) {{
            let el = document.getElementById(id);
            el.style.display = (el.style.display === 'none' || el.style.display === '') ? 'block' : 'none';
        }}

        function vincularRecetaAEvolucion() {{
            let diagReceta = document.getElementById('diagnostico_receta_input').value;
            let farmacosReceta = document.getElementById('receta_input').value;
            if (!diagReceta && !farmacosReceta) {{
                alert("Complete el diagnóstico o los medicamentos en la tarjeta de receta primero.");
                return;
            }}
            if (diagReceta) document.getElementById('diagnostico_evolucion').value = diagReceta;
            if (farmacosReceta) {{
                let campoTratamiento = document.getElementById('tratamiento_evolucion');
                campoTratamiento.value += (campoTratamiento.value ? "\\n" : "") + "Prescripción: " + farmacosReceta;
            }}
            alert("¡Diagnóstico y Tratamiento vinculados con éxito a la Evolución de Hoy!");
        }}

        function calcularAntropometria() {{
            let p = parseFloat(document.getElementById('form_peso').value);
            let t = parseFloat(document.getElementById('form_talla').value);
            if (!p || !t || isNaN(p) || isNaN(t)) {{
                document.getElementById('form_imc').value = '';
                document.getElementById('form_bsa').value = '';
                return;
            }}
            let imc = (p / ((t / 100) * (t / 100))).toFixed(1);
            let clasificacionIMC = imc < 18.5 ? "Bajo peso" : imc < 25 ? "Normal" : imc < 30 ? "Sobrepeso" : imc < 35 ? "Obesidad I" : imc < 40 ? "Obesidad II" : "Obesidad III";
            let imcTexto = imc + " (" + clasificacionIMC + ")";
            document.getElementById('form_imc').value = imcTexto;

            let bsa = Math.sqrt((p * t) / 3600).toFixed(2);
            document.getElementById('form_bsa').value = bsa + " m²";
        }}

        // 1. CHA₂DS₂-VA
        function calcFA_VA() {{
            let ptsVA = 0;
            if(document.getElementById('va_chf').checked) ptsVA++;
            if(document.getElementById('va_htn').checked) ptsVA++;
            let edadVal = parseInt(document.getElementById('va_edad_select').value) || 0;
            ptsVA += edadVal;
            if(document.getElementById('va_dm').checked) ptsVA++;
            if(document.getElementById('va_stroke').checked) ptsVA += 2;
            if(document.getElementById('va_vasc').checked) ptsVA++;
            document.getElementById('res_va').innerText = "CHA₂DS₂-VA: " + ptsVA + " pts";
        }}

        // 2. HAS-BLED
        function calcFA_HB() {{
            let ptsHB = 0;
            if(document.getElementById('hb_htn').checked) ptsHB++;
            if(document.getElementById('hb_renal').checked) ptsHB++;
            if(document.getElementById('hb_liver').checked) ptsHB++;
            if(document.getElementById('hb_stroke').checked) ptsHB++;
            if(document.getElementById('hb_bleed').checked) ptsHB++;
            if(document.getElementById('hb_labile').checked) ptsHB++;
            if(document.getElementById('hb_elderly').checked) ptsHB++;
            if(document.getElementById('hb_drugs').checked) ptsHB++;
            document.getElementById('res_hb').innerText = "HAS-BLED: " + ptsHB + " pts";
        }}

        // 3. Cockcroft-Gault
        function calcCockcroft() {{
            let scr = parseFloat(document.getElementById('cg_scr').value);
            let p = parseFloat(document.getElementById('form_peso').value) || 70;
            if(!scr) {{ alert("Ingrese creatinina sérica."); return; }}
            let isFem = (sexoPacienteStr.toLowerCase() === 'mujer');
            let cg = ((140 - edadPacienteNum) * p) / (72 * scr);
            if(isFem) cg *= 0.85;
            document.getElementById('res_cg').innerText = "Cockcroft-Gault (CrCl): " + cg.toFixed(1) + " mL/min";
        }}

        // 4. CKD-EPI 2021
        function calcCKDEPI() {{
            let scr = parseFloat(document.getElementById('ren_scr').value);
            if(!scr) {{ alert("Ingrese creatinina sérica."); return; }}
            let isFem = (sexoPacienteStr.toLowerCase() === 'mujer');
            let kappa = isFem ? 0.7 : 0.9;
            let alfa = isFem ? -0.241 : -0.302;
            let minVal = Math.min(scr / kappa, 1);
            let maxVal = Math.max(scr / kappa, 1);
            let factorFem = isFem ? 1.012 : 1.0;
            let tfg = (142 * Math.pow(minVal, alfa) * Math.pow(maxVal, -1.200) * Math.pow(0.9938, edadPacienteNum) * factorFem).toFixed(1);
            let estadioG = tfg >= 90 ? "G1 (≥90)" : tfg >= 60 ? "G2 (60-89)" : tfg >= 45 ? "G3a (45-59)" : tfg >= 30 ? "G3b (30-44)" : tfg >= 15 ? "G4 (15-29)" : "G5 (<15)";
            document.getElementById('res_ckdepi').innerText = "CKD-EPI 2021 (TFG): " + tfg + " mL/min [" + estadioG + "]";
        }}

        // 5. RAC
        function calcRAC() {{
            let alb = parseFloat(document.getElementById('ren_alb').value);
            let creaU = parseFloat(document.getElementById('ren_creau').value);
            if(!alb || !creaU) {{ alert("Ingrese albúmina y creatinina urinaria."); return; }}
            let rac = (alb / creaU).toFixed(1);
            let estadioA = rac < 30 ? "A1 (<30 mg/g)" : rac <= 300 ? "A2 (30-300 mg/g)" : "A3 (>300 mg/g)";
            document.getElementById('res_rac').innerText = "RAC: " + rac + " mg/g [" + estadioA + "]";
        }}

        // 6. PREQUIRÚRGICO
        function calcPreOp() {{
            let tipoCx = document.getElementById('pre_tipo_cx').value || 'General';
            let riesgoCx = document.getElementById('pre_riesgo_cx').value || 'Moderado';
            let caracter = document.getElementById('pre_caracter').value || 'Electiva';
            let mets = document.getElementById('pre_mets').value || '4-10 METs';
            let asa = document.getElementById('pre_asa').value || 'ASA II';
            let condActivas = document.getElementById('pre_cond').value || 'Ninguna';

            let leePts = 0;
            if(document.getElementById('lee_qx').checked) leePts++;
            if(document.getElementById('lee_ihq').checked) leePts++;
            if(document.getElementById('lee_icc').checked) leePts++;
            if(document.getElementById('lee_avc').checked) leePts++;
            if(document.getElementById('lee_dm').checked) leePts++;
            if(document.getElementById('lee_crea').checked) leePts++;

            let rcriClase = leePts === 0 ? "Clase I (~0.4%)" : leePts === 1 ? "Clase II (~1.3%)" : leePts === 2 ? "Clase III (~4%)" : "Clase IV (>9%)";
            let res = "Pre-Op [" + caracter + "] - Cx: " + tipoCx + " (" + riesgoCx + ") | METs: " + mets + " | " + asa + " | RCRI/Lee: " + leePts + " pto(s) (" + rcriClase + ") | Cond. Activas: " + condActivas;
            document.getElementById('preop_res').innerText = res;
        }}

        // 7. GRACE 2.0
        function calcGRACE() {{
            let edad = edadPacienteNum;
            let fc = parseFloat(document.getElementById('grace_fc').value) || 75;
            let pas = parseFloat(document.getElementById('grace_pas').value) || 120;
            let crea = parseFloat(document.getElementById('grace_crea').value) || 1.0;
            let killip = parseInt(document.getElementById('grace_killip').value) || 1;
            let arresto = document.getElementById('grace_arresto').checked ? 1 : 0;
            let stDev = document.getElementById('grace_st').checked ? 1 : 0;
            let enzimas = document.getElementById('grace_enzimas').checked ? 1 : 0;

            let pEdad = edad < 30 ? 0 : edad < 40 ? 8 : edad < 50 ? 25 : edad < 60 ? 41 : edad < 70 ? 58 : edad < 80 ? 75 : 91;
            let pFC = fc < 70 ? 0 : fc < 90 ? 3 : fc < 110 ? 9 : fc < 150 ? 15 : fc < 200 ? 24 : 38;
            let pPAS = pas < 80 ? 58 : pas < 100 ? 53 : pas < 120 ? 43 : pas < 140 ? 34 : pas < 160 ? 24 : pas < 200 ? 10 : 0;
            let pCrea = crea < 0.4 ? 1 : crea < 0.8 ? 3 : crea < 1.2 ? 4 : crea < 1.6 ? 7 : crea < 2.0 ? 10 : crea < 4.0 ? 13 : 21;
            let pKillip = killip == 1 ? 0 : killip == 2 ? 21 : killip == 3 ? 43 : 64;
            let pArresto = arresto ? 39 : 0;
            let pST = stDev ? 28 : 0;
            let pEnzimas = enzimas ? 14 : 0;

            let totalGrace = pEdad + pFC + pPAS + pCrea + pKillip + pArresto + pST + pEnzimas;
            let riesgoGrace = totalGrace < 108 ? "Bajo riesgo" : totalGrace <= 140 ? "Riesgo Intermedio" : "Alto riesgo";
            document.getElementById('res_grace').innerText = "GRACE 2.0: " + totalGrace + " pts (" + riesgoGrace + ")";
        }}

        // 8. TIMI SCASEST
        function calcTIMISCASEST() {{
            let timiSCASEST = 0;
            if(document.getElementById('t_edad').checked) timiSCASEST++;
            if(document.getElementById('t_factores').checked) timiSCASEST++;
            if(document.getElementById('t_estenosis').checked) timiSCASEST++;
            if(document.getElementById('t_aspirina').checked) timiSCASEST++;
            if(document.getElementById('t_angina').checked) timiSCASEST++;
            if(document.getElementById('t_st').checked) timiSCASEST++;
            if(document.getElementById('t_enzimas').checked) timiSCASEST++;
            document.getElementById('res_timi_scasest').innerText = "TIMI SCASEST: " + timiSCASEST + "/7 pts";
        }}

        // 9. TIMI STEMI
        function calcTIMISTEMI() {{
            let timiSTEMI = 0;
            if(document.getElementById('ts_edad').checked) timiSTEMI += 2;
            if(document.getElementById('ts_diabetes').checked) timiSTEMI++;
            if(document.getElementById('ts_angina').checked) timiSTEMI++;
            if(document.getElementById('ts_pas').checked) timiSTEMI += 3;
            if(document.getElementById('ts_fc').checked) timiSTEMI += 2;
            if(document.getElementById('ts_killip').checked) timiSTEMI += 2;
            if(document.getElementById('ts_peso').checked) timiSTEMI++;
            if(document.getElementById('ts_anterior').checked) timiSTEMI++;
            if(document.getElementById('ts_tiempo').checked) timiSTEMI++;
            document.getElementById('res_timi_stemi').innerText = "TIMI STEMI: " + timiSTEMI + "/14 pts";
        }}

        // 10. H₂FPEF
        function calcH2FPEF() {{
            let h2 = 0;
            if(document.getElementById('h2_bmi').checked) h2 += 2;
            if(document.getElementById('h2_htn').checked) h2 += 1;
            if(document.getElementById('h2_af').checked) h2 += 3;
            if(document.getElementById('h2_pap').checked) h2 += 1;
            if(document.getElementById('h2_edad').checked) h2 += 1;
            if(document.getElementById('h2_ee').checked) h2 += 1;
            document.getElementById('res_h2fpef').innerText = "H₂FPEF Score: " + h2 + "/9 pts";
        }}

        // 11. HFA-PEFF
        function calcPEFF() {{
            let f = parseInt(document.querySelector('input[name="peff_f"]:checked')?.value || 0);
            let m = parseInt(document.querySelector('input[name="peff_m"]:checked')?.value || 0);
            let b = parseInt(document.querySelector('input[name="peff_b"]:checked')?.value || 0);
            let total = f + m + b;
            let cat = total >= 5 ? "Definitivo (HFpEF)" : total >= 2 ? "Intermedio / Indeterminado" : "Improbable";
            document.getElementById('res_peff').innerText = "HFA-PEFF: " + total + "/6 pts (" + cat + ")";
        }}

        // 12. MAGGIC
        function calcMAGGIC() {{
            let val = document.getElementById('maggic_input').value || 'Medio';
            document.getElementById('res_maggic').innerText = "MAGGIC Score: " + val;
        }}

        // 13 & 14. QTc BAZETT Y FRIDERICIA
        function calcQTc() {{
            let qt = parseFloat(document.getElementById('ecg_qt').value);
            let fc = parseFloat(document.getElementById('ecg_fc').value);
            if(!qt || !fc) {{ alert("Ingrese QT (ms) y FC (lpm)."); return; }}
            let rr = 60 / fc;
            let qtcB = (qt / Math.sqrt(rr)).toFixed(0);
            let qtcF = (qt / Math.cbrt(rr)).toFixed(0);
            document.getElementById('res_qtc_b').innerText = "QTc Bazett: " + qtcB + " ms";
            document.getElementById('res_qtc_f').innerText = "QTc Fridericia: " + qtcF + " ms";
        }}

        function pasarIndependiente(elementId, inputId, rowId) {{
            let texto = document.getElementById(elementId).innerText;
            if(!texto) {{ alert("Primero calcule el score correspondiente."); return; }}
            let target = document.getElementById(inputId);
            target.value += (target.value ? " | " : "") + texto;
            let row = document.getElementById(rowId);
            if(row) row.style.display = 'block';
            alert("¡Resultado transferido a su campo en la evolución!");
        }}
        </script>
    </head>
    <body style="font-family:Segoe UI; background:#f4f7f6; margin:0; display:flex; height:100vh;">
        <div style="width:260px; background:#1e293b; color:white; padding:20px; box-sizing:border-box; display:flex; flex-direction:column;">
            <h2 style="color:white; margin-top:0; margin-bottom:5px;">CardioSys 1.0</h2>
            <p style="color:#38bdf8; font-size:15px; font-weight:bold; margin-top:0; margin-bottom:25px; line-height:1.3;">Dr. Herve Benitez</p>
            <ul style="list-style:none; padding:0; margin-top:0; flex:1;">
                <li style="margin:15px 0;"><a href="/" style="color:#38bdf8; text-decoration:none; font-weight:bold;">📋 Agenda de Hoy</a></li>
                <li style="margin:15px 0;"><a href="/nuevo" style="color:white; text-decoration:none;">➕ Nuevo Ingreso</a></li>
                <li style="margin:15px 0;"><a href="/estudios-recientes" style="color:white; text-decoration:none;">📁 Estudios Recientes</a></li>
            </ul>
            <div style="margin-bottom:20px;">
                <a href="/backup" style="display:block; background:#e67e22; color:white; padding:12px; text-align:center; text-decoration:none; border-radius:6px; font-weight:bold;">💾 Backup Manual</a>
            </div>
        </div>
        <div style="flex:1; padding:30px; overflow-y:auto;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <a href="/" style="color:#3498db; text-decoration:none; font-weight:bold;">⬅ Volver al Panel</a>
            </div>
            {mensaje_guardado}
            
            <!-- TARJETA SUPERIOR PRINCIPAL -->
            <div style="background:#1e293b; color:white; padding:25px; border-radius:8px; display:flex; justify-content:space-between; align-items:flex-start; box-shadow:0 4px 12px rgba(0,0,0,0.1); margin-bottom:30px;">
                <div style="flex:2;">
                    <h1 style="margin:0 0 10px 0; font-size:26px;">{paciente[2]}</h1>
                    <div style="display:flex; gap:20px; font-size:14px; color:#cbd5e1; flex-wrap:wrap; margin-bottom:10px;">
                        <span><b>C.I.:</b> {paciente[1]}</span>
                        <span><b>Nacimiento:</b> {paciente[3]} ({edad_actual})</span>
                        <span><b>Sexo:</b> {paciente[4] or 'N/D'}</span>
                        <span><b>Profesión:</b> {paciente[6] or 'N/D'}</span>
                        <span><b>Sanatorio:</b> {paciente[7] or 'N/D'}</span>
                        <span><b>Teléfono:</b> {paciente[5]}</span>
                    </div>
                    <div style="font-size:13px; color:#94a3b8; background:rgba(255,255,255,0.05); padding:10px; border-radius:6px;">
                        <span><b>Antecedentes:</b> {paciente[10] or 'Ninguno registrado'}</span>
                    </div>
                    {alerta_alergia}
                </div>

                <div style="flex:1.4; background:rgba(255,255,255,0.08); padding:20px; border-radius:8px;">
                    <form method="POST" action="/generar_receta_pdf/{paciente[0]}" target="_blank">
                        <label style="font-size:13px; font-weight:bold;">Diagnóstico:</label>
                        <input type="text" id="diagnostico_receta_input" name="diagnostico" placeholder="Ej: Hipertensión Arterial" style="width:100%; padding:8px; margin:5px 0 10px 0; border-radius:4px; border:none; box-sizing:border-box;">
                        
                        <label style="font-size:13px; font-weight:bold;">Vademécum:</label>
                        <select onchange="seleccionarFarmaco(this)" style="width:100%; padding:8px; margin:5px 0 8px 0; border-radius:4px; border:none; font-size:12px; background:#f1f5f9; cursor:pointer;">
                            {vademecum_options_html}
                        </select>
                    </form>

                    <!-- FORMULARIO PARA AGREGAR NUEVO FÁRMACO AL VADEMÉCUM -->
                    <form method="POST" action="/agregar_vademecum/{paciente[0]}" style="background:rgba(255,255,255,0.05); padding:8px; border-radius:4px; margin-bottom:10px;">
                        <label style="font-size:11px; font-weight:bold; color:#38bdf8;">➕ Guardar Nuevo Fármaco/Comercial:</label>
                        <div style="display:flex; gap:5px; margin-top:4px;">
                            <input type="text" name="cat_vademecum" placeholder="Categoría" style="flex:1; padding:4px; font-size:11px; border-radius:4px; border:none;" required>
                            <input type="text" name="nuevo_farmaco" placeholder="Nombre y Dosis" style="flex:1.5; padding:4px; font-size:11px; border-radius:4px; border:none;" required>
                            <button type="submit" style="background:#10b981; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer; font-weight:bold;">Guardar</button>
                        </div>
                    </form>

                    <form method="POST" action="/generar_receta_pdf/{paciente[0]}" target="_blank">
                        <input type="hidden" name="diagnostico" id="diag_hidden">
                        <label style="font-size:13px; font-weight:bold;">Rx (Medicamentos):</label>
                        <textarea id="receta_input" name="receta" rows="3" placeholder="Ej: Losartán 50mg..." style="width:100%; padding:8px; margin:5px 0 10px 0; border-radius:4px; border:none; box-sizing:border-box;"></textarea>
                        
                        <label style="font-size:13px; font-weight:bold;">Indicaciones de Uso:</label>
                        <textarea name="indicaciones" rows="3" placeholder="Ej: Tomar con agua..." style="width:100%; padding:8px; margin:5px 0 15px 0; border-radius:4px; border:none; box-sizing:border-box;"></textarea>
                        
                        <button type="button" onclick="vincularRecetaAEvolucion()" style="background:#0284c7; color:white; border:none; padding:8px; border-radius:4px; font-weight:bold; cursor:pointer; width:100%; margin-bottom:8px; font-size:12px;">🔗 Copiar a Evolución de Hoy</button>
                        
                        <button type="submit" onclick="document.getElementById('diag_hidden').value = document.getElementById('diagnostico_receta_input').value;" style="background:#e74c3c; color:white; border:none; padding:10px 15px; border-radius:6px; font-weight:bold; cursor:pointer; width:100%;">📄 Generar Receta PDF Oficial</button>
                    </form>
                </div>
            </div>

            <!-- SECCIÓN CENTRAL: EVOLUCIÓN Y HISTORIAL -->
            <div style="display:flex; gap:25px; margin-bottom:30px;">
                <div style="flex:1.5; background:white; padding:25px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                    <h3 style="margin-top:0; color:#2c3e50;">Evolución de Hoy</h3>
                    
                    <!-- BOTONES SEPARADOS PARA CADA CALCULADORA INDEPENDIENTE -->
                    <div style="margin-bottom:15px; display:flex; gap:5px; flex-wrap:wrap;">
                        <button type="button" onclick="toggleCalc('calc_va')" style="background:#2563eb; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">⚡ CHA₂DS₂-VA</button>
                        <button type="button" onclick="toggleCalc('calc_hb')" style="background:#1d4ed8; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">🩸 HAS-BLED</button>
                        <button type="button" onclick="toggleCalc('calc_cg')" style="background:#1e40af; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">⚙️ Cockcroft-Gault</button>
                        <button type="button" onclick="toggleCalc('calc_ckdepi')" style="background:#7c3aed; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">🧪 CKD-EPI 2021</button>
                        <button type="button" onclick="toggleCalc('calc_rac')" style="background:#6d28d9; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">🧬 Albúmina/Crea (RAC)</button>
                        <button type="button" onclick="toggleCalc('calc_preop')" style="background:#d97706; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">🏥 Prequirúrgico (RCRI/ASA)</button>
                        <button type="button" onclick="toggleCalc('calc_grace')" style="background:#e11d48; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">❤️ GRACE 2.0</button>
                        <button type="button" onclick="toggleCalc('calc_timiscasest')" style="background:#be123c; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">❤️ TIMI SCASEST</button>
                        <button type="button" onclick="toggleCalc('calc_timistemi')" style="background:#9f1239; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">❤️ TIMI STEMI</button>
                        <button type="button" onclick="toggleCalc('calc_h2fpef')" style="background:#0284c7; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">🫀 H₂FPEF</button>
                        <button type="button" onclick="toggleCalc('calc_peff')" style="background:#0369a1; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">🫀 HFA-PEFF (Guías ESC)</button>
                        <button type="button" onclick="toggleCalc('calc_maggic')" style="background:#075985; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">🫀 MAGGIC</button>
                        <button type="button" onclick="toggleCalc('calc_qtc')" style="background:#0f172a; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">📈 QTc (Bazett/Fridericia)</button>
                        <button type="button" onclick="toggleCalc('seccion_mapa_holter')" style="background:#475569; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">📊 MAPA / Holter</button>
                        <button type="button" onclick="toggleCalc('seccion_generador_informes')" style="background:#0284c7; color:white; border:none; padding:7px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;">📝 Generador de Informes PDF</button>
                    </div>

                    <!-- 1. CHA₂DS₂-VA -->
                    <div id="calc_va" style="display:none; background:#f8fafc; border:1px solid #2563eb; padding:12px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 8px 0; color:#2563eb; font-size:13px;">⚡ Calculadora CHA₂DS₂-VA</h4>
                        <div style="font-size:11px; margin:4px 0; display:flex; gap:8px; flex-wrap:wrap;">
                            <label><input type="checkbox" id="va_chf"> ICC (+1)</label>
                            <label><input type="checkbox" id="va_htn"> HTA (+1)</label>
                            <label>Edad: <select id="va_edad_select" style="font-size:11px;"><option value="0">&lt;65</option><option value="1">65-74 (+1)</option><option value="2">≥75 (+2)</option></select></label>
                            <label><input type="checkbox" id="va_dm"> DM (+1)</label>
                            <label><input type="checkbox" id="va_stroke"> ACV/AIT (+2)</label>
                            <label><input type="checkbox" id="va_vasc"> Vasculopatía (+1)</label>
                        </div>
                        <button type="button" onclick="calcFA_VA()" style="background:#2563eb; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Calcular CHA₂DS₂-VA</button>
                        <button type="button" onclick="pasarIndependiente('res_va', 'input_score_fa', 'row_score_fa')" style="background:#2c3e50; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">📥 Pasar a campo FA</button>
                        <span id="res_va" style="font-size:11px; font-weight:bold; color:#2563eb; display:block; margin-top:4px;"></span>
                    </div>

                    <!-- 2. HAS-BLED -->
                    <div id="calc_hb" style="display:none; background:#f8fafc; border:1px solid #1d4ed8; padding:12px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 8px 0; color:#1d4ed8; font-size:13px;">🩸 Calculadora HAS-BLED</h4>
                        <div style="font-size:11px; margin:4px 0; display:flex; gap:8px; flex-wrap:wrap;">
                            <label><input type="checkbox" id="hb_htn"> HTA (+1)</label>
                            <label><input type="checkbox" id="hb_renal"> Renal (+1)</label>
                            <label><input type="checkbox" id="hb_liver"> Hepática (+1)</label>
                            <label><input type="checkbox" id="hb_stroke"> ACV (+1)</label>
                            <label><input type="checkbox" id="hb_bleed"> Sangrado (+1)</label>
                            <label><input type="checkbox" id="hb_labile"> INR labil (+1)</label>
                            <label><input type="checkbox" id="hb_elderly"> Edad &gt; 65 (+1)</label>
                            <label><input type="checkbox" id="hb_drugs"> Fármacos/Alcohol (+1)</label>
                        </div>
                        <button type="button" onclick="calcFA_HB()" style="background:#1d4ed8; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Calcular HAS-BLED</button>
                        <button type="button" onclick="pasarIndependiente('res_hb', 'input_score_fa', 'row_score_fa')" style="background:#2c3e50; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">📥 Pasar a campo FA</button>
                        <span id="res_hb" style="font-size:11px; font-weight:bold; color:#1d4ed8; display:block; margin-top:4px;"></span>
                    </div>

                    <!-- 3. COCKCROFT-GAULT -->
                    <div id="calc_cg" style="display:none; background:#f8fafc; border:1px solid #1e40af; padding:12px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 8px 0; color:#1e40af; font-size:13px;">⚙️ Calculadora Cockcroft-Gault (CrCl)</h4>
                        <div style="margin:5px 0;">
                            <input type="number" step="0.01" id="cg_scr" placeholder="Creatinina sérica (mg/dL)" style="padding:4px; font-size:11px; border:1px solid #ccc; border-radius:4px; width:220px;">
                        </div>
                        <button type="button" onclick="calcCockcroft()" style="background:#1e40af; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Calcular CrCl</button>
                        <button type="button" onclick="pasarIndependiente('res_cg', 'input_score_renal', 'row_score_renal')" style="background:#2c3e50; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">📥 Pasar a campo Renal</button>
                        <span id="res_cg" style="font-size:11px; font-weight:bold; color:#1e40af; display:block; margin-top:4px;"></span>
                    </div>

                    <!-- 4. CKD-EPI 2021 -->
                    <div id="calc_ckdepi" style="display:none; background:#f8fafc; border:1px solid #7c3aed; padding:12px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 8px 0; color:#7c3aed; font-size:13px;">🧪 Calculadora CKD-EPI 2021 (TFG & KDIGO G1-G5)</h4>
                        <div style="margin:5px 0;">
                            <input type="number" step="0.01" id="ren_scr" placeholder="Creatinina sérica (mg/dL)" style="padding:4px; font-size:11px; border:1px solid #ccc; border-radius:4px; width:220px;">
                        </div>
                        <button type="button" onclick="calcCKDEPI()" style="background:#7c3aed; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Calcular TFG</button>
                        <button type="button" onclick="pasarIndependiente('res_ckdepi', 'input_score_renal', 'row_score_renal')" style="background:#2c3e50; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">📥 Pasar a campo Renal</button>
                        <span id="res_ckdepi" style="font-size:11px; font-weight:bold; color:#7c3aed; display:block; margin-top:4px;"></span>
                    </div>

                    <!-- 5. RAC -->
                    <div id="calc_rac" style="display:none; background:#f8fafc; border:1px solid #6d28d9; padding:12px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 8px 0; color:#6d28d9; font-size:13px;">🧬 Relación Albúmina / Creatinina (RAC & KDIGO A1-A3)</h4>
                        <div style="display:flex; gap:6px; margin:5px 0;">
                            <input type="number" step="0.1" id="ren_alb" placeholder="Albúmina urinaria (mg/L)" style="flex:1; padding:4px; font-size:11px; border:1px solid #ccc; border-radius:4px;">
                            <input type="number" step="0.1" id="ren_creau" placeholder="Creatinina urinaria (mg/dL)" style="flex:1; padding:4px; font-size:11px; border:1px solid #ccc; border-radius:4px;">
                        </div>
                        <button type="button" onclick="calcRAC()" style="background:#6d28d9; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Calcular RAC</button>
                        <button type="button" onclick="pasarIndependiente('res_rac', 'input_score_renal', 'row_score_renal')" style="background:#2c3e50; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">📥 Pasar a campo Renal</button>
                        <span id="res_rac" style="font-size:11px; font-weight:bold; color:#6d28d9; display:block; margin-top:4px;"></span>
                    </div>

                    <!-- 6. PREQUIRÚRGICO -->
                    <div id="calc_preop" style="display:none; background:#f8fafc; border:1px solid #d97706; padding:12px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 8px 0; color:#d97706; font-size:13px;">🏥 Evaluador Prequirúrgico (ASA, RCRI/Lee, METs, Tipo, Urgente/Electiva, Cond. Activas)</h4>
                        <div style="display:flex; gap:6px; margin:5px 0; flex-wrap:wrap;">
                            <input type="text" id="pre_tipo_cx" placeholder="Tipo de cirugía" style="flex:1; padding:4px; font-size:11px; border:1px solid #ccc; border-radius:4px;">
                            <select id="pre_riesgo_cx" style="font-size:11px;"><option value="Bajo riesgo">Bajo riesgo</option><option value="Moderado riesgo" selected>Moderado riesgo</option><option value="Alto riesgo">Alto riesgo</option></select>
                            <select id="pre_caracter" style="font-size:11px;"><option value="Electiva" selected>Electiva</option><option value="Urgente">Urgente</option></select>
                            <select id="pre_mets" style="font-size:11px;"><option value="&lt;4 METs">&lt;4 METs</option><option value="4-10 METs" selected>4-10 METs</option><option value="&gt;10 METs">&gt;10 METs</option></select>
                            <select id="pre_asa" style="font-size:11px;"><option value="ASA I">ASA I</option><option value="ASA II" selected>ASA II</option><option value="ASA III">ASA III</option><option value="ASA IV">ASA IV</option></select>
                        </div>
                        <div style="margin:5px 0;">
                            <input type="text" id="pre_cond" placeholder="Condiciones cardiovasculares activas (ej: IAM reciente, ICC descompensada)" style="width:100%; padding:4px; font-size:11px; border:1px solid #ccc; border-radius:4px;">
                        </div>
                        <div style="font-size:11px; display:flex; gap:8px; flex-wrap:wrap; margin:4px 0;">
                            <label><input type="checkbox" id="lee_qx"> Cx alto riesgo (+1)</label>
                            <label><input type="checkbox" id="lee_ihq"> Cardiopatía isquémica (+1)</label>
                            <label><input type="checkbox" id="lee_icc"> ICC (+1)</label>
                            <label><input type="checkbox" id="lee_avc"> ACV/AIT (+1)</label>
                            <label><input type="checkbox" id="lee_dm"> DM insulino-dep. (+1)</label>
                            <label><input type="checkbox" id="lee_crea"> Crea &gt; 2.0 (+1)</label>
                        </div>
                        <button type="button" onclick="calcPreOp()" style="background:#d97706; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Calcular Pre-Op</button>
                        <button type="button" onclick="pasarIndependiente('preop_res', 'input_score_preop', 'row_score_preop')" style="background:#2c3e50; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">📥 Pasar a su campo</button>
                        <span id="preop_res" style="font-size:11px; font-weight:bold; color:#d97706; display:block; margin-top:4px;"></span>
                    </div>

                    <!-- 7. GRACE 2.0 -->
                    <div id="calc_grace" style="display:none; background:#f8fafc; border:1px solid #e11d48; padding:12px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 8px 0; color:#e11d48; font-size:13px;">❤️ Calculadora GRACE 2.0 (Edad auto = {edad_paciente_num} años)</h4>
                        <div style="display:flex; gap:6px; margin:5px 0; flex-wrap:wrap;">
                            <input type="number" id="grace_fc" placeholder="FC (lpm)" style="flex:1; padding:4px; font-size:11px; border:1px solid #ccc; border-radius:4px;">
                            <input type="number" id="grace_pas" placeholder="PAS (mmHg)" style="flex:1; padding:4px; font-size:11px; border:1px solid #ccc; border-radius:4px;">
                            <input type="number" step="0.1" id="grace_crea" placeholder="Creatinina (mg/dL)" style="flex:1; padding:4px; font-size:11px; border:1px solid #ccc; border-radius:4px;">
                            <select id="grace_killip" style="font-size:11px;"><option value="1">Killip I</option><option value="2">Killip II</option><option value="3">Killip III</option><option value="4">Killip IV</option></select>
                        </div>
                        <div style="font-size:11px; margin:4px 0; display:flex; gap:8px; flex-wrap:wrap;">
                            <label><input type="checkbox" id="grace_arresto"> Paro al ingreso</label>
                            <label><input type="checkbox" id="grace_st"> Desv. ST</label>
                            <label><input type="checkbox" id="grace_enzimas"> Enzimas elevadas</label>
                        </div>
                        <button type="button" onclick="calcGRACE()" style="background:#e11d48; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Calcular GRACE</button>
                        <button type="button" onclick="pasarIndependiente('res_grace', 'input_score_sca', 'row_score_sca')" style="background:#2c3e50; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">📥 Pasar a campo SCA</button>
                        <span id="res_grace" style="font-size:11px; font-weight:bold; color:#e11d48; display:block; margin-top:4px;"></span>
                    </div>

                    <!-- 8. TIMI SCASEST -->
                    <div id="calc_timiscasest" style="display:none; background:#f8fafc; border:1px solid #be123c; padding:12px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 8px 0; color:#be123c; font-size:13px;">❤️ Calculadora TIMI para SCASEST</h4>
                        <div style="font-size:11px; margin:4px 0; display:flex; gap:8px; flex-wrap:wrap;">
                            <label><input type="checkbox" id="t_edad"> Edad ≥ 65</label>
                            <label><input type="checkbox" id="t_factores"> ≥3 factores RC</label>
                            <label><input type="checkbox" id="t_estenosis"> Estenosis conocida</label>
                            <label><input type="checkbox" id="t_aspirina"> Uso aspirina 7d</label>
                            <label><input type="checkbox" id="t_angina"> Angina severa</label>
                            <label><input type="checkbox" id="t_st"> Desv. ST</label>
                            <label><input type="checkbox" id="t_enzimas"> Enzimas elevadas</label>
                        </div>
                        <button type="button" onclick="calcTIMISCASEST()" style="background:#be123c; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Calcular TIMI SCASEST</button>
                        <button type="button" onclick="pasarIndependiente('res_timi_scasest', 'input_score_sca', 'row_score_sca')" style="background:#2c3e50; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">📥 Pasar a campo SCA</button>
                        <span id="res_timi_scasest" style="font-size:11px; font-weight:bold; color:#be123c; display:block; margin-top:4px;"></span>
                    </div>

                    <!-- 9. TIMI STEMI -->
                    <div id="calc_timistemi" style="display:none; background:#f8fafc; border:1px solid #9f1239; padding:12px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 8px 0; color:#9f1239; font-size:13px;">❤️ Calculadora TIMI para STEMI</h4>
                        <div style="font-size:11px; margin:4px 0; display:flex; gap:8px; flex-wrap:wrap;">
                            <label><input type="checkbox" id="ts_edad"> Edad 65-75 (+2) / &gt;75 (+3)</label>
                            <label><input type="checkbox" id="ts_diabetes"> DM / HTA / Angina (+1)</label>
                            <label><input type="checkbox" id="ts_pas"> PAS &lt; 100 (+3)</label>
                            <label><input type="checkbox" id="ts_fc"> FC &gt; 100 (+2)</label>
                            <label><input type="checkbox" id="ts_killip"> Killip II-IV (+2)</label>
                            <label><input type="checkbox" id="ts_peso"> Peso &lt; 67kg (+1)</label>
                            <label><input type="checkbox" id="ts_anterior"> IAM anterior / BCRI (+1)</label>
                            <label><input type="checkbox" id="ts_tiempo"> Tiempo &gt; 4h (+1)</label>
                        </div>
                        <button type="button" onclick="calcTIMISTEMI()" style="background:#9f1239; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Calcular TIMI STEMI</button>
                        <button type="button" onclick="pasarIndependiente('res_timi_stemi', 'input_score_sca', 'row_score_sca')" style="background:#2c3e50; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">📥 Pasar a campo SCA</button>
                        <span id="res_timi_stemi" style="font-size:11px; font-weight:bold; color:#9f1239; display:block; margin-top:4px;"></span>
                    </div>

                    <!-- 10. H₂FPEF -->
                    <div id="calc_h2fpef" style="display:none; background:#f8fafc; border:1px solid #0284c7; padding:12px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 8px 0; color:#0284c7; font-size:13px;">🫀 Calculadora H₂FPEF (Insuficiencia Cardíaca)</h4>
                        <div style="font-size:11px; margin:4px 0; display:flex; gap:8px; flex-wrap:wrap;">
                            <label><input type="checkbox" id="h2_bmi"> IMC &gt; 30 (+2)</label>
                            <label><input type="checkbox" id="h2_htn"> ≥2 HTA (+1)</label>
                            <label><input type="checkbox" id="h2_af"> FA (+3)</label>
                            <label><input type="checkbox" id="h2_pap"> PAPs &gt; 35 (+1)</label>
                            <label><input type="checkbox" id="h2_edad"> Edad &gt; 60 (+1)</label>
                            <label><input type="checkbox" id="h2_ee"> E/e' &gt; 9 (+1)</label>
                        </div>
                        <button type="button" onclick="calcH2FPEF()" style="background:#0284c7; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Calcular H₂FPEF</button>
                        <button type="button" onclick="pasarIndependiente('res_h2fpef', 'input_score_ic', 'row_score_ic')" style="background:#2c3e50; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">📥 Pasar a campo IC</button>
                        <span id="res_h2fpef" style="font-size:11px; font-weight:bold; color:#0284c7; display:block; margin-top:4px;"></span>
                    </div>

                    <!-- 11. HFA-PEFF -->
                    <div id="calc_peff" style="display:none; background:#f8fafc; border:1px solid #0369a1; padding:14px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 10px 0; color:#0369a1; font-size:13px;">🫀 Evaluador Clínico HFA-PEFF (Consenso ESC)</h4>
                        
                        <div style="font-size:11px; margin-bottom:8px;">
                            <b>1. Dominio Funcional (F):</b> E/e' ≥ 15, TR > 2.8 m/s (Mayor = 2 pts) | E/e' 9-14, TR ≤ 2.8 m/s, e' disminuido (Menor = 1 pt)
                            <div style="display:flex; gap:12px; margin-top:3px;">
                                <label><input type="radio" name="peff_f" value="0" checked> Normal (0)</label>
                                <label><input type="radio" name="peff_f" value="1"> Menor (1 pt)</label>
                                <label><input type="radio" name="peff_f" value="2"> Mayor (2 pts)</label>
                            </div>
                        </div>

                        <div style="font-size:11px; margin-bottom:8px; border-top:1px dashed #cbd5e1; padding-top:6px;">
                            <b>2. Dominio Morfológico (M):</b> LAVI > 34 mL/m² o MVI elevada (Mayor = 2 pts) | RWT aumentado / HVI leve (Menor = 1 pt)
                            <div style="display:flex; gap:12px; margin-top:3px;">
                                <label><input type="radio" name="peff_m" value="0" checked> Normal (0)</label>
                                <label><input type="radio" name="peff_m" value="1"> Menor (1 pt)</label>
                                <label><input type="radio" name="peff_m" value="2"> Mayor (2 pts)</label>
                            </div>
                        </div>

                        <div style="font-size:11px; margin-bottom:10px; border-top:1px dashed #cbd5e1; padding-top:6px;">
                            <b>3. Dominio Biomarcadores (B):</b> NT-proBNP > 225 pg/mL (sinusal) o > 900 (FA) (Mayor = 2 pts) | Valores intermedios (Menor = 1 pt)
                            <div style="display:flex; gap:12px; margin-top:3px;">
                                <label><input type="radio" name="peff_b" value="0" checked> Normal (0)</label>
                                <label><input type="radio" name="peff_b" value="1"> Menor (1 pt)</label>
                                <label><input type="radio" name="peff_b" value="2"> Mayor (2 pts)</label>
                            </div>
                        </div>

                        <button type="button" onclick="calcPEFF()" style="background:#0369a1; color:white; border:none; padding:6px 12px; border-radius:4px; font-size:11px; cursor:pointer; font-weight:bold;">Calcular HFA-PEFF</button>
                        <button type="button" onclick="pasarIndependiente('res_peff', 'input_score_ic', 'row_score_ic')" style="background:#2c3e50; color:white; border:none; padding:6px 12px; border-radius:4px; font-size:11px; cursor:pointer; font-weight:bold;">📥 Pasar a campo IC</button>
                        <span id="res_peff" style="font-size:11px; font-weight:bold; color:#0369a1; display:block; margin-top:6px;"></span>
                    </div>

                    <!-- 12. MAGGIC -->
                    <div id="calc_maggic" style="display:none; background:#f8fafc; border:1px solid #075985; padding:12px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 8px 0; color:#075985; font-size:13px;">🫀 Evaluador MAGGIC (Pronóstico IC)</h4>
                        <div style="margin:5px 0;">
                            <input type="text" id="maggic_input" placeholder="Mortalidad estimada / Puntuación MAGGIC" style="padding:4px; font-size:11px; border:1px solid #ccc; border-radius:4px; width:260px;">
                        </div>
                        <button type="button" onclick="calcMAGGIC()" style="background:#075985; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Registrar MAGGIC</button>
                        <button type="button" onclick="pasarIndependiente('res_maggic', 'input_score_ic', 'row_score_ic')" style="background:#2c3e50; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">📥 Pasar a campo IC</button>
                        <span id="res_maggic" style="font-size:11px; font-weight:bold; color:#075985; display:block; margin-top:4px;"></span>
                    </div>

                    <!-- 13. QTc (BAZETT / FRIDERICIA) -->
                    <div id="calc_qtc" style="display:none; background:#f8fafc; border:1px solid #0f172a; padding:12px; border-radius:8px; margin-bottom:12px;">
                        <h4 style="margin:0 0 8px 0; color:#0f172a; font-size:13px;">📈 Calculadora QTc (Bazett y Fridericia)</h4>
                        <div style="display:flex; gap:6px; margin:5px 0;">
                            <input type="number" id="ecg_qt" placeholder="Intervalo QT (ms)" style="flex:1; padding:4px; font-size:11px; border:1px solid #ccc; border-radius:4px;">
                            <input type="number" id="ecg_fc" placeholder="Frecuencia Cardíaca (lpm)" style="flex:1; padding:4px; font-size:11px; border:1px solid #ccc; border-radius:4px;">
                        </div>
                        <button type="button" onclick="calcQTc()" style="background:#0f172a; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">Calcular QTc</button>
                        <button type="button" onclick="pasarIndependiente('res_qtc_b', 'input_score_ecg', 'row_score_ecg'); pasarIndependiente('res_qtc_f', 'input_score_ecg', 'row_score_ecg');" style="background:#2c3e50; color:white; border:none; padding:4px 8px; border-radius:4px; font-size:11px; cursor:pointer;">📥 Pasar a campo ECG</button>
                        <span id="res_qtc_b" style="font-size:11px; font-weight:bold; color:#0f172a; display:block; margin-top:4px;"></span>
                        <span id="res_qtc_f" style="font-size:11px; font-weight:bold; color:#0f172a; display:block; margin-top:2px;"></span>
                    </div>

                    <form method="POST">
                        <!-- MOTIVO Y ANTECEDENTES -->
                        <div style="display:flex; gap:15px; margin-bottom:15px;">
                            <div style="flex:1;">
                                <label style="font-weight:bold; font-size:13px;">Motivo:</label>
                                <input type="text" name="motivo" placeholder="Ej: Control cardiológico..." style="width:100%; padding:8px; margin-top:4px; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;">
                            </div>
                            <div style="flex:1;">
                                <label style="font-weight:bold; font-size:13px;">Antecedentes:</label>
                                <textarea name="antecedentes_evo" rows="2" placeholder="Ej: Refiere mejoría..." style="width:100%; padding:8px; margin-top:4px; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></textarea>
                            </div>
                        </div>
                        
                        <!-- ANTROPOMETRÍA Y SIGNOS VITALES -->
                        <div style="display:flex; gap:8px; margin-bottom:15px;">
                            <div style="flex:1;"><label style="font-size:11px; font-weight:bold;">Peso (Kg):</label><input type="text" name="peso" id="form_peso" placeholder="75.5" oninput="calcularAntropometria()" style="width:100%; padding:8px; margin-top:4px; border:1px solid #ccc; border-radius:4px;"></div>
                            <div style="flex:1;"><label style="font-size:11px; font-weight:bold;">Talla (cm):</label><input type="text" name="talla" id="form_talla" placeholder="170" oninput="calcularAntropometria()" style="width:100%; padding:8px; margin-top:4px; border:1px solid #ccc; border-radius:4px;"></div>
                            <div style="flex:1;"><label style="font-size:11px; font-weight:bold;">Cintura (cm):</label><input type="text" name="cintura" id="form_cintura" placeholder="88" style="width:100%; padding:8px; margin-top:4px; border:1px solid #ccc; border-radius:4px;"></div>
                            <div style="flex:1;"><label style="font-size:11px; font-weight:bold;">IMC (Auto):</label><input type="text" name="imc" id="form_imc" placeholder="Auto" style="width:100%; padding:8px; margin-top:4px; border:1px solid #ccc; border-radius:4px; background:#f8fafc;" readonly></div>
                            <div style="flex:1;"><label style="font-size:11px; font-weight:bold;">BSA m² (Auto):</label><input type="text" name="bsa" id="form_bsa" placeholder="Auto" style="width:100%; padding:8px; margin-top:4px; border:1px solid #ccc; border-radius:4px; background:#f8fafc;" readonly></div>
                        </div>

                        <div style="display:flex; gap:10px; margin-bottom:15px;">
                            <div style="flex:1;"><label style="font-size:12px; font-weight:bold;">PA Sistólica:</label><input type="text" name="pas" placeholder="120" style="width:100%; padding:8px; margin-top:4px; border:1px solid #ccc; border-radius:4px;"></div>
                            <div style="flex:1;"><label style="font-size:12px; font-weight:bold;">PA Diastólica:</label><input type="text" name="pad" placeholder="80" style="width:100%; padding:8px; margin-top:4px; border:1px solid #ccc; border-radius:4px;"></div>
                        </div>

                        <!-- CAMPOS DINÁMICOS (OCULTOS HASTA QUE SE USE UNA CALCULADORA) -->
                        <div style="background:#eff6ff; padding:15px; border-radius:6px; border:1px solid #bfdbfe; margin-bottom:15px; display:flex; flex-direction:column; gap:10px;">
                            <label style="font-size:13px; font-weight:bold; color:#1e40af;">📋 Scores y Parámetros Clínicos:</label>
                            
                            <div id="row_score_fa" style="display:none;">
                                <label style="font-size:11px; font-weight:bold; color:#2563eb;">Fibrilación Auricular (CHA₂DS₂-VA / HAS-BLED / CrCl):</label>
                                <input type="text" id="input_score_fa" name="score_fa" placeholder="Resultado de FA..." style="width:100%; padding:6px; font-size:11px; border:1px solid #93c5fd; border-radius:4px; background:white;">
                            </div>
                            <div id="row_score_renal" style="display:none;">
                                <label style="font-size:11px; font-weight:bold; color:#8b5cf6;">Función Renal (TFG / CrCl / RAC / KDIGO):</label>
                                <input type="text" id="input_score_renal" name="score_renal" placeholder="Resultado de Función Renal..." style="width:100%; padding:6px; font-size:11px; border:1px solid #c4b5fd; border-radius:4px; background:white;">
                            </div>
                            <div id="row_score_preop" style="display:none;">
                                <label style="font-size:11px; font-weight:bold; color:#d97706;">Prequirúrgico (ASA / RCRI / METs / Cond. Activas):</label>
                                <input type="text" id="input_score_preop" name="score_preop" placeholder="Resultado Prequirúrgico..." style="width:100%; padding:6px; font-size:11px; border:1px solid #fde68a; border-radius:4px; background:white;">
                            </div>
                            <div style="display:flex; gap:10px;">
                                <div id="row_score_sca" style="display:none; flex:1;">
                                    <label style="font-size:11px; font-weight:bold; color:#e11d48;">SCA (GRACE/TIMI):</label>
                                    <input type="text" id="input_score_sca" name="score_sca" placeholder="SCA..." style="width:100%; padding:6px; font-size:11px; border:1px solid #fecdd3; border-radius:4px; background:white;">
                                </div>
                                <div id="row_score_ic" style="display:none; flex:1;">
                                    <label style="font-size:11px; font-weight:bold; color:#0284c7;">Insuficiencia Cardíaca:</label>
                                    <input type="text" id="input_score_ic" name="score_ic" placeholder="IC..." style="width:100%; padding:6px; font-size:11px; border:1px solid #bae6fd; border-radius:4px; background:white;">
                                </div>
                                <div id="row_score_ecg" style="display:none; flex:1;">
                                    <label style="font-size:11px; font-weight:bold; color:#0f172a;">ECG (QTc):</label>
                                    <input type="text" id="input_score_ecg" name="score_ecg" placeholder="QTc..." style="width:100%; padding:6px; font-size:11px; border:1px solid #cbd5e1; border-radius:4px; background:white;">
                                </div>
                            </div>
                        </div>

                        <!-- SECCIÓN MAPA Y HOLTER (OCULTA POR DEFECTO) -->
                        <div id="seccion_mapa_holter" style="display:none; background:#f8fafc; padding:15px; border-radius:6px; border:1px solid #e2e8f0; margin-bottom:15px;">
                            <h4 style="margin:0 0 10px 0; color:#2c3e50; font-size:14px;">📊 Registro MAPA y Holter:</h4>
                            <div style="display:flex; gap:10px; margin-bottom:10px;">
                                <div style="flex:1;"><label style="font-size:11px; font-weight:bold;">MAPA Diurno:</label><input type="text" name="mapa_diurno" placeholder="135/85" style="width:100%; padding:6px; font-size:12px; border:1px solid #ccc; border-radius:4px;"></div>
                                <div style="flex:1;"><label style="font-size:11px; font-weight:bold;">MAPA Nocturno:</label><input type="text" name="mapa_nocturno" placeholder="118/72" style="width:100%; padding:6px; font-size:12px; border:1px solid #ccc; border-radius:4px;"></div>
                                <div style="flex:1;">
                                    <label style="font-size:11px; font-weight:bold;">Patrón:</label>
                                    <select name="patron" style="width:100%; padding:6px; font-size:12px; border:1px solid #ccc; border-radius:4px;">
                                        <option value="">Seleccionar...</option>
                                        <option value="Dipper">Dipper</option>
                                        <option value="Non-Dipper">Non-Dipper</option>
                                    </select>
                                </div>
                            </div>
                            <label style="font-size:11px; font-weight:bold;">Holter 24hs:</label>
                            <input type="text" name="holter" placeholder="Carga de EV 3.5%" style="width:100%; padding:6px; font-size:12px; margin-top:4px; border:1px solid #ccc; border-radius:4px;">
                        </div>

                        <label style="font-weight:bold; font-size:13px;">Examen Físico y ECG:</label>
                        <div style="margin:8px 0; display:flex; gap:6px; flex-wrap:wrap;">
                            <button type="button" onclick="agregarTexto('[Ritmo Sinusal]')" style="background:#34495e; color:white; border:none; padding:5px 10px; border-radius:4px; font-size:12px; cursor:pointer;">+ Ritmo Sinusal</button>
                            <button type="button" onclick="agregarTexto('[BCRD]')" style="background:#34495e; color:white; border:none; padding:5px 10px; border-radius:4px; font-size:12px; cursor:pointer;">+ BCRD</button>
                            <button type="button" onclick="agregarTexto('[BCRI]')" style="background:#34495e; color:white; border:none; padding:5px 10px; border-radius:4px; font-size:12px; cursor:pointer;">+ BCRI</button>
                        </div>
                        <textarea id="examen_ecg" name="examen" rows="3" placeholder="Detalles de auscultación y ECG..." style="width:100%; padding:10px; margin:4px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></textarea>

                        <label style="font-weight:bold; font-size:13px;">Diagnóstico (CIE-10):</label>
                        <input type="text" id="diagnostico_evolucion" name="diagnostico" placeholder="Ej: I10 - HTA" style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;">

                        <!-- CONSULTA ACTUAL / PLAN -->
                        <label style="font-weight:bold; font-size:13px;">Consulta Actual / Plan:</label>
                        <textarea id="tratamiento_evolucion" name="tratamiento" rows="4" placeholder="Detalles de la evaluación y plan médico..." style="width:100%; padding:10px; margin:6px 0 15px 0; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;"></textarea>
                        
                        <button type="submit" style="background:#2ecc71; color:white; border:none; padding:12px 20px; border-radius:6px; font-weight:bold; cursor:pointer; width:100%;">💾 Guardar Consulta en Historial</button>
                    </form>
                </div>

                <!-- HISTORIAL CLÍNICO -->
                <div style="flex:1; background:white; padding:25px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                    <h3 style="margin-top:0; color:#2c3e50;">Historial Clínico</h3>
                    <div style="max-height:750px; overflow-y:auto; padding-right:5px;">
                        {historial_html}
                    </div>
                </div>
            </div>

            <!-- GENERADOR DE INFORMES DE ESTUDIOS PROPIOS (OCULTO POR DEFECTO) -->
            <div id="seccion_generador_informes" style="display:none; background:white; padding:25px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05); border-top:4px solid #0284c7; margin-bottom:30px;">
                <h3 style="margin-top:0; color:#2c3e50;">📝 Generador de Informes de Estudios (Holter, MAPA, ECO)</h3>
                <form method="POST" action="/generar_informe_estudio/{paciente[0]}" target="_blank" style="display:flex; flex-direction:column; gap:15px; margin-top:15px;">
                    <div style="display:flex; gap:15px;">
                        <div style="flex:1;">
                            <label style="font-size:12px; font-weight:bold;">Tipo de Estudio:</label>
                            <select name="tipo_estudio" required style="width:100%; padding:8px; margin-top:4px; border:1px solid #ccc; border-radius:4px;">
                                <option value="Holter 24 horas">Holter 24 horas</option>
                                <option value="MAPA de Presión Arterial">MAPA (Monitoreo Ambulatorio de Presión)</option>
                                <option value="Ecocardiograma Doppler">Ecocardiograma Doppler</option>
                            </select>
                        </div>
                        <div style="flex:1;">
                            <label style="font-size:12px; font-weight:bold;">Fecha del Estudio:</label>
                            <input type="date" name="fecha_estudio" value="{datetime.today().strftime('%Y-%m-%d')}" required style="width:100%; padding:8px; margin-top:4px; border:1px solid #ccc; border-radius:4px;">
                        </div>
                    </div>
                    <div>
                        <label style="font-size:12px; font-weight:bold;">Descripción de Hallazgos y Parámetros:</label>
                        <textarea name="hallazgos" rows="4" placeholder="Ej: Ritmo sinusal basal, FC media 72 lpm, extrasístoles ventriculares aisladas (<1%)..." style="width:100%; padding:10px; margin-top:4px; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;" required></textarea>
                    </div>
                    <div>
                        <label style="font-size:12px; font-weight:bold;">Conclusión / Dictamen Médico:</label>
                        <textarea name="conclusion" rows="2" placeholder="Ej: Estudio dentro de límites normales para la edad..." style="width:100%; padding:10px; margin-top:4px; border:1px solid #ccc; border-radius:4px; box-sizing:border-box;" required></textarea>
                    </div>
                    <button type="submit" style="background:#0284c7; color:white; border:none; padding:12px; border-radius:6px; font-weight:bold; cursor:pointer;">📄 Generar Informe PDF Oficial del Estudio</button>
                </form>
            </div>

            <!-- GRÁFICO Y ARCHIVOS -->
            <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 25px; margin-bottom: 40px;">
                <div style="background:white; padding:25px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05); border-top:4px solid #3498db; box-sizing:border-box;">
                    <h3 style="margin-top:0; color:#2c3e50;">Evolución Clínica (Presión y Peso)</h3>
                    <div style="width: 100%; height: 250px; position: relative;">
                        <canvas id="graficoEvolucion"></canvas>
                    </div>
                    <script>
                        const ctx = document.getElementById('graficoEvolucion').getContext('2d');
                        const graficoEvolucion = new Chart(ctx, {{
                            type: 'line',
                            data: {{
                                labels: {fechas_js},
                                datasets: [
                                    {{
                                        label: 'PA Sistólica (mmHg)',
                                        data: {pas_js},
                                        borderColor: '#e74c3c',
                                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                                        tension: 0.1
                                    }},
                                    {{
                                        label: 'PA Diastólica (mmHg)',
                                        data: {pad_js},
                                        borderColor: '#3498db',
                                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                                        tension: 0.1
                                    }},
                                    {{
                                        label: 'Peso (Kg)',
                                        data: {peso_js},
                                        borderColor: '#2ecc71',
                                        backgroundColor: 'rgba(46, 204, 113, 0.1)',
                                        tension: 0.1,
                                        yAxisID: 'y1'
                                    }}
                                ]
                            }},
                            options: {{
                                responsive: true,
                                maintainAspectRatio: false,
                                scales: {{
                                    y: {{ type: 'linear', display: true, position: 'left' }},
                                    y1: {{ type: 'linear', display: true, position: 'right', grid: {{ drawOnChartArea: false }} }}
                                }}
                            }}
                        }});
                    </script>
                </div>

                <div style="background:white; padding:25px; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.05); border-top:4px solid #9b59b6; box-sizing:border-box;">
                    <h3 style="margin-top:0; color:#2c3e50;">Archivos y Estudios</h3>
                    <form method="POST" enctype="multipart/form-data">
                        <input type="hidden" name="accion" value="subir_estudio">
                        <label style="font-size:12px; font-weight:bold;">Nombre del Estudio:</label>
                        <input type="text" name="nombre_estudio" placeholder="Ej: Ecocardiograma" required style="width:100%; padding:8px; margin:5px 0 10px 0; border:1px solid #ccc; border-radius:4px;">
                        <label style="font-size:12px; font-weight:bold;">Seleccionar Archivo:</label>
                        <input type="file" name="archivo_estudio" required style="margin:5px 0 12px 0; width:100%; font-size:12px;">
                        <button type="submit" style="background:#9b59b6; color:white; border:none; padding:10px; border-radius:6px; font-weight:bold; cursor:pointer; width:100%;">📁 Subir Estudio</button>
                    </form>
                    <div style="margin-top:15px; max-height:160px; overflow-y:auto; border-top:1px solid #eee; padding-top:10px;">
                        {estudios_html}
                    </div>
                </div>
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

@app.route('/generar_receta_pdf/<int:id>', methods=['POST'])
def generar_receta_pdf(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, cedula, nombre, nacimiento, telefono, alergias FROM pacientes WHERE id = ?", (id,))
    paciente = cursor.fetchone()
    conn.close()
    if not paciente: return "Paciente no encontrado", 404

    diagnostico = request.form.get('diagnostico', 'Control Cardiológico')
    receta = request.form.get('receta', 'Sin medicamentos')
    indicaciones = request.form.get('indicaciones', 'Seguir indicaciones')
    edad_txt = calcular_edad(paciente[3])

    pdf_path = os.path.join(base_dir, f"receta_oficial_{id}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=letter)
    
    # Página 1: Receta
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Dr. Herve Benitez")
    c.setFont("Helvetica", 10)
    c.drawString(50, 735, "Especialista en Cardiología y Medicina Interna")
    c.line(50, 720, 560, 720)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 690, "RECETA MÉDICA ELECTRÓNICA (RP)")
    c.setFont("Helvetica", 10)
    c.drawString(50, 670, f"Paciente: {paciente[2]} | C.I.: {paciente[1]} | Edad: {edad_txt}")
    c.drawString(50, 652, f"Diagnóstico: {diagnostico}")
    c.line(50, 640, 560, 640)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 600, "Prescripción Farmacológica:")
    c.setFont("Helvetica", 11)
    y = 570
    for med in receta.split('\n'):
        if med.strip():
            c.drawString(70, y, f"• {med.strip()}")
            y -= 25
    c.line(350, 200, 530, 200)
    c.setFont("Helvetica", 9)
    c.drawString(380, 185, "Dr. Herve Benitez")
    
    c.showPage()
    
    # Página 2: Indicaciones
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Dr. Herve Benitez")
    c.setFont("Helvetica", 10)
    c.drawString(50, 735, "Especialista en Cardiología y Medicina Interna")
    c.line(50, 720, 560, 720)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 690, "PLAN E INDICACIONES MÉDICAS")
    c.setFont("Helvetica", 10)
    c.drawString(50, 670, f"Paciente: {paciente[2]} | C.I.: {paciente[1]} | Edad: {edad_txt}")
    c.line(50, 640, 560, 640)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 600, "Indicaciones Generales y Recomendaciones:")
    c.setFont("Helvetica", 11)
    y = 570
    for ind in indicaciones.split('\n'):
        if ind.strip():
            c.drawString(70, y, f"- {ind.strip()}")
            y -= 25
    c.line(350, 200, 530, 200)
    c.setFont("Helvetica", 9)
    c.drawString(380, 185, "Dr. Herve Benitez")
    
    c.save()
    return send_file(pdf_path, as_attachment=True)

@app.route('/generar_informe_estudio/<int:id>', methods=['POST'])
def generar_informe_estudio(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, cedula, nombre, nacimiento, telefono, alergias FROM pacientes WHERE id = ?", (id,))
    paciente = cursor.fetchone()
    conn.close()
    if not paciente: return "Paciente no encontrado", 404

    tipo_estudio = request.form.get('tipo_estudio', 'Estudio Cardiológico')
    fecha_estudio = request.form.get('fecha_estudio', datetime.today().strftime('%Y-%m-%d'))
    hallazgos = request.form.get('hallazgos', 'Sin hallazgos especificados.')
    conclusion = request.form.get('conclusion', 'Sin conclusión especificada.')
    edad_txt = calcular_edad(paciente[3])

    pdf_path = os.path.join(base_dir, f"informe_{tipo_estudio.replace(' ', '_')}_{id}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=letter)
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Dr. Herve Benitez")
    c.setFont("Helvetica", 10)
    c.drawString(50, 735, "Especialista en Cardiología y Medicina Interna")
    c.line(50, 720, 560, 720)
    
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 690, f"INFORME MÉDICO: {tipo_estudio.upper()}")
    c.setFont("Helvetica", 10)
    c.drawString(50, 670, f"Paciente: {paciente[2]} | C.I.: {paciente[1]} | Edad: {edad_txt}")
    c.drawString(50, 655, f"Fecha del Estudio: {fecha_estudio}")
    c.line(50, 642, 560, 642)
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 610, "Descripción y Hallazgos:")
    c.setFont("Helvetica", 11)
    
    y = 590
    for linea in hallazgos.split('\n'):
        if linea.strip():
            c.drawString(70, y, f"• {linea.strip()}")
            y -= 20
            
    y -= 15
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Conclusión / Dictamen:")
    c.setFont("Helvetica", 11)
    y -= 25
    for linea in conclusion.split('\n'):
        if linea.strip():
            c.drawString(70, y, f"- {linea.strip()}")
            y -= 20

    c.line(350, 180, 530, 180)
    c.setFont("Helvetica", 9)
    c.drawString(380, 165, "Dr. Herve Benitez")
    
    c.save()
    return send_file(pdf_path, as_attachment=True)

@app.route('/backup')
def backup():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if os.path.exists(db_path):
        return send_file(db_path, as_attachment=True)
    return "Base de datos no encontrada", 404

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    Timer(1.5, lambda: webbrowser.open_new("http://127.0.0.1:5001/")).start()
    app.run(host='0.0.0.0', port=5001, debug=True)

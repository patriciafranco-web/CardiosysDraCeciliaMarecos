import os
import sys
import sqlite3
import csv
import json
import traceback
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, request, redirect, url_for, session, send_file, render_template, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

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

template_dir = os.path.join(base_dir, 'templates')
app = Flask(__name__, template_folder=template_dir)
app.secret_key = 'cardio_elite_seguro_2026'
app.config['TEMPLATES_AUTO_RELOAD'] = True

# --- FUNCIÓN PARA CALCULAR LA EDAD EXACTA ---
def calcular_edad(nacimiento_str):
    if not nacimiento_str:
        return "N/D"
    try:
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
            try:
                f_nac = datetime.strptime(nacimiento_str.strip(), fmt)
                hoy = datetime.today()
                edad = hoy.year - f_nac.year - ((hoy.month, hoy.day) < (f_nac.month, f_nac.day))
                return f"{edad} años"
            except ValueError:
                continue
        return nacimiento_str
    except Exception:
        return "N/D"

app.jinja_env.filters['edad'] = calcular_edad

def init_db():
    try:
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
        cursor.execute('DELETE FROM usuarios WHERE username = ?', ('draceciliamarecos',))
        cursor.execute('''
            INSERT INTO usuarios (username, password_hash) 
            VALUES ('draceciliamarecos', ?)
        ''', (pass_hash,))

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
                adicional TEXT,
                alergias TEXT,
                antecedentes TEXT,
                antecedentes_principales TEXT,
                resumen_anterior TEXT,
                tratamiento_actual TEXT,
                indicaciones_actual TEXT,
                fecha_cita TEXT,
                tiene_estudios TEXT,
                es_estudio INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT,
                motivo TEXT,
                diagnostico TEXT,
                pas TEXT,
                fc TEXT,
                peso TEXT,
                talla TEXT,
                scores TEXT,
                cintura TEXT,
                imc TEXT,
                bsa TEXT,
                paciente_id INTEGER,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS estudios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_estudio TEXT,
                archivo TEXT,
                fecha TEXT,
                sanatorio TEXT,
                paciente_id INTEGER,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS estudios_generales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_estudio TEXT,
                descripcion TEXT,
                archivo TEXT,
                fecha TEXT
            )
        ''')

        for col, tipo in [
            ('sexo', 'TEXT'),
            ('adicional', 'TEXT'),
            ('nacimiento', 'TEXT'),
            ('antecedentes_principales', 'TEXT'),
            ('resumen_anterior', 'TEXT'),
            ('tratamiento_actual', 'TEXT'),
            ('indicaciones_actual', 'TEXT'),
            ('sanatorio', 'TEXT'),
            ('tiene_estudios', 'TEXT'),
            ('es_estudio', 'INTEGER DEFAULT 0')
        ]:
            try:
                cursor.execute(f'ALTER TABLE pacientes ADD COLUMN {col} {tipo}')
            except sqlite3.OperationalError:
                pass

        for col, tipo in [
            ('diagnostico', 'TEXT'),
            ('pas', 'TEXT'),
            ('fc', 'TEXT'),
            ('peso', 'TEXT'),
            ('talla', 'TEXT'),
            ('scores', 'TEXT'),
            ('cintura', 'TEXT'),
            ('imc', 'TEXT'),
            ('bsa', 'TEXT')
        ]:
            try:
                cursor.execute(f'ALTER TABLE historial ADD COLUMN {col} {tipo}')
            except sqlite3.OperationalError:
                pass

        conn.commit()
        conn.close()
    except Exception as e:
        print("Error en init_db:", e)

init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT password_hash FROM usuarios WHERE username = ?', ('draceciliamarecos',))
        user_row = cursor.fetchone()
        conn.close()

        if user_row and check_password_hash(user_row[0], password):
            session['logged_in'] = True
            session['username'] = 'draceciliamarecos'
            return redirect(url_for('index'))
        else:
            error = 'Contraseña incorrecta.'
    return render_template('login.html', error=error)

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        busqueda = request.args.get('q', '').strip()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if busqueda:
            cursor.execute('SELECT * FROM pacientes WHERE es_estudio = 0 AND (nombre LIKE ? OR cedula LIKE ?)', (f'%{busqueda}%', f'%{busqueda}%'))
        else:
            cursor.execute('SELECT * FROM pacientes WHERE es_estudio = 0')
        
        pacientes = cursor.fetchall()
        conn.close()
        return render_template('dashboard.html', pacientes=pacientes, busqueda=busqueda)
    except Exception as e:
        return f"<h3>Error en Agenda:</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route('/nuevo', methods=['GET', 'POST'])
@app.route('/nuevo_paciente', methods=['GET', 'POST'])
def nuevo():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            cedula = request.form.get('cedula', '').strip()
            nombre = request.form.get('nombre', '').strip()
            
            nacimiento = request.form.get('nacimiento', '').strip()
            if not nacimiento:
                nacimiento = request.form.get('edad_manual', '').strip()

            sexo = request.form.get('sexo', '').strip()
            telefono = request.form.get('telefono', '').strip()
            profesion = request.form.get('profesion', '').strip()
            sanatorio = request.form.get('sanatorio', '').strip()
            direccion = request.form.get('direccion', '').strip()
            adicional = request.form.get('adicional', '').strip()
            alergias = request.form.get('alergias', '').strip()
            
            fecha_cita = datetime.now().strftime('%Y-%m-%d')

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO pacientes (cedula, nombre, nacimiento, sexo, telefono, profesion, sanatorio, direccion, adicional, alergias, tiene_estudios, fecha_cita, es_estudio) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'No', ?, 0)
            ''', (cedula, nombre, nacimiento, sexo, telefono, profesion, sanatorio, direccion, adicional, alergias, fecha_cita))
            
            paciente_id = cursor.lastrowid

            evolucion = request.form.get('evolucion', '').strip()
            scores = request.form.get('scores_copiados', '').strip()
            pas = request.form.get('pas', '').strip()
            fc = request.form.get('fc', '').strip()
            peso = request.form.get('peso', '').strip()
            talla = request.form.get('talla', '').strip()
            cintura = request.form.get('cintura', '').strip()
            imc = request.form.get('imc', '').strip()
            bsa = request.form.get('bsa', '').strip()
            
            tratamiento = request.form.get('tratamiento_actual', '').strip()
            indicaciones = request.form.get('indicaciones_actual', '').strip()

            if tratamiento or indicaciones:
                cursor.execute('UPDATE pacientes SET tratamiento_actual = ?, indicaciones_actual = ? WHERE id = ?', (tratamiento, indicaciones, paciente_id))

            if evolucion or scores or pas or peso or tratamiento:
                cursor.execute('''
                    INSERT INTO historial (fecha, motivo, diagnostico, pas, fc, peso, talla, scores, cintura, imc, bsa, paciente_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (fecha_cita, evolucion, evolucion, pas, fc, peso, talla, scores, cintura, imc, bsa, paciente_id))

            conn.commit()
            conn.close()

            accion_form = request.form.get('accion_form', 'guardar')
            if accion_form == 'imprimir':
                return f"""
                <!DOCTYPE html>
                <html lang="es">
                <head>
                    <meta charset="UTF-8">
                    <title>Receta e Indicaciones - {nombre}</title>
                    <style>
                        @page {{
                            size: A4 landscape;
                            margin: 2mm;
                        }}
                        @media print {{
                            html, body {{
                                width: 297mm;
                                height: 206mm;
                                overflow: hidden !important;
                                page-break-after: avoid;
                                page-break-before: avoid;
                            }}
                        }}
                        body {{
                            font-family: 'Segoe UI', Arial, sans-serif;
                            margin: 0;
                            padding: 0;
                            color: #333;
                            -webkit-print-color-adjust: exact;
                        }}
                        .container {{
                            display: flex;
                            width: 100%;
                            height: 196mm;
                            gap: 8px;
                            box-sizing: border-box;
                        }}
                        .columna {{
                            flex: 1;
                            display: flex;
                            flex-direction: column;
                            justify-content: space-between;
                            box-sizing: border-box;
                            padding: 6px 8px;
                            border: 1.5px dashed #94a3b8;
                            border-radius: 6px;
                            background: #fff;
                            height: 100%;
                            overflow: hidden;
                        }}
                        .footer-aviso {{
                            border-top: 1px dashed #cbd5e1;
                            padding-top: 2mm;
                            margin-top: 2px;
                            text-align: center;
                            font-size: 10px;
                            font-weight: bold;
                            color: #e74c3c;
                            letter-spacing: 0.5px;
                        }}
                        .content {{
                            background: #f8fafc;
                            padding: 4px 6px;
                            border-radius: 4px;
                            border: 1px solid #e2e8f0;
                            font-size: 20px !important;
                            flex: 1;
                            margin-top: 2px;
                            overflow: hidden;
                        }}
                        /* Forzar tamaño de letra grande y legible, anulando estilos inline de Quill */
                        .content p, .content div, .content span, .content li, .content strong, .content em {{
                            font-size: 20px !important;
                            line-height: 1.35 !important;
                        }}
                        .content .ql-size-huge {{
                            font-size: 26px !important;
                        }}
                        .content .ql-size-large {{
                            font-size: 22px !important;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="columna">
                            <div>
                                {obtener_membrete_html()}
                                <div style="background: #cbd5e1; padding: 5px 8px; border-radius: 5px; margin-bottom: 4px; font-weight: bold; color: #0f172a; display: flex; justify-content: space-between; align-items: center; border: 1px solid #94a3b8;">
                                    <div>
                                        <div style="font-size: 16px; margin-bottom: 1px;"><strong>Paciente:</strong> {nombre}</div>
                                        <div style="font-size: 14px;"><strong>C.I.:</strong> {cedula}</div>
                                    </div>
                                    <div style="font-size: 11px; text-align: right;">
                                        <strong>Fecha:</strong> {datetime.now().strftime('%d/%m/%Y')}
                                    </div>
                                </div>
                                <h4 style="color:#2c3e50; margin:0 0 2px 0; font-size:10px;">RECETA MÉDICA:</h4>
                                <div class="content">{tratamiento}</div>
                            </div>
                            <div class="footer-aviso">POR FAVOR NO CAMBIAR RECETA MEDICA</div>
                        </div>
                        <div class="columna">
                            <div>
                                {obtener_membrete_html()}
                                <div style="background: #cbd5e1; padding: 5px 8px; border-radius: 5px; margin-bottom: 4px; font-weight: bold; color: #0f172a; display: flex; justify-content: space-between; align-items: center; border: 1px solid #94a3b8;">
                                    <div>
                                        <div style="font-size: 16px; margin-bottom: 1px;"><strong>Paciente:</strong> {nombre}</div>
                                        <div style="font-size: 14px;"><strong>C.I.:</strong> {cedula}</div>
                                    </div>
                                    <div style="font-size: 11px; text-align: right;">
                                        <strong>Fecha:</strong> {datetime.now().strftime('%d/%m/%Y')}
                                    </div>
                                </div>
                                <h4 style="color:#2c3e50; margin:0 0 2px 0; font-size:10px;">INDICACIONES MÉDICAS / PLAN:</h4>
                                <div class="content">{indicaciones}</div>
                            </div>
                            <div class="footer-aviso">POR FAVOR NO CAMBIAR RECETA MEDICA</div>
                        </div>
                    </div>
                    <script>
                        window.onload = function() {{ window.print(); window.location.href = "/ficha/{paciente_id}"; }};
                    </script>
                </body>
                </html>
                """

            return redirect(url_for('ficha', id=paciente_id))
        except Exception as e:
            return f"<h3>Error al crear paciente:</h3><pre>{traceback.format_exc()}</pre>", 500
    return render_template('nuevo_paciente.html')

@app.route('/eliminar_paciente/<int:id>', methods=['POST'])
def eliminar_paciente(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM historial WHERE paciente_id = ?', (id,))
        cursor.execute('DELETE FROM estudios WHERE paciente_id = ?', (id,))
        cursor.execute('DELETE FROM pacientes WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    except Exception as e:
        return f"<h3>Error al eliminar paciente:</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route('/estudios-lista', methods=['GET'])
def estudios_lista():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        busqueda = request.args.get('q', '').strip()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if busqueda:
            cursor.execute('SELECT * FROM estudios_generales WHERE nombre_estudio LIKE ? ORDER BY id DESC', (f'%{busqueda}%',))
        else:
            cursor.execute('SELECT * FROM estudios_generales ORDER BY id DESC')
        estudios = cursor.fetchall()
        conn.close()
        
        return render_template('estudios_lista.html', estudios=estudios, busqueda=busqueda)
    except Exception as e:
        return f"<h3>Error en Lista de Estudios:</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route('/estudios-nuevo', methods=['GET', 'POST'])
def estudios_nuevo():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    mensaje = ""
    if request.method == 'POST':
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            archivo = request.files.get('archivo_estudio')
            nombre_est = request.form.get('nombre_estudio', '').strip()
            descripcion = request.form.get('descripcion', '').strip()
            
            if archivo and archivo.filename:
                filename = f"global_{int(datetime.now().timestamp())}_{archivo.filename}"
                filepath = os.path.join(upload_folder, filename)
                archivo.save(filepath)
                
                if not nombre_est:
                    nombre_est = archivo.filename
                
                cursor.execute('INSERT INTO estudios_generales (nombre_estudio, descripcion, archivo, fecha) VALUES (?, ?, ?, ?)',
                               (nombre_est, descripcion, filename, datetime.now().strftime('%Y-%m-%d')))
                conn.commit()
                mensaje = "¡Estudio guardado correctamente en el Catálogo General!"
            conn.close()
        except Exception as e:
            mensaje = f"Error al procesar el archivo: {e}"
            
    return render_template('estudios_nuevo.html', mensaje=mensaje)

@app.route('/eliminar_estudio_general/<int:est_id>', methods=['POST'])
def eliminar_estudio_general(est_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT archivo FROM estudios_generales WHERE id = ?', (est_id,))
        est = cursor.fetchone()
        if est:
            archivo = est[0]
            if archivo:
                filepath = os.path.join(upload_folder, archivo)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
            cursor.execute('DELETE FROM estudios_generales WHERE id = ?', (est_id,))
            conn.commit()
        conn.close()
        return redirect(url_for('estudios_lista'))
    except Exception as e:
        return f"<h3>Error al eliminar estudio general:</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route('/eliminar_todos_estudios_generales', methods=['POST'])
def eliminar_todos_estudios_generales():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT archivo FROM estudios_generales')
        estudios = cursor.fetchall()
        for est in estudios:
            archivo = est[0]
            if archivo:
                filepath = os.path.join(upload_folder, archivo)
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
        cursor.execute('DELETE FROM estudios_generales')
        conn.commit()
        conn.close()
        return redirect(url_for('estudios_lista'))
    except Exception as e:
        return f"<h3>Error al vaciar el catálogo:</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route('/cambiar-contrasena', methods=['GET', 'POST'])
@app.route('/cambiar-password', methods=['GET', 'POST'])
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
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if request.method == 'POST':
            accion = request.form.get('accion')
            if accion == 'subir_estudio':
                nombre_estudio = request.form.get('nombre_estudio', 'Estudio')
                archivo_obj = request.files.get('archivo_estudio')
                if archivo_obj and archivo_obj.filename:
                    original_filename = archivo_obj.filename
                    timestamp = int(datetime.now().timestamp())
                    filename_original = f'Estudio_{id}_{timestamp}_{original_filename}'
                    filepath_original = os.path.join(upload_folder, filename_original)
                    archivo_obj.save(filepath_original)
                    
                    ext = original_filename.lower().split('.')[-1]
                    filename_a_guardar = filename_original
                    
                    if ext == 'xlsx':
                        pdf_name = f'Estudio_{id}_{timestamp}_convertido.pdf'
                        pdf_path = os.path.join(upload_folder, pdf_name)
                        try:
                            filas_tabla = []
                            with zipfile.ZipFile(filepath_original, 'r') as z:
                                shared_strings = []
                                if 'xl/sharedStrings.xml' in z.namelist():
                                    tree_ss = ET.fromstring(z.read('xl/sharedStrings.xml'))
                                    for si in tree_ss.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t'):
                                        shared_strings.append(si.text if si.text else '')
                                if 'xl/worksheets/sheet1.xml' in z.namelist():
                                    tree_ws = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
                                    for row in tree_ws.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                                        fila_txt = []
                                        for c in row.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                                            v = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                                            val = ""
                                            if v is not None and v.text is not None:
                                                if c.attrib.get('t') == 's':
                                                    idx = int(v.text)
                                                    val = shared_strings[idx] if idx < len(shared_strings) else v.text
                                                else:
                                                    val = v.text
                                            fila_txt.append(val)
                                        if any(fila_txt):
                                            filas_tabla.append("   |   ".join([f"{cell}" for cell in fila_txt if cell.strip()]))
                            
                            doc = SimpleDocTemplate(pdf_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
                            styles = getSampleStyleSheet()
                            story = [
                                Paragraph(f"<b>INFORME CLÍNICO / ESTUDIO: {nombre_estudio}</b>", styles['Heading1']),
                                Spacer(1, 15)
                            ]
                            for linea in filas_tabla:
                                story.append(Paragraph(linea, styles['Normal']))
                                story.append(Spacer(1, 4))
                            doc.build(story)
                            filename_a_guardar = pdf_name
                        except Exception as ex:
                            print("Error convirtiendo Excel a PDF:", ex)

                    cursor.execute('INSERT INTO estudios (nombre_estudio, archivo, fecha, sanatorio, paciente_id) VALUES (?, ?, ?, ?, ?)',
                                   (nombre_estudio, filename_a_guardar, datetime.now().strftime('%Y-%m-%d'), 'Consultorio', id))
                    conn.commit()
            else:
                fecha_cons = datetime.now().strftime('%Y-%m-%d')
                evolucion = request.form.get('evolucion', '').strip()
                scores = request.form.get('scores_copiados', '').strip()
                
                pas = request.form.get('pas', '').strip()
                fc = request.form.get('fc', '').strip()
                peso = request.form.get('peso', '').strip()
                talla = request.form.get('talla', '').strip()
                cintura = request.form.get('cintura', '').strip()
                imc = request.form.get('imc', '').strip()
                bsa = request.form.get('bsa', '').strip()

                if evolucion or scores or pas or peso:
                    cursor.execute('''
                        INSERT INTO historial (fecha, motivo, diagnostico, pas, fc, peso, talla, scores, cintura, imc, bsa, paciente_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (fecha_cons, evolucion, evolucion, pas, fc, peso, talla, scores, cintura, imc, bsa, id))
                    
                    resumen_texto = f"Fecha: {fecha_cons}"
                    if evolucion:
                        resumen_texto += f"\nEvolución: {evolucion}"
                    if scores:
                        resumen_texto += f"\nScores: {scores}"
                    if pas or peso:
                        resumen_texto += f"\nSignos Vitales: PA {pas} mmHg | FC {fc} lpm | Peso {peso} Kg | Talla {talla} cm | IMC {imc}"
                    
                    cursor.execute('UPDATE pacientes SET resumen_anterior = ? WHERE id = ?', (resumen_texto, id))
                    conn.commit()
            
            conn.close()
            return redirect(url_for('ficha', id=id))

        cursor.execute('SELECT * FROM pacientes WHERE id = ?', (id,))
        paciente = cursor.fetchone()

        cursor.execute('SELECT * FROM historial WHERE paciente_id = ? ORDER BY id DESC', (id,))
        historiales_rows = cursor.fetchall()
        historiales = historiales_rows

        cursor.execute('SELECT * FROM estudios WHERE paciente_id = ? ORDER BY id DESC', (id,))
        estudios = cursor.fetchall()

        conn.close()

        if not paciente:
            return 'Paciente no encontrado', 404

        historiales_json = json.dumps([dict(row) for row in historiales_rows], default=str)

        return render_template('ficha.html', paciente=paciente, historiales=historiales, estudios=estudios, historiales_json=historiales_json)
    except Exception as e:
        return f"<h3>Error en la Ficha:</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route('/ver_estudio/<filename>')
def ver_estudio(filename):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    filepath = os.path.join(upload_folder, filename)
    if not os.path.exists(filepath):
        return "Archivo no encontrado", 404
        
    ext = filename.lower().split('.')[-1]
    if ext == 'pdf':
        return send_file(filepath, mimetype='application/pdf', as_attachment=False)
    
    return send_file(filepath, as_attachment=False)

@app.route('/eliminar_estudio/<int:est_id>', methods=['POST'])
def eliminar_estudio(est_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT archivo, paciente_id FROM estudios WHERE id = ?', (est_id,))
        est = cursor.fetchone()
        if est:
            archivo, paciente_id = est[0], est[1]
            filepath = os.path.join(upload_folder, archivo)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            cursor.execute('DELETE FROM estudios WHERE id = ?', (est_id,))
            conn.commit()
            conn.close()
            return redirect(url_for('ficha', id=paciente_id))
        conn.close()
        return redirect(url_for('index'))
    except Exception as e:
        return f"<h3>Error al eliminar estudio:</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return send_file(os.path.join(upload_folder, filename), as_attachment=False)

@app.route('/actualizar_paciente/<int:id>', methods=['POST'])
def actualizar_paciente(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        nombre = request.form.get('nombre')
        cedula = request.form.get('cedula')
        nacimiento = request.form.get('nacimiento')
        profesion = request.form.get('profesion')
        direccion = request.form.get('direccion')
        sanatorio = request.form.get('sanatorio')
        antecedentes = request.form.get('antecedentes')
        alergias = request.form.get('alergias')

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE pacientes 
            SET nombre = ?, cedula = ?, nacimiento = ?, profesion = ?, direccion = ?, sanatorio = ?, antecedentes = ?, alergias = ?
            WHERE id = ?
        ''', (nombre, cedula, nacimiento, profesion, direccion, sanatorio, antecedentes, alergias, id))
        conn.commit()
        conn.close()
        return redirect(url_for('ficha', id=id))
    except Exception as e:
        return f"<h3>Error al actualizar paciente:</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route('/actualizar_antecedentes_principales/<int:id>', methods=['POST'])
def actualizar_antecedentes_principales(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        ant_prin = request.form.get('antecedentes_principales', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE pacientes SET antecedentes_principales = ? WHERE id = ?', (ant_prin, id))
        conn.commit()
        conn.close()
        return redirect(url_for('ficha', id=id))
    except Exception as e:
        return f"<h3>Error:</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route('/actualizar_resumen_anterior/<int:id>', methods=['POST'])
def actualizar_resumen_anterior(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        resumen = request.form.get('resumen_anterior', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE pacientes SET resumen_anterior = ? WHERE id = ?', (resumen, id))
        conn.commit()
        conn.close()
        return redirect(url_for('ficha', id=id))
    except Exception as e:
        return f"<h3>Error:</h3><pre>{traceback.format_exc()}</pre>", 500

@app.route('/actualizar_tratamiento_actual/<int:id>', methods=['POST'])
def actualizar_tratamiento_actual(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    try:
        tratamiento = request.form.get('tratamiento_actual', '')
        indicaciones = request.form.get('indicaciones_actual', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE pacientes SET tratamiento_actual = ?, indicaciones_actual = ? WHERE id = ?', (tratamiento, indicaciones, id))
        conn.commit()
        conn.close()
        return redirect(url_for('ficha', id=id))
    except Exception as e:
        return f"<h3>Error al actualizar tratamiento:</h3><pre>{traceback.format_exc()}</pre>", 500

def obtener_membrete_html():
    return f"""
    <div style="border-bottom: 2px solid #2c3e50; padding-bottom: 2px; margin-bottom: 3px; display: flex; align-items: center; gap: 15px;">
        <div style="flex-shrink: 0;">
            <img src="/static/logo_cardiologia.png" alt="Logo" style="width: 130px; height: auto; object-fit: contain;">
        </div>
        <div style="flex: 1; font-family: 'Segoe UI', Arial, sans-serif;">
            <h3 style="margin: 0 0 1px 0; color: #111; font-size: 13px; font-weight: bold; letter-spacing: 0.5px;">DRA. CECILIA MONSERRAT MARECOS VIANA</h3>
            <p style="margin: 0 0 1px 0; color: #333; font-size: 9.5px;">Especialista en Cardiología Clínica – Medicina Interna</p>
            <p style="margin: 0 0 1px 0; color: #333; font-size: 8.5px;">Ecocardiograma Doppler Color, Mapeo de Presión Arterial, Ergometría, Holter 24 horas</p>
            <p style="margin: 0 0 1px 0; color: #333; font-size: 8.5px;">Miembro Titular de la Sociedad Paraguaya de Cardiología y Cirugía Cardiovascular</p>
            <p style="margin: 0; color: #333; font-size: 8.5px;">Asunción – Coronel Oviedo, Py.</p>
        </div>
    </div>
    """

@app.route('/generar_plan_pdf/<int:id>', methods=['POST'])
def generar_plan_pdf(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    tratamiento = request.form.get('tratamiento', '')
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
        <title>Receta e Indicaciones - {p['nombre']}</title>
        <style>
            @page {{
                size: A4 landscape;
                margin: 2mm;
            }}
            @media print {{
                html, body {{
                    width: 297mm;
                    height: 206mm;
                    overflow: hidden !important;
                    page-break-after: avoid;
                    page-break-before: avoid;
                }}
            }}
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                margin: 0;
                padding: 0;
                color: #333;
                -webkit-print-color-adjust: exact;
            }}
            .container {{
                display: flex;
                width: 100%;
                height: 196mm;
                gap: 8px;
                box-sizing: border-box;
            }}
            .columna {{
                flex: 1;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                box-sizing: border-box;
                padding: 6px 8px;
                border: 1.5px dashed #94a3b8;
                border-radius: 6px;
                background: #fff;
                height: 100%;
                overflow: hidden;
            }}
            .footer-aviso {{
                border-top: 1px dashed #cbd5e1;
                padding-top: 2mm;
                margin-top: 2px;
                text-align: center;
                font-size: 10px;
                font-weight: bold;
                color: #e74c3c;
                letter-spacing: 0.5px;
            }}
            .content {{
                background: #f8fafc;
                padding: 4px 6px;
                border-radius: 4px;
                border: 1px solid #e2e8f0;
                font-size: 20px !important;
                flex: 1;
                margin-top: 2px;
                overflow: hidden;
            }}
            .content p, .content div, .content span, .content li, .content strong, .content em {{
                font-size: 20px !important;
                line-height: 1.35 !important;
            }}
            .content .ql-size-huge {{
                font-size: 26px !important;
            }}
            .content .ql-size-large {{
                font-size: 22px !important;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="columna">
                <div>
                    {obtener_membrete_html()}
                    <div style="background: #cbd5e1; padding: 5px 8px; border-radius: 5px; margin-bottom: 4px; font-weight: bold; color: #0f172a; display: flex; justify-content: space-between; align-items: center; border: 1px solid #94a3b8;">
                        <div>
                            <div style="font-size: 16px; margin-bottom: 1px;"><strong>Paciente:</strong> {p['nombre']}</div>
                            <div style="font-size: 14px;"><strong>C.I.:</strong> {p['cedula']}</div>
                        </div>
                        <div style="font-size: 11px; text-align: right;">
                            <strong>Fecha:</strong> {datetime.now().strftime('%d/%m/%Y')}
                        </div>
                    </div>
                    <h4 style="color:#2c3e50; margin:0 0 2px 0; font-size:10px;">RECETA MÉDICA:</h4>
                    <div class="content">{tratamiento}</div>
                </div>
                <div class="footer-aviso">
                    POR FAVOR NO CAMBIAR RECETA MEDICA
                </div>
            </div>

            <div class="columna">
                <div>
                    {obtener_membrete_html()}
                    <div style="background: #cbd5e1; padding: 5px 8px; border-radius: 5px; margin-bottom: 4px; font-weight: bold; color: #0f172a; display: flex; justify-content: space-between; align-items: center; border: 1px solid #94a3b8;">
                        <div>
                            <div style="font-size: 16px; margin-bottom: 1px;"><strong>Paciente:</strong> {p['nombre']}</div>
                            <div style="font-size: 14px;"><strong>C.I.:</strong> {p['cedula']}</div>
                        </div>
                        <div style="font-size: 11px; text-align: right;">
                            <strong>Fecha:</strong> {datetime.now().strftime('%d/%m/%Y')}
                        </div>
                    </div>
                    <h4 style="color:#2c3e50; margin:0 0 2px 0; font-size:10px;">INDICACIONES MÉDICAS / PLAN:</h4>
                    <div class="content">{indicaciones}</div>
                </div>
                <div class="footer-aviso">
                    POR FAVOR NO CAMBIAR RECETA MEDICA
                </div>
            </div>
        </div>
        <script>
            window.onload = function() {{ window.print(); }};
        </script>
    </body>
    </html>
    """

@app.route('/imprimir_historial_pdf/<int:h_id>', methods=['GET'])
def imprimir_historial_pdf(h_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.*, p.nombre, p.cedula 
        FROM historial h 
        JOIN pacientes p ON h.paciente_id = p.id 
        WHERE h.id = ?
    """, (h_id,))
    h = cursor.fetchone()
    conn.close()

    if not h:
        return "Consulta no encontrada", 404

    texto_evolucion = h['motivo'] or h['diagnostico'] or 'N/D'
    scores_txt = h['scores'] or ''
    sv_txt = f"PA: {h['pas']} | FC: {h['fc']} | Peso: {h['peso']} Kg | Talla: {h['talla']} cm | IMC: {h['imc']}" if h['pas'] else ""

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Consulta - {h['nombre']}</title>
        <style>
            @page {{ size: A4; margin: 15mm; }}
            body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 10px; color: #333; max-width: 800px; margin: auto; }}
            .box {{ background: #f8fafc; padding: 15px; border-radius: 6px; border: 1px solid #e2e8f0; margin-bottom: 15px; font-size: 14px; white-space: pre-wrap; }}
        </style>
    </head>
    <body>
        {obtener_membrete_html()}
        <div style="background: #cbd5e1; padding: 10px 15px; border-radius: 6px; margin-bottom: 20px; font-weight: bold; color: #0f172a; display: flex; justify-content: space-between; align-items: center; border: 1px solid #94a3b8;">
            <div>
                <div style="font-size: 17px; margin-bottom: 3px;"><strong>Paciente:</strong> {h['nombre']}</div>
                <div style="font-size: 15px;"><strong>C.I.:</strong> {h['cedula']}</div>
            </div>
            <div style="font-size: 13.5px; text-align: right;">
                <strong>Fecha:</strong> {h['fecha']}
            </div>
        </div>
        <div class="box">
            <p style="margin:0 0 10px 0;"><b>Evolución:</b><br>{texto_evolucion}</p>
            {f"<p style='margin:0 0 10px 0;'><b>Scores:</b> {scores_txt}</p>" if scores_txt else ""}
            {f"<p style='margin:0;'><b>Examen Físico:</b> {sv_txt}</p>" if sv_txt else ""}
        </div>
        <script>
            window.onload = function() {{ window.print(); }}
        </script>
    </body>
    </html>
    """

@app.route('/imprimir_multiples_historiales', methods=['POST'])
def imprimir_multiples_historiales():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    h_ids = request.form.getlist('h_ids')
    if not h_ids:
        return "No se seleccionó ninguna consulta para imprimir.", 400
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    placeholders = ','.join(['?'] * len(h_ids))
    cursor.execute(f"""
        SELECT h.*, p.nombre, p.cedula 
        FROM historial h 
        JOIN pacientes p ON h.paciente_id = p.id 
        WHERE h.id IN ({placeholders})
        ORDER BY h.fecha ASC
    """, h_ids)
    historiales = cursor.fetchall()
    conn.close()

    if not historiales:
        return "No se encontraron las consultas seleccionadas.", 404

    p_nombre = historiales[0]['nombre']
    p_cedula = historiales[0]['cedula']

    consultas_html = ""
    for h in historiales:
        texto_evolucion = h['motivo'] or h['diagnostico'] or 'N/D'
        scores_txt = h['scores'] or ''
        sv_txt = f"PA: {h['pas']} | FC: {h['fc']} | Peso: {h['peso']} Kg | Talla: {h['talla']} cm | IMC: {h['imc']}" if h['pas'] else ""

        consultas_html += f"""
        <div style="background: #f8fafc; padding: 15px; border-radius: 6px; border: 1px solid #e2e8f0; margin-bottom: 20px; font-size: 13px;">
            <div style="font-weight: bold; color: #1d4ed8; margin-bottom: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 5px; font-size: 14px;">
                📅 Fecha de Consulta: {h['fecha']}
            </div>
            <p style="margin:0 0 8px 0; white-space: pre-wrap;"><b>Evolución:</b><br>{texto_evolucion}</p>
            {f"<p style='margin:0 0 8px 0;'><b>Scores:</b> {scores_txt}</p>" if scores_txt else ""}
            {f"<p style='margin:0;'><b>Examen Físico:</b> {sv_txt}</p>" if sv_txt else ""}
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Historial Clínico - {p_nombre}</title>
        <style>
            @page {{ size: A4; margin: 15mm; }}
            body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 10px; color: #333; max-width: 800px; margin: auto; }}
        </style>
    </head>
    <body>
        {obtener_membrete_html()}
        <div style="background: #cbd5e1; padding: 10px 15px; border-radius: 6px; margin-bottom: 20px; font-weight: bold; color: #0f172a; display: flex; justify-content: space-between; align-items: center; border: 1px solid #94a3b8;">
            <div>
                <div style="font-size: 17px; margin-bottom: 3px;"><strong>Paciente:</strong> {p_nombre}</div>
                <div style="font-size: 15px;"><strong>C.I.:</strong> {p_cedula}</div>
            </div>
            <div style="font-size: 13.5px; text-align: right;">
                <strong>Reporte de Consultas Seleccionadas</strong>
            </div>
        </div>
        {consultas_html}
        <script>
            window.onload = function() {{ window.print(); }};
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
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)

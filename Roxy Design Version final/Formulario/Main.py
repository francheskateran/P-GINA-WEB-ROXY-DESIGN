from flask import Flask, render_template, request, redirect, url_for, flash
from Conexion import obtener_conexion

app = Flask(__name__)
app.secret_key = 'roxy_design_key_123'

@app.route('/')
def index():
    return render_template('formulario.html')

@app.route('/registrar', methods=['POST'])
def registrar():
    if request.method == 'POST':
        nombre_form = request.form.get('Nombre')
        email_form = request.form.get('email')
        password_form = request.form.get('contraseña')

        conexion = obtener_conexion()
        if conexion:
            try:
                cursor = conexion.cursor()
                query = "INSERT INTO usuario (nombre, email, contraseña) VALUES (%s, %s, %s)"
                cursor.execute(query, (nombre_form, email_form, password_form))
                conexion.commit()
                cursor.close()
                conexion.close()
                flash("¡Registro exitoso! Bienvenido a RoxyDesign.", "success")
                return redirect(url_for('index'))
            except Exception as e:
                flash(f"Error en el registro: {e}", "error")
                return redirect(url_for('index'))
        else:
            flash("Error de conexión con la base de datos.", "error")
            return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        email_cand = request.form.get('email_login')
        pass_cand = request.form.get('password_login')

        conexion = obtener_conexion()
        if conexion:
            cursor = conexion.cursor()
            query = "SELECT * FROM usuario WHERE email = %s AND contraseña = %s"
            cursor.execute(query, (email_cand, pass_cand))
            usuario_encontrado = cursor.fetchone()
            cursor.close()
            conexion.close()

            if usuario_encontrado:
                flash(f"¡Hola de nuevo, {usuario_encontrado[1]}!", "success")
                return redirect(url_for('index'))
            else:
                flash("Correo o contraseña incorrectos.", "error")
                return redirect(url_for('index'))
        else:
            flash("Error de conexión con la base de datos.", "error")
            return redirect(url_for('index'))


@app.route('/recuperar', methods=['POST'])
def recuperar():
    email_usuario = request.form.get('email')
    nombre_usuario = request.form.get('nombre') 
    conexion = obtener_conexion()
    if conexion:
        try:
            cursor = conexion.cursor()
            query = "SELECT contraseña FROM usuario WHERE email = %s AND nombre = %s"
            cursor.execute(query, (email_usuario, nombre_usuario))
            resultado = cursor.fetchone()
            cursor.close()
            conexion.close()

            if resultado:
                return f"OK|Identidad verificada. Tu contraseña es: {resultado[0]}"
            else:
                return "ERROR|Los datos ingresados no coinciden con nuestros registros."
        
        except Exception as e:
            return f"ERROR|Error en el servidor: {str(e)}"
    
    return "ERROR|No se pudo conectar con la base de datos."

if __name__ == '__main__':
    app.run(debug=True)
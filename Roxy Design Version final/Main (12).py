from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
from Conexion import obtener_conexion
from datetime import timedelta
import re
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'roxy_design_key_123'

# Configuración de subida de imágenes
UPLOAD_FOLDER = 'static/img'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- CONTEXT PROCESSOR ---
@app.context_processor
def inject_site_config():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM configuracion_web WHERE id=1")
    config = cursor.fetchone()

    # Obtener categorías para el menú
    cursor.execute("SELECT * FROM categorias")
    categorias = cursor.fetchall()

    # Notificaciones para el usuario (Pedidos aprobados esperando pago)
    notificacion_pago = 0
    if 'user_id' in session:
        cursor.execute("SELECT COUNT(*) as cant FROM orden WHERE usuario_id = %s AND status = 'Esperando Pago'", (session['user_id'],))
        row = cursor.fetchone()
        notificacion_pago = row['cant'] if row else 0

    conexion.close()

    # Valores por defecto si no existe configuración en la DB
    if not config:
        config = {
            'color_principal': '#2b8a78',
            'color_fondo': '#f4f4f4',
            'tasa_bcv': 0,
            'titulo_hero': 'RoxyDesign',
            'texto_hero': 'Bienvenido'
        }

    return dict(site_config=config, lista_categorias=categorias, notificacion_pago=notificacion_pago)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- CONFIGURACIÓN DE SEGURIDAD Y SESIÓN ---
@app.before_request
def configurar_sesion():
    session.permanent = True
    if session.get('es_admin'):
        app.permanent_session_lifetime = timedelta(days=365)
    else:
        app.permanent_session_lifetime = timedelta(minutes=120)

# --- VALIDACIONES ---
def es_correo_profesional(correo):
    dominios_validos = ['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'icloud.com']
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(patron, correo): return False
    dominio = correo.split('@')[-1].lower()
    return dominio in dominios_validos

def validar_password(password):
    if len(password) < 8: return "Mínimo 8 caracteres."
    if not re.search(r"[A-Z]", password): return "Falta una mayúscula."
    if not re.search(r"[0-9]", password): return "Falta un número."
    return None

def validar_telefono_ve(telefono):
    tel = telefono.replace(" ", "").replace("-", "")
    if not re.match(r"^\d{11}$", tel):
        return "El número debe tener exactamente 11 dígitos (ej: 04141234567)."
    prefijos_validos = ('0414', '0412', '0424', '0416', '0426', '0212')
    if not tel.startswith(prefijos_validos):
        return "Prefijo no válido. Use 0414, 0412, 0424, 0416, 0426 o 0212."
    return None

# --- RUTAS PRINCIPALES ---

@app.route('/')
def inicio():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM productos WHERE stock > 0 ORDER BY rand() LIMIT 8")
    productos = cursor.fetchall()
    conexion.close()
    return render_template('inicio.html', productos=productos)

@app.route('/login', methods=['POST'])
def login():
    identificador = request.form.get('nombre', '').strip()
    password = request.form.get('password', '').strip()

    if not identificador or not password:
        flash("Rellene todos los campos", "error")
        return redirect(url_for('form_acceso'))

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    query = "SELECT * FROM usuario WHERE (nombre = %s OR email = %s) AND contraseña = %s"
    cursor.execute(query, (identificador, identificador, password))
    user = cursor.fetchone()
    conexion.close()

    if user:
        session['usuario'] = user['nombre']
        session['user_id'] = user['id']
        session['es_admin'] = (user['rol'] == 'admin')
        return redirect(url_for('inicio'))
    else:
        flash("Credenciales incorrectas", "error")
        return redirect(url_for('form_acceso'))

@app.route('/registro', methods=['POST'])
def registro():
    nombre = request.form.get('Nombre', '').strip()
    email = request.form.get('email', '').strip()
    telefono = request.form.get('numeroT', '').strip()
    password = request.form.get('password', '').strip()

    if not es_correo_profesional(email):
        flash("Correo no válido o no profesional", "error")
        return render_template('formulario.html', modo='registro', Nombre=nombre, email=email, numeroT=telefono)

    error_tel = validar_telefono_ve(telefono)
    if error_tel:
        flash(error_tel, "error")
        return render_template('formulario.html', modo='registro', Nombre=nombre, email=email, numeroT=telefono)

    error_p = validar_password(password)
    if error_p:
        flash(error_p, "error")
        return render_template('formulario.html', modo='registro', Nombre=nombre, email=email, numeroT=telefono)

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM usuario WHERE nombre = %s OR email = %s", (nombre, email))
        if cursor.fetchone():
            flash("El usuario o correo ya existe", "error")
            return render_template('formulario.html', modo='registro', Nombre=nombre, email=email, numeroT=telefono)

        cursor.execute("""
            INSERT INTO usuario (nombre, contraseña, email, numeroT, rol)
            VALUES (%s, %s, %s, %s, 'cliente')
        """, (nombre, password, email, telefono))

        nuevo_id = cursor.lastrowid
        conexion.commit()

        session['usuario'] = nombre
        session['user_id'] = nuevo_id
        session['es_admin'] = False

        return redirect(url_for('inicio'))

    except Exception as e:
        flash("Error al procesar el registro", "error")
        return render_template('formulario.html', modo='registro', Nombre=nombre, email=email, numeroT=telefono)
    finally:
        conexion.close()

@app.route('/acceso')
def form_acceso():
    if 'usuario' in session:
        return redirect(url_for('inicio'))
    return render_template('formulario.html', modo='login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('inicio'))

# --- GESTIÓN DE PRODUCTOS (ADMIN) ---

@app.route('/guardar_producto', methods=['POST'])
def guardar_producto():
    if not session.get('es_admin'):
        return redirect(url_for('inicio'))

    id_prod = request.form.get('id')
    nombre = request.form.get('nombre')
    stock = request.form.get('stock', 0)

    precio_str = request.form.get('precio', '0').replace('$', '').replace(',', '')
    try:
        precio = float(precio_str)
        stock = int(stock)
    except ValueError:
        flash("Precio o Stock inválidos", "error")
        return redirect(url_for('inicio'))

    categoria = request.form.get('categoria')
    imagen_url = request.form.get('imagen_actual')

    if 'imagen' in request.files:
        file = request.files['imagen']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagen_url = filename

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    if id_prod:
        cursor.execute("""
            UPDATE productos
            SET NombreP=%s, Precio=%s, stock=%s, categoria_id=%s, imagen_url=%s
            WHERE idP=%s
        """, (nombre, precio, stock, categoria, imagen_url, id_prod))
        flash("Producto actualizado correctamente", "success")
    else:
        cursor.execute("""
            INSERT INTO productos (NombreP, Precio, stock, categoria_id, imagen_url)
            VALUES (%s, %s, %s, %s, %s)
        """, (nombre, precio, stock, categoria, imagen_url))
        flash("Producto creado exitosamente", "success")

    conexion.commit()
    conexion.close()
    return redirect(url_for('inicio'))

@app.route('/eliminar_producto/<int:id_prod>')
def eliminar_producto(id_prod):
    if not session.get('es_admin'):
        return redirect(url_for('inicio'))
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM productos WHERE idP=%s", (id_prod,))
    conexion.commit()
    conexion.close()
    flash("Producto eliminado", "success")
    return redirect(url_for('inicio'))

# --- GESTIÓN DE CATEGORÍAS (ADMIN) ---

@app.route('/admin/categorias', methods=['POST'])
def gestionar_categorias():
    if not session.get('es_admin'):
        return redirect(url_for('inicio'))
    accion = request.form.get('accion')
    nombre_cat = request.form.get('nombre')
    id_cat = request.form.get('id')
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    if accion == 'crear':
        try:
            cursor.execute("INSERT INTO categorias (nombre) VALUES (%s)", (nombre_cat,))
            flash("Categoría creada", "success")
        except:
            flash("Error: La categoría ya existe", "error")
    elif accion == 'editar':
        cursor.execute("UPDATE categorias SET nombre=%s WHERE id=%s", (nombre_cat, id_cat))
        flash("Categoría actualizada", "success")
    elif accion == 'eliminar':
        cursor.execute("DELETE FROM categorias WHERE id=%s", (id_cat,))
        flash("Categoría eliminada", "success")

    conexion.commit()
    conexion.close()
    return redirect(url_for('admin_dashboard'))

# --- CONFIGURACIÓN WEB (ADMIN) ---

@app.route('/actualizar_config', methods=['POST'])
def actualizar_config():
    if not session.get('es_admin'):
        return redirect(url_for('inicio'))

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    hero_img_name = request.form.get('hero_img_actual')
    if 'hero_img' in request.files:
        file = request.files['hero_img']
        if file and allowed_file(file.filename):
            filename = secure_filename("hero_" + file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            hero_img_name = filename

    cursor.execute("""
        UPDATE configuracion_web
        SET color_principal=%s, color_fondo=%s, titulo_hero=%s, texto_hero=%s, tasa_bcv=%s, hero_img=%s
        WHERE id=1
    """, (
        request.form.get('color_principal'),
        request.form.get('color_fondo'),
        request.form.get('titulo_hero'),
        request.form.get('texto_hero'),
        request.form.get('tasa_bcv'),
        hero_img_name
    ))

    conexion.commit()
    conexion.close()
    flash("Diseño y Tasa BCV actualizados", "success")
    return redirect(url_for('inicio'))

# --- DASHBOARD ADMIN ---
@app.route('/admin')
def admin_dashboard():
    if not session.get('es_admin'):
        return redirect(url_for('inicio'))

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("""
        SELECT o.*, u.nombre as cliente
        FROM orden o
        JOIN usuario u ON o.usuario_id = u.id
        ORDER BY o.created_at DESC
    """)
    ordenes = cursor.fetchall()

    cursor.execute("SELECT * FROM categorias")
    categorias = cursor.fetchall()

    conexion.close()
    return render_template('admin_dashboard.html', ordenes=ordenes, categorias=categorias)

@app.route('/admin/info_orden/<int:id_orden>')
def admin_info_orden(id_orden):
    if not session.get('es_admin'):
        return jsonify({'error': 'No autorizado'}), 403

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("""
        SELECT u.nombre, u.email, u.numeroT, o.total, o.status, o.created_at
        FROM orden o
        JOIN usuario u ON o.usuario_id = u.id
        WHERE o.idO = %s
    """, (id_orden,))
    info_gral = cursor.fetchone()

    cursor.execute("""
        SELECT op.cantidad, op.precio_historico, p.NombreP
        FROM orden_productos op
        LEFT JOIN productos p ON op.productos_id = p.idP
        WHERE op.orden_id = %s
    """, (id_orden,))
    productos = cursor.fetchall()

    cursor.execute("SELECT * FROM pagos WHERE orden_id = %s", (id_orden,))
    info_pago = cursor.fetchone()

    conexion.close()
    return jsonify({'info': info_gral, 'productos': productos, 'pago': info_pago})

@app.route('/admin/aprobar_orden/<int:id_orden>', methods=['POST'])
def admin_aprobar_orden(id_orden):
    if not session.get('es_admin'):
        return redirect(url_for('inicio'))

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("UPDATE orden SET status = 'Esperando Pago' WHERE idO = %s", (id_orden,))
    conexion.commit()
    conexion.close()
    flash("Orden aprobada. El usuario ahora puede pagar.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/finalizar_orden/<int:id_orden>', methods=['POST'])
def admin_finalizar_orden(id_orden):
    """Ruta para que el admin marque la orden como pagada y cerrada definitivamente."""
    if not session.get('es_admin'):
        return redirect(url_for('inicio'))

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("UPDATE orden SET status = 'Finalizado' WHERE idO = %s", (id_orden,))
    conexion.commit()
    conexion.close()
    flash("Orden marcada como Finalizada con éxito.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/cancelar_orden/<int:id_orden>', methods=['POST'])
def admin_cancelar_orden(id_orden):
    if not session.get('es_admin'):
        return redirect(url_for('inicio'))
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT productos_id, cantidad FROM orden_productos WHERE orden_id = %s", (id_orden,))
    items = cursor.fetchall()
    for item in items:
        if item['productos_id']:
            cursor.execute("UPDATE productos SET stock = stock + %s WHERE idP = %s", (item['cantidad'], item['productos_id']))
    cursor.execute("UPDATE orden SET status = 'Cancelado' WHERE idO = %s", (id_orden,))
    conexion.commit()
    conexion.close()
    flash("Orden cancelada y stock restaurado.", "info")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/eliminar_orden/<int:id_orden>', methods=['POST'])
def admin_eliminar_orden(id_orden):
    # Verificamos el rol según tu tabla 'usuario'
    # Si en el login guardaste el rol en session['rol'], usamos esto:
    if session.get('rol') != 'admin' and not session.get('es_admin'):
        return redirect(url_for('inicio'))

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    try:
        # 1. Eliminar de 'pagos' (esta tabla tiene FK a orden, hay que borrarla primero)
        cursor.execute("DELETE FROM pagos WHERE orden_id = %s", (id_orden,))

        # 2. Eliminar de 'orden_productos' (tu nueva tabla según el SQL)
        cursor.execute("DELETE FROM orden_productos WHERE orden_id = %s", (id_orden,))

        # 3. Eliminar la orden principal
        cursor.execute("DELETE FROM orden WHERE idO = %s", (id_orden,))

        conexion.commit()
        flash("Orden y registros asociados eliminados permanentemente.", "success")
    except Exception as e:
        print(f"ERROR EN BD AL ELIMINAR: {e}")
        conexion.rollback()
        flash(f"Error de base de datos: {e}", "error")
    finally:
        conexion.close()

    return redirect(url_for('admin_dashboard'))


# --- CATÁLOGO ---

@app.route('/categorias', endpoint='ver_todas_categorias')
def ver_todas_categorias():
    return render_template('categorias.html')

@app.route('/categoria/<int:id_categoria>')
def ver_categoria(id_categoria):
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM categorias WHERE id = %s", (id_categoria,))
    cat = cursor.fetchone()
    if not cat:
        conexion.close()
        return redirect(url_for('ver_todas_categorias'))

    cursor.execute("SELECT * FROM productos WHERE categoria_id = %s AND stock > 0", (id_categoria,))
    productos = cursor.fetchall()
    conexion.close()
    return render_template('categoria_detalle.html', nombre_categoria=cat['nombre'], productos=productos)

# --- CARRITO ---

@app.route('/agregar_carrito/<int:producto_id>', methods=['POST'])
def agregar_al_carrito(producto_id):
    if 'usuario' not in session:
        flash("Debes iniciar sesión", "warning")
        return redirect(url_for('form_acceso'))

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("SELECT stock FROM productos WHERE idP = %s", (producto_id,))
    prod = cursor.fetchone()
    if not prod or prod['stock'] < 1:
        flash("Producto agotado", "error")
        conexion.close()
        return redirect(request.referrer or url_for('inicio'))

    cursor.execute("SELECT idC FROM carrito WHERE usuario_id = %s", (session['user_id'],))
    carrito = cursor.fetchone()

    if not carrito:
        cursor.execute("INSERT INTO carrito (usuario_id) VALUES (%s)", (session['user_id'],))
        carrito_id = cursor.lastrowid
    else:
        carrito_id = carrito['idC']

    cursor.execute("SELECT * FROM carrito_productos WHERE carrito_id=%s AND productos_id=%s", (carrito_id, producto_id))
    existente = cursor.fetchone()

    if existente:
        if existente['cantidad'] < prod['stock']:
            cursor.execute("UPDATE carrito_productos SET cantidad = cantidad + 1 WHERE idCP=%s", (existente['idCP'],))
            flash("Cantidad actualizada", "success")
        else:
            flash("No hay más stock disponible", "warning")
    else:
        cursor.execute("INSERT INTO carrito_productos (carrito_id, productos_id, cantidad) VALUES (%s, %s, 1)", (carrito_id, producto_id))
        flash("Producto añadido", "success")

    conexion.commit()
    conexion.close()
    return redirect(request.referrer or url_for('inicio'))

@app.route('/actualizar_carrito', methods=['POST'])
def actualizar_carrito():
    if 'usuario' not in session: return redirect(url_for('inicio'))

    id_item = request.form.get('id_cp')
    accion = request.form.get('accion')

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute("""
        SELECT cp.idCP, cp.cantidad, p.stock
        FROM carrito_productos cp
        JOIN productos p ON cp.productos_id = p.idP
        WHERE cp.idCP = %s
    """, (id_item,))
    item = cursor.fetchone()

    if item:
        nueva_cantidad = item['cantidad']
        if accion == 'sumar':
            if item['cantidad'] < item['stock']: nueva_cantidad += 1
            else: flash("Máximo stock alcanzado", "warning")
        elif accion == 'restar':
            nueva_cantidad -= 1
        elif accion == 'eliminar':
            nueva_cantidad = 0

        if nueva_cantidad > 0:
            cursor.execute("UPDATE carrito_productos SET cantidad = %s WHERE idCP = %s", (nueva_cantidad, id_item))
        else:
            cursor.execute("DELETE FROM carrito_productos WHERE idCP = %s", (id_item,))

        conexion.commit()

    conexion.close()
    return redirect(url_for('ver_carrito'))

@app.route('/procesar_pedido', methods=['POST'])
def procesar_pedido():
    if 'usuario' not in session: return redirect(url_for('inicio'))

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    # Límite de 5 pedidos al día
    cursor.execute("""
        SELECT COUNT(*) as cuenta
        FROM orden
        WHERE usuario_id = %s AND DATE(created_at) = CURDATE()
    """, (session['user_id'],))
    conteo = cursor.fetchone()

    if conteo and conteo['cuenta'] >= 5:
        flash("Has alcanzado el límite de 5 pedidos diarios.", "error")
        conexion.close()
        return redirect(url_for('ver_carrito'))

    query_items = """
        SELECT cp.productos_id, cp.cantidad, p.Precio, p.stock
        FROM carrito_productos cp
        JOIN productos p ON cp.productos_id = p.idP
        JOIN carrito c ON cp.carrito_id = c.idC
        WHERE c.usuario_id = %s
    """
    cursor.execute(query_items, (session['user_id'],))
    items = cursor.fetchall()

    if not items:
        conexion.close()
        return redirect(url_for('ver_carrito'))

    total_pedido = 0
    for item in items:
        if item['cantidad'] > item['stock']:
            flash(f"Stock insuficiente para uno de los productos.", "error")
            conexion.close()
            return redirect(url_for('ver_carrito'))
        total_pedido += (item['cantidad'] * item['Precio'])

    cursor.execute("INSERT INTO orden (usuario_id, status, total) VALUES (%s, 'Pendiente', %s)",
                   (session['user_id'], total_pedido))
    orden_id = cursor.lastrowid

    for item in items:
        cursor.execute("""
            INSERT INTO orden_productos (orden_id, productos_id, cantidad, precio_historico)
            VALUES (%s, %s, %s, %s)
        """, (orden_id, item['productos_id'], item['cantidad'], item['Precio']))

        cursor.execute("UPDATE productos SET stock = stock - %s WHERE idP = %s",
                       (item['cantidad'], item['productos_id']))

    cursor.execute("DELETE FROM carrito_productos WHERE carrito_id = (SELECT idC FROM carrito WHERE usuario_id=%s)", (session['user_id'],))

    conexion.commit()
    conexion.close()

    flash("Pedido solicitado. Espere la confirmación del administrador.", "success")
    return redirect(url_for('ver_carrito'))

@app.route('/reportar_pago', methods=['POST'])
def reportar_pago():
    if 'usuario' not in session: return redirect(url_for('inicio'))

    orden_id = request.form.get('orden_id')
    tipo_doc = request.form.get('tipo_doc')
    num_doc = request.form.get('num_doc')
    banco = request.form.get('banco')
    telefono = request.form.get('telefono')
    referencia = request.form.get('referencia')
    cedula_completa = f"{tipo_doc}-{num_doc}"

    if not all([orden_id, num_doc, banco, telefono, referencia]):
        flash("Faltan datos por llenar.", "error")
        return redirect(url_for('ver_carrito'))

    if len(referencia) < 6 or not referencia.isdigit():
        flash("La referencia debe tener al menos 6 dígitos numéricos.", "error")
        return redirect(url_for('ver_carrito'))

    imagen_pago = ''
    if 'imagen_pago' in request.files:
        file = request.files['imagen_pago']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"pago_{orden_id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagen_pago = filename

    if not imagen_pago:
        flash("La imagen del comprobante es obligatoria.", "error")
        return redirect(url_for('ver_carrito'))

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute("""
            INSERT INTO pagos (usuario_id, orden_id, Numero_Telefono, id_Numero, bank_name, Referencia_pago, pago_imagen_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (session['user_id'], orden_id, telefono, cedula_completa, banco, referencia, imagen_pago))

        cursor.execute("UPDATE orden SET status = 'Confirmado' WHERE idO = %s", (orden_id,))
        conexion.commit()
        flash("¡Pago reportado con éxito! El administrador verificará su pago.", "success")
    except Exception as e:
        flash("Error al registrar el pago.", "error")
    finally:
        conexion.close()

    return redirect(url_for('ver_carrito'))

@app.route('/carrito')
def ver_carrito():
    if 'usuario' not in session: return redirect(url_for('inicio'))

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    query = """
        SELECT cp.*, p.NombreP, p.Precio, p.imagen_url, p.stock
        FROM carrito_productos cp
        JOIN productos p ON cp.productos_id = p.idP
        JOIN carrito c ON cp.carrito_id = c.idC
        WHERE c.usuario_id = %s
    """
    cursor.execute(query, (session['user_id'],))
    items = cursor.fetchall()

    cursor.execute("SELECT * FROM orden WHERE usuario_id = %s AND status = 'Esperando Pago'", (session['user_id'],))
    ordenes_pago = cursor.fetchall()

    conexion.close()
    return render_template('carrito.html', items=items, ordenes_pago=ordenes_pago)

# --- RECUPERACIÓN DE CONTRASEÑA ---
@app.route('/recuperar_password', methods=['GET', 'POST'])
def recuperar_password():
    if request.method == 'POST':
        nombre = request.form.get('Nombre')
        email = request.form.get('email')

        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuario WHERE nombre = %s AND email = %s", (nombre, email))
        user = cursor.fetchone()
        conexion.close()

        if user:
            # En un sistema real se enviaría un email. Aquí simulamos la recuperación mostrando la clave.
            flash(f"Datos verificados. Su contraseña es: {user['contraseña']}", "info")
        else:
            flash("No se encontró ningún usuario con esos datos.", "error")

        return redirect(url_for('form_acceso'))
    return render_template('formulario.html', modo='recuperar')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
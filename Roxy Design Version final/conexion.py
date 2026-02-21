import mysql.connector

def obtener_conexion():
    config = {
        'user': '',
        'password': '',
        'host': '',
        'database': '' 
    }
    try:
        conn = mysql.connector.connect(**config)
        return conn
    except mysql.connector.Error as err:
        print(f"Error de conexión: {err}")
        return None
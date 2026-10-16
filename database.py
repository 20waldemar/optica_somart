import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    """Obtener conexión a PostgreSQL"""
    return psycopg2.connect(
        host='localhost',
        port='5432',
        database='optica_db',
        user='postgres',
        password='Bizwork123'  # <--- CAMBIA ESTO por tu contraseña real de PostgreSQL
    )

def get_dict_connection():
    """Obtener conexión con cursor que devuelve diccionarios"""
    conn = get_connection()
    return conn.cursor(cursor_factory=RealDictCursor)

def verificar_conexion():
    """Verificar que la conexión funcione"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Conectado a PostgreSQL: {version[0][:50]}...")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

if __name__ == "__main__":
    verificar_conexion()
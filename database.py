import os
import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://optica_db_owner:npg_xxxxx@ep-floral-salad-b7qgint5-pooler.c-13.us-east-1.aws.neon.tech/optica_db?sslmode=require"
)

def get_connection():
    return psycopg2.connect(DATABASE_URL)
def get_connection():
    """Conecta a la base de datos en Neon.tech (PostgreSQL en la nube)"""
    return psycopg2.connect(DATABASE_URL)
    
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

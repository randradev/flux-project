import os
from dotenv import load_dotenv
from supabase import create_client, Client

def test_connection():
    # Cargar .env
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    print(f"Probando conexion a: {url}")
    
    if not url or not key:
        print("ERROR: Faltan variables de entorno SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY")
        return

    try:
        supabase: Client = create_client(url, key)
        # Intentar una consulta simple a la tabla 'users'
        response = supabase.table("users").select("count", count="exact").limit(1).execute()
        print("Conexion exitosa!")
        print(f"Respuesta: {response}")
    except Exception as e:
        print(f"Error detectado: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_connection()

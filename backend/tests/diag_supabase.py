import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Cargar variables de entorno
load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def diagnostic():
    print("\n--- DIAGNOSTICO DE CONEXION SUPABASE ---")
    
    if not url or not key:
        print("[ERROR] Faltan variables de entorno (SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY).")
        return

    print(f"[INFO] URL detectada: {url}")
    print(f"[INFO] Key detectada: {key[:10]}...{key[-5:]}")

    try:
        print("[INFO] Intentando inicializar cliente...")
        client = create_client(url, key)
        print("[OK] Cliente inicializado.")

        print("[INFO] Intentando consulta simple a tabla 'users'...")
        # Usamos limit(1) para probar conectividad básica
        response = client.table("users").select("email").limit(1).execute()
        
        if response:
            print(f"[OK] CONSULTA EXITOSA. Datos recibidos: {response.data}")
        else:
            print("[ERROR] La ejecucion devolvio None (Posible timeout o fallo silencioso).")

    except Exception as e:
        print(f"[ERROR CRITICO] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnostic()

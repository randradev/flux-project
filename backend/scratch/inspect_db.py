import os
from dotenv import load_dotenv
from supabase import create_client, Client

def inspect_users_table():
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    supabase: Client = create_client(url, key)
    
    # Intentar obtener un registro para ver las columnas, o usar rpc si estuviera disponible
    # Pero una forma facil es intentar insertar algo mal o simplemente ver la respuesta de un select *
    try:
        response = supabase.table("users").select("*").limit(1).execute()
        if response.data:
            print("Columnas detectadas en 'users':")
            for key in response.data[0].keys():
                print(f"- {key}")
        else:
            print("La tabla 'users' esta vacia, no puedo ver las columnas con select *")
            # Podriamos intentar una consulta que falle para ver el error de postgres
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_users_table()

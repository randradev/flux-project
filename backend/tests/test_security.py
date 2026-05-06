import asyncio
import os
from dotenv import load_dotenv
from app.modules.security import generate_otp, validate_otp, send_otp_email

# Cargamos el .env para que reconozca la RESEND_API_KEY si existe
load_dotenv()

def test_security_flow():
    print("🔐 --- PRUEBA DE MÓDULO DE SEGURIDAD FLUX ---")
    
    # 1. Simular datos del usuario (como vendrían del state)
    user_email = "randradev.dev@gmail.com" # CAMBIA ESTO por tu mail real para probar
    intentos_actuales = 0
    
    # 2. Generar el código
    codigo_generado = generate_otp()
    print(f"[LOG] Código generado internamente: {codigo_generado}")

    # 3. Intentar envío (Real o Mock)
    print(f"[LOG] Intentando enviar código a {user_email}...")
    exito = send_otp_email(user_email, codigo_generado)
    
    if exito:
        print("✅ Proceso de envío ejecutado.")
    else:
        print("❌ Error en el proceso de envío.")

    # 4. Simular entrada del usuario
    print("\n" + "-"*30)
    user_input = input("👉 Ingresa el código que recibiste (o el que ves en consola): ")
    
    # 5. Validar
    es_valido = validate_otp(user_input, codigo_generado)
    
    if es_valido:
        print("\n🏆 ¡ÉXITO! El código coincide. Usuario verificado.")
    else:
        print("\n🚫 ERROR: El código es incorrecto.")

if __name__ == "__main__":
    test_security_flow()
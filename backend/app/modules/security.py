import random
import hashlib
import logging
import os
from dotenv import load_dotenv

# 1. Cargar variables de entorno inmediatamente
load_dotenv()

# 2. Intentar importar resend
try:
    import resend
except ImportError:
    resend = None

log = logging.getLogger("flux.security")

def generate_otp() -> str:
    return f"{random.randint(0, 999999):06d}"

def validate_otp(user_input: str, actual_code: str) -> bool:
    if not user_input or not actual_code:
        return False
    return user_input.strip() == actual_code.strip()

def verify_attempts(current_attempts: int, max_attempts: int = 3) -> bool:
    return current_attempts < max_attempts

def send_otp_email(mail: str, code: str):
    # Recuperamos la key dentro de la función para asegurar que esté cargada
    api_key = os.getenv("RESEND_API_KEY")
    
    if resend and api_key:
        resend.api_key = api_key # Configuramos la key justo antes de usarla
        try:
            params = {
                "from": "Flux <onboarding@resend.dev>", 
                "to": [mail],
                "subject": f"{code} es tu código de verificación Flux",
                "html": f"""
                    <div style="font-family: sans-serif; max-width: 400px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
                        <h2 style="color: #111;">Hola,</h2>
                        <p>Tu código de seguridad para confirmar tu solicitud de crédito es:</p>
                        <div style="background: #f4f4f4; padding: 10px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 5px;">
                            {code}
                        </div>
                        <p style="font-size: 12px; color: #666; margin-top: 20px;">
                            Este código expira en 5 minutos. Si no solicitaste esto, ignora este correo.
                        </p>
                    </div>
                """,
            }
            resend.Emails.send(params)
            print(f"✅ [REAL] Email enviado a {mail}")
            return True
        except Exception as e:
            # Aquí capturamos el error real de la API (ej: 403 si el mail no es el tuyo)
            print(f"❌ [API ERROR] Resend falló: {e}")
    
    # 2. Modo MOCK (Respaldo si no hay key o si falló el try anterior)
    print("\n" + "="*40)
    print(f"DEBUG MOCK OTP")
    print(f"PARA: {mail}")
    print(f"CÓDIGO: {code}")
    print("="*40 + "\n")
    return True

def create_digital_signature(payload: dict) -> str:
    data_str = str(sorted(payload.items()))
    return hashlib.sha256(data_str.encode()).hexdigest()
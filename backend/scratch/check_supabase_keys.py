import sys
import os
# Esto permite que el script encuentre el módulo 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import settings  # <--- Esta es la línea que falta
import base64
import json

def jwt_payload_no_verify(token: str) -> dict:
    # JWT: header.payload.signature
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("No parece JWT")
    payload_b64 = parts[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)  # padding base64url
    payload_bytes = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
    return json.loads(payload_bytes.decode("utf-8"))

print("ANON role:", jwt_payload_no_verify(settings.supabase_anon_key).get("role"))
print("SERVICE role:", jwt_payload_no_verify(settings.supabase_service_role_key).get("role"))
"""
app/api/deps.py
─────────────────────────────────────────────────────────────
Inyección de dependencias para los endpoints de FastAPI.

PROCESO: Provee funciones reutilizables que FastAPI resuelve automáticamente
         en cada request mediante el sistema de Depends().

SALIDA:
  - get_current_user(): Valida el JWT de Supabase y retorna el user_id.
  - get_verified_user(): Extiende get_current_user() verificando que el
    usuario existe en la tabla `users` y no está bloqueado.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.infra.supabase import supabase_admin, get_user_by_email

# Esquema de seguridad Bearer Token (JWT de Supabase Auth)
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    """
    Valida el JWT de Supabase Auth incluido en el header Authorization.

    INPUT:  Bearer token en el header de la request.
    PROCESO:
        1. Extrae el JWT del header Authorization: Bearer <token>.
        2. Llama a supabase_admin.auth.get_user(token) para validar el token.
        3. Si el token es inválido o expiró, retorna 401.
        4. Si es válido, retorna el diccionario con los datos del usuario Auth.
    OUTPUT: dict con {user_id, email} del usuario autenticado.

    RAISES: HTTPException 401 si el token es inválido o expirado.
    """
    token = credentials.credentials

    try:
        # Validar el JWT contra Supabase Auth (hace una llamada al servidor de Auth)
        auth_response = supabase_admin.auth.get_user(token)
        if not auth_response or not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = auth_response.user
        return {"user_id": user.id, "email": user.email}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error de autenticación: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_verified_user(
    auth_user: dict = Depends(get_current_user)
) -> dict:
    """
    Extiende get_current_user() verificando el estado del usuario en la DB de negocio.

    INPUT:  auth_user (dict) — usuario autenticado provisto por get_current_user().
    PROCESO:
        1. Busca el usuario en la tabla `users` por email.
        2. Si no existe en la tabla `users` (es un usuario Auth pero sin perfil),
           retorna 403 con mensaje instructivo.
        3. Si el usuario tiene estado BLOCKED_SECURITY, retorna 403.
        4. Si está activo, retorna el perfil completo.
    OUTPUT: dict con el perfil completo del usuario desde la tabla `users`.

    RAISES: HTTPException 403 si el usuario no tiene perfil o está bloqueado.
    """
    email = auth_user.get("email")
    user_profile = get_user_by_email(email)

    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No se encontró un perfil de usuario asociado a esta cuenta. Contacta a soporte.",
        )

    user_status = user_profile.get("user_statuses", {}).get("code", "")
    if user_status == "BLOCKED_SECURITY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta ha sido bloqueada temporalmente por razones de seguridad. Contacta a soporte.",
        )

    return user_profile
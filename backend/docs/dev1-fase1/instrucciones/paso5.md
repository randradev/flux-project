# PASO 5 — Autenticación y Threading de Sesión

**Objetivo:** Implementar la validación de JWT de Supabase Auth en los endpoints de FastAPI y la lógica de `thread_id` vinculado al `user_id` + `conversation_id`. Esto garantiza que cada petición al grafo esté autenticada y que el checkpointer recupere exactamente el estado del usuario correcto.

**Al comenzar este paso, el agente debe [CREAR] el archivo `CP-05-dev1-fase1.md`.**

---

## Sub-paso 5.1 — Implementar la inyección de dependencias en `app/api/deps.py`

**Acción:** [MODIFICAR] `/backend/app/api/deps.py`:

```python
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
```

**[DETENCIÓN OBLIGATORIA 5.1]**
Reportar en `CP-05-dev1-fase1.md`: Confirmación del archivo. Pedir confirmación para continuar al sub-paso 5.2.

---

## Sub-paso 5.2 — Implementar la lógica de Thread ID

**Acción:** [CREAR] `/backend/app/infra/threading.py`:

```python
"""
app/infra/threading.py
─────────────────────────────────────────────────────────────
Gestión del thread_id de LangGraph y su vinculación con el usuario.

PROCESO: En LangGraph, el `thread_id` es la clave que el checkpointer
         usa para almacenar y recuperar el estado del grafo.
         En FLUX, el thread_id equivale al UUID de la conversación,
         que a su vez pertenece a un usuario específico.
         Esta vinculación es lo que garantiza que un usuario solo
         pueda acceder a sus propias conversaciones.

SALIDA:  Funciones para crear o recuperar el thread_id de una sesión.
"""

from app.infra.supabase import supabase_client, create_conversation


def get_or_create_thread(user_id: str, conversation_id: str | None = None) -> str:
    """
    Retorna un thread_id válido para la sesión del usuario.

    INPUT:  user_id (str) — UUID del usuario autenticado.
            conversation_id (str | None) — UUID de conversación existente
              para reanudar, o None para crear una nueva.
    PROCESO:
        1. Si conversation_id es None: crea una nueva conversación en la DB
           y retorna su UUID como thread_id.
        2. Si conversation_id es provisto: verifica que la conversación
           pertenece al user_id (seguridad). Si la verificación pasa,
           retorna el conversation_id como thread_id.
    OUTPUT: thread_id (str) — UUID de la conversación = thread_id de LangGraph.

    RAISES: ValueError si el conversation_id no pertenece al user_id.
    """
    if conversation_id is None:
        # Crear nueva conversación
        new_conv = create_conversation(user_id=user_id)
        return new_conv["id"]
    else:
        # Verificar propiedad de la conversación (CRÍTICO para seguridad)
        response = (
            supabase_client
            .table("conversations")
            .select("id, user_id, is_active")
            .eq("id", conversation_id)
            .eq("user_id", user_id)  # Doble filtro: id Y user_id deben coincidir
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise ValueError(
                f"La conversación {conversation_id} no existe o no pertenece al usuario {user_id}."
            )
        return conversation_id


def get_langgraph_config(thread_id: str) -> dict:
    """
    Retorna el dict de configuración que LangGraph requiere para el checkpointer.

    INPUT:  thread_id (str) — UUID de la conversación.
    OUTPUT: dict {"configurable": {"thread_id": thread_id}}
            Listo para pasar como `config=` en compiled_graph.invoke() / astream().
    """
    return {"configurable": {"thread_id": thread_id}}
```

**[DETENCIÓN OBLIGATORIA 5.2]**
Reportar en `CP-05-dev1-fase1.md`: Confirmación del archivo. Pedir confirmación para continuar al checkpoint del Paso 5.

---

## ✅ CHECKPOINT 5 — Pruebas del Paso 5

---

### Prueba 5.A — Test de Integración: Validación de JWT

**Objetivo:** Verificar que `get_current_user` acepta tokens válidos y rechaza inválidos.

**Diseño:** Agregar a `/backend/tests/test_config.py` (o crear `/backend/tests/test_auth.py`):

```python
"""Tests de autenticación."""
import pytest
from fastapi.testclient import TestClient


def test_protected_endpoint_rejects_missing_token():
    """
    Verifica que un endpoint protegido rechaza requests sin token.
    Para esta prueba, se agrega un endpoint de test temporal a la app.
    """
    from main import app
    from fastapi import Depends
    from app.api.deps import get_current_user

    # Endpoint de prueba (solo para testing)
    @app.get("/test-auth-only")
    async def test_auth_endpoint(user=Depends(get_current_user)):
        return {"user_id": user["user_id"]}

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/test-auth-only")
    # Sin token → debe retornar 403 (HTTPBearer) o 401
    assert response.status_code in [401, 403]


def test_protected_endpoint_rejects_invalid_token():
    """Verifica que un token malformado es rechazado."""
    from main import app
    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        "/test-auth-only",
        headers={"Authorization": "Bearer token_invalido_definitivamente"}
    )
    assert response.status_code in [401, 403]
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/test_auth.py -v`

**Resultado esperado:** 2 tests `PASSED`.

---

### Prueba 5.B — Test Unitario: Thread ID

```python
def test_get_langgraph_config_format():
    """Verifica que get_langgraph_config retorna el formato correcto."""
    from app.infra.threading import get_langgraph_config
    import uuid

    thread_id = str(uuid.uuid4())
    config = get_langgraph_config(thread_id)

    assert "configurable" in config
    assert "thread_id" in config["configurable"]
    assert config["configurable"]["thread_id"] == thread_id


def test_get_or_create_thread_creates_new_conversation():
    """
    Verifica que get_or_create_thread crea una conversación nueva en la DB.
    Requiere un usuario de prueba en la DB.
    """
    from app.infra.supabase import supabase_client
    from app.infra.threading import get_or_create_thread

    users = supabase_client.table("users").select("id").limit(1).execute()
    if not users.data:
        pytest.skip("No hay usuarios en la DB.")

    user_id = users.data[0]["id"]
    thread_id = get_or_create_thread(user_id=user_id)

    assert thread_id is not None
    assert len(thread_id) == 36  # Formato UUID

    # Limpieza
    supabase_client.table("conversations").delete().eq("id", thread_id).execute()
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/ -k "test_get_langgraph_config or test_get_or_create" -v`

---

**[DETENCIÓN OBLIGATORIA — CIERRE PASO 5]**

Reporte Final en `CP-05-dev1-fase1.md`:
1. Resultado de todas las pruebas.
2. Estado: PASO 5 COMPLETADO / PASO 5 BLOQUEADO.
3. Solicitar aprobación para iniciar el Paso 6.

---
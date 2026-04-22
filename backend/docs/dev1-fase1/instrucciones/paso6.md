# PASO 6 — API Endpoints Básicos

**Objetivo:** Exponer el grafo de LangGraph a través de endpoints FastAPI. Implementar el endpoint `/chat` con `StreamingResponse` (HTTP Server-Sent Events) y el endpoint `/history` para recuperación del historial de mensajes.

**Al comenzar este paso, el agente debe [CREAR] el archivo `CP-06-dev1-fase1.md`.**

---

## Sub-paso 6.1 — Implementar el endpoint `/chat` en `app/api/v1/chat.py`

**Acción:** [MODIFICAR] `/backend/app/api/v1/chat.py`:

```python
"""
app/api/v1/chat.py
─────────────────────────────────────────────────────────────
Endpoint principal del sistema FLUX.

PROCESO: Recibe un mensaje del usuario (autenticado), lo inyecta en el
         grafo de LangGraph y transmite la respuesta del asistente en
         tiempo real usando HTTP StreamingResponse (Server-Sent Events).

INPUT:   POST /api/v1/chat con body JSON y JWT en Authorization header.
OUTPUT:  StreamingResponse con eventos SSE. Cada evento contiene un fragmento
         del mensaje del asistente o metadatos de nodo.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from app.api.deps import get_verified_user
from app.graph.workflow import compiled_graph
from app.infra.threading import get_or_create_thread, get_langgraph_config
from app.infra.supabase import save_message, update_conversation_node


router = APIRouter()


# ── Modelos de Request/Response ───────────────────────────────

class ChatRequest(BaseModel):
    """Cuerpo del request POST /chat."""
    message: str                    # Texto del usuario
    conversation_id: str | None = None  # None = nueva conversación; UUID = reanudar


class ChatMetadata(BaseModel):
    """Metadatos opcionales incluidos en los eventos SSE."""
    node: str | None = None
    conversation_id: str | None = None
    product_intent: str | None = None


# ── Generador de Streaming ────────────────────────────────────

async def stream_graph_response(
    user_message: str,
    user_profile: dict,
    thread_id: str,
):
    """
    Generador asíncrono que ejecuta el grafo y emite eventos SSE.

    INPUT:  user_message (str) — Texto del usuario.
            user_profile (dict) — Perfil del usuario desde la DB.
            thread_id (str) — UUID de la conversación (thread del checkpointer).
    PROCESO:
        1. Construye el estado inicial con el mensaje del usuario y el perfil.
        2. Invoca compiled_graph.astream() para streaming asíncrono.
        3. Por cada evento del grafo, emite un evento SSE formateado.
        4. Persiste el mensaje del usuario y la respuesta del asistente en la DB.
    OUTPUT: Genera strings con formato SSE: "data: {json}\n\n"
    """
    config = get_langgraph_config(thread_id)

    # Persistir mensaje del usuario en la DB
    save_message(
        conversation_id=thread_id,
        role="user",
        content=user_message,
    )

    # Estado inicial para el grafo
    initial_state = {
        "messages": [HumanMessage(content=user_message)],
        "user_data": {
            "user_id": str(user_profile.get("id", "")),
            "full_name": user_profile.get("full_name", ""),
            "email": user_profile.get("email", ""),
            "rut": user_profile.get("rut", ""),
            "birth_date": str(user_profile.get("birth_date", "")),
            "user_status": user_profile.get("user_statuses", {}).get("code", "ACTIVE"),
            "user_category": user_profile.get("user_categories", {}).get("code") if user_profile.get("user_categories") else None,
        },
        "session": {
            "conversation_id": thread_id,
            "current_node": "START",
            "is_transversal_active": False,
        },
        "collected_data": {},
        "control_flags": {
            "security_blocked": False,
            "service_error": False,
            "otp_attempts": 0,
            "error_detail": None,
        },
    }

    full_assistant_response = ""
    last_node = "START"

    try:
        # Streaming del grafo: cada evento es una transición de nodo
        async for event in compiled_graph.astream(initial_state, config=config):
            for node_name, node_output in event.items():
                last_node = node_name

                # Extraer mensajes del asistente del output del nodo
                messages = node_output.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "type") and msg.type == "ai":
                        content = msg.content
                        full_assistant_response += content

                        # Emitir evento SSE con el contenido del mensaje
                        sse_data = json.dumps({
                            "type": "message",
                            "content": content,
                            "node": node_name,
                        })
                        yield f"data: {sse_data}\n\n"

                # Emitir metadato de transición de nodo (para el Progress Monitor del FE)
                session_update = node_output.get("session", {})
                if session_update.get("current_node"):
                    meta_data = json.dumps({
                        "type": "node_transition",
                        "node": session_update["current_node"],
                        "product_intent": session_update.get("product_intent"),
                    })
                    yield f"data: {meta_data}\n\n"

        # Persistir respuesta del asistente en la DB
        if full_assistant_response:
            save_message(
                conversation_id=thread_id,
                role="assistant",
                content=full_assistant_response,
                node_at_time=last_node,
            )

        # Señal de fin del stream
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': thread_id})}\n\n"

    except Exception as e:
        error_data = json.dumps({"type": "error", "detail": str(e)})
        yield f"data: {error_data}\n\n"


# ── Endpoint Principal ────────────────────────────────────────

@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    user_profile: dict = Depends(get_verified_user),
):
    """
    Endpoint principal de chat. Procesa un mensaje y transmite la respuesta.

    INPUT:  POST body con {message, conversation_id?} + JWT en Authorization header.
    PROCESO:
        1. Valida el usuario mediante JWT (get_verified_user).
        2. Resuelve o crea el thread_id de la conversación.
        3. Inicia el streaming del grafo.
    OUTPUT: StreamingResponse con eventos SSE.
    """
    user_id = str(user_profile.get("id"))

    try:
        thread_id = get_or_create_thread(
            user_id=user_id,
            conversation_id=request.conversation_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return StreamingResponse(
        stream_graph_response(
            user_message=request.message,
            user_profile=user_profile,
            thread_id=thread_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Deshabilita buffering en nginx
            "X-Conversation-Id": thread_id,
        },
    )
```

**[DETENCIÓN OBLIGATORIA 6.1]**
Reportar en `CP-06-dev1-fase1.md`: Confirmación del endpoint. Pedir confirmación para continuar al sub-paso 6.2.

---

## Sub-paso 6.2 — Implementar el endpoint `/history` en `app/api/v1/docs.py`

**Acción:** [MODIFICAR] `/backend/app/api/v1/docs.py`:

```python
"""
app/api/v1/docs.py
─────────────────────────────────────────────────────────────
Endpoints para recuperación de historial y gestión de documentos.

En Fase 1: Solo el endpoint /history para el historial de conversaciones.
En Fase 2+: Se agregan endpoints para descarga de contratos PDF y verificación de hash.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_verified_user
from app.infra.supabase import supabase_client, get_conversation_messages

router = APIRouter()


@router.get("/history")
async def get_conversation_history(
    user_profile: dict = Depends(get_verified_user),
):
    """
    Recupera todas las conversaciones del usuario con sus últimos mensajes.

    INPUT:  JWT en Authorization header (usuario autenticado).
    PROCESO:
        1. Consulta la tabla `conversations` del usuario, ordenadas por created_at DESC.
        2. Para cada conversación, incluye el último mensaje como preview.
    OUTPUT: Lista de conversaciones con metadatos para el Sidebar del FE.
    """
    user_id = str(user_profile.get("id"))

    response = (
        supabase_client
        .table("conversations")
        .select("id, product_type_id, current_node, is_active, created_at, updated_at, product_types(name)")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(20)
        .execute()
    )

    return {"conversations": response.data or []}


@router.get("/history/{conversation_id}")
async def get_messages_by_conversation(
    conversation_id: str,
    user_profile: dict = Depends(get_verified_user),
):
    """
    Recupera todos los mensajes de una conversación específica.

    INPUT:  conversation_id (str) — UUID de la conversación.
            JWT en Authorization header.
    PROCESO:
        1. Verifica que la conversación pertenece al usuario autenticado.
        2. Recupera todos los mensajes ordenados cronológicamente.
    OUTPUT: Lista de mensajes para reconstruir el hilo en el chat.
    """
    user_id = str(user_profile.get("id"))

    # Verificar propiedad
    conv = (
        supabase_client
        .table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    if not conv.data:
        raise HTTPException(
            status_code=404,
            detail="Conversación no encontrada o no tienes acceso a ella."
        )

    messages = get_conversation_messages(conversation_id)
    return {"conversation_id": conversation_id, "messages": messages}
```

**[DETENCIÓN OBLIGATORIA 6.2]**
Reportar en `CP-06-dev1-fase1.md`: Confirmación del endpoint. Pedir confirmación para continuar al sub-paso 6.3.

---

## Sub-paso 6.3 — Registrar los routers en `main.py`

**Acción:** [MODIFICAR] `/backend/main.py`. Descomentar las líneas de los routers y agregar los imports:

```python
# Agregar estos imports al inicio del archivo (después de los imports existentes):
from app.api.v1 import chat, docs

# Reemplazar las líneas comentadas de routers por:
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(docs.router, prefix="/api/v1", tags=["documents"])
```

**[EJECUTAR]:** Reiniciar el servidor y verificar que `/docs` de Swagger muestra los nuevos endpoints:
```bash
uvicorn main:app --reload
```
Abrir `http://localhost:8000/docs` y confirmar que aparecen:
- `POST /api/v1/chat`
- `GET /api/v1/history`
- `GET /api/v1/history/{conversation_id}`

**[DETENCIÓN OBLIGATORIA 6.3]**
Reportar en `CP-06-dev1-fase1.md`: Screenshot/descripción de los endpoints visibles en Swagger. Pedir confirmación para continuar al checkpoint del Paso 6.

---

## ✅ CHECKPOINT 6 — Pruebas del Paso 6

---

### Prueba 6.A — Test de Integración: Endpoint `/chat` sin autenticación

**Objetivo:** Verificar que el endpoint protegido rechaza requests sin token.

```python
def test_chat_endpoint_requires_auth():
    """POST /chat sin token debe retornar 401/403."""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/v1/chat", json={"message": "Hola"})
    assert response.status_code in [401, 403]


def test_history_endpoint_requires_auth():
    """GET /history sin token debe retornar 401/403."""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/history")
    assert response.status_code in [401, 403]
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/ -k "requires_auth" -v`

**Resultado esperado:** 2 tests `PASSED`.

---

### Prueba 6.B — Test de Integración End-to-End: Flujo completo de mensaje

**Objetivo:** Verificar el flujo completo desde HTTP hasta la DB, usando un usuario de prueba real en Supabase.

> **NOTA IMPORTANTE:** Esta prueba requiere:
> 1. Un usuario creado en Supabase Auth.
> 2. Un registro correspondiente en la tabla `users` con el mismo email.
> 3. El token JWT del usuario de prueba (se obtiene llamando al login de Supabase Auth).
>
> Si no existe un usuario de prueba, el agente debe **reportarlo en el CP y pedir al desarrollador humano que lo cree** antes de continuar.

```python
def test_e2e_chat_flow():
    """
    Test end-to-end: POST /chat → grafo LangGraph → respuesta streamed → DB.
    REQUIERE: Usuario de prueba con JWT válido.
    Ver instrucciones en el comentario de la prueba para obtener el token.
    """
    import os
    import httpx

    # El token de prueba debe estar en una variable de entorno de test
    test_token = os.getenv("FLUX_TEST_JWT_TOKEN")
    if not test_token:
        import pytest
        pytest.skip(
            "FLUX_TEST_JWT_TOKEN no configurado. "
            "Para configurarlo: crear usuario en Supabase Auth, "
            "hacer login y copiar el access_token al .env de test."
        )

    # Hacer request al endpoint usando httpx (soporta streaming)
    with httpx.Client() as client:
        with client.stream(
            "POST",
            "http://localhost:8000/api/v1/chat",
            json={"message": "Hola, quiero un crédito"},
            headers={"Authorization": f"Bearer {test_token}"},
            timeout=30.0,
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            events = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    event_data = json.loads(line[6:])
                    events.append(event_data)
                    if event_data.get("type") == "done":
                        break

    # Verificar que se recibieron eventos
    assert len(events) > 0, "No se recibieron eventos SSE"

    # Verificar que hay al menos un evento de mensaje
    message_events = [e for e in events if e.get("type") == "message"]
    assert len(message_events) > 0, "No se recibió ningún mensaje del asistente"

    # Verificar que hay un evento de finalización
    done_events = [e for e in events if e.get("type") == "done"]
    assert len(done_events) == 1, "No se recibió el evento 'done'"

    conversation_id = done_events[0].get("conversation_id")
    assert conversation_id is not None

    print(f"\nConversation ID creado: {conversation_id}")
    print(f"Total de eventos recibidos: {len(events)}")
    print(f"Respuesta del asistente: {' '.join([e['content'] for e in message_events])}")
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/ -k "test_e2e_chat_flow" -v -s`

**Resultado esperado:** `PASSED` o `SKIPPED` (si no hay token configurado).

---

### Prueba 6.C — Test de Integración: Mensajes persistidos en DB post-chat

**Objetivo:** Verificar que los mensajes del usuario y el asistente se guardan correctamente en la tabla `messages` después de completar un turno de conversación.

```python
def test_messages_persist_after_chat():
    """
    Verifica que tras un turno de chat, los mensajes se guardan en la DB.
    Simula la lógica del stream_graph_response directamente (sin HTTP).
    """
    import uuid
    from app.infra.supabase import supabase_client, save_message, get_conversation_messages, create_conversation

    # Verificar si hay usuario de prueba
    users = supabase_client.table("users").select("id").limit(1).execute()
    if not users.data:
        import pytest
        pytest.skip("No hay usuarios de prueba en la DB.")

    user_id = users.data[0]["id"]

    # Crear conversación de prueba
    conv = create_conversation(user_id=user_id)
    conv_id = conv["id"]

    # Simular guardado de mensajes
    save_message(conv_id, "user", "Quiero abrir una cuenta")
    save_message(conv_id, "assistant", "¡Claro! Te ayudo con tu Cuenta Corriente.", node_at_time="WELCOME_NODE")

    # Verificar persistencia
    messages = get_conversation_messages(conv_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["node_at_time"] == "WELCOME_NODE"

    # Limpieza
    supabase_client.table("messages").delete().eq("conversation_id", conv_id).execute()
    supabase_client.table("conversations").delete().eq("id", conv_id).execute()

    print(f"\nMensajes persistidos y verificados correctamente.")
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/ -k "test_messages_persist" -v -s`

**Resultado esperado:** `PASSED`.

---

**[DETENCIÓN OBLIGATORIA — CIERRE PASO 6]**

Reporte Final en `CP-06-dev1-fase1.md`:
1. Resultado de todas las pruebas del checkpoint.
2. Output de la consola del servidor al recibir el request de chat (si se ejecutó el E2E).
3. Respuesta completa del asistente recibida en el test E2E.
4. Estado general: PASO 6 COMPLETADO / PASO 6 BLOQUEADO.

---
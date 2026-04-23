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
# from app.graph.workflow import compiled_graph
from app.graph.workflow import get_active_graph # Adaptado a patrón Lazy Init para la compilación del grafo
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
        # Cambios para adaptar el uso del grafo compilado: Importación y obtención de instancia
        compiled_graph = get_active_graph()
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
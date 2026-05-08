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

# ── Integrar friendly_label y progress_percent desde flux.js ───────────────────────────────

# Espejo del NODE_DETAILS de flux.js. Fuente de verdad para etiquetas en el stream.
_NODE_LABELS: dict[str, dict] = {
    "WELCOME_NODE":               {"label": "Recepcion",          "progress": 0},
    "INTENT_ROUTER":              {"label": "Clasificacion",       "progress": 5},
    "GENERAL_RESPONSE":           {"label": "Respuesta general",   "progress": 100},
    "LOAN_INIT":                  {"label": "Inicio credito",      "progress": 10},
    "LOAN_COLLECTING_PROFILE":    {"label": "Perfil financiero",   "progress": 20},
    "LOAN_COLLECTING_SIMULATION": {"label": "Simulacion",          "progress": 35},
    "LOAN_RISK_ENGINE":           {"label": "Motor de riesgo",     "progress": 55},
    "LOAN_PRE_APPROVED":          {"label": "Oferta transparente", "progress": 65},
    "LOAN_OTP_VALIDATION":        {"label": "Validacion OTP",      "progress": 80},
    "LOAN_FORMALIZATION":         {"label": "Formalizacion",       "progress": 90},
    "LOAN_COMPLETED":             {"label": "Credito completado",  "progress": 100},
    "LOAN_REJECTED_POLICY":       {"label": "Solicitud rechazada", "progress": 100},
    "LOAN_SECURITY_BLOCK":        {"label": "Bloqueo seguridad",   "progress": 100},
    "LOAN_CLOSED_BY_USER":        {"label": "Cierre voluntario",   "progress": 100},
    # Agregar ACCOUNT_* y DAP_* cuando sus flujos estén listos
}

def enrich_payload_with_labels(payload: dict) -> dict:
    """Agrega friendly_label y progress_percent al payload usando _NODE_LABELS."""
    node = payload.get("node", "")
    meta = _NODE_LABELS.get(node, {})
    payload["friendly_label"] = meta.get("label", node)
    payload["progress_percent"] = meta.get("progress", None)
    return payload

# Lista de nodos cuya entrada debe pre-anunciar un estado PROCESSING
_ENGINE_NODES = {
    "LOAN_RISK_ENGINE",
    "ACCOUNT_EVALUATION_ENGINE",
    "DAP_INVESTMENT_ENGINE",
    "LOAN_FORMALIZATION",
}

# ── Extractor dinámico de namespaces ───────────────────────────────

# Namespaces del FluxState que el Frontend necesita consumir.
# Para agregar soporte a un nuevo namespace, solo añadir su key aquí.
_STATE_NAMESPACES = [
    "transparency_data",
    "collecting_data",
    "evaluation_results",
    "offer_data",
    "auth_control",
    "flow_result",
]

def build_node_transition_payload(
    node_name: str,
    node_output: dict,
) -> dict | None:
    """
    Construye el payload de un evento node_transition a partir del output
    de un nodo de LangGraph.

    Retorna None si no hay datos de sesión relevantes para emitir.
    Solo incluye en el payload los namespaces que el nodo realmente modificó
    (i.e., que están presentes como keys en node_output con valor no None).
    """
    session = node_output.get("session", {})
    current_node = session.get("current_node")

    if not current_node:
        return None

    payload = {
        "type": "node_transition",
        "node": current_node,
        "node_status": "SUCCESS",  # Extendible: ERROR, PROCESSING
        "product_intent": session.get("product_intent"),
        "application_id": session.get("application_id"),
        "friendly_label": None,    # Ver Paso 1.2
        "progress_percent": None,  # Ver Paso 1.2
    }

    # Inyección dinámica de namespaces: solo los que el nodo escribió
    for namespace_key in _STATE_NAMESPACES:
        value = node_output.get(namespace_key)
        if value is not None:
            payload[namespace_key] = value

    return payload

# ── Modelos de Request/Response ───────────────────────────────

class ChatRequest(BaseModel):
    """Cuerpo del request POST /chat."""
    message: str                    # Texto del usuario
    conversation_id: str | None = None  # None = nueva conversación; UUID = reanudar
    product_intent: str | None = None   # <--- AGREGAR ESTO (Opcional: LOAN, ACCOUNT, DAP)


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
    product_intent: str | None = None, # <--- AGREGAR ESTO
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

    # Persistir mensaje del usuario en la DB para el historial
    from app.infra.supabase import save_message
    save_message(
        conversation_id=thread_id,
        role="user",
        content=user_message,
    )

    # --- NUEVO: Rehidratación de Memoria desde la DB ---
    # Si no hay una intención nueva (es un mensaje de seguimiento), buscamos el último estado en la DB
    db_snapshot = None
    if not product_intent:
        from app.infra.supabase import get_conversation_snapshot
        db_snapshot = get_conversation_snapshot(thread_id)

    # 1. Hidratación Base
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
        }
    }

    # 2. Si hay un snapshot en la DB, lo inyectamos como base para que el Grafo no arranque en blanco
    if db_snapshot:
        # Inyectamos los namespaces críticos para que route_after_welcome sepa qué hacer
        initial_state["session"] = db_snapshot.get("session", {})
        initial_state["collecting_data"] = db_snapshot.get("collecting_data", {})
        initial_state["evaluation_results"] = db_snapshot.get("evaluation_results", {})
        initial_state["offer_data"] = db_snapshot.get("offer_data", {})
        initial_state["auth_control"] = db_snapshot.get("auth_control", {})
        initial_state["transparency_data"] = db_snapshot.get("transparency_data", {})

    # 3. Solo si hay una intención nueva (botón), forzamos el reset de sesión
    if product_intent:
        initial_state["session"] = {
            "conversation_id": thread_id,
            "product_intent": product_intent,
            "current_node": "START",
            "is_transversal_active": False,
        }
        initial_state["collecting_data"] = {}
        initial_state["evaluation_results"] = {}
        initial_state["offer_data"] = {}
        initial_state["auth_control"] = {"security_blocked": False, "otp_attempts": 0}
        initial_state["transparency_data"] = {}

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

                # Emitir metadato de transición de nodo (para el Progress Monitor del FE) con namespaces completos
                                # ── 2. Emitir transición de nodo con namespaces completos (Paso 1.3 y 1.4) ──
                transition_payload = build_node_transition_payload(node_name, node_output)
                
                if transition_payload:
                    # Enriquecer con labels y progreso antes de emitir cualquier cosa
                    transition_payload = enrich_payload_with_labels(transition_payload)
                    
                    # A. Si es un nodo ENGINE, pre-anunciar estado PROCESSING
                    if transition_payload.get("node") in _ENGINE_NODES:
                        processing_event = {
                            "type": "node_transition",
                            "node": transition_payload["node"],
                            "node_status": "PROCESSING",
                            "product_intent": transition_payload.get("product_intent"),
                            "friendly_label": transition_payload.get("friendly_label"),
                            "progress_percent": transition_payload.get("progress_percent"),
                        }
                        yield f"data: {json.dumps(processing_event)}\n\n"
                    
                    # B. Emitir siempre el evento SUCCESS final con los namespaces
                    yield f"data: {json.dumps(transition_payload)}\n\n"

                    # El evento SUCCESS con los namespaces se emite al finalizar el nodo (lógica anterior)
                    
                # Persistir respuesta del asistente en la DB
                if full_assistant_response:
                    save_message(
                        conversation_id=thread_id,
                        role="assistant",
                        content=full_assistant_response,
                        node_at_time=last_node,
                    )

# --- NUEVO: Sincronización centralizada de Estado y Producto ---
        # Capturamos el estado final para la próxima vez
        final_state = await compiled_graph.get_state(config)
        state_values = final_state.values
        
        # Extraemos los valores reales de la sesión (que ya vienen en UPPER_CASE desde los nodos)
        session_data = state_values.get("session", {})
        current_product = session_data.get("product_intent")
        current_node_upper = session_data.get("current_node", last_node.upper()) # Usamos el de la sesión o forzamos upper
        from app.infra.supabase import update_conversation_node, update_conversation_product
        
        if current_product and current_product != "GENERAL":
            update_conversation_product(thread_id, current_product)
            
        # IMPORTANTE: Guardamos el current_node_upper para que el ruteador lo reconozca al volver
        update_conversation_node(
            conversation_id=thread_id,
            current_node=current_node_upper,
            state_snapshot=state_values
        )
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
    print(f"\n[DEBUG-API] LLEGADA: ID={request.conversation_id}, INTENT={request.product_intent}")
    print(f"[DEBUG-API] MENSAJE: '{request.message}'")
    
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
            product_intent=request.product_intent,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Deshabilita buffering en nginx
            "X-Conversation-Id": thread_id,
        },
    )
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

# Mapeo de Acciones Directas (Bypass de LLM)
# Formato: { PRODUCTO: { ACCION: { "node": "SIGUIENTE_NODO", "progress_flag": "campo_a_marcar" } } }
DIRECT_ACTION_RULES = {
    "LOAN": {
        "ACCEPT_OFFER": {
            "node": "LOAN_OTP_VALIDATION",
            "progress_flag": "pre_approval_accepted"
        },
        "REJECT_OFFER": {
            "node": "LOAN_CLOSED_BY_USER",
            "progress_flag": "closed_by_user"
        }
    }
}

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

class ActionRequest(BaseModel):
    conversation_id: str
    action: str

# ── Generador de Streaming ────────────────────────────────────

async def stream_graph_response(
    user_message: str,
    user_profile: dict,
    thread_id: str,
    product_intent: str | None = None, 
    
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
        "messages": [{"type": "human", "content": user_message}],
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
        initial_state["messages"] = db_snapshot.get("messages", []) + [{"type": "human", "content": user_message}]

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

    # --- BORRA DESDE AQUÍ (Línea 226 aprox) ---
    full_assistant_response = ""
    last_node = "START"
    current_snapshot = initial_state.copy()

    try:
        compiled_graph = get_active_graph()
        async for event in compiled_graph.astream(initial_state, config=config):
            for node_name, node_output in event.items():
                last_node = node_name
                
                for key, val in node_output.items():
                    if key == "messages":
                        serializable_msgs = [m.dict() if hasattr(m, "dict") else m for m in val]
                        current_snapshot["messages"] = current_snapshot.get("messages", []) + serializable_msgs
                    else:
                        current_snapshot[key] = val
                
                # 2. Guardar en la base de datos de inmediato
                # 2. Guardar en la base de datos de inmediato
                update_conversation_node(
                    conversation_id=thread_id,
                    current_node=last_node,
                    state_snapshot=current_snapshot # Usamos el snapshot que ya actualizamos arriba
                )

                # 3. Emitir mensajes del asistente
                messages = node_output.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "type") and msg.type == "ai":
                        content = msg.content
                        full_assistant_response += content
                        yield f"data: {json.dumps({'type': 'message', 'content': content, 'node': node_name})}\n\n"

                # 4. Emitir transiciones de nodo (Lo que pedía el frontend)
                transition_payload = build_node_transition_payload(node_name, node_output)
                if transition_payload:
                    transition_payload = enrich_payload_with_labels(transition_payload)
                    if transition_payload.get("node") in _ENGINE_NODES:
                        yield f"data: {json.dumps({**transition_payload, 'node_status': 'PROCESSING'})}\n\n"
                    yield f"data: {json.dumps(transition_payload)}\n\n"
    
    except Exception as e:
        print(f"Error en stream: {e}")
        yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"
    
    if full_assistant_response:
        save_message(
            conversation_id=thread_id,
            role="assistant",
            content=full_assistant_response,
            node_at_time=last_node,
        )
    
    yield f"data: {json.dumps({'type': 'done', 'conversation_id': thread_id})}\n\n"


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

@router.post("/action")
async def action_endpoint(
    request: ActionRequest,
    user_profile: dict = Depends(get_verified_user),
):
    """
    Ejecuta una acción de negocio directa (ej: Aceptar Oferta) sin pasar por el LLM.
    Actualiza el estado en la DB y dispara la respuesta del siguiente nodo.
    """
    conv_id = request.conversation_id
    action_key = request.action
    # 1. Obtener snapshot actual desde la DB para saber dónde estamos
    from app.infra.supabase import get_conversation_snapshot, update_conversation_node
    snapshot = get_conversation_snapshot(conv_id)
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="No se encontró la conversación.")
    # 2. Identificar el Producto y buscar la regla
    session = snapshot.get("session", {})
    product = session.get("product_intent", "GENERAL")

    # 3. CIRUGÍA: Actualizar estado manualmente
    if product == "LOAN" and action_key == "ACCEPT_OFFER":
        next_node = "LOAN_OTP"  # El siguiente paso es el OTP
        flag = "pre_approval_accepted"
    elif product == "ACCOUNT" and action_key == "ACCEPT_OFFER":
        # Por si acaso, para otros productos
        next_node = "ACCOUNT_OTP" 
        flag = "pre_approval_accepted"
    elif product == "DAP" and action_key == "ACCEPT_OFFER":
        # Por si acaso, para otros productos
        next_node = "DAPT_OTP" 
        flag = "pre_approval_accepted"
    # else:
    #     # Por si acaso...
    #     next_node = "WELCOME" 
    #     flag = "unknown"
    
    # Marcamos el progreso (ej: pre_approval_accepted = True)
    progress = session.get("progress", {})
    if product == "LOAN":
        # En crédito, estas flags van directo en el root del progress
        progress[flag] = True
        # Si aceptó, marcamos que el paso de pre-aprobación terminó con éxito
        from app.graph.constants import CompletedStep
        if action_key == "ACCEPT_OFFER":
            session["just_completed_step"] = CompletedStep.LOAN_PRE_APPROVED
    
    session["progress"] = progress
    session["current_node"] = next_node
    snapshot["session"] = session
    # 4. Persistir el cambio: Ahora la DB dice que estamos en el SIGUIENTE nodo
    update_conversation_node(
        conversation_id=conv_id,
        current_node=next_node,
        state_snapshot=snapshot
    )
    # 5. Disparar el Grafo: Como ya actualizamos la DB, al rehidratar 
    # el Grafo despertará directamente en el nodo destino (ej: OTP).
    return StreamingResponse(
        stream_graph_response(
            user_message=f"[ACCION_DIRECTA:{action_key}]", # Mensaje interno para logs
            user_profile=user_profile,
            thread_id=conv_id,
            product_intent=None
        ),
        media_type="text/event-stream",
    )
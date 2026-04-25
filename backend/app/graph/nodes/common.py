"""
app/graph/nodes/common.py
─────────────────────────────────────────────────────────────
Nodos transversales y utilitarios del Grafo FLUX.

Contiene los nodos compartidos por todos los flujos de producto:
- WELCOME_NODE: Saludo inicial y carga del perfil de usuario.
- INTENT_ROUTER_NODE: Clasificador de intención del primer mensaje.

Fase 3 agregará aquí: KNOWLEDGE_BASE_RAG, AMBIGUITY_HANDLER,
SERVICE_ERROR_HANDLER, SECURITY_WATCHDOG, GLOBAL_END, RESUME_HANDLER.
"""

from datetime import date
from langchain_core.messages import AIMessage, SystemMessage
from app.graph.state import FluxState
from app.infra.supabase import get_user_by_email, update_conversation_node
from app.infra.gemini_client import get_chat_model
from app.infra.supabase import update_application_semaphores


def _calculate_age(birth_date_str: str) -> int:
    """
    Calcula la edad en años completos a partir de una fecha ISO8601.

    INPUT:  birth_date_str — string ISO8601 (ej: "1990-05-15")
    OUTPUT: edad en años completos (int)
    EDGE CASE: Si el cumpleaños es hoy, ya cumplió → se cuenta el año.
    """
    birth = date.fromisoformat(birth_date_str)
    today = date.today()
    return today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )


def welcome_node(state: FluxState) -> dict:
    """
    Nodo de bienvenida, carga de perfil y preparación de datos universales.

    INPUT (State):
        - state["user_data"]: Perfil RAW del usuario desde DB.
        - state["session"]: Metadatos de sesión.
        - state["messages"]: Historial (vacío=nueva sesión, con contenido=reanudada).

    PROCESO:
        1. Detecta si es sesión nueva o reanudada.
        2. Calcula edad a partir de birth_date (centralizado aquí para toda la app).
        3. Genera mensaje de bienvenida personalizado.
        4. Actualiza GPS en Supabase.
        5. Escribe preparation_data con datos procesados.

    OUTPUT (campos del State que modifica):
        - messages: Agrega mensaje de bienvenida.
        - session["current_node"]: "WELCOME_NODE".
        - preparation_data: {nombre, rut, mail, edad}.
    """
    user = state.get("user_data", {})
    session = state.get("session", {})
    messages = state.get("messages", [])

    full_name = user.get("full_name", "")
    first_name = full_name.split()[0] if full_name else "amig@"

    # Calcular edad (responsabilidad centralizada en este nodo desde v2.0)
    birth_date_str = user.get("birth_date")
    edad = _calculate_age(birth_date_str) if birth_date_str else 0

    # Detectar si es sesión nueva o reanudada
    is_resumed = len(messages) > 0 and session.get("previous_node") is not None

    if is_resumed:
        welcome_text = (
            f"¡Hola de nuevo, {first_name}! 👋 Veo que nos habíamos quedado a mitad del camino. "
            f"No te preocupes, tu progreso está guardado. ¿Continuamos donde lo dejamos?"
        )
    else:
        welcome_text = (
            f"¡Hola, {first_name}! 👋 Soy Flux, tu asistente financiero. "
            f"Estoy aquí para ayudarte a solicitar un **Crédito de Consumo**, "
            f"abrir una **Cuenta Corriente**, o contratar un **Depósito a Plazo**. "
            f"¿Con qué te puedo ayudar hoy?"
        )

    # Actualizar GPS en la DB
    conversation_id = session.get("conversation_id")
    if conversation_id:
        update_conversation_node(conversation_id, "WELCOME_NODE")

    # ── Actualizar semáforo del inicio ──
    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id,
            current_node_id="WELCOME_NODE",
            node_status="SUCCESS",
            engine_status="PENDING"
        )

    return {
        "messages": [AIMessage(content=welcome_text)],
        "session": {**session, "current_node": "WELCOME_NODE"},
        # ── NUEVO en v2.0: preparation_data ──────────────────────
        "preparation_data": {
            "nombre": full_name,
            "rut": user.get("rut", ""),
            "mail": user.get("email", ""),
            "edad": edad,
        },
    }


# ── INTENT_ROUTER_NODE ────────────────────────────────────────

_INTENT_SYSTEM_PROMPT = """
Eres el clasificador de intenciones de FLUX, un sistema bancario conversacional.
Tu única función es analizar el mensaje del usuario y clasificar su intención
en UNA de las siguientes categorías exactas. Responde SOLO con la categoría, sin explicaciones.

CATEGORÍAS:
- LOAN: El usuario quiere solicitar un crédito, préstamo, financiamiento o dinero prestado.
- ACCOUNT: El usuario quiere abrir una cuenta corriente o cuenta bancaria.
- DAP: El usuario quiere invertir, hacer un depósito a plazo, ahorrar con intereses o un DAP.
- GENERAL: El usuario tiene una pregunta general, duda, saludo, o algo que no encaja en las categorías anteriores.

EJEMPLOS:
"Quiero un crédito de 5 millones" → LOAN
"Necesito abrir una cuenta" → ACCOUNT
"¿Puedo invertir mi sueldo?" → DAP
"¿Cómo funciona esto?" → GENERAL
"hola" → GENERAL
"¿Qué es el CAE?" → GENERAL
"""


def intent_router_node(state: FluxState) -> dict:
    """
    Nodo clasificador de la intención inicial del usuario.

    INPUT (State):
        - state["messages"]: Último mensaje del usuario.
        - state["session"]: Datos de sesión actuales.

    PROCESO:
        1. Extrae el último mensaje del usuario del historial.
        2. Envía el mensaje al LLM con el prompt de clasificación.
        3. Parsea la respuesta para obtener el código de intención (LOAN, ACCOUNT, DAP, GENERAL).
        4. Actualiza el product_intent en el estado.

    OUTPUT (campos del State que modifica):
        - session["product_intent"]: Código de intención detectada.
        - session["current_node"]: Actualizado a "INTENT_ROUTER".
    """
    from langchain_core.messages import HumanMessage

    messages = state.get("messages", [])
    session = state.get("session", {})

    # Obtener el último mensaje del usuario
    last_user_message = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_message = msg.content
            break

    if not last_user_message:
        # Si no hay mensaje del usuario, asumir intención GENERAL
        intent = "GENERAL"
    else:
        model = get_chat_model()
        classification_messages = [
            SystemMessage(content=_INTENT_SYSTEM_PROMPT),
            HumanMessage(content=last_user_message),
        ]
        response = model.invoke(classification_messages)
        content = response.content
        
        # Manejo robusto: Gemini a veces retorna una lista de bloques
        if isinstance(content, list):
            content = " ".join([c if isinstance(c, str) else str(c.get("text", "")) for c in content])
        
        raw_intent = content.strip().upper()

        # Validar que la respuesta es una categoría válida
        valid_intents = {"LOAN", "ACCOUNT", "DAP", "GENERAL"}
        intent = raw_intent if raw_intent in valid_intents else "GENERAL"


    return {
        "session": {
            **session,
            "product_intent": intent,
            "current_node": "INTENT_ROUTER",
        }
    }

# ── GENERAL_RESPONSE_NODE ────────────────────────────────────────

def general_response_node(state: FluxState) -> dict:
    """
    INPUT: state["messages"] (último mensaje del usuario con intención GENERAL)
    PROCESO: Genera una respuesta empática para preguntas generales o saludos,
             redirigiendo al usuario hacia los productos disponibles.
    OUTPUT: messages (respuesta general)
    """
    session = state.get("session", {})
    msg = (
        "¡Hola! Estoy aquí para ayudarte. Puedo asistirte con:\n\n"
        "• 💳 **Crédito de Consumo** — Financiamiento para lo que necesitas\n"
        "• 🏦 **Cuenta Corriente** — Abre tu cuenta hoy\n"
        "• 📈 **Depósito a Plazo** — Haz crecer tu dinero\n\n"
        "¿Con cuál de estos productos te puedo ayudar?"
    )
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "GENERAL_RESPONSE"},
    }
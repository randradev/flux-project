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
from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema
from app.infra.gemini_client import get_structured_model

# ======================================================================================================
# LLM Y PROMPTS
# ======================================================================================================

# ── CONFIGURACIÓN DE INTELIGENCIA (SINGLETONS) ──────────────
# Singletons de modelos (se instancian una vez al importar el módulo)
_intent_extractor = get_structured_model(IntentExtractionSchema)

# ─────────────────────────────────────────────────────────────────────────────────────────
# ── PROMPT DE RECONOCIMIENTO DE INTENCIÓN (INTENT_ROUTER_NODE) ───────────────────────────
# ─────────────────────────────────────────────────────────────────────────────────────────

# ── PROMPT LLAMADA A: EXTRACCIÓN ────────────────────────────────────────────
# Directivo y sin ambigüedad. Temperatura 0.0 hace el trabajo pesado;
# el prompt solo establece el contrato de qué retornar.

_INTENT_SYSTEM_PROMPT = """
Eres el clasificador de intenciones de FLUX, un sistema bancario conversacional.
Analiza el mensaje del usuario y clasifica su intención en UNA categoría exacta.

CATEGORÍAS:
  LOAN    — Crédito, préstamo, financiamiento, plata prestada.
  ACCOUNT — Cuenta corriente, cuenta bancaria, abrir cuenta.
  DAP     — Depósito a plazo, inversión, ahorrar con intereses, DAP.
  GENERAL — Saludo, pregunta general, duda o mensaje fuera de las categorías anteriores.

REGLA DE ORO: Retorna JSON con los campos razonamiento, intencion y confianza.

EJEMPLOS:
  "Quiero un crédito de 5 millones" → LOAN, ALTA
  "Necesito abrir una cuenta"       → ACCOUNT, ALTA
  "¿Puedo invertir mi sueldo?"      → DAP, MEDIA
  "¿Qué es el CAE?"                 → GENERAL, ALTA
  "hola"                            → GENERAL, ALTA
"""

# ======================================================================================================
# HELPERS
# ======================================================================================================

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

# ======================================================================================================
# NODOS TRANSVERSALES
# ======================================================================================================

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
        3. Genera mensaje de bienvenida personalizado dependiendo del modo de operación.
        4. Actualiza GPS en Supabase.
        5. Escribe preparation_data con datos procesados.

    OUTPUT (campos del State que modifica):
        - messages: Agrega mensaje de bienvenida.
        - session["current_node"]: "WELCOME_NODE".
        - preparation_data: {nombre, rut, mail, edad}.

    VERSIÓN 2.1 — Nodo de Hidratación Silenciosa.

    MODOS DE OPERACIÓN:
      A) Silencioso: cuando product_intent ya existe O hay mensajes previos.
         → Solo hidrata preparation_data y actualiza GPS. Sin AIMessage.
      B) Bienvenida: cuando es sesión completamente nueva (sin intención ni historial).
         → Emite mensaje de bienvenida con los productos disponibles.

    REGLA DE ORO: Este nodo NUNCA sobreescribe current_node si ya hay
    un proceso activo (ver _RESUME_MAP en edges.py). Su current_node
    propio ("WELCOME_NODE") sólo se escribe en Modo Bienvenida.
    """
    user = state.get("user_data", {})
    session = state.get("session", {})
    messages = state.get("messages", [])

    # ── Datos universales (siempre se calculan) ───────────────
    full_name = user.get("full_name", "")
    first_name = full_name.split()[0] if full_name else "amig@"

    # Calcular edad (responsabilidad centralizada en este nodo desde v2.0)
    birth_date_str = user.get("birth_date")
    edad = _calculate_age(birth_date_str) if birth_date_str else 0

    preparation_data = {
        "nombre": full_name,
        "rut": user.get("rut", ""),
        "mail": user.get("email", ""),
        "edad": edad,
    }

    # ── Detección de modo ─────────────────────────────────────
    product_intent = session.get("product_intent")
    has_history = len(messages) > 0
    is_silent_mode = (product_intent is not None) or has_history

    # ── Actualizar GPS en Supabase (siempre) ─────────────────
    conversation_id = session.get("conversation_id")
    application_id = session.get("application_id")

    if is_silent_mode:
        # MODO SILENCIOSO: hidrata datos, no toca current_node del proceso activo
        if conversation_id:
            # No sobreescribir: informar a Supabase que welcome pasó pero no es el nodo activo
            pass  # El nodo activo real se actualizará en su propio nodo
        if application_id:
            update_application_semaphores(
                application_id,
                current_node_id="WELCOME_NODE",
                node_status="SUCCESS",   # No "BYPASSED" hasta validar el enum en la DB
                engine_status="PENDING"
            )
        # Retornar sin messages: sólo preparation_data se escribe
        return {
            "preparation_data": preparation_data,
            # session NO se modifica: current_node del proceso activo se preserva
        }

    else:
        # MODO BIENVENIDA: sesión nueva, sin intención, sin historial
        welcome_text = (
            f"¡Hola, {first_name}! 👋 Soy Flux, tu asistente financiero. "
            f"Estoy aquí para ayudarte a solicitar un **Crédito de Consumo**, "
            f"abrir una **Cuenta Corriente**, o contratar un **Depósito a Plazo**. "
            f"¿Con qué te puedo ayudar hoy?"
        )
        if conversation_id:
            update_conversation_node(conversation_id, "WELCOME_NODE")
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
            "preparation_data": preparation_data,
        }

# ── INTENT_ROUTER_NODE ────────────────────────────────────────
def intent_router_node(state: FluxState) -> dict:
    """
    VERSIÓN 2.1 — Clasificador con extracción estructurada (Llamada Tipo A).

    INPUT (State):
        - state["messages"]: Último mensaje del usuario.
        - state["session"]: Datos de sesión actuales.

    PROCESO:
        1. Extrae el último mensaje del usuario del historial.
        2. Envía el mensaje al LLM con el prompt de clasificación.
        3. Usa _intent_extractor (LLM.with_structured_output(IntentExtractionSchema))
        en lugar de text completion con parsing manual.
        4. Registra confianza en session para futuros umbrales.
        5. Actualiza el product_intent en el estado.

    OUTPUT (campos del State que modifica):
        - session["product_intent"]: Código de intención detectada.
        - session["current_node"]: Actualizado a "INTENT_ROUTER".
    """
    from langchain_core.messages import HumanMessage

    messages = state.get("messages", [])
    session = state.get("session", {})

    # Obtener el último mensaje del usuario
    last_user_message = next(
        (m.content for m in reversed(messages) if hasattr(m, "type") and m.type == "human"),
        ""
    )

    if not last_user_message:
        return {
            "session": {
                **session,
                "product_intent": "GENERAL",
                "current_node": "INTENT_ROUTER",
            }
        }

    # Extracción con LLM estructurado
    extracted: IntentExtractionSchema = _intent_extractor.invoke([
        {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
        {"role": "user",   "content": last_user_message},
    ]) or IntentExtractionSchema(intencion="GENERAL", razonamiento="Error en extracción")


    return {
        "session": {
            **session,
            "product_intent": extracted.intencion,
            "current_node":   "INTENT_ROUTER",
            # confianza se puede guardar en session para logging si se agrega a SessionData
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
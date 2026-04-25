from langchain_core.messages import AIMessage
from app.graph.state import FluxState
from app.infra.supabase import update_application_semaphores

def loan_entry_node(state: FluxState) -> dict:
    """
    Nodo LOAN_INIT: punto de entrada al flujo de Crédito de Consumo.

    INPUT (State):
        - state["preparation_data"]: Datos del usuario (nombre, rut, mail, edad).
        - state["session"]: Para verificar product_intent == "LOAN".
        - state["collecting_data"]["loan_profile"]: Se limpiará (reset).
        - state["collecting_data"]["loan_sim"]: Se limpiará (reset).

    PROCESO (Fase 2):
        1. Handshake: Verificar que product_intent == "LOAN".
        2. Reset: Limpiar loan_profile y loan_sim.
        3. Saludo personalizado con datos de preparation_data.

    OUTPUT (campos del State que modifica):
        - messages: Saludo de bienvenida al flujo de crédito.
        - session["current_node"]: "LOAN_INIT".
        - collecting_data["loan_profile"]: {} (limpio).
        - collecting_data["loan_sim"]: {} (limpio).

    NOTA FASE 1: Este nodo es un stub. Solo hace el reset y confirma la intención.
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})

    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    # Handshake: verificar intención (defensa en profundidad)
    product_intent = session.get("product_intent")
    if product_intent != "LOAN":
        # Esto no debería ocurrir si edges.py está bien configurado
        # pero es una salvaguarda explícita
        msg = "Hubo un error de navegación. Por favor, indica nuevamente qué necesitas."
    else:
        msg = (
            f"¡Perfecto, {first_name}! Vamos a revisar tu solicitud de **Crédito de Consumo**. "
            f"Es un proceso rápido. Primero necesito conocer un poco tu perfil financiero. "
            f"¿Cuál es tu renta líquida mensual?"
        )

    # Actualizamos semáforo para notificar que el Nodo de Inicio del Flujo terminó
    application_id = session.get("application_id")

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_INIT", # Cambia según el nodo
            node_status="IN_PROGRESS",       # Avisamos que el INIT terminó
            engine_status="PENDING"      # El motor de producto aún no arranca
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "LOAN_INIT"},
        # ── RESET del namespace del producto ─────────────────────
        # Limpia datos de intentos anteriores sin tocar los otros productos.
        "collecting_data": {
            "loan_profile": {},
            "loan_sim": {},
        },
    }
"""
app/graph/nodes/account.py
─────────────────────────────────────────────────────────────
Nodos del flujo de Cuenta Corriente.

Ruta del grafo: account_entry → account_evaluation_engine → END
  - account_entry              (ID LangGraph) → current_node = "ACCOUNT_INIT"
  - account_evaluation_engine  (ID LangGraph) → current_node = "ACCOUNT_EVALUATION_ENGINE"
"""

from langchain_core.messages import AIMessage
from app.graph.state import FluxState
from app.infra.supabase import update_application_semaphores


# ── ACCOUNT_ENTRY (account_entry) ────────────────────────────

def account_entry_node(state: FluxState) -> dict:
    """
    Nodo ACCOUNT_INIT: punto de entrada al flujo de Cuenta Corriente.

    ID LangGraph : account_entry
    current_node : ACCOUNT_INIT   ← valor semántico para GPS y Supabase

    PROCESO:
        1. Handshake: Verificar que product_intent == "ACCOUNT".
        2. Reset: Limpiar account_profile.
        3. Saludo personalizado con datos de preparation_data.
        4. Actualizar semáforo: ACCOUNT_INIT / SUCCESS / PENDING.

    OUTPUT:
        - messages: Saludo de bienvenida al flujo de cuenta.
        - session["current_node"]: "ACCOUNT_INIT".
        - collecting_data["account_profile"]: {} (limpio).
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})
    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    msg = (
        f"¡Genial, {first_name}! Vamos a abrir tu **Cuenta Corriente**. "
        f"Para asignarte la mejor categoría, cuéntame: ¿cuál es tu renta líquida mensual?"
    )

    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="ACCOUNT_INIT",
            node_status="SUCCESS",
            engine_status="PENDING",
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "ACCOUNT_INIT"},
        "collecting_data": {
            "account_profile": {},
        },
    }


# ── ACCOUNT_EVALUATION_ENGINE (account_evaluation_engine) ────

def account_evaluation_engine_node(state: FluxState) -> dict:
    """
    Nodo ACCOUNT_EVALUATION_ENGINE: motor de evaluación para cuenta corriente.

    ID LangGraph : account_evaluation_engine
    current_node : ACCOUNT_EVALUATION_ENGINE   ← valor semántico para GPS y Supabase

    INPUT (State leído):
        - state["collecting_data"]["account_profile"]: renta, antiguedad_laboral, nivel_estudios
        - state["preparation_data"]["edad"]: edad del usuario

    PROCESO:
        1. Extraer inputs de los namespaces correctos.
        2. Invocar al motor de evaluación comercial (modules/account_eng.py).
        3. Escribir todos los outputs en evaluation_results["account_engine"].
        4. Actualizar semáforo: ACCOUNT_EVALUATION_ENGINE / SUCCESS / COMPLETED.

    OUTPUT:
        - evaluation_results["account_engine"]: Resultado completo del motor.
        - session["current_node"]: "ACCOUNT_EVALUATION_ENGINE".

    NOTA ARQUITECTURA:
        Wrapper de flujo. La lógica de categorización está delegada a
        modules/account_eng.py para asegurar testabilidad.
    """
    session = state.get("session", {})
    prep = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})

    account_profile = collecting.get("account_profile", {})
    renta = account_profile.get("renta", 0)
    antiguedad_laboral = account_profile.get("antiguedad_laboral", 0)
    nivel_estudios = account_profile.get("nivel_estudios", "")
    edad = prep.get("edad", 0)

    # TODO Fase 3: engine_result = account_eng.calculate_account_category(...)
    engine_result = {
        "status_proceso": "PRE_APPROVED",
        "is_elegible": True,
        "base_category": "ADVANCE",
        "final_category": "ADVANCE",
        "has_upgrade": False,
        "credit_line_amount": 500000,
        "monthly_cost": 0,
        "motivo_rechazo": None,
    }

    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="ACCOUNT_EVALUATION_ENGINE",
            node_status="SUCCESS",
            engine_status="COMPLETED",
        )

    return {
        "evaluation_results": {
            "account_engine": engine_result,
        },
        "session": {**session, "current_node": "ACCOUNT_EVALUATION_ENGINE"},
    }
from langchain_core.messages import AIMessage
from app.graph.state import FluxState
from app.infra.supabase import update_application_semaphores


def account_entry_node(state: FluxState) -> dict:
    """
    Nodo ACCOUNT_INIT: punto de entrada al flujo de Cuenta Corriente.

    RESET: Limpia collecting_data["account_profile"].
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})
    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    msg = (
        f"¡Genial, {first_name}! Vamos a abrir tu **Cuenta Corriente**. "
        f"Para asignarte la mejor categoría, cuéntame: ¿cuál es tu renta líquida mensual?"
    )

    # Actualizamos semáforo para notificar que el Nodo de Inicio del Flujo terminó
    application_id = session.get("application_id")
    
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="ACCOUNT_INIT", # Cambia según el nodo
            node_status="SUCCESS",       # Avisamos que el INIT terminó
            engine_status="PENDING"      # El motor de producto aún no arranca
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "ACCOUNT_INIT"},
        "collecting_data": {
            "account_profile": {},   # Reset del namespace de cuenta
        },
    }


def account_evaluation_engine_node(state: FluxState) -> dict:
    """
    Nodo ACCOUNT_EVALUATION_ENGINE: motor de evaluación para cuenta corriente.

    INPUT (State leído):
        - state["collecting_data"]["account_profile"]: renta, antiguedad_laboral, nivel_estudios
        - state["preparation_data"]["edad"]: edad del usuario

    PROCESO:
        1. Extraer inputs de los namespaces correctos.
        2. Invocar al motor de evaluación comercial (modules/account_eng.py).
        3. Escribir todos los outputs en evaluation_results["account_engine"].

    OUTPUT (campos del State que modifica):
        - evaluation_results["account_engine"]: Resultado completo del motor.
        - session["current_node"]: "ACCOUNT_EVALUATION_ENGINE".

    NOTA DE ARQUITECTURA: 
    Este nodo es un wrapper de flujo. La complejidad del cálculo está delegada
    a módulos externos para asegurar testabilidad y desacoplamiento.
    """
    session = state.get("session", {})
    prep = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})

    # ── Lectura de inputs desde los namespaces correctos ──────────
    account_profile = collecting.get("account_profile", {})
    renta = account_profile.get("renta", 0)
    antiguedad_laboral = account_profile.get("antiguedad_laboral", 0)
    nivel_estudios = account_profile.get("nivel_estudios", "")
    edad = prep.get("edad", 0)

    # ── Lógica del motor (Orquestación) ──────────────────────────
    # TODO: En Fase 3, delegar este cálculo a:
    # engine_result = account_eng.calculate_account_category(renta, antiguedad, nivel, edad)

    # Por ahora, stub de cumplimiento arquitectónico:
    engine_result = {
        "status_proceso": "PRE_APPROVED", # Stub
        "is_elegible": True,
        "base_category": "ADVANCE",
        "final_category": "ADVANCE",
        "has_upgrade": False,
        "credit_line_amount": 500000,
        "monthly_cost": 0,
        "motivo_rechazo": None,
    }

    # ── Sincronía ──────────────────────────────
    # Notificamos que el procesamiento del motor ha terminado con éxito
    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="ACCOUNT_EVALUATION_ENGINE",
            node_status="SUCCESS",  # El nodo finalizó su ejecución
            engine_status="COMPLETED"  # El motor terminó su proceso
        )

    return {
        "evaluation_results": {
            "account_engine": engine_result,
        },
        "session": {**session, "current_node": "ACCOUNT_EVALUATION_ENGINE"},
    }
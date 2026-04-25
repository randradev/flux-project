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
            node_status="IN_PROGRESS",       # Avisamos que el INIT terminó
            engine_status="PENDING"      # El motor de producto aún no arranca
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "ACCOUNT_INIT"},
        "collecting_data": {
            "account_profile": {},   # Reset del namespace de cuenta
        },
    }
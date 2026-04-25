from langchain_core.messages import AIMessage
from app.graph.state import FluxState
from app.infra.supabase import update_application_semaphores

def deposit_entry_node(state: FluxState) -> dict:
    """
    Nodo DAP_INIT: punto de entrada al flujo de Depósito a Plazo.

    RESET: Limpia collecting_data["dap_params"].
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})
    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    msg = (
        f"Excelente elección, {first_name}! Un **Depósito a Plazo** es una forma segura "
        f"de hacer crecer tu dinero. Para calcular tu proyección, necesito saber: "
        f"¿cuánto deseas invertir y en qué moneda? (CLP, UF o USD)"
    )

    # Actualizamos semáforo para notificar que el Nodo de Inicio del Flujo terminó
    application_id = session.get("application_id")
    
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="DAP_INIT", # Cambia según el nodo
            node_status="SUCCESS",       # Avisamos que el INIT terminó
            engine_status="PENDING"      # El motor de producto aún no arranca
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "DAP_INIT"},
        "collecting_data": {
            "dap_params": {},   # Reset del namespace de DAP
        },
    }
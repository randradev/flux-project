"""
app/graph/nodes/credit.py
─────────────────────────────────────────────────────────────
Nodos del flujo de Crédito de Consumo.
FASE 1: Solo contiene el nodo de entrada (stub).
FASE 2: Se implementarán todos los nodos del flujo completo.
"""
from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def loan_entry_node(state: FluxState) -> dict:
    """
    INPUT: state["session"]["product_intent"] == "LOAN"
    PROCESO: [STUB FASE 1] Confirma la intención y avisa que el flujo completo viene en Fase 2.
    OUTPUT: messages (confirmación), session["current_node"] = "LOAN_ENTRY_STUB"
    """
    user_data = state.get("user_data", {})
    first_name = user_data.get("full_name", "").split()[0] or "amig@"
    msg = (
        f"¡Perfecto, {first_name}! Entendido, quieres solicitar un **Crédito de Consumo**. "
        f"El flujo completo estará disponible muy pronto. ¡Gracias por tu paciencia!"
    )
    session = state.get("session", {})
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "LOAN_ENTRY_STUB"},
    }
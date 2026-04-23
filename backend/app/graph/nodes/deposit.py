"""
app/graph/nodes/deposit.py
FASE 1: Stub. FASE 3: Implementación completa.
"""
from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def deposit_entry_node(state: FluxState) -> dict:
    """
    INPUT: state["session"]["product_intent"] == "DAP"
    PROCESO: [STUB FASE 1]
    OUTPUT: messages (confirmación stub)
    """
    session = state.get("session", {})
    msg = "Entendido, quieres contratar un **Depósito a Plazo**. El flujo completo estará disponible en Fase 3."
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "DAP_ENTRY_STUB"},
    }
"""
app/graph/nodes/account.py
FASE 1: Stub. FASE 3: Implementación completa.
"""
from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def account_entry_node(state: FluxState) -> dict:
    """
    INPUT: state["session"]["product_intent"] == "ACCOUNT"
    PROCESO: [STUB FASE 1]
    OUTPUT: messages (confirmación stub)
    """
    session = state.get("session", {})
    msg = "Entendido, quieres abrir una **Cuenta Corriente**. El flujo completo estará disponible en Fase 3."
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "ACCOUNT_ENTRY_STUB"},
    }
"""
app/graph/edges.py
─────────────────────────────────────────────────────────────
Lógica de ruteo condicional entre nodos del Grafo FLUX.

PROCESO: Define las funciones que LangGraph usa como Conditional Edges
         para decidir, basándose en el State, qué nodo ejecutar a continuación.

SALIDA:  Funciones que retornan el nombre del próximo nodo como string.
"""

from app.graph.state import FluxState


def route_after_welcome(state: FluxState) -> str:
    """
    Función de ruteo ejecutada después de WELCOME_NODE.

    INPUT (State): state["session"]["product_intent"]
    PROCESO: Si ya se detectó una intención (sesión reanudada), redirigir
             directamente al nodo de entrada del producto. Si no, ir al router.
    OUTPUT: Nombre del nodo destino como string.
    """
    session = state.get("session", {})
    product_intent = session.get("product_intent")

    # Si ya había intención detectada (sesión reanudada), reanudar el flujo
    if product_intent == "LOAN":
        return "loan_entry"   # Placeholder: en Fase 2 será LOAN_INIT
    elif product_intent == "ACCOUNT":
        return "account_entry"  # Placeholder: en Fase 3 será ACCOUNT_INIT
    elif product_intent == "DAP":
        return "dap_entry"    # Placeholder: en Fase 3 será DAP_INIT

    # Sin intención previa → ir al clasificador
    return "intent_router"


def route_after_intent(state: FluxState) -> str:
    """
    Función de ruteo ejecutada después de INTENT_ROUTER_NODE.

    INPUT (State): state["session"]["product_intent"]
    PROCESO: Dirige al nodo de entrada del producto correspondiente.
             En Fase 1, los nodos de producto son stubs que solo confirman
             la intención detectada.
    OUTPUT: Nombre del nodo destino como string.
    """
    session = state.get("session", {})
    product_intent = session.get("product_intent", "GENERAL")

    if product_intent == "LOAN":
        return "loan_entry"
    elif product_intent == "ACCOUNT":
        return "account_entry"
    elif product_intent == "DAP":
        return "dap_entry"
    else:
        return "general_response"
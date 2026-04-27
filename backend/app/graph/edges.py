"""
app/graph/edges.py
─────────────────────────────────────────────────────────────
Lógica de ruteo condicional entre nodos del Grafo FLUX.

PROCESO: Define las funciones que LangGraph usa como Conditional Edges
         para decidir, basándose en el State, qué nodo ejecutar a continuación.

SALIDA:  Funciones que retornan el nombre del próximo nodo como string.

NOTA DE NOMENCLATURA:
  Los strings que retornan estas funciones son IDs de nodo LangGraph (snake_case).
  Deben coincidir exactamente con los nombres registrados en workflow.py.
  Ver la tabla de nomenclatura en workflow.py para el mapeo completo.
"""

from app.graph.state import FluxState


def route_after_welcome(state: FluxState) -> str:
    """
    Función de ruteo ejecutada después de WELCOME_NODE (ID: welcome).

    INPUT (State): state["session"]["product_intent"]
    PROCESO: Si ya se detectó una intención (sesión reanudada), redirigir
             directamente al nodo de entrada del producto. Si no, ir al router.
    OUTPUT: ID de nodo LangGraph (snake_case) como string.
    """
    session = state.get("session", {})
    product_intent = session.get("product_intent")

    # Si ya había intención detectada (sesión reanudada), reanudar el flujo
    if product_intent == "LOAN":
        return "loan_entry"
    elif product_intent == "ACCOUNT":
        return "account_entry"
    elif product_intent == "DAP":
        return "dap_entry"

    # Sin intención previa → ir al clasificador
    return "intent_router"


def route_after_intent(state: FluxState) -> str:
    """
    Función de ruteo ejecutada después de INTENT_ROUTER_NODE.

    INPUT (State): state["session"]["product_intent"]
    PROCESO: Dirige al nodo de entrada del producto correspondiente.
    OUTPUT: ID de nodo LangGraph (snake_case) como string.
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
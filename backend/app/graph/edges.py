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

VERSIÓN: 2.1 — Jerarquía de ruteo con prioridad de reanudación.

JERARQUÍA DE DECISIÓN (orden estricto):
  P1. current_node activo  → bypass total, ir al nodo guardado.
  P2. product_intent botón → ir al INIT del producto.
  P3. ninguna señal         → intent_router (clasificación LLM).
"""

from app.graph.state import FluxState

# Mapa de reanudación: current_node (UPPER) → ID LangGraph (snake_case)
_RESUME_MAP = {
    # Crédito de Consumo
    "LOAN_INIT":                   "loan_init",
    "LOAN_COLLECTING_PROFILE":     "loan_collecting_profile",
    "LOAN_COLLECTING_SIMULATION":  "loan_collecting_simulation",
    # Cuenta Corriente
    "ACCOUNT_INIT":                "account_init",
    "ACCOUNT_COLLECTING_PROFILE":  "account_collecting_profile",
    # Depósito a Plazo
    "DAP_INIT":                    "dap_init",
    "DAP_COLLECT_DATA":            "dap_collect_data",
}

# Mapa de intención inicial: product_intent → ID LangGraph
_INTENT_MAP = {
    "LOAN":    "loan_init",
    "ACCOUNT": "account_init",
    "DAP":     "dap_init",
}

def route_after_welcome(state: FluxState) -> str:
    """
    Cerebro del ruteo post-WELCOME_NODE.

    INPUT (State):
        - state["session"]["current_node"]: GPS del turno anterior.
        - state["session"]["product_intent"]: Intención del clic/chat.

    OUTPUT: ID de nodo LangGraph (snake_case).
    """
    session = state.get("session", {})
    current_node = session.get("current_node", "")
    product_intent = session.get("product_intent")

    # ── PRIORIDAD 1: Reanudación (current_node activo en proceso) ──
    # Si el turno anterior terminó dentro de un flujo de producto,
    # ir directamente al nodo registrado. Bypass total.
    if current_node in _RESUME_MAP:
        return _RESUME_MAP[current_node]

    # ── PRIORIDAD 2: Clic de botón (intención declarada, sin historial) ──
    if product_intent in _INTENT_MAP:
        return _INTENT_MAP[product_intent]

    # ── PRIORIDAD 3: Chat libre → clasificar intención con LLM ──
    return "intent_router"


def route_after_intent(state: FluxState) -> str:
    """
    Ruteo post-INTENT_ROUTER_NODE. Sin cambios lógicos vs v1.0.
    Centralizado aquí para usar _INTENT_MAP.
    """
    session = state.get("session", {})
    product_intent = session.get("product_intent", "GENERAL")

    return _INTENT_MAP.get(product_intent, "general_response")
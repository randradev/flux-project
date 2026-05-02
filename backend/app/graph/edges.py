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
import logging
from app.graph.constants import CompletedStep
from langgraph.graph import END

# ===================================================================
# ========================== MAPAS DE RUTEO =========================
# ===================================================================

# Mapa de reanudación: current_node (UPPER) → ID LangGraph (snake_case)
# VERSIÓN 2.0: Nodos de oferta, formalización y excepciones de crédito agregados.
_RESUME_MAP = {
    # Crédito de Consumo — Recolección
    "LOAN_INIT":                   "loan_init",
    "LOAN_COLLECTING_PROFILE":     "loan_collecting_profile",
    "LOAN_COLLECTING_SIMULATION":  "loan_collecting_simulation",
    # Crédito de Consumo — Evaluación y Oferta (NUEVOS)
    "LOAN_PRE_APPROVED":           "loan_pre_approved",
    "LOAN_OTP_VALIDATION":         "loan_otp_validation",
    # NOTA: LOAN_RISK_ENGINE y LOAN_FORMALIZATION son nodos de servicio automáticos.
    # No tienen reanudación por turno: si el proceso se interrumpe en ellos,
    # la reanudación ocurre vía _SUCCESS_MAP desde el paso previo.

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

# Nodos válidos como destino del _SUCCESS_MAP.
# VERSIÓN 2.0: Nodos de crédito completo agregados.
_VALID_DESTINATION_NODES: frozenset[str] = frozenset({
    # Crédito
    "loan_collecting_profile",
    "loan_collecting_simulation",
    "loan_risk_engine",
    "loan_pre_approved",
    "loan_otp_validation",
    "loan_formalization",
    "loan_completed",
    "loan_rejected_policy",
    "loan_security_block",
    "loan_closed_by_user",
    # Cuenta Corriente
    "account_collecting_profile",
    "account_evaluation_engine",
    # DAP
    "dap_collect_data",
    "dap_investment_engine",
    # Transversales
    "intent_router",
    "general_response",
})

# Mapa de éxito: producto → {CompletedStep → ID LangGraph destino}
# VERSIÓN 2.0: Flujo completo de crédito definido.
_SUCCESS_MAP: dict[str, dict[str, str]] = {
    "LOAN": {
        # Recolección
        CompletedStep.LOAN_PROFILE:    "loan_collecting_simulation",
        CompletedStep.LOAN_SIMULATION: "loan_risk_engine",
        # Evaluación → Oferta
        CompletedStep.LOAN_RISK_SUCCESS:  "loan_pre_approved",
        CompletedStep.LOAN_RISK_REJECTED: "loan_rejected_policy",
        # Oferta → OTP
        CompletedStep.LOAN_PRE_APPROVED:  "loan_otp_validation",
        CompletedStep.LOAN_CLOSED_BY_USER: "loan_closed_by_user",
        # OTP → Formalización
        CompletedStep.LOAN_OTP_SUCCESS:   "loan_formalization",
        CompletedStep.LOAN_SECURITY_BLOCK: "loan_security_block",
    },
    "ACCOUNT": {
        CompletedStep.ACCOUNT_PROFILE: "account_evaluation_engine",
    },
    "DAP": {
        CompletedStep.DAP_DATA: "dap_investment_engine",
    },
}

# ===================================================================
# ========================= HELPERS DE RUTEO ========================
# ===================================================================

_routing_logger = logging.getLogger("flux.routing")

def _infer_product_from_node(current_node: str) -> str | None:
    """Infiere el producto desde el current_node para detectar cambio de intención."""
    from app.graph.constants import ProductPrefix
    return ProductPrefix.from_node(current_node)


def _get_completed_steps_for_product(progress: dict, product: str) -> list[str]:
    """
    Retorna lista de pasos completados para un producto, en orden cronológico.
    Usado por P1 para verificar si hay un salto de éxito pendiente.
    """
    product_progress = progress.get(product.lower(), {})
    completed = []
    if product == "LOAN":
        if product_progress.get("profile_completed"):
            completed.append(CompletedStep.LOAN_PROFILE)
        if product_progress.get("simulation_completed"):
            completed.append(CompletedStep.LOAN_SIMULATION)
    elif product == "ACCOUNT":
        if product_progress.get("profile_completed"):
            completed.append(CompletedStep.ACCOUNT_PROFILE)
    elif product == "DAP":
        if product_progress.get("data_completed"):
            completed.append(CompletedStep.DAP_DATA)
    return completed

# ==================================================================================
# ========================= FUNCIONES DE DECISIÓN DE ARISTA ========================
# ==================================================================================

def route_after_welcome(state: FluxState) -> str:
    """
    VERSIÓN 2.2 — Jerarquía de 4 prioridades.

    P0 — Cambio de producto: el usuario (o frontend) señaló un producto
         distinto al que está en proceso → ir al INIT del nuevo producto.
    P1 — Salto por éxito: el progreso histórico indica que el paso actual
         ya se completó → consultar _SUCCESS_MAP y saltar al siguiente.
    P2 — Reanudación estándar: current_node activo → ir ahí.
    P3 — Intención directa: product_intent declarado → ir al INIT.
    P4 — Sin señales: intent_router.
    """
    session      = state.get("session", {})
    current_node = session.get("current_node", "")
    product_intent = session.get("product_intent")
    progress     = session.get("progress", {})

    # ── P0: Cambio de producto ────────────────────────────────
    # Si hay un current_node de un producto activo Y product_intent apunta
    # a un producto DIFERENTE, el usuario está cambiando de flujo.
    if current_node in _RESUME_MAP and product_intent in _INTENT_MAP:
        node_product   = _infer_product_from_node(current_node)
        intent_product = product_intent  # LOAN | ACCOUNT | DAP
        if node_product and node_product != intent_product:
            _routing_logger.info(
                f"P0 — Cambio de producto: {node_product} → {intent_product}. "
                f"Redirigiendo a {_INTENT_MAP[intent_product]}."
            )
            return _INTENT_MAP[intent_product]

    # ── P1: Salto por éxito (seguridad inter-turno) ───────────
    # Si current_node indica que estamos en un flujo de producto,
    # verificar si el paso actual ya fue completado en el historial.
    # Esto evita el bucle cuando el intra-turno no completó el salto.
    if current_node in _RESUME_MAP:
        node_product = _infer_product_from_node(current_node)
        if node_product and node_product in _SUCCESS_MAP:
            completed_steps = _get_completed_steps_for_product(progress, node_product)
            product_success_map = _SUCCESS_MAP[node_product]
            for step in reversed(completed_steps):  # El más reciente primero
                if step in product_success_map:
                    next_node = product_success_map[step]
                    # Validación de existencia: el nodo debe estar en _RESUME_MAP o ser conocido
                    if next_node in _VALID_DESTINATION_NODES:
                        _routing_logger.info(
                            f"P1 — Salto por éxito: '{step}' completado. "
                            f"Redirigiendo a '{next_node}'."
                        )
                        return next_node
                    else:
                        _routing_logger.error(
                            f"P1 — CRÍTICO: Nodo destino '{next_node}' no registrado en el grafo. "
                            f"Redirigiendo a 'intent_router' para recuperación."
                        )
                        return "intent_router"

    # ── P2: Reanudación estándar ──────────────────────────────
    if current_node in _RESUME_MAP:
        return _RESUME_MAP[current_node]

    # ── P3: Intención directa (clic de botón) ─────────────────
    if product_intent in _INTENT_MAP:
        return _INTENT_MAP[product_intent]

    # ── P4: Sin señales → clasificar ──────────────────────────
    return "intent_router"


def route_after_intent(state: FluxState) -> str:
    """
    Ruteo post-INTENT_ROUTER_NODE. Sin cambios lógicos vs v1.0.
    Centralizado aquí para usar _INTENT_MAP.
    """
    session = state.get("session", {})
    product_intent = session.get("product_intent", "GENERAL")

    return _INTENT_MAP.get(product_intent, "general_response")

def route_after_loan_collecting_profile(state: FluxState) -> str:
    """
    Decisión de arista post-loan_collecting_profile.

    Si el perfil acaba de completarse (just_completed_step = LOAN_PROFILE),
    salta directamente a loan_collecting_simulation en el mismo turno.
    Si no, va a END para esperar el siguiente mensaje del usuario.

    NOTA: No se usa progress aquí deliberadamente; just_completed_step es
    la señal más fresca y específica del turno actual.
    """
    session = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.LOAN_PROFILE:
        return "loan_collecting_simulation"
    return END

def route_after_loan_collecting_sim(state: FluxState) -> str:
    """
    Decisión de arista post-loan_collecting_simulation.

    Si la simulación se completó (just_completed_step = LOAN_SIMULATION),
    salta al motor de riesgo en el mismo turno.
    Si no, va a END.
    """
    session = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.LOAN_SIMULATION:
        return "loan_risk_engine"
    return END

def route_after_account_collecting_profile(state: FluxState) -> str:
    """Decisión de arista post-account_collecting_profile."""
    session = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.ACCOUNT_PROFILE:
        return "account_evaluation_engine"
    return END
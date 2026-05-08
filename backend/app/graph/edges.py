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
    # Crédito de Consumo — Evaluación y Oferta
    "LOAN_PRE_APPROVED":           "loan_pre_approved",
    "LOAN_OTP_VALIDATION":         "loan_otp_validation",
    # NOTA: LOAN_RISK_ENGINE y LOAN_FORMALIZATION son nodos de servicio automáticos.
    # No tienen reanudación por turno: si el proceso se interrumpe en ellos,
    # la reanudación ocurre vía _SUCCESS_MAP desde el paso previo.

    # Cuenta Corriente
    "ACCOUNT_INIT":                "account_init",
    "ACCOUNT_COLLECTING_PROFILE":  "account_collecting_profile",
    # Cuenta Corriente - Evaluación y Oferta
    "ACCOUNT_PRE_APPROVED":        "account_pre_approved",
    "ACCOUNT_OTP_VALIDATION":      "account_otp_validation",
    # NOTA: ACCOUNT_EVALUATION_ENGINE y ACCOUNT_FORMALIZATION son nodos de servicio automáticos.
    # No tienen reanudación por turno: si el proceso se interrumpe en ellos,
    # la reanudación ocurre vía _SUCCESS_MAP desde el paso previo.
    
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
    "loan_init",
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
    "account_init",
    "account_collecting_profile",
    "account_evaluation_engine",
    "account_pre_approved",
    "account_otp_validation",
    "account_formalization",
    "account_completed",
    "account_rejected_policy",
    "account_security_block",
    "account_closed_by_user",
    # DAP
    "dap_init",
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
        CompletedStep.LOAN_PROFILE:       "loan_collecting_simulation",
        CompletedStep.LOAN_SIMULATION:    "loan_risk_engine",
        CompletedStep.LOAN_RISK_SUCCESS:  "loan_pre_approved",
        CompletedStep.LOAN_PRE_APPROVED:  "loan_otp_validation",
        CompletedStep.LOAN_OTP_SUCCESS:   "loan_formalization",
        CompletedStep.LOAN_FORMALIZATION_SUCCESS: "loan_completed",
        
        CompletedStep.LOAN_RISK_REJECTED: "loan_rejected_policy",
        CompletedStep.LOAN_CLOSED_BY_USER: "loan_closed_by_user",
        CompletedStep.LOAN_SECURITY_BLOCK: "loan_security_block",
    },
    "ACCOUNT": {
        CompletedStep.ACCOUNT_PROFILE:               "account_evaluation_engine",
        CompletedStep.ACCOUNT_EVALUATION_SUCCESS:    "account_pre_approved",
        CompletedStep.ACCOUNT_PRE_APPROVED:          "account_otp_validation",
        CompletedStep.ACCOUNT_OTP_SUCCESS:           "account_formalization",
        CompletedStep.ACCOUNT_FORMALIZATION_SUCCESS: "account_completed",

        CompletedStep.ACCOUNT_EVALUATION_REJECTED:   "account_rejected_policy",
        CompletedStep.ACCOUNT_CLOSED_BY_USER:        "account_closed_by_user",
        CompletedStep.ACCOUNT_SECURITY_BLOCK:        "account_security_block",
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


def _get_completed_steps_for_product(state: dict, product: str) -> list[str]:
    """
    Retorna lista de pasos completados para un producto, en orden cronológico.
    Usado por P1 para verificar si hay un salto de éxito pendiente.
    """
    progress = state.get("session", {}).get("progress", {})
    product_progress = progress.get(product.lower(), {})
    completed = []
    
    # CRÉDITO DE CONSUMO
    if product == "LOAN":
        # A. Recolección
        if product_progress.get("profile_completed"):
            completed.append(CompletedStep.LOAN_PROFILE)
        if product_progress.get("simulation_completed"):
            completed.append(CompletedStep.LOAN_SIMULATION)
            
        # B. Evaluación
        if product_progress.get("risk_engine_completed"):
            # Discriminamos éxito vs rechazo
            engine_status = state.get("evaluation_results", {}).get("loan_engine", {}).get("status_proceso")
            if engine_status == "PRE_APPROVED":
                completed.append(CompletedStep.LOAN_RISK_SUCCESS)
            else:
                completed.append(CompletedStep.LOAN_RISK_REJECTED)
        # C. Oferta y OTP
        if product_progress.get("pre_approval_accepted"):
            completed.append(CompletedStep.LOAN_PRE_APPROVED)
        elif product_progress.get("closed_by_user"):
            completed.append(CompletedStep.LOAN_CLOSED_BY_USER)
            
        if product_progress.get("otp_validated"):
            completed.append(CompletedStep.LOAN_OTP_SUCCESS)
        elif state.get("auth_control", {}).get("security_blocked"):
            completed.append(CompletedStep.LOAN_SECURITY_BLOCK)
        
        # D. Formalización (Final del flujo)
        if product_progress.get("contract_signed"):
            completed.append(CompletedStep.LOAN_FORMALIZATION_SUCCESS)
    
    # CUENTA CORRIENTE
    elif product == "ACCOUNT":
        # A. Recolección
        if product_progress.get("profile_completed"):
            completed.append(CompletedStep.ACCOUNT_PROFILE)

        # B. Evaluación
        if product_progress.get("evaluation_engine_completed"):
            engine_status = state.get("evaluation_results", {}).get("account_engine", {}).get("status_proceso")
            if engine_status == "PRE_APPROVED":
                completed.append(CompletedStep.ACCOUNT_EVALUATION_SUCCESS)
            else:
                completed.append(CompletedStep.ACCOUNT_EVALUATION_REJECTED)

        # C. Oferta y OTP
        if product_progress.get("pre_approval_accepted"):
            completed.append(CompletedStep.ACCOUNT_PRE_APPROVED)
        elif product_progress.get("closed_by_user"):
            completed.append(CompletedStep.ACCOUNT_CLOSED_BY_USER)

        if product_progress.get("otp_validated"):
            completed.append(CompletedStep.ACCOUNT_OTP_SUCCESS)
        elif state.get("auth_control", {}).get("security_blocked"):
            completed.append(CompletedStep.ACCOUNT_SECURITY_BLOCK)

        # D. Formalización (Final del flujo)
        if product_progress.get("contract_signed"):
            completed.append(CompletedStep.ACCOUNT_FORMALIZATION_SUCCESS)
    
    elif product == "DAP":
        if product_progress.get("data_completed"):
            completed.append(CompletedStep.DAP_DATA)
    return completed

# ==================================================================================
# ========================= FUNCIONES DE DECISIÓN DE ARISTA ========================
# ==================================================================================

# ──────────────────────────────────────────────────────────────────────────────────────
# DECISIONES DE ARISTAS NODOS GENERALES
# ──────────────────────────────────────────────────────────────────────────────────────

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
            completed_steps = _get_completed_steps_for_product(state, node_product)
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

# ──────────────────────────────────────────────────────────────────────────────────────
# DECISIONES DE ARISTAS NODOS DE CRÉDITO DE CONSUMO
# ──────────────────────────────────────────────────────────────────────────────────────

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

def route_after_loan_risk_engine(state: FluxState) -> str:
    """
    Decisión de arista post-loan_risk_engine.

    El motor de riesgo es un nodo de servicio automático: siempre completa
    su trabajo en el mismo turno y emite exactamente uno de dos CompletedStep:
      - LOAN_RISK_SUCCESS  → loan_pre_approved
      - LOAN_RISK_REJECTED → loan_rejected_policy

    NOTA: Este edge NO tiene rama END porque loan_risk_engine nunca
    espera input del usuario. Si just_completed_step es None o inesperado,
    se redirige a loan_rejected_policy como fallback seguro (evita loop).
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.LOAN_RISK_SUCCESS:
        return "loan_pre_approved"
    if just_completed == CompletedStep.LOAN_RISK_REJECTED:
        return "loan_rejected_policy"

    # Fallback defensivo: si el motor no emitió señal, redirigir a rechazo
    _routing_logger.warning(
        f"route_after_loan_risk_engine: just_completed_step='{just_completed}' "
        "inesperado. Redirigiendo a 'loan_rejected_policy' como fallback."
    )
    return "loan_rejected_policy"


def route_after_loan_pre_approved(state: FluxState) -> str:
    """
    Decisión de arista post-loan_pre_approved.

    Este nodo espera la decisión del usuario (ACCEPTED / REJECTED).
    La señal viaja en just_completed_step:
      - LOAN_PRE_APPROVED  → loan_otp_validation  (usuario aceptó)
      - LOAN_CLOSED_BY_USER → loan_closed_by_user  (usuario rechazó)
      - None               → END                   (primer turno: espera respuesta)

    REGLA: Si el nodo acaba de generar la tarjeta de transparencia y aún
    no hay respuesta del usuario, just_completed_step será None → END.
    En el siguiente turno, el nodo vuelve a ejecutarse, lee la respuesta
    y emite el CompletedStep correspondiente.
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.LOAN_PRE_APPROVED:
        return "loan_otp_validation"
    if just_completed == CompletedStep.LOAN_CLOSED_BY_USER:
        return "loan_closed_by_user"

    return END  # Esperar respuesta del usuario


def route_after_loan_otp_validation(state: FluxState) -> str:
    """
    Decisión de arista post-loan_otp_validation.

    El nodo OTP espera que el usuario ingrese el código.
    La señal viaja en just_completed_step:
      - LOAN_OTP_SUCCESS   → loan_formalization    (código correcto)
      - LOAN_SECURITY_BLOCK → loan_security_block  (3 intentos fallidos)
      - None               → END                   (código incorrecto, reintento)

    DISEÑO DE RETENCIÓN: Cuando el código es incorrecto pero hay intentos
    disponibles, el nodo actualiza el contador en auth_control y retorna
    sin setear just_completed_step → este edge retorna END → el grafo espera
    otro turno → el nodo OTP vuelve a ejecutarse en el siguiente mensaje.
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.LOAN_OTP_SUCCESS:
        return "loan_formalization"
    if just_completed == CompletedStep.LOAN_SECURITY_BLOCK:
        return "loan_security_block"

    return END  # Código incorrecto: esperar reintento del usuario

def route_after_loan_formalization(state: FluxState) -> str:
    """
    Ruteador post-formalización.
    Solo permite el avance al éxito si el contrato se selló y subió correctamente.
    """
    session = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.LOAN_FORMALIZATION_SUCCESS:
        return "loan_completed"

    return END # Si falló (None), el flujo se detiene por seguridad.

# ──────────────────────────────────────────────────────────────────────────────────────
# DECISIONES DE ARISTAS NODOS DE CUENTA CORRIENTE
# ──────────────────────────────────────────────────────────────────────────────────────

def route_after_account_collecting_profile(state: FluxState) -> str:
    """Decisión de arista post-account_collecting_profile."""
    session = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.ACCOUNT_PROFILE:
        return "account_evaluation_engine"
    return END

def route_after_account_evaluation_engine(state: FluxState) -> str:
    """
    Decisión de arista post-account_evaluation_engine.

    El motor de evaluación es un nodo de servicio automático: siempre completa
    su trabajo en el mismo turno y emite exactamente uno de dos CompletedStep:
      - ACCOUNT_EVALUATION_SUCCESS  → account_pre_approved
      - ACCOUNT_EVALUATION_REJECTED → account_rejected_policy

    NOTA: Este edge NO tiene rama END porque account_evaluation_engine nunca
    espera input del usuario. Si just_completed_step es None o inesperado,
    se redirige a account_rejected_policy como fallback seguro (evita loop).
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.ACCOUNT_EVALUATION_SUCCESS:
        return "account_pre_approved"
    if just_completed == CompletedStep.ACCOUNT_EVALUATION_REJECTED:
        return "account_rejected_policy"

    # Fallback defensivo: si el motor no emitió señal, redirigir a rechazo
    _routing_logger.warning(
        f"route_after_account_evaluation_engine: just_completed_step='{just_completed}' "
        "inesperado. Redirigiendo a 'account_rejected_policy' como fallback."
    )
    return "account_rejected_policy"


def route_after_account_pre_approved(state: FluxState) -> str:
    """
    Decisión de arista post-account_pre_approved.

    Este nodo espera la decisión del usuario (ACCEPTED / REJECTED).
    La señal viaja en just_completed_step:
      - ACCOUNT_PRE_APPROVED    → account_otp_validation  (usuario aceptó)
      - ACCOUNT_CLOSED_BY_USER  → account_closed_by_user  (usuario rechazó)
      - None                    → END                      (primer turno: espera respuesta)

    REGLA: Si el nodo acaba de generar la tarjeta de transparencia y aún
    no hay respuesta del usuario, just_completed_step será None → END.
    En el siguiente turno, el nodo vuelve a ejecutarse, lee la respuesta
    y emite el CompletedStep correspondiente.
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.ACCOUNT_PRE_APPROVED:
        return "account_otp_validation"
    if just_completed == CompletedStep.ACCOUNT_CLOSED_BY_USER:
        return "account_closed_by_user"

    return END  # Esperar respuesta del usuario


def route_after_account_otp_validation(state: FluxState) -> str:
    """
    Decisión de arista post-account_otp_validation.

    El nodo OTP espera que el usuario ingrese el código.
    La señal viaja en just_completed_step:
      - ACCOUNT_OTP_SUCCESS    → account_formalization    (código correcto)
      - ACCOUNT_SECURITY_BLOCK → account_security_block   (3 intentos fallidos)
      - None                   → END                      (código incorrecto, reintento)

    DISEÑO DE RETENCIÓN: Cuando el código es incorrecto pero hay intentos
    disponibles, el nodo actualiza el contador en auth_control y retorna
    sin setear just_completed_step → este edge retorna END → el grafo espera
    otro turno → el nodo OTP vuelve a ejecutarse en el siguiente mensaje.
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.ACCOUNT_OTP_SUCCESS:
        return "account_formalization"
    if just_completed == CompletedStep.ACCOUNT_SECURITY_BLOCK:
        return "account_security_block"

    return END  # Código incorrecto: esperar reintento del usuario


def route_after_account_formalization(state: FluxState) -> str:
    """
    Decisión de arista post-account_formalization.
    Solo permite el avance al éxito si el contrato se selló y subió correctamente.
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.ACCOUNT_FORMALIZATION_SUCCESS:
        return "account_completed"

    return END  # Si falló (None), el flujo se detiene por seguridad.
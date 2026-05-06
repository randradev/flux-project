## IV. Fase 3 — `_SUCCESS_MAP` y Nueva Jerarquía de Prioridades en `edges.py`

**Archivo:** `app/graph/edges.py`

### 4.1 Definición del `_SUCCESS_MAP`

```python
# Mapa de éxito: producto → {CompletedStep → ID LangGraph destino}
# Propósito: dado un paso completado en el historial, indica el siguiente nodo lógico.
# Es la capa de seguridad inter-turno que evita el bucle infinito.
_SUCCESS_MAP: dict[str, dict[str, str]] = {
    "LOAN": {
        CompletedStep.LOAN_PROFILE:    "loan_collecting_simulation",
        CompletedStep.LOAN_SIMULATION: "loan_risk_engine",
    },
    "ACCOUNT": {
        CompletedStep.ACCOUNT_PROFILE: "account_evaluation_engine",
    },
    "DAP": {
        CompletedStep.DAP_DATA: "dap_investment_engine",
    },
}
```

### 4.2 Helpers de ruteo

```python
import logging

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
```

### 4.3 Función `route_after_welcome` refactorizada

```python
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
                            f"P1 — Nodo destino '{next_node}' no existe en el grafo. "
                            f"Fallback a END."
                        )
                        return "end_fallback"  # Nodo de error genérico

    # ── P2: Reanudación estándar ──────────────────────────────
    if current_node in _RESUME_MAP:
        return _RESUME_MAP[current_node]

    # ── P3: Intención directa (clic de botón) ─────────────────
    if product_intent in _INTENT_MAP:
        return _INTENT_MAP[product_intent]

    # ── P4: Sin señales → clasificar ──────────────────────────
    return "intent_router"
```

### 4.4 Set de nodos destino válidos

```python
# Nodos válidos como destino del _SUCCESS_MAP.
# Debe actualizarse al registrar nuevos nodos en workflow.py.
_VALID_DESTINATION_NODES: frozenset[str] = frozenset({
    "loan_collecting_profile",
    "loan_collecting_simulation",
    "loan_risk_engine",
    "account_collecting_profile",
    "account_evaluation_engine",
    "dap_collect_data",
    "dap_investment_engine",
    "intent_router",
    "general_response",
})
```

### 4.5 Nota sobre `P1` vs Fase 4

Con la Fase 4 correctamente implementada (aristas condicionales intra-turno), el `P1` de `edges.py` debería **raramente activarse** en condiciones normales. Su rol es de **cortafuegos inter-turno**: si por alguna razón (error de red, timeout, estado corrupto) el salto intra-turno no se completó y el `current_node` quedó desincronizado con el `progress`, P1 lo corrige en el siguiente turno.

---

### ✅ Tests Fase 3

#### TEST 3.A — Prioridades en `route_after_welcome`

```python
# tests/unit/test_edges_v22.py
from app.graph.edges import route_after_welcome
from app.graph.constants import CompletedStep


def _state(current_node="", product_intent=None, progress=None):
    return {
        "session": {
            "current_node": current_node,
            "product_intent": product_intent,
            "progress": progress or {},
        }
    }


# P0: Cambio de producto
def test_p0_product_switch_loan_to_account():
    """Usuario estaba en crédito y ahora quiere cuenta corriente."""
    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="ACCOUNT"
    )
    assert route_after_welcome(state) == "account_init"


def test_p0_same_product_does_not_trigger():
    """Mismo producto: no es cambio, P0 no activa."""
    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="LOAN",
        progress={}
    )
    # Debe ir a P2 (reanudación) porque product matches
    assert route_after_welcome(state) == "loan_collecting_profile"


# P1: Salto por éxito (seguridad inter-turno)
def test_p1_success_jump_profile_completed():
    """Perfil completado: P1 salta a simulación aunque current_node sea profile."""
    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="LOAN",
        progress={"loan": {"profile_completed": True}},
    )
    assert route_after_welcome(state) == "loan_collecting_simulation"


def test_p1_success_jump_simulation_completed():
    state = _state(
        current_node="LOAN_COLLECTING_SIMULATION",
        product_intent="LOAN",
        progress={"loan": {"profile_completed": True, "simulation_completed": True}},
    )
    assert route_after_welcome(state) == "loan_risk_engine"


def test_p1_not_triggered_when_progress_empty():
    """Sin progreso registrado, P1 no activa; se va a P2."""
    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="LOAN",
        progress={}
    )
    assert route_after_welcome(state) == "loan_collecting_profile"


# P2: Reanudación estándar (sin progreso que dispare P1)
def test_p2_resume_without_progress():
    state = _state(current_node="LOAN_COLLECTING_SIMULATION")
    assert route_after_welcome(state) == "loan_collecting_simulation"


# P3 y P4: sin cambios respecto a tests anteriores
def test_p3_product_intent_no_current_node():
    state = _state(current_node="WELCOME_NODE", product_intent="DAP")
    assert route_after_welcome(state) == "dap_init"


def test_p4_no_signals_intent_router():
    state = _state()
    assert route_after_welcome(state) == "intent_router"
```

#### TEST 3.B — Fallback ante nodo destino inválido en `_SUCCESS_MAP`

```python
from unittest.mock import patch
from app.graph import edges as edges_module


def test_p1_fallback_if_destination_not_valid():
    """Si el nodo destino del _SUCCESS_MAP no está en _VALID_DESTINATION_NODES,
    el router no debe fallar; debe ir al fallback de error."""
    original_valid = edges_module._VALID_DESTINATION_NODES
    edges_module._VALID_DESTINATION_NODES = frozenset()  # Vaciar para simular nodo faltante

    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="LOAN",
        progress={"loan": {"profile_completed": True}},
    )
    result = route_after_welcome(state)
    assert result == "end_fallback"

    edges_module._VALID_DESTINATION_NODES = original_valid  # Restaurar
```

---
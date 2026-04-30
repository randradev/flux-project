## II. Paso 1 — Blindar `edges.py` (Prioridad Máxima)

> **Racional de orden:** Este paso va primero porque es el que desbloquea todo. Si el ruteo es incorrecto, ningún cambio en los nodos tendrá efecto observable en pruebas multi-turno.

### 1.1 Reescribir `route_after_welcome`

**Archivo:** `app/graph/edges.py`

**Lógica de la jerarquía de 3 prioridades:**

```python
"""
app/graph/edges.py
─────────────────────────────────────────────────────────────
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
```

**Puntos clave del diseño:**
- `_RESUME_MAP` es la fuente de verdad del ruteo. Agregar un nodo nuevo al flujo sólo requiere añadir una línea aquí.
- `WELCOME_NODE` y `GENERAL_RESPONSE` están **excluidos** del mapa de reanudación intencionalmente: no son nodos de proceso, son estados transitorios.
- `INTENT_ROUTER` también está excluido: si el grafo se reanuda y el `current_node` es `INTENT_ROUTER`, significa que el turno anterior terminó en clasificación sin llegar a un producto — el comportamiento correcto es repetir la clasificación.

### 1.2 Actualizar `workflow.py` — Ampliar el mapa de `conditional_edges`

El mapa de destinos que LangGraph valida en `add_conditional_edges` debe incluir todos los nodos del `_RESUME_MAP`. Esto es un requisito del framework.

```python
# En build_graph(), reemplazar el bloque de conditional_edges existente:

graph.add_conditional_edges(
    "welcome",
    route_after_welcome,
    {
        # Prioridad 3 — clasificación
        "intent_router":               "intent_router",
        # Prioridad 2 — intención directa
        "loan_init":                   "loan_init",
        "account_init":                "account_init",
        "dap_init":                    "dap_init",
        # Prioridad 1 — reanudación profunda (nodos de proceso)
        "loan_collecting_profile":     "loan_collecting_profile",
        "loan_collecting_simulation":  "loan_collecting_simulation",
        "account_collecting_profile":  "account_collecting_profile",
        "dap_collect_data":            "dap_collect_data",
    }
)
```

> **Nota:** Los nodos de reanudación deben estar registrados en el grafo. Ver Sección VII, Hallazgo Crítico #1.

---

### ✅ Tests del Paso 1

#### TEST 1.A — Unitario: Jerarquía de prioridades de `route_after_welcome`

```python
# tests/unit/test_edges.py
import pytest
from app.graph.edges import route_after_welcome


def _make_state(current_node=None, product_intent=None):
    return {
        "session": {
            "current_node": current_node or "",
            "product_intent": product_intent,
        }
    }

# Prioridad 1: current_node activo siempre gana
def test_p1_resume_loan_collecting_profile():
    state = _make_state(current_node="LOAN_COLLECTING_PROFILE", product_intent="LOAN")
    assert route_after_welcome(state) == "loan_collecting_profile"

def test_p1_resume_loan_collecting_simulation():
    state = _make_state(current_node="LOAN_COLLECTING_SIMULATION")
    assert route_after_welcome(state) == "loan_collecting_simulation"

def test_p1_resume_overrides_product_intent():
    """P1 debe ganarle a P2: aunque haya product_intent, si current_node indica
    reanudación profunda, ir ahí."""
    state = _make_state(current_node="LOAN_COLLECTING_PROFILE", product_intent="DAP")
    assert route_after_welcome(state) == "loan_collecting_profile"

# Prioridad 2: sin current_node activo, product_intent manda
def test_p2_product_intent_loan():
    state = _make_state(current_node="WELCOME_NODE", product_intent="LOAN")
    assert route_after_welcome(state) == "loan_init"

def test_p2_product_intent_account():
    state = _make_state(current_node="WELCOME_NODE", product_intent="ACCOUNT")
    assert route_after_welcome(state) == "account_init"

def test_p2_product_intent_dap():
    state = _make_state(current_node="WELCOME_NODE", product_intent="DAP")
    assert route_after_welcome(state) == "dap_init"

# Prioridad 3: sin señales, ir al clasificador
def test_p3_no_signals_go_to_intent_router():
    state = _make_state()
    assert route_after_welcome(state) == "intent_router"

def test_p3_general_intent_goes_to_intent_router():
    state = _make_state(current_node="WELCOME_NODE", product_intent="GENERAL")
    assert route_after_welcome(state) == "intent_router"

# Edge case: WELCOME_NODE y GENERAL_RESPONSE NO deben causar reanudación
def test_welcome_node_is_not_resumable():
    state = _make_state(current_node="WELCOME_NODE")
    assert route_after_welcome(state) == "intent_router"

def test_general_response_is_not_resumable():
    state = _make_state(current_node="GENERAL_RESPONSE")
    assert route_after_welcome(state) == "intent_router"
```

#### TEST 1.B — Unitario: `route_after_intent`

```python
def test_route_after_intent_loan():
    from app.graph.edges import route_after_intent
    state = {"session": {"product_intent": "LOAN"}}
    assert route_after_intent(state) == "loan_init"

def test_route_after_intent_fallback_to_general():
    from app.graph.edges import route_after_intent
    state = {"session": {"product_intent": "GENERAL"}}
    assert route_after_intent(state) == "general_response"

def test_route_after_intent_unknown_falls_back():
    from app.graph.edges import route_after_intent
    state = {"session": {"product_intent": "UNKNOWN_FUTURE"}}
    assert route_after_intent(state) == "general_response"
```

#### TEST 1.C — Estructural: Cobertura del mapa en `workflow.py`

```python
# tests/unit/test_workflow_structure.py
from app.graph.workflow import build_graph
from app.graph.edges import _RESUME_MAP

def test_all_resume_targets_registered_in_graph():
    """Todos los destinos del _RESUME_MAP deben estar registrados en el grafo."""
    graph = build_graph()
    registered_nodes = set(graph.nodes.keys())
    for current_node_val, langgraph_id in _RESUME_MAP.items():
        assert langgraph_id in registered_nodes, (
            f"El nodo '{langgraph_id}' (reanudación de '{current_node_val}') "
            f"no está registrado en workflow.py"
        )
```

---
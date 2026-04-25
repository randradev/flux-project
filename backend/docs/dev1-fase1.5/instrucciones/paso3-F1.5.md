## PASO 3 — Patrón de Reset en Nodos INIT {#paso-3}

### 3.1 Contexto y Decisión de Diseño

Cuando un usuario abandona a mitad de un flujo de crédito y luego inicia un flujo de cuenta corriente, `collecting_data.loan_profile` puede tener datos residuales. Los nodos INIT deben limpiar **solo su propio sub-cajón** al arrancar.

**Patrón de reset:** Retornar el sub-cajón como un `TypedDict` vacío (`{}`). LangGraph hará merge: el sub-cajón queda limpio, los otros sub-cajones (de otros productos) se preservan.

### 3.2 Implementación de `loan_entry_node` (Stub + Reset)

```python
# app/graph/nodes/credit.py

from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def loan_entry_node(state: FluxState) -> dict:
    """
    Nodo LOAN_INIT: punto de entrada al flujo de Crédito de Consumo.

    INPUT (State):
        - state["preparation_data"]: Datos del usuario (nombre, rut, mail, edad).
        - state["session"]: Para verificar product_intent == "LOAN".
        - state["collecting_data"]["loan_profile"]: Se limpiará (reset).
        - state["collecting_data"]["loan_sim"]: Se limpiará (reset).

    PROCESO (Fase 2):
        1. Handshake: Verificar que product_intent == "LOAN".
        2. Reset: Limpiar loan_profile y loan_sim.
        3. Saludo personalizado con datos de preparation_data.

    OUTPUT (campos del State que modifica):
        - messages: Saludo de bienvenida al flujo de crédito.
        - session["current_node"]: "LOAN_INIT".
        - collecting_data["loan_profile"]: {} (limpio).
        - collecting_data["loan_sim"]: {} (limpio).

    NOTA FASE 1: Este nodo es un stub. Solo hace el reset y confirma la intención.
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})

    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    # Handshake: verificar intención (defensa en profundidad)
    product_intent = session.get("product_intent")
    if product_intent != "LOAN":
        # Esto no debería ocurrir si edges.py está bien configurado
        # pero es una salvaguarda explícita
        msg = "Hubo un error de navegación. Por favor, indica nuevamente qué necesitas."
    else:
        msg = (
            f"¡Perfecto, {first_name}! Vamos a revisar tu solicitud de **Crédito de Consumo**. "
            f"Es un proceso rápido. Primero necesito conocer un poco tu perfil financiero. "
            f"¿Cuál es tu renta líquida mensual?"
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "LOAN_INIT"},
        # ── RESET del namespace del producto ─────────────────────
        # Limpia datos de intentos anteriores sin tocar los otros productos.
        "collecting_data": {
            "loan_profile": {},
            "loan_sim": {},
        },
    }
```

### 3.3 Implementación de `account_entry_node` (Stub + Reset)

```python
# app/graph/nodes/account.py

from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def account_entry_node(state: FluxState) -> dict:
    """
    Nodo ACCOUNT_INIT: punto de entrada al flujo de Cuenta Corriente.

    RESET: Limpia collecting_data["account_profile"].
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})
    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    msg = (
        f"¡Genial, {first_name}! Vamos a abrir tu **Cuenta Corriente**. "
        f"Para asignarte la mejor categoría, cuéntame: ¿cuál es tu renta líquida mensual?"
    )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "ACCOUNT_INIT"},
        "collecting_data": {
            "account_profile": {},   # Reset del namespace de cuenta
        },
    }
```

### 3.4 Implementación de `deposit_entry_node` (Stub + Reset)

```python
# app/graph/nodes/deposit.py

from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def deposit_entry_node(state: FluxState) -> dict:
    """
    Nodo DAP_INIT: punto de entrada al flujo de Depósito a Plazo.

    RESET: Limpia collecting_data["dap_params"].
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})
    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    msg = (
        f"Excelente elección, {first_name}! Un **Depósito a Plazo** es una forma segura "
        f"de hacer crecer tu dinero. Para calcular tu proyección, necesito saber: "
        f"¿cuánto deseas invertir y en qué moneda? (CLP, UF o USD)"
    )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "DAP_INIT"},
        "collecting_data": {
            "dap_params": {},   # Reset del namespace de DAP
        },
    }
```

### 3.5 Sub-paso: Verificación Post-Implementación

**Checklist de verificación manual:**
- [ ] Simular un escenario de "flujo cruzado": ejecutar `loan_entry_node` con `collecting_data.loan_profile` pre-poblado → verificar que el resultado tiene `loan_profile: {}`.
- [ ] Verificar que el reset de `loan_entry_node` NO borra `account_profile` ni `dap_params` (otros productos deben ser intocables).
- [ ] Verificar que `preparation_data` se puede leer correctamente en cada nodo INIT (datos disponibles antes de la primera interacción del usuario).

### 3.6 Pruebas del Paso 3

```python
# tests/test_init_nodes_v2.py
import pytest


def make_polluted_state():
    """State con datos residuales de múltiples productos (simula sesiones anteriores)."""
    return {
        "preparation_data": {
            "nombre": "Carlos López",
            "rut": "98765432-1",
            "mail": "carlos@example.com",
            "edad": 32,
        },
        "session": {
            "conversation_id": "test-002",
            "product_intent": "LOAN",
        },
        "collecting_data": {
            "loan_profile": {"renta": 999999, "antiguedad_laboral": 99},
            "loan_sim": {"monto_solicitado": 10000000, "plazo_solicitado": 24},
            "account_profile": {"renta": 888888},  # Datos de otro producto
            "dap_params": {"monto": 5000000.0},      # Datos de otro producto
        },
        "messages": [],
    }


def test_loan_init_resets_only_loan_namespace():
    """loan_entry_node resetea solo loan_profile y loan_sim, no los demás."""
    from app.graph.nodes.credit import loan_entry_node
    state = make_polluted_state()
    result = loan_entry_node(state)

    cd = result.get("collecting_data", {})
    # Loan reseteado
    assert cd.get("loan_profile") == {}
    assert cd.get("loan_sim") == {}
    # Otros productos NO en el resultado (no fueron tocados)
    assert "account_profile" not in cd
    assert "dap_params" not in cd


def test_account_init_resets_only_account_namespace():
    """account_entry_node resetea solo account_profile."""
    from app.graph.nodes.account import account_entry_node
    state = make_polluted_state()
    state["session"]["product_intent"] = "ACCOUNT"
    result = account_entry_node(state)

    cd = result.get("collecting_data", {})
    assert cd.get("account_profile") == {}
    assert "loan_profile" not in cd
    assert "dap_params" not in cd


def test_init_node_uses_preparation_data():
    """Los nodos INIT usan preparation_data (no user_data) para el nombre."""
    from app.graph.nodes.credit import loan_entry_node
    state = make_polluted_state()
    result = loan_entry_node(state)
    welcome_msg = result["messages"][0].content
    assert "Carlos" in welcome_msg


def test_init_node_updates_current_node():
    """El nodo INIT actualiza session["current_node"]."""
    from app.graph.nodes.credit import loan_entry_node
    state = make_polluted_state()
    result = loan_entry_node(state)
    assert result["session"]["current_node"] == "LOAN_INIT"
```

**Documentación del Paso 3:**
> Se estandarizó el patrón de reset en los 3 nodos INIT: cada uno limpia exclusivamente su sub-cajón en `collecting_data`. Este patrón garantiza que datos residuales de un flujo anterior no contaminan el nuevo flujo. Los nodos INIT también fueron refactorizados para leer `preparation_data` en lugar de `user_data`, desacoplándolos del acceso directo a la DB.

---
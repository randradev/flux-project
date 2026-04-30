## III. Paso 2 — `welcome_node` como Hidratador Silencioso

**Archivo:** `app/graph/nodes/common.py`

### 2.1 Lógica de silencio

Se introducen dos modos de operación para `welcome_node`:

- **Modo Hidratación (silencioso):** carga `preparation_data` y actualiza el GPS, pero NO emite `AIMessage`. Se activa cuando `product_intent is not None` O `len(messages) > 0`.
- **Modo Bienvenida (con mensaje):** comportamiento actual para sesiones verdaderamente nuevas (sin intención, sin historial).

```python
def welcome_node(state: FluxState) -> dict:
    """
    VERSIÓN 2.1 — Nodo de Hidratación Silenciosa.

    MODOS DE OPERACIÓN:
      A) Silencioso: cuando product_intent ya existe O hay mensajes previos.
         → Solo hidrata preparation_data y actualiza GPS. Sin AIMessage.
      B) Bienvenida: cuando es sesión completamente nueva (sin intención ni historial).
         → Emite mensaje de bienvenida con los productos disponibles.

    REGLA DE ORO: Este nodo NUNCA sobreescribe current_node si ya hay
    un proceso activo (ver _RESUME_MAP en edges.py). Su current_node
    propio ("WELCOME_NODE") sólo se escribe en Modo Bienvenida.
    """
    user = state.get("user_data", {})
    session = state.get("session", {})
    messages = state.get("messages", [])

    # ── Datos universales (siempre se calculan) ───────────────
    full_name = user.get("full_name", "")
    first_name = full_name.split()[0] if full_name else "amig@"

    birth_date_str = user.get("birth_date")
    edad = _calculate_age(birth_date_str) if birth_date_str else 0

    preparation_data = {
        "nombre": full_name,
        "rut": user.get("rut", ""),
        "mail": user.get("email", ""),
        "edad": edad,
    }

    # ── Detección de modo ─────────────────────────────────────
    product_intent = session.get("product_intent")
    has_history = len(messages) > 0
    is_silent_mode = (product_intent is not None) or has_history

    # ── Actualizar GPS en Supabase (siempre) ─────────────────
    conversation_id = session.get("conversation_id")
    application_id = session.get("application_id")

    if is_silent_mode:
        # MODO SILENCIOSO: hidrata datos, no toca current_node del proceso activo
        if conversation_id:
            # No sobreescribir: informar a Supabase que welcome pasó pero no es el nodo activo
            pass  # El nodo activo real se actualizará en su propio nodo
        if application_id:
            update_application_semaphores(
                application_id,
                current_node_id="WELCOME_NODE",
                node_status="BYPASSED",
                engine_status="PENDING"
            )
        # Retornar sin messages: sólo preparation_data se escribe
        return {
            "preparation_data": preparation_data,
            # session NO se modifica: current_node del proceso activo se preserva
        }

    else:
        # MODO BIENVENIDA: sesión nueva, sin intención, sin historial
        welcome_text = (
            f"¡Hola, {first_name}! 👋 Soy Flux, tu asistente financiero. "
            f"Estoy aquí para ayudarte a solicitar un **Crédito de Consumo**, "
            f"abrir una **Cuenta Corriente**, o contratar un **Depósito a Plazo**. "
            f"¿Con qué te puedo ayudar hoy?"
        )
        if conversation_id:
            update_conversation_node(conversation_id, "WELCOME_NODE")
        if application_id:
            update_application_semaphores(
                application_id,
                current_node_id="WELCOME_NODE",
                node_status="SUCCESS",
                engine_status="PENDING"
            )
        return {
            "messages": [AIMessage(content=welcome_text)],
            "session": {**session, "current_node": "WELCOME_NODE"},
            "preparation_data": preparation_data,
        }
```

**Decisiones de diseño documentadas:**

1. **`session` no se toca en modo silencioso.** Si el `current_node` era `LOAN_COLLECTING_PROFILE` antes del renacimiento del grafo, así debe quedar para que `route_after_welcome` lo lea en P1.
2. **`preparation_data` siempre se escribe.** Es necesario para cualquier nodo que venga después (incluyendo `loan_init` en su nueva versión con LLM).
3. **`update_application_semaphores` con estado `"BYPASSED"** (valor nuevo de negocio). El informe no lo especifica, pero es útil para auditoría. Si el enum de Supabase no lo permite, usar `"SUCCESS"`.

---

### ✅ Tests del Paso 2

#### TEST 2.A — Unitario: comportamiento silencioso

```python
# tests/unit/test_welcome_node.py
from unittest.mock import patch, MagicMock
from app.graph.nodes.common import welcome_node


def _base_state(product_intent=None, messages=None, current_node="WELCOME_NODE"):
    return {
        "user_data": {
            "full_name": "Juan Pérez",
            "rut": "12345678-9",
            "email": "juan@test.com",
            "birth_date": "1990-01-01",
        },
        "session": {
            "conversation_id": None,
            "application_id": None,
            "product_intent": product_intent,
            "current_node": current_node,
        },
        "messages": messages or [],
    }


@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_silent_when_product_intent_set(mock_conv, mock_sem):
    state = _base_state(product_intent="LOAN")
    result = welcome_node(state)
    assert "messages" not in result, "No debe emitir mensaje si hay product_intent"
    assert result["preparation_data"]["nombre"] == "Juan Pérez"

@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_silent_when_has_history(mock_conv, mock_sem):
    from langchain_core.messages import HumanMessage
    state = _base_state(messages=[HumanMessage(content="Hola")])
    result = welcome_node(state)
    assert "messages" not in result

@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_welcome_message_on_fresh_session(mock_conv, mock_sem):
    state = _base_state()
    result = welcome_node(state)
    assert "messages" in result
    assert len(result["messages"]) == 1
    assert "Flux" in result["messages"][0].content

@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_silent_mode_does_not_overwrite_current_node(mock_conv, mock_sem):
    """Modo silencioso NO debe modificar session, preservando current_node activo."""
    state = _base_state(
        product_intent="LOAN",
        current_node="LOAN_COLLECTING_PROFILE"
    )
    result = welcome_node(state)
    assert "session" not in result, (
        "En modo silencioso, session no debe modificarse para preservar current_node"
    )

@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_preparation_data_always_populated(mock_conv, mock_sem):
    """preparation_data se escribe en ambos modos."""
    for intent in [None, "LOAN"]:
        state = _base_state(product_intent=intent)
        result = welcome_node(state)
        assert "preparation_data" in result
        assert result["preparation_data"]["edad"] > 0
```

#### TEST 2.B — Integración: `welcome_node` → `route_after_welcome` encadenados

```python
def test_welcome_silent_plus_route_resumes_correctly():
    """
    Verifica que cuando welcome es silencioso y current_node es LOAN_COLLECTING_PROFILE,
    el router lo detecta y devuelve el destino correcto.
    """
    from unittest.mock import patch
    from app.graph.edges import route_after_welcome

    # Simular estado post-welcome (silencioso no modificó session)
    state_after_welcome = {
        "session": {
            "current_node": "LOAN_COLLECTING_PROFILE",
            "product_intent": "LOAN",
        },
        "preparation_data": {"nombre": "Juan Pérez", "rut": "", "mail": "", "edad": 33},
    }
    destination = route_after_welcome(state_after_welcome)
    assert destination == "loan_collecting_profile"
```

---
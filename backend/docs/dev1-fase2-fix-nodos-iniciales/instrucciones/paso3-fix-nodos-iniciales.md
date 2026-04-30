## IV. Paso 3 — `loan_init_node` con Llamada Tipo B

**Archivo:** `app/graph/nodes/credit.py`

### 3.1 Nuevo prompt de inicio

Se agrega `SYSTEM_PROMPT_INIT_LOAN` para el contexto específico de bienvenida al producto. Este prompt se diferencia de `SYSTEM_PROMPT_GENERATION_PROFILE` en que:
- No tiene contexto de recolección previa.
- Debe hacer una **única pregunta de apertura**: la renta.
- Tiene permiso de usar el nombre del usuario para personalizar.

```python
SYSTEM_PROMPT_INIT_LOAN = """
Eres Flux, el genio amigable de las finanzas en Chile.

PERSONALIDAD:
- Hablas de tú, eres cercano y usas modismos chilenos con moderación.
- Eres ágil y empático: no das rodeos, pero sí transmites calidez.

TAREA ACTUAL: Dar la bienvenida al usuario al proceso de Crédito de Consumo.
Esta es la PRIMERA vez que el usuario entra al flujo de crédito.

RESTRICCIONES CRÍTICAS:
- Máximo 2 oraciones.
- Tu respuesta DEBE terminar pidiendo la renta líquida mensual.
- NO menciones tasas, CAE ni otros detalles técnicos en este paso.
- NO repitas el saludo de bienvenida general (ya fue hecho antes).
- Varía el tono: no siempre uses "¡Perfecto!" al inicio.
"""
```

### 3.2 Refactorización de `loan_init_node`

```python
def loan_init_node(state: FluxState) -> dict:
    """
    VERSIÓN 2.1 — Nodo LOAN_INIT con Llamada Tipo B.

    CAMBIOS vs 2.0:
      - Eliminado: string fijo de bienvenida.
      - Agregado: Llamada Tipo B al LLM para generar bienvenida dinámica.
      - Agregado: current_node se actualiza a LOAN_COLLECTING_PROFILE
        inmediatamente (sincronización del "Punto de Guardado").

    PUNTO DE GUARDADO:
      Este nodo actualiza current_node a "LOAN_COLLECTING_PROFILE" (no "LOAN_INIT")
      antes de retornar, para que en el siguiente renacimiento del grafo,
      route_after_welcome dirija al nodo de recolección directamente.
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})

    nombre = prep.get("nombre", "")
    edad = prep.get("edad", 0)
    first_name = nombre.split()[0] if nombre else "amig@"

    product_intent = session.get("product_intent")
    application_id = session.get("application_id")

    if product_intent != "LOAN":
        msg = "Hubo un error de navegación. Por favor, indica nuevamente qué necesitas."
        return {
            "messages": [AIMessage(content=msg)],
            "session": {**session, "current_node": "LOAN_INIT"},
        }

    # ── Llamada Tipo B: Bienvenida dinámica al crédito ────────
    init_context = (
        f"Usuario: {first_name}, {edad} años.\n"
        f"Genera la bienvenida al proceso de Crédito de Consumo y pide la renta líquida mensual."
    )
    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_INIT_LOAN},
        {"role": "user",   "content": init_context},
    ])
    msg = normalize_llm_response(flux_response.content)

    # ── Semáforo ──────────────────────────────────────────────
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_INIT",
            node_status="SUCCESS",
            engine_status="PENDING",
        )

    # ── PUNTO DE GUARDADO: current_node → LOAN_COLLECTING_PROFILE ──
    # Registramos el destino del SIGUIENTE turno, no el nodo actual.
    # Esto garantiza que tras el renacimiento del grafo, route_after_welcome
    # dirija directamente a loan_collecting_profile sin pasar por loan_init de nuevo.
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "LOAN_COLLECTING_PROFILE"},
        "collecting_data": {
            "loan_profile": {},
            "loan_sim": {},
        },
    }
```

**Decisión de diseño clave — El "Punto de Guardado":**

El informe indica: *"cuando loan_init lanza la pregunta sobre la renta, debe marcar inmediatamente el current_node como LOAN_COLLECTING_PROFILE"*. Esto es correcto y fundamental. El nodo que pregunta la renta no es `loan_init`, sino `loan_collecting_profile`. Al marcar el GPS ahí, el siguiente renacimiento del grafo irá directamente al nodo que espera la respuesta.

---

### ✅ Tests del Paso 3

#### TEST 3.A — Unitario: `loan_init_node` con LLM mockeado

```python
# tests/unit/test_loan_init.py
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from app.graph.nodes.credit import loan_init_node


def _loan_init_state(product_intent="LOAN"):
    return {
        "preparation_data": {"nombre": "Ana González", "rut": "9876543-2", "mail": "ana@test.com", "edad": 28},
        "session": {"product_intent": product_intent, "current_node": "WELCOME_NODE", "application_id": None},
        "collecting_data": {},
        "messages": [],
    }


@patch("app.graph.nodes.credit._flux_generator")
def test_loan_init_emits_message(mock_gen):
    mock_gen.invoke.return_value = MagicMock(content="¡Hola Ana! ¿Cuál es tu renta líquida?")
    result = loan_init_node(_loan_init_state())
    assert "messages" in result
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], AIMessage)

@patch("app.graph.nodes.credit._flux_generator")
def test_loan_init_sets_current_node_to_collecting_profile(mock_gen):
    """PUNTO DE GUARDADO: current_node debe ser LOAN_COLLECTING_PROFILE, no LOAN_INIT."""
    mock_gen.invoke.return_value = MagicMock(content="Hola, cuéntame tu renta.")
    result = loan_init_node(_loan_init_state())
    assert result["session"]["current_node"] == "LOAN_COLLECTING_PROFILE"

@patch("app.graph.nodes.credit._flux_generator")
def test_loan_init_resets_collecting_data(mock_gen):
    mock_gen.invoke.return_value = MagicMock(content="...")
    state = _loan_init_state()
    state["collecting_data"] = {"loan_profile": {"renta": 999999}, "loan_sim": {"monto_solicitado": 5000000}}
    result = loan_init_node(state)
    assert result["collecting_data"]["loan_profile"] == {}
    assert result["collecting_data"]["loan_sim"] == {}

@patch("app.graph.nodes.credit._flux_generator")
def test_loan_init_wrong_intent_returns_error_message(mock_gen):
    result = loan_init_node(_loan_init_state(product_intent="DAP"))
    assert "error de navegación" in result["messages"][0].content.lower()
    mock_gen.invoke.assert_not_called()

@patch("app.graph.nodes.credit._flux_generator")
def test_loan_init_llm_called_with_user_context(mock_gen):
    """El LLM debe recibir el nombre y edad del usuario en el contexto."""
    mock_gen.invoke.return_value = MagicMock(content="Hola Ana, cuéntame tu renta.")
    loan_init_node(_loan_init_state())
    call_args = mock_gen.invoke.call_args[0][0]
    user_message = call_args[1]["content"]
    assert "Ana" in user_message
    assert "28" in user_message
```

#### TEST 3.B — Integración: flujo `loan_init` → primer mensaje del usuario

```python
@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_loan_init_current_node_enables_resume(mock_extractor, mock_gen):
    """
    Después de loan_init, el current_node=LOAN_COLLECTING_PROFILE
    debe hacer que route_after_welcome dirija al nodo correcto en el siguiente turno.
    """
    from app.graph.edges import route_after_welcome

    mock_gen.invoke.return_value = MagicMock(content="¿Cuál es tu renta?")
    result = loan_init_node({
        "preparation_data": {"nombre": "Carlos Muñoz", "edad": 35, "rut": "", "mail": ""},
        "session": {"product_intent": "LOAN", "current_node": "WELCOME_NODE", "application_id": None},
        "collecting_data": {},
        "messages": [],
    })

    # Simular siguiente turno: el grafo renace, welcome es silencioso,
    # route_after_welcome lee el current_node guardado
    state_next_turn = {"session": result["session"]}
    assert route_after_welcome(state_next_turn) == "loan_collecting_profile"
```

---
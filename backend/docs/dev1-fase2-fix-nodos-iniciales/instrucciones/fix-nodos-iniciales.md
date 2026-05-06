# Plan de Implementación: Resolución del "Bucle de Amnesia" y Estabilización de la Fase 2

**Proyecto:** FLUX — Asistente Financiero  
**Versión objetivo:** 2.1  
**Archivos afectados:** `edges.py`, `common.py`, `credit.py`, `workflow.py` + nuevo `common_schemas.py`  
**Archivos inmutables:** `state.py`, `loan_schemas.py`

---

## I. Análisis y Evaluación de la Propuesta

### 1.1 Hallazgos del Análisis de Código

Antes de describir los cambios, se documentan los resultados del análisis de los archivos fuente, incluyendo desviaciones respecto al informe original.

#### Requerimiento 1 — Welcome Silencioso ✅ Aprobado (con precisión)

El `welcome_node` actual siempre emite un `AIMessage`, sobreescribiendo `current_node` a `"WELCOME_NODE"` en cada invocación. La lógica de `is_resumed` ya existe pero **sólo cambia el texto del saludo, no lo elimina**. El informe está en lo correcto: el nodo debe operar en modo silencioso cuando ya hay intención o historial activo.

**Condición de silencio propuesta (refinada):** el nodo no emitirá mensaje cuando se cumpla **cualquiera** de:
- `session.product_intent` es distinto de `None`, o
- `len(messages) > 0` (hay historial — sesión reanudada).

> **Nota de precisión:** el informe señala "si hay intención o historial", lo cual es correcto. La primera condición cubre el caso de clic de botón en sesión nueva; la segunda cubre la reanudación.

#### Requerimiento 2 — Eliminación del Saludo Hardcodeado en `loan_init_node` ✅ Aprobado

El string fijo confirmado en `credit.py` línea 181:
```
"¡Perfecto, {first_name}! Vamos a revisar tu solicitud de Crédito de Consumo..."
```
El nodo ya tiene `_flux_generator` instanciado y `SYSTEM_PROMPT_GENERATION_PROFILE` definido. Se puede reutilizar el mismo generador, con un prompt de bienvenida distinto (`SYSTEM_PROMPT_INIT_LOAN`) para no contaminar el flujo de recolección.

#### Requerimiento 3 — Blindar `edges.py` con jerarquía `current_node` ✅ Aprobado

La función `route_after_welcome` actual sólo evalúa `product_intent`. La Prioridad 1 (Reanudación basada en `current_node`) está **completamente ausente**. Esto es la causa raíz del bucle.

**Mapa de reanudación requerido** (inferido de `workflow.py` y `state.py`):
| `current_node` | Destino de reanudación |
|---|---|
| `LOAN_INIT` | `loan_init` |
| `LOAN_COLLECTING_PROFILE` | `loan_collecting_profile` |
| `LOAN_COLLECTING_SIMULATION` | `loan_collecting_simulation` |
| `ACCOUNT_INIT` | `account_init` |
| `ACCOUNT_COLLECTING_PROFILE` | `account_collecting_profile` |
| `DAP_INIT` | `dap_init` |
| `DAP_COLLECT_DATA` | `dap_collect_data` |

#### Requerimiento 4 — `common_schemas.py` ✅ Aprobado con modificación metodológica

El informe sugiere usar `LLM.with_structured_output()` para el `intent_router_node`, igual que los nodos de crédito. Sin embargo, el `intent_router_node` actual ya funciona con clasificación de texto plano y validación de categorías, lo cual es robusto para 4 categorías simples. La mejora con Pydantic agrega:
- Documentación del contrato de extracción.
- Validación en tiempo de parseo.
- Campo `confianza` para logging (opcional pero útil).
- Uniformidad metodológica con `loan_schemas.py`.

Se aprueba el cambio; el schema será `IntentExtractionSchema`.

#### Requerimiento 5 — Script Simulador ✅ Aprobado, con arquitectura expandida

El informe describe el simulador conceptualmente. Este plan lo convierte en código concreto.

---

### 1.2 Hallazgos Propios (Críticos — Sección VII)

> ⚠️ Se detectaron 2 brechas críticas no cubiertas en el informe original que deben resolverse en este mismo sprint. Ver **Sección VII**.

---

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

## V. Paso 4 — Crear `common_schemas.py`

**Archivo nuevo:** `app/graph/nodes/schemas/common_schemas.py`

### 4.1 Schema `IntentExtractionSchema`

Este schema sigue el estilo de `loan_schemas.py`: campos `Optional`, validadores `@field_validator`, campo `razonamiento` y `intencion` como `Literal`.

```python
"""
app/graph/nodes/schemas/common_schemas.py
─────────────────────────────────────────────────────────────
Esquemas Pydantic para extracción estructurada en nodos transversales.
Usados con LLM.with_structured_output() en los nodos COMMON.

ESTILO: Mismo contrato que loan_schemas.py.
  - Campos Optional con None como default.
  - Validadores @field_validator normalizan valores centinela.
  - Campo `razonamiento` para trazabilidad del LLM.
  - Campo `confianza` para logging y futuros umbrales de decisión.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal


class IntentExtractionSchema(BaseModel):
    """
    Schema para INTENT_ROUTER_NODE.
    Clasifica la intención del usuario en un producto financiero o consulta general.

    Usado en: app/graph/nodes/common.py → intent_router_node
    """

    razonamiento: str = Field(
        default="",
        description=(
            "Justificación breve de por qué se clasifica en esta categoría, "
            "basada ÚNICAMENTE en el texto del mensaje del usuario."
        )
    )
    intencion: Literal["LOAN", "ACCOUNT", "DAP", "GENERAL"] = Field(
        description=(
            "Categoría de intención detectada:\n"
            "  LOAN    — Crédito, préstamo, financiamiento, plata prestada.\n"
            "  ACCOUNT — Cuenta corriente, cuenta bancaria, abrir cuenta.\n"
            "  DAP     — Depósito a plazo, inversión, ahorrar con intereses.\n"
            "  GENERAL — Saludo, pregunta general, duda, o mensaje fuera de categoría."
        )
    )
    confianza: Optional[Literal["ALTA", "MEDIA", "BAJA"]] = Field(
        default="MEDIA",
        description=(
            "Nivel de certeza de la clasificación:\n"
            "  ALTA  — El mensaje es explícito y no hay ambigüedad.\n"
            "  MEDIA — El mensaje es probable pero podría interpretarse de otra forma.\n"
            "  BAJA  — Poca información; la clasificación es una suposición razonada."
        )
    )

    @field_validator("intencion", mode="before")
    @classmethod
    def normalize_intent(cls, v):
        """Normaliza a GENERAL si el LLM devuelve un valor fuera del Literal."""
        valid = {"LOAN", "ACCOUNT", "DAP", "GENERAL"}
        if isinstance(v, str) and v.upper() in valid:
            return v.upper()
        return "GENERAL"

    @field_validator("confianza", mode="before")
    @classmethod
    def normalize_confianza(cls, v):
        valid = {"ALTA", "MEDIA", "BAJA"}
        if isinstance(v, str) and v.upper() in valid:
            return v.upper()
        return "MEDIA"
```

### 4.2 Refactorizar `intent_router_node` para usar el schema

```python
# En app/graph/nodes/common.py — reemplazar el bloque de importaciones y el nodo

from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema
from app.infra.gemini_client import get_structured_model  # ya debería existir

# Singleton del extractor de intención estructurado
_intent_extractor = get_structured_model(IntentExtractionSchema)

_INTENT_SYSTEM_PROMPT = """
Eres el clasificador de intenciones de FLUX, un sistema bancario conversacional.
Analiza el mensaje del usuario y clasifica su intención en UNA categoría exacta.

CATEGORÍAS:
  LOAN    — Crédito, préstamo, financiamiento, plata prestada.
  ACCOUNT — Cuenta corriente, cuenta bancaria, abrir cuenta.
  DAP     — Depósito a plazo, inversión, ahorrar con intereses, DAP.
  GENERAL — Saludo, pregunta general, duda o mensaje fuera de las categorías anteriores.

REGLA DE ORO: Retorna JSON con los campos razonamiento, intencion y confianza.

EJEMPLOS:
  "Quiero un crédito de 5 millones" → LOAN, ALTA
  "Necesito abrir una cuenta"       → ACCOUNT, ALTA
  "¿Puedo invertir mi sueldo?"      → DAP, MEDIA
  "¿Qué es el CAE?"                 → GENERAL, ALTA
  "hola"                            → GENERAL, ALTA
"""

def intent_router_node(state: FluxState) -> dict:
    """
    VERSIÓN 2.1 — Clasificador con extracción estructurada (Llamada Tipo A).

    CAMBIOS vs 2.0:
      - Usa _intent_extractor (LLM.with_structured_output(IntentExtractionSchema))
        en lugar de text completion con parsing manual.
      - Registra confianza en session para futuros umbrales.
    """
    from langchain_core.messages import HumanMessage

    messages = state.get("messages", [])
    session = state.get("session", {})

    last_user_message = next(
        (m.content for m in reversed(messages) if hasattr(m, "type") and m.type == "human"),
        ""
    )

    if not last_user_message:
        return {
            "session": {
                **session,
                "product_intent": "GENERAL",
                "current_node": "INTENT_ROUTER",
            }
        }

    extracted: IntentExtractionSchema = _intent_extractor.invoke([
        {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
        {"role": "user",   "content": last_user_message},
    ]) or IntentExtractionSchema(intencion="GENERAL", razonamiento="Error en extracción")

    return {
        "session": {
            **session,
            "product_intent": extracted.intencion,
            "current_node":   "INTENT_ROUTER",
            # confianza se puede guardar en session para logging si se agrega a SessionData
        }
    }
```

---

### ✅ Tests del Paso 4

#### TEST 4.A — Unitario: validadores del schema

```python
# tests/unit/test_common_schemas.py
import pytest
from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema


def test_valid_intent_loan():
    schema = IntentExtractionSchema(intencion="LOAN", razonamiento="Es un crédito")
    assert schema.intencion == "LOAN"

def test_valid_intent_general():
    schema = IntentExtractionSchema(intencion="GENERAL", razonamiento="Saludo")
    assert schema.intencion == "GENERAL"

def test_unknown_intent_normalized_to_general():
    schema = IntentExtractionSchema(intencion="UNKNOWN_PRODUCT", razonamiento="")
    assert schema.intencion == "GENERAL"

def test_lowercase_intent_normalized():
    schema = IntentExtractionSchema(intencion="loan", razonamiento="")
    assert schema.intencion == "LOAN"

def test_default_confianza_is_media():
    schema = IntentExtractionSchema(intencion="LOAN", razonamiento="")
    assert schema.confianza == "MEDIA"

def test_invalid_confianza_normalized_to_media():
    schema = IntentExtractionSchema(intencion="LOAN", razonamiento="", confianza="MUY_ALTA")
    assert schema.confianza == "MEDIA"

def test_razonamiento_defaults_to_empty():
    schema = IntentExtractionSchema(intencion="DAP")
    assert schema.razonamiento == ""
```

#### TEST 4.B — Unitario: `intent_router_node` con extractor mockeado

```python
# tests/unit/test_intent_router.py
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage
from app.graph.nodes.common import intent_router_node
from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema


def _make_state(user_msg: str):
    return {
        "messages": [HumanMessage(content=user_msg)],
        "session": {"current_node": "WELCOME_NODE", "product_intent": None},
    }


@patch("app.graph.nodes.common._intent_extractor")
def test_intent_router_sets_loan(mock_extractor):
    mock_extractor.invoke.return_value = IntentExtractionSchema(
        intencion="LOAN", razonamiento="Crédito", confianza="ALTA"
    )
    result = intent_router_node(_make_state("quiero un crédito"))
    assert result["session"]["product_intent"] == "LOAN"

@patch("app.graph.nodes.common._intent_extractor")
def test_intent_router_sets_current_node(mock_extractor):
    mock_extractor.invoke.return_value = IntentExtractionSchema(
        intencion="ACCOUNT", razonamiento="Cuenta"
    )
    result = intent_router_node(_make_state("quiero abrir cuenta"))
    assert result["session"]["current_node"] == "INTENT_ROUTER"

@patch("app.graph.nodes.common._intent_extractor")
def test_intent_router_no_message_defaults_general(mock_extractor):
    state = {"messages": [], "session": {"current_node": "WELCOME_NODE"}}
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "GENERAL"
    mock_extractor.invoke.assert_not_called()

@patch("app.graph.nodes.common._intent_extractor")
def test_intent_router_extractor_error_defaults_general(mock_extractor):
    """Si el extractor devuelve None (error), el nodo debe manejar gracefully."""
    mock_extractor.invoke.return_value = None
    result = intent_router_node(_make_state("algo raro"))
    assert result["session"]["product_intent"] == "GENERAL"
```

---

## VI. Paso 5 — Script Simulador de Orquestación

**Archivo nuevo:** `scripts/simulate_conversation.py`

Este script es autónomo: no depende del backend corriendo, sólo del módulo del grafo y del checkpointer en memoria.

```python
#!/usr/bin/env python3
"""
scripts/simulate_conversation.py
─────────────────────────────────────────────────────────────
Simulador de Orquestación FLUX — Entorno de Pruebas de Conversación.

PROPÓSITO:
  Replicar el ciclo de vida de una conversación real en consola,
  verificando que el State persiste correctamente entre turnos y
  que el ruteo no retrocede.

USO:
  python scripts/simulate_conversation.py [--scenario <nombre>]

ESCENARIOS DISPONIBLES:
  happy_path_loan       — Flujo completo de crédito (renta, antigüedad, estudios, monto, plazo)
  resume_mid_loan       — Simula renacimiento del grafo en medio de la recolección
  button_click_loan     — Simula clic de botón sin mensaje previo
  intent_change         — Usuario en crédito pregunta por cuenta corriente (a futuro)

SALIDA:
  - Cada turno imprime: input del usuario, nodo(s) ejecutados, State diff y mensaje de Flux.
  - Al final imprime: resumen de la conversación y validación de invariantes.
"""

import sys
import copy
import json
import uuid
from typing import Any
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver

# Importar el grafo SIN el checkpointer de producción
from app.graph.workflow import build_graph


# ══════════════════════════════════════════════════════════════
# UTILIDADES DE CONSOLA
# ══════════════════════════════════════════════════════════════

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
GREY   = "\033[90m"


def _print_header(text: str):
    print(f"\n{BOLD}{CYAN}{'═'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'═'*60}{RESET}")


def _print_turn(turn_num: int, user_input: str):
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}TURNO {turn_num}{RESET}")
    print(f"{GREEN}👤 Usuario:{RESET} {user_input}")


def _print_state_diff(before: dict, after: dict, path: str = ""):
    """
    Imprime recursivamente los campos del State que cambiaron entre dos snapshots.
    Ignora el campo 'messages' (tiene su propio pretty-printer).
    """
    for key in set(list(before.keys()) + list(after.keys())):
        if key == "messages":
            continue
        full_path = f"{path}.{key}" if path else key
        val_before = before.get(key)
        val_after  = after.get(key)
        if isinstance(val_before, dict) and isinstance(val_after, dict):
            _print_state_diff(val_before, val_after, full_path)
        elif val_before != val_after:
            if val_before is None and val_after is not None:
                print(f"  {YELLOW}+ {full_path}:{RESET} {GREY}None{RESET} → {GREEN}{val_after}{RESET}")
            elif val_before is not None and val_after is None:
                print(f"  {RED}- {full_path}:{RESET} {val_before} → {GREY}None{RESET}")
            else:
                print(f"  {YELLOW}~ {full_path}:{RESET} {GREY}{val_before}{RESET} → {GREEN}{val_after}{RESET}")


def _print_messages_diff(before_msgs: list, after_msgs: list):
    new_msgs = after_msgs[len(before_msgs):]
    for msg in new_msgs:
        role = "🤖 Flux" if isinstance(msg, AIMessage) else "👤 User"
        print(f"\n{BOLD}{role}:{RESET} {msg.content}")


def _extract_state_snapshot(state_values: dict) -> dict:
    """Extrae un snapshot serializable del State para diff."""
    snap = {}
    for key, val in state_values.items():
        if key == "messages":
            snap[key] = [{"type": type(m).__name__, "content": m.content[:80]} for m in val]
        elif isinstance(val, dict):
            snap[key] = copy.deepcopy(val)
        else:
            snap[key] = val
    return snap


# ══════════════════════════════════════════════════════════════
# MOTOR DE SIMULACIÓN
# ══════════════════════════════════════════════════════════════

class ConversationSimulator:
    """
    Simula turnos de conversación con el grafo FLUX usando MemorySaver.
    """

    def __init__(self, initial_user_data: dict, initial_session: dict):
        # Compilar con checkpointer en memoria (no necesita Supabase)
        self.checkpointer = MemorySaver()
        self.graph = build_graph().compile(checkpointer=self.checkpointer)
        self.thread_id = str(uuid.uuid4())
        self.config = {"configurable": {"thread_id": self.thread_id}}

        # Estado inicial que se inyecta en el primer turno
        self._initial_user_data = initial_user_data
        self._initial_session = initial_session

        self.turn_number = 0
        self.validation_log = []
        self._last_snapshot = {}

    def _get_current_state(self) -> dict:
        """Obtiene el State actual del checkpointer."""
        checkpoint = self.graph.get_state(self.config)
        return checkpoint.values if checkpoint else {}

    def send(self, user_input: str, *, inject_product_intent: str = None) -> dict:
        """
        Envía un mensaje al grafo y retorna el State resultante.

        Args:
            user_input: Texto del usuario (None para el turno inicial sin mensaje).
            inject_product_intent: Simula clic de botón (inyecta product_intent en sesión).
        """
        self.turn_number += 1
        _print_turn(self.turn_number, user_input or "(sin mensaje — turno de inicio)")

        # Construir el input del turno
        if self.turn_number == 1:
            # Primer turno: incluir todo el estado inicial
            session = {**self._initial_session}
            if inject_product_intent:
                session["product_intent"] = inject_product_intent
            turn_input = {
                "messages": [HumanMessage(content=user_input)] if user_input else [],
                "user_data": self._initial_user_data,
                "session": session,
                "collecting_data": {},
                "preparation_data": {},
                "evaluation_results": {},
                "offer_data": {},
                "auth_control": {},
                "flow_result": {},
            }
        else:
            # Turnos siguientes: solo el mensaje nuevo (el State persiste via checkpointer)
            session_patch = {}
            if inject_product_intent:
                session_patch["product_intent"] = inject_product_intent

            turn_input = {"messages": [HumanMessage(content=user_input)]}
            if session_patch:
                current = self._get_current_state()
                turn_input["session"] = {**current.get("session", {}), **session_patch}

        snapshot_before = _extract_state_snapshot(self._get_current_state())

        # Invocar el grafo
        result = self.graph.invoke(turn_input, config=self.config)

        snapshot_after = _extract_state_snapshot(result)

        # ── Imprimir diff del State ────────────────────────────
        print(f"\n{BOLD}📊 State Diff:{RESET}")
        _print_state_diff(snapshot_before, snapshot_after)

        # ── Imprimir mensajes nuevos ───────────────────────────
        msgs_before = [m for m in (self._get_current_state().get("messages", []))]
        _print_messages_diff(
            snapshot_before.get("messages", []),
            snapshot_after.get("messages", [])
        )

        # ── Validar invariantes ────────────────────────────────
        self._validate_invariants(snapshot_before, snapshot_after)

        self._last_snapshot = snapshot_after
        return result

    def _validate_invariants(self, before: dict, after: dict):
        """
        Valida que el State cumple las reglas de negocio tras cada turno.
        Registra violaciones en self.validation_log.
        """
        session_after = after.get("session", {})
        current_node = session_after.get("current_node", "")

        # Invariante 1: current_node nunca debe retroceder en el flujo de crédito
        # (simplificado: no debe volver a WELCOME_NODE si ya estaba en el flujo)
        session_before = before.get("session", {})
        current_node_before = session_before.get("current_node", "")
        loan_flow = ["LOAN_INIT", "LOAN_COLLECTING_PROFILE", "LOAN_COLLECTING_SIMULATION"]
        if current_node_before in loan_flow and current_node == "WELCOME_NODE":
            violation = f"⚠️ VIOLACIÓN T{self.turn_number}: current_node retrocedió de {current_node_before} a WELCOME_NODE"
            self.validation_log.append(violation)
            print(f"\n{RED}{violation}{RESET}")

        # Invariante 2: preparation_data debe estar poblado después del welcome
        if self.turn_number >= 1:
            prep = after.get("preparation_data", {})
            if not prep.get("nombre") and not prep.get("rut"):
                warning = f"⚠️ AVISO T{self.turn_number}: preparation_data vacío después del turno {self.turn_number}"
                self.validation_log.append(warning)
                print(f"\n{YELLOW}{warning}{RESET}")

        # Invariante 3: loan_init no debe emitir el saludo fijo hardcodeado
        messages_after = after.get("messages", [])
        if messages_after:
            last_msg_content = messages_after[-1].get("content", "")
            if "Vamos a revisar tu solicitud de **Crédito de Consumo**" in last_msg_content:
                violation = f"⚠️ VIOLACIÓN T{self.turn_number}: Saludo hardcodeado detectado en el mensaje de Flux"
                self.validation_log.append(violation)
                print(f"\n{RED}{violation}{RESET}")

    def print_summary(self):
        """Imprime un resumen al final de la simulación."""
        _print_header("RESUMEN DE LA SIMULACIÓN")
        print(f"  Turnos completados: {self.turn_number}")
        print(f"  Thread ID: {self.thread_id}")
        if not self.validation_log:
            print(f"\n  {GREEN}✅ Todos los invariantes cumplidos. Sin violaciones.{RESET}")
        else:
            print(f"\n  {RED}❌ Se detectaron {len(self.validation_log)} violaciones:{RESET}")
            for v in self.validation_log:
                print(f"    {v}")


# ══════════════════════════════════════════════════════════════
# DATOS DE PRUEBA
# ══════════════════════════════════════════════════════════════

MOCK_USER = {
    "user_id": "test-user-001",
    "full_name": "Juan Pérez López",
    "email": "juan.perez@test.cl",
    "rut": "12345678-9",
    "birth_date": "1990-05-15",
    "user_status": "ACTIVE",
    "user_category": None,
}

MOCK_SESSION_NEW = {
    "conversation_id": "conv-test-001",
    "application_id": None,
    "product_intent": None,
    "current_node": "",
    "previous_node": None,
    "is_transversal_active": False,
}


# ══════════════════════════════════════════════════════════════
# ESCENARIOS
# ══════════════════════════════════════════════════════════════

def scenario_happy_path_loan():
    """
    Escenario 1: Happy Path del Crédito de Consumo.
    Simula el flujo completo desde el saludo hasta la recolección de datos.
    """
    _print_header("ESCENARIO: Happy Path — Crédito de Consumo")

    sim = ConversationSimulator(MOCK_USER, MOCK_SESSION_NEW)

    # Turno 1: Usuario abre el chat, clic en botón "Crédito"
    sim.send("", inject_product_intent="LOAN")

    # Turno 2: Usuario entrega renta
    sim.send("gano 2 palos líquidos")

    # Turno 3: Usuario entrega antigüedad
    sim.send("llevo 3 años en mi pega actual")

    # Turno 4: Usuario entrega nivel de estudios
    sim.send("soy ingeniero comercial")

    sim.print_summary()


def scenario_resume_mid_loan():
    """
    Escenario 2: Reanudación en medio del flujo.
    Simula que el grafo "renace" (nueva invocación) después de que
    el usuario ya entregó la renta.
    """
    _print_header("ESCENARIO: Reanudación — Grafo renace en LOAN_COLLECTING_PROFILE")

    # Sesión con current_node ya en el flujo de crédito (turno anterior guardado)
    session_resumed = {
        **MOCK_SESSION_NEW,
        "current_node": "LOAN_COLLECTING_PROFILE",
        "product_intent": "LOAN",
    }
    sim = ConversationSimulator(MOCK_USER, session_resumed)

    # Turno 1: El grafo renace. El usuario envía su antigüedad laboral.
    # EXPECTATIVA: welcome es silencioso, route_after_welcome va a loan_collecting_profile.
    sim.send("llevo 5 años trabajando en la misma empresa")

    sim.print_summary()


def scenario_button_click_no_prior_history():
    """
    Escenario 3: Clic de botón en sesión completamente nueva.
    EXPECTATIVA: welcome silencioso (P2), route va a loan_init.
    """
    _print_header("ESCENARIO: Clic de Botón — Sin historial previo")

    sim = ConversationSimulator(MOCK_USER, MOCK_SESSION_NEW)
    sim.send("", inject_product_intent="LOAN")

    # Verificar que se fue a loan_init y current_node quedó en LOAN_COLLECTING_PROFILE
    state = sim._get_current_state()
    cn = state.get("session", {}).get("current_node", "")
    status = "✅ PASS" if cn == "LOAN_COLLECTING_PROFILE" else f"❌ FAIL (fue a {cn})"
    print(f"\n{BOLD}Validación Punto de Guardado:{RESET} {status}")

    sim.print_summary()


# ══════════════════════════════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════════════════════════════

SCENARIOS = {
    "happy_path_loan":            scenario_happy_path_loan,
    "resume_mid_loan":            scenario_resume_mid_loan,
    "button_click_loan":          scenario_button_click_no_prior_history,
}

if __name__ == "__main__":
    scenario_name = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--scenario" else None

    if scenario_name:
        if scenario_name not in SCENARIOS:
            print(f"Escenario desconocido: {scenario_name}")
            print(f"Disponibles: {', '.join(SCENARIOS.keys())}")
            sys.exit(1)
        SCENARIOS[scenario_name]()
    else:
        # Si no se especifica, correr todos
        for name, fn in SCENARIOS.items():
            fn()
            print("\n")
```

**Uso:**
```bash
# Correr todos los escenarios
python scripts/simulate_conversation.py

# Correr uno específico
python scripts/simulate_conversation.py --scenario resume_mid_loan

# Correr con output guardado para CI
python scripts/simulate_conversation.py > logs/simulation_$(date +%Y%m%d).txt
```

---

### ✅ Tests del Paso 5 (Meta-tests del Simulador)

Los tests del simulador son los escenarios mismos, pero se agrega una suite de aserciones programáticas:

```python
# tests/integration/test_simulator_scenarios.py
"""
Suite de validación automática de los escenarios del simulador.
Usa MemorySaver directamente para no depender de Supabase.
"""
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from scripts.simulate_conversation import ConversationSimulator, MOCK_USER, MOCK_SESSION_NEW


def _mock_llm():
    """Mock del LLM para tests rápidos sin API."""
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content="Respuesta mockeada de Flux.")
    return mock


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
@patch("app.graph.nodes.common._intent_extractor")
@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_scenario_resume_preserves_current_node(
    mock_conv, mock_sem, mock_intent_ext, mock_profile_ext, mock_gen
):
    """
    INVARIANTE PRINCIPAL: En una sesión reanudada con current_node=LOAN_COLLECTING_PROFILE,
    el grafo no debe pasar por loan_init ni generar un segundo saludo.
    """
    from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema
    from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction

    mock_gen.invoke.return_value = MagicMock(content="¿Cuánto tiempo llevas en tu trabajo?")
    mock_profile_ext.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        razonamiento="Antigüedad detectada",
        antiguedad_laboral=36,
    )

    session_resumed = {
        **MOCK_SESSION_NEW,
        "current_node": "LOAN_COLLECTING_PROFILE",
        "product_intent": "LOAN",
    }
    sim = ConversationSimulator(MOCK_USER, session_resumed)
    result = sim.send("llevo 3 años trabajando")

    # Verificar que no hubo violaciones
    assert len(sim.validation_log) == 0, f"Violaciones detectadas: {sim.validation_log}"

    # Verificar que el current_node sigue en LOAN_COLLECTING_PROFILE
    final_cn = result.get("session", {}).get("current_node", "")
    assert final_cn == "LOAN_COLLECTING_PROFILE"


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_scenario_button_click_sets_punto_de_guardado(mock_conv, mock_sem, mock_gen):
    """
    Después del primer turno con product_intent=LOAN (clic de botón),
    el current_node debe quedar en LOAN_COLLECTING_PROFILE (Punto de Guardado).
    """
    mock_gen.invoke.return_value = MagicMock(content="Hola Juan! ¿Cuál es tu renta?")

    sim = ConversationSimulator(MOCK_USER, MOCK_SESSION_NEW)
    result = sim.send("", inject_product_intent="LOAN")

    current_node = result.get("session", {}).get("current_node", "")
    assert current_node == "LOAN_COLLECTING_PROFILE", (
        f"Punto de Guardado no establecido. current_node fue: {current_node}"
    )
```

---

## VII. Hallazgos Propios — Brechas Críticas

> Estas brechas no están cubiertas en el informe original y bloquearían la implementación si no se resuelven en paralelo.

### 🔴 Hallazgo 1 (Crítico): `loan_collecting_profile_node` no está registrado en `workflow.py`

**Evidencia:** `credit.py` tiene implementado `loan_collecting_profile_node` (y presumiblemente `loan_collecting_simulation_node`), pero `workflow.py` sólo registra `loan_init` y `loan_risk_engine`, con un edge directo entre ellos:

```python
# workflow.py actual — INCORRECTO
graph.add_edge("loan_init", "loan_risk_engine")  # Salta toda la recolección
```

Esto significa que actualmente **el flujo de crédito nunca recolecta datos**: va de `loan_init` directamente al motor de riesgo, que necesita `collecting_data` para funcionar.

**Acción requerida:** Registrar todos los nodos del flujo de crédito y reconectar las aristas. La topología correcta es:

```
loan_init
    ↓
loan_collecting_profile  ←─ (reanudación desde aquí en turnos siguientes)
    ↓ (cuando profile está completo — avance silencioso)
loan_collecting_simulation
    ↓ (cuando sim está completo — avance silencioso)
loan_risk_engine
    ↓
END
```

**Cambios en `workflow.py`:**

```python
# Importar los nodos que faltan
from app.graph.nodes.credit import (
    loan_init_node,
    loan_collecting_profile_node,     # AGREGAR
    loan_collecting_simulation_node,   # AGREGAR (si existe)
    loan_risk_engine_node,
)

# Registrar nodos que faltan
graph.add_node("loan_collecting_profile",    loan_collecting_profile_node)
graph.add_node("loan_collecting_simulation", loan_collecting_simulation_node)

# Reconectar aristas (reemplazar la línea incorrecta)
# ELIMINAR: graph.add_edge("loan_init", "loan_risk_engine")
# AGREGAR:
graph.add_edge("loan_init",                  "loan_collecting_profile")
graph.add_edge("loan_collecting_profile",    "loan_collecting_simulation")
graph.add_edge("loan_collecting_simulation", "loan_risk_engine")
graph.add_edge("loan_risk_engine",           END)
```

**Nota:** Si `loan_collecting_profile` puede avanzar silenciosamente (sin mensaje del usuario), LangGraph lo manejará dentro del mismo `invoke()`. No se necesita un edge condicional para esto; el nodo simplemente retorna sin `messages` y el grafo continúa.

---

### 🟡 Hallazgo 2 (Importante): `update_application_semaphores` con `"BYPASSED"` puede fallar

**Evidencia:** El `Paso 2` propone usar `node_status="BYPASSED"` en el modo silencioso del `welcome_node`. Si el enum en Supabase no tiene este valor, generará un error.

**Acción:** Usar `"SUCCESS"` para el semáforo de welcome en modo silencioso, o agregar `"BYPASSED"` al enum en la migración de DB correspondiente. Se recomienda la primera opción para no bloquear el sprint.

```python
# Alternativa segura en welcome_node modo silencioso:
if application_id:
    update_application_semaphores(
        application_id,
        current_node_id="WELCOME_NODE",
        node_status="SUCCESS",   # No "BYPASSED" hasta validar el enum
        engine_status="PENDING"
    )
```

---

## VIII. Orden de Implementación Recomendado

| # | Paso | Archivo(s) | Dependencias |
|---|---|---|---|
| 1 | Crear `common_schemas.py` | Nuevo archivo | Ninguna |
| 2 | Blindar `edges.py` | `edges.py` | Paso 1 (mapa de reanudación) |
| 3 | Registrar nodos en `workflow.py` | `workflow.py` | Paso 2 (mapa de edges) |
| 4 | `welcome_node` silencioso | `common.py` | Paso 2 |
| 5 | `intent_router_node` estructurado | `common.py` | Paso 1 |
| 6 | `loan_init_node` Llamada Tipo B | `credit.py` | Pasos 4 y 5 |
| 7 | Script Simulador | `scripts/` | Pasos 2–6 |
| 8 | Tests unitarios por paso | `tests/` | Cada paso |

---

## IX. Checklist de Validación Final

Antes de considerar el sprint completo, ejecutar:

```bash
# 1. Todos los tests unitarios
pytest tests/unit/ -v

# 2. Tests de integración del simulador
pytest tests/integration/test_simulator_scenarios.py -v

# 3. Escenario de Happy Path en consola (validación visual)
python scripts/simulate_conversation.py --scenario happy_path_loan

# 4. Escenario de reanudación (el más crítico)
python scripts/simulate_conversation.py --scenario resume_mid_loan
```

**Criterios de aceptación:**

- [ ] `route_after_welcome` devuelve `loan_collecting_profile` cuando `current_node=LOAN_COLLECTING_PROFILE`.
- [ ] `welcome_node` no emite mensaje cuando `product_intent="LOAN"`.
- [ ] `welcome_node` no emite mensaje cuando `len(messages) > 0`.
- [ ] `loan_init_node` llama al LLM y no usa el string fijo.
- [ ] `loan_init_node` deja `current_node="LOAN_COLLECTING_PROFILE"` al retornar.
- [ ] El simulador no reporta violaciones en el escenario `resume_mid_loan`.
- [ ] `loan_collecting_profile_node` está registrado en `workflow.py`.
- [ ] `IntentExtractionSchema` normaliza intenciones inválidas a `GENERAL`.
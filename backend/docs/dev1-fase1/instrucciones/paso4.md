# PASO 4 — Core del Grafo LangGraph

**Objetivo:** Definir el esquema de estado global del grafo, implementar los nodos fundamentales (`WELCOME_NODE` e `INTENT_ROUTER`), configurar el `workflow.py` y compilar el grafo con el checkpointer de Supabase.

**Al comenzar este paso, el agente debe [CREAR] el archivo `CP-04-dev1-fase1.md`.**

---

## Sub-paso 4.1 — Definir el StateSchema en `app/graph/state.py`

**Acción:** [MODIFICAR] `/backend/app/graph/state.py`:

```python
"""
app/graph/state.py
─────────────────────────────────────────────────────────────
Definición del Estado Global del Grafo (The Single Source of Truth).

REGLA DE ORO #1: Este archivo es la única fuente de verdad del sistema.
Ningún desarrollador puede modificarlo sin aprobación del Dev 1 (Orchestrator).

PROCESO: Define el TypedDict FluxState que LangGraph usa como contenedor
         de información entre nodos. Cada clave tiene un propósito específico
         y su escritura está reservada a los nodos indicados en los comentarios.

SALIDA:  Clase FluxState importada por workflow.py y todos los nodos.
"""

from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages


class UserData(TypedDict, total=False):
    """
    Datos del usuario cargados desde la DB al iniciar el grafo.
    Estos campos son inmutables durante la sesión; solo WELCOME_NODE los escribe.
    """
    user_id: str           # UUID del usuario en la tabla `users`
    full_name: str         # Nombre completo para personalización de mensajes
    email: str             # Correo para envío de OTP
    rut: str               # RUT (sin puntos, con guión)
    birth_date: str        # Fecha de nacimiento ISO8601 (para cálculo de edad)
    user_status: str       # Código de estado: ACTIVE, BLOCKED_SECURITY, PROSPECT
    user_category: str | None  # START, MEDIUM, ADVANCE o None


class SessionData(TypedDict, total=False):
    """
    Datos de la sesión conversacional activa.
    Estos campos los escriben los nodos de orquestación.
    """
    conversation_id: str       # UUID de la conversación = thread_id de LangGraph
    application_id: str | None # UUID de la solicitud en financial_applications
    product_intent: str | None # Intención detectada: LOAN, ACCOUNT, DAP, GENERAL
    current_node: str          # Nombre del nodo activo (para el GPS visual del FE)
    previous_node: str | None  # Nodo previo (para retorno desde transversales)
    is_transversal_active: bool  # True si el flujo está en un nodo transversal


class FluxState(TypedDict):
    """
    Estado global del Grafo FLUX.
    
    Es el TypedDict raíz que LangGraph serializa y persiste en el
    checkpointer de Supabase después de cada transición de nodo.

    CAMPOS:
    - messages: Historial de mensajes LangChain (acumulativo, no reemplazable).
                Usa `add_messages` como reducer para que cada nodo agregue
                mensajes sin sobreescribir el historial anterior.
    - user_data: Perfil del usuario cargado desde la DB.
    - session:   Metadatos de la sesión activa (IDs, intención, nodo GPS).
    - collected_data: Datos recolectados por los nodos de extracción.
                      Es un dict flexible para acomodar los distintos productos.
    - control_flags: Flags de control del flujo del grafo.
    """

    # ── Mensajes (reducer acumulativo) ───────────────────────
    messages: Annotated[list, add_messages]

    # ── Datos del Usuario (escritura única: WELCOME_NODE) ────
    user_data: UserData

    # ── Sesión Activa ─────────────────────────────────────────
    session: SessionData

    # ── Datos Recolectados (escritura: nodos de extracción) ──
    # Estructura flexible: cada producto agrega sus llaves sin conflicto.
    # Ejemplo LOAN: {"renta": 1500000, "antiguedad": 12, "nivel_estudios": "UNIVERSITARIO"}
    # Ejemplo DAP:  {"monto_inversion": 5000000, "moneda": "CLP", "plazo_dias": 180}
    collected_data: dict

    # ── Flags de Control del Flujo ────────────────────────────
    # Escritura reservada a nodos de seguridad y manejo de errores.
    control_flags: dict
    # Estructura esperada de control_flags:
    # {
    #   "security_blocked": bool,    # True si SECURITY_WATCHDOG bloqueó el flujo
    #   "service_error": bool,       # True si un servicio externo falló
    #   "otp_attempts": int,         # Contador de intentos de OTP (0-3)
    #   "error_detail": str | None,  # Descripción técnica del error para logging
    # }
```

**[DETENCIÓN OBLIGATORIA 4.1]**
Reportar en `CP-04-dev1-fase1.md`: Confirmación del StateSchema. Si el agente considera que falta algún campo basado en los documentos de referencia (credito-datos.md, estados-transversales.md), debe documentarlo como nota técnica y pedir instrucciones. Pedir confirmación para continuar al sub-paso 4.2.

---

## Sub-paso 4.2 — Implementar `WELCOME_NODE` en `app/graph/nodes/common.py`

**Acción:** [MODIFICAR] `/backend/app/graph/nodes/common.py`:

```python
"""
app/graph/nodes/common.py
─────────────────────────────────────────────────────────────
Nodos transversales y utilitarios del Grafo FLUX.

Contiene los nodos compartidos por todos los flujos de producto:
- WELCOME_NODE: Saludo inicial y carga del perfil de usuario.
- INTENT_ROUTER_NODE: Clasificador de intención del primer mensaje.

Fase 3 agregará aquí: KNOWLEDGE_BASE_RAG, AMBIGUITY_HANDLER,
SERVICE_ERROR_HANDLER, SECURITY_WATCHDOG, GLOBAL_END, RESUME_HANDLER.
"""

from langchain_core.messages import AIMessage, SystemMessage
from app.graph.state import FluxState
from app.infra.supabase import get_user_by_email, update_conversation_node
from app.infra.gemini_client import get_chat_model


# ── WELCOME_NODE ──────────────────────────────────────────────

def welcome_node(state: FluxState) -> dict:
    """
    Nodo de bienvenida y carga de perfil de usuario.

    INPUT (State):
        - state["session"]["conversation_id"]: UUID de la conversación activa.
        - state["user_data"]["email"]: Email del usuario autenticado.
        - state["messages"]: Historial de mensajes (puede estar vacío en sesión nueva
          o contener historial en sesión reanudada).

    PROCESO:
        1. Verifica si es una sesión nueva o reanudada basándose en
           la presencia de mensajes previos en el historial.
        2. Si es nueva: saluda al usuario por su nombre.
        3. Si es reanudada: genera un saludo de continuación referenciando
           el punto donde se abandonó la sesión (previous_node).
        4. Actualiza el `current_node` en la DB (GPS del frontend).

    OUTPUT (campos del State que modifica):
        - messages: Agrega el mensaje de bienvenida del asistente.
        - session["current_node"]: Actualizado a "WELCOME_NODE".
    """
    user = state.get("user_data", {})
    session = state.get("session", {})
    messages = state.get("messages", [])
    full_name = user.get("full_name", "")
    first_name = full_name.split()[0] if full_name else "amig@"

    # Determinar si es sesión nueva o reanudada
    is_resumed = len(messages) > 0 and session.get("previous_node") is not None

    if is_resumed:
        previous_node = session.get("previous_node", "")
        welcome_text = (
            f"¡Hola de nuevo, {first_name}! 👋 Veo que nos habíamos quedado a mitad del camino. "
            f"No te preocupes, tu progreso está guardado. ¿Continuamos donde lo dejamos?"
        )
    else:
        welcome_text = (
            f"¡Hola, {first_name}! 👋 Soy Flux, tu asistente financiero. "
            f"Estoy aquí para ayudarte a solicitar un **Crédito de Consumo**, "
            f"abrir una **Cuenta Corriente**, o contratar un **Depósito a Plazo**. "
            f"¿Con qué te puedo ayudar hoy?"
        )

    # Actualizar GPS en la DB
    conversation_id = session.get("conversation_id")
    if conversation_id:
        update_conversation_node(conversation_id, "WELCOME_NODE")

    return {
        "messages": [AIMessage(content=welcome_text)],
        "session": {**session, "current_node": "WELCOME_NODE"},
    }


# ── INTENT_ROUTER_NODE ────────────────────────────────────────

_INTENT_SYSTEM_PROMPT = """
Eres el clasificador de intenciones de FLUX, un sistema bancario conversacional.
Tu única función es analizar el mensaje del usuario y clasificar su intención
en UNA de las siguientes categorías exactas. Responde SOLO con la categoría, sin explicaciones.

CATEGORÍAS:
- LOAN: El usuario quiere solicitar un crédito, préstamo, financiamiento o dinero prestado.
- ACCOUNT: El usuario quiere abrir una cuenta corriente, cuenta bancaria o cuenta de cheques.
- DAP: El usuario quiere invertir, hacer un depósito a plazo, ahorrar con intereses o un DAP.
- GENERAL: El usuario tiene una pregunta general, duda, saludo, o algo que no encaja en las categorías anteriores.

EJEMPLOS:
"Quiero un crédito de 5 millones" → LOAN
"Necesito abrir una cuenta" → ACCOUNT
"¿Puedo invertir mi sueldo?" → DAP
"¿Cómo funciona esto?" → GENERAL
"hola" → GENERAL
"¿Qué es el CAE?" → GENERAL
"""


def intent_router_node(state: FluxState) -> dict:
    """
    Nodo clasificador de la intención inicial del usuario.

    INPUT (State):
        - state["messages"]: Último mensaje del usuario.
        - state["session"]: Datos de sesión actuales.

    PROCESO:
        1. Extrae el último mensaje del usuario del historial.
        2. Envía el mensaje al LLM con el prompt de clasificación.
        3. Parsea la respuesta para obtener el código de intención (LOAN, ACCOUNT, DAP, GENERAL).
        4. Actualiza el product_intent en el estado.

    OUTPUT (campos del State que modifica):
        - session["product_intent"]: Código de intención detectada.
        - session["current_node"]: Actualizado a "INTENT_ROUTER".
    """
    from langchain_core.messages import HumanMessage

    messages = state.get("messages", [])
    session = state.get("session", {})

    # Obtener el último mensaje del usuario
    last_user_message = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_message = msg.content
            break

    if not last_user_message:
        # Si no hay mensaje del usuario, asumir intención GENERAL
        intent = "GENERAL"
    else:
        model = get_chat_model()
        classification_messages = [
            SystemMessage(content=_INTENT_SYSTEM_PROMPT),
            HumanMessage(content=last_user_message),
        ]
        response = model.invoke(classification_messages)
        raw_intent = response.content.strip().upper()

        # Validar que la respuesta es una categoría válida
        valid_intents = {"LOAN", "ACCOUNT", "DAP", "GENERAL"}
        intent = raw_intent if raw_intent in valid_intents else "GENERAL"

    return {
        "session": {
            **session,
            "product_intent": intent,
            "current_node": "INTENT_ROUTER",
        }
    }
```

**[DETENCIÓN OBLIGATORIA 4.2]**
Reportar en `CP-04-dev1-fase1.md`: Confirmación de los nodos. Pedir confirmación para continuar al sub-paso 4.3.

---

## Sub-paso 4.3 — Implementar `app/graph/edges.py`

**Acción:** [MODIFICAR] `/backend/app/graph/edges.py`:

```python
"""
app/graph/edges.py
─────────────────────────────────────────────────────────────
Lógica de ruteo condicional entre nodos del Grafo FLUX.

PROCESO: Define las funciones que LangGraph usa como Conditional Edges
         para decidir, basándose en el State, qué nodo ejecutar a continuación.

SALIDA:  Funciones que retornan el nombre del próximo nodo como string.
"""

from app.graph.state import FluxState


def route_after_welcome(state: FluxState) -> str:
    """
    Función de ruteo ejecutada después de WELCOME_NODE.

    INPUT (State): state["session"]["product_intent"]
    PROCESO: Si ya se detectó una intención (sesión reanudada), redirigir
             directamente al nodo de entrada del producto. Si no, ir al router.
    OUTPUT: Nombre del nodo destino como string.
    """
    session = state.get("session", {})
    product_intent = session.get("product_intent")

    # Si ya había intención detectada (sesión reanudada), reanudar el flujo
    if product_intent == "LOAN":
        return "loan_init"   # Placeholder: en Fase 2 será LOAN_INIT
    elif product_intent == "ACCOUNT":
        return "account_init"  # Placeholder: en Fase 3 será ACCOUNT_INIT
    elif product_intent == "DAP":
        return "dap_init"    # Placeholder: en Fase 3 será DAP_INIT

    # Sin intención previa → ir al clasificador
    return "intent_router"


def route_after_intent(state: FluxState) -> str:
    """
    Función de ruteo ejecutada después de INTENT_ROUTER_NODE.

    INPUT (State): state["session"]["product_intent"]
    PROCESO: Dirige al nodo de entrada del producto correspondiente.
             En Fase 1, los nodos de producto son stubs que solo confirman
             la intención detectada.
    OUTPUT: Nombre del nodo destino como string.
    """
    session = state.get("session", {})
    product_intent = session.get("product_intent", "GENERAL")

    if product_intent == "LOAN":
        return "loan_init"
    elif product_intent == "ACCOUNT":
        return "account_init"
    elif product_intent == "DAP":
        return "dap_init"
    else:
        return "general_response"
```

**[DETENCIÓN OBLIGATORIA 4.3]**
Reportar en `CP-04-dev1-fase1.md`: Confirmación del archivo. Pedir confirmación para continuar al sub-paso 4.4.

---

## Sub-paso 4.4 — Crear stubs de nodos de producto en credit.py, account.py, deposit.py

**Acción:** [MODIFICAR] los tres archivos con stubs funcionales que confirman la intención y esperan implementación en fases futuras.

**`/backend/app/graph/nodes/credit.py`:**
```python
"""
app/graph/nodes/credit.py
─────────────────────────────────────────────────────────────
Nodos del flujo de Crédito de Consumo.
FASE 1: Solo contiene el nodo de entrada (stub).
FASE 2: Se implementarán todos los nodos del flujo completo.
"""
from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def loan_init_node(state: FluxState) -> dict:
    """
    INPUT: state["session"]["product_intent"] == "LOAN"
    PROCESO: [STUB FASE 1] Confirma la intención y avisa que el flujo completo viene en Fase 2.
    OUTPUT: messages (confirmación), session["current_node"] = "LOAN_INIT_STUB"
    """
    user_data = state.get("user_data", {})
    first_name = user_data.get("full_name", "").split()[0] or "amig@"
    msg = (
        f"¡Perfecto, {first_name}! Entendido, quieres solicitar un **Crédito de Consumo**. "
        f"El flujo completo estará disponible muy pronto. ¡Gracias por tu paciencia!"
    )
    session = state.get("session", {})
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "LOAN_INIT_STUB"},
    }
```

**`/backend/app/graph/nodes/account.py`:**
```python
"""
app/graph/nodes/account.py
FASE 1: Stub. FASE 3: Implementación completa.
"""
from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def account_init_node(state: FluxState) -> dict:
    """
    INPUT: state["session"]["product_intent"] == "ACCOUNT"
    PROCESO: [STUB FASE 1]
    OUTPUT: messages (confirmación stub)
    """
    session = state.get("session", {})
    msg = "Entendido, quieres abrir una **Cuenta Corriente**. El flujo completo estará disponible en Fase 3."
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "ACCOUNT_INIT_STUB"},
    }
```

**`/backend/app/graph/nodes/deposit.py`:**
```python
"""
app/graph/nodes/deposit.py
FASE 1: Stub. FASE 3: Implementación completa.
"""
from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def dap_init_node(state: FluxState) -> dict:
    """
    INPUT: state["session"]["product_intent"] == "DAP"
    PROCESO: [STUB FASE 1]
    OUTPUT: messages (confirmación stub)
    """
    session = state.get("session", {})
    msg = "Entendido, quieres contratar un **Depósito a Plazo**. El flujo completo estará disponible en Fase 3."
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "DAP_INIT_STUB"},
    }
```

Agregar también un nodo de respuesta general en `/backend/app/graph/nodes/common.py` (al final del archivo):

```python
def general_response_node(state: FluxState) -> dict:
    """
    INPUT: state["messages"] (último mensaje del usuario con intención GENERAL)
    PROCESO: Genera una respuesta empática para preguntas generales o saludos,
             redirigiendo al usuario hacia los productos disponibles.
    OUTPUT: messages (respuesta general)
    """
    session = state.get("session", {})
    msg = (
        "¡Hola! Estoy aquí para ayudarte. Puedo asistirte con:\n\n"
        "• 💳 **Crédito de Consumo** — Financiamiento para lo que necesitas\n"
        "• 🏦 **Cuenta Corriente** — Abre tu cuenta hoy\n"
        "• 📈 **Depósito a Plazo** — Haz crecer tu dinero\n\n"
        "¿Con cuál de estos productos te puedo ayudar?"
    )
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "GENERAL_RESPONSE"},
    }
```

**[DETENCIÓN OBLIGATORIA 4.4]**
Reportar en `CP-04-dev1-fase1.md`: Confirmación de los 4 archivos. Pedir confirmación para continuar al sub-paso 4.5.

---

## Sub-paso 4.5 — Compilar el Grafo en `app/graph/workflow.py`

**Acción:** [MODIFICAR] `/backend/app/graph/workflow.py`:

```python
"""
app/graph/workflow.py
─────────────────────────────────────────────────────────────
Definición, compilación y exposición del Grafo de Estados FLUX.

PROCESO: Instancia el StateGraph, registra todos los nodos y aristas,
         y compila el grafo con el checkpointer de Supabase.
         El resultado es `compiled_graph`, el objeto que los endpoints
         de FastAPI invocan para procesar mensajes.

SALIDA:  `compiled_graph` — instancia de CompiledGraph lista para invoke/stream.
"""

from langgraph.graph import StateGraph, END

from app.graph.state import FluxState
from app.graph.nodes.common import (
    welcome_node,
    intent_router_node,
    general_response_node,
)
from app.graph.nodes.credit import loan_init_node
from app.graph.nodes.account import account_init_node
from app.graph.nodes.deposit import dap_init_node
from app.graph.edges import route_after_welcome, route_after_intent
from app.infra.checkpointer import get_checkpointer


# ── Construcción del Grafo ────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Construye y retorna el StateGraph sin compilar.
    Útil para testing de la estructura del grafo.

    INPUT:  Ninguno.
    PROCESO: Crea un StateGraph con FluxState, agrega nodos y aristas.
    OUTPUT: Instancia de StateGraph sin compilar.
    """
    graph = StateGraph(FluxState)

    # ── Registro de Nodos ─────────────────────────────────────
    graph.add_node("welcome",          welcome_node)
    graph.add_node("intent_router",    intent_router_node)
    graph.add_node("loan_init",       loan_init_node)
    graph.add_node("account_init",    account_init_node)
    graph.add_node("dap_init",        dap_init_node)
    graph.add_node("general_response", general_response_node)

    # ── Punto de Entrada ──────────────────────────────────────
    graph.set_entry_point("welcome")

    # ── Aristas Condicionales ─────────────────────────────────
    # Después de WELCOME: redirigir según intención (nueva o reanudada)
    graph.add_conditional_edges(
        "welcome",
        route_after_welcome,
        {
            "intent_router":  "intent_router",
            "loan_init":     "loan_init",
            "account_init":  "account_init",
            "dap_init":      "dap_init",
        }
    )

    # Después de INTENT_ROUTER: redirigir al producto correspondiente
    graph.add_conditional_edges(
        "intent_router",
        route_after_intent,
        {
            "loan_init":       "loan_init",
            "account_init":    "account_init",
            "dap_init":        "dap_init",
            "general_response": "general_response",
        }
    )

    # ── Aristas Finales (todos los stubs terminan por ahora) ──
    graph.add_edge("loan_init",       END)
    graph.add_edge("account_init",    END)
    graph.add_edge("dap_init",        END)
    graph.add_edge("general_response", END)

    return graph


def get_compiled_graph():
    """
    Compila el grafo con el checkpointer de Supabase.

    INPUT:  Ninguno.
    PROCESO: Llama a build_graph() y compile() con el PostgresSaver.
    OUTPUT: CompiledGraph listo para invoke/astream.

    NOTA: El checkpointer.setup() se llama dentro de get_checkpointer(),
          lo que garantiza que las tablas internas de LangGraph existen en Supabase.
    """
    graph = build_graph()
    checkpointer = get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


# ── Instancia Singleton del Grafo Compilado ───────────────────
# Los endpoints de FastAPI importan directamente este objeto.
compiled_graph = get_compiled_graph()
```

**[DETENCIÓN OBLIGATORIA 4.5]**
Reportar en `CP-04-dev1-fase1.md`: Confirmación del archivo. Pedir confirmación para continuar al checkpoint del Paso 4.

---

## ✅ CHECKPOINT 4 — Pruebas del Paso 4

---

### Prueba 4.A — Test Unitario: Validación del StateSchema

**Objetivo:** Verificar que el StateSchema tiene todos los campos requeridos por el sistema.

**Diseño:** [MODIFICAR] `/backend/tests/test_graph.py`:

```python
"""Tests del Grafo LangGraph."""
import pytest


def test_flux_state_schema_has_required_fields():
    """Verifica que FluxState define todos los campos necesarios."""
    from app.graph.state import FluxState
    import typing
    
    hints = typing.get_type_hints(FluxState)
    required_fields = ["messages", "user_data", "session", "collected_data", "control_flags"]
    
    for field in required_fields:
        assert field in hints, f"Campo requerido '{field}' no encontrado en FluxState"


def test_graph_compiles_without_error():
    """Verifica que el StateGraph se compila sin lanzar excepciones."""
    from app.graph.workflow import build_graph
    graph = build_graph()
    # Si llegamos aquí, el grafo se construyó sin error
    assert graph is not None


def test_graph_has_correct_nodes():
    """Verifica que el grafo tiene registrados todos los nodos esperados para Fase 1."""
    from app.graph.workflow import build_graph
    graph = build_graph()
    
    expected_nodes = {
        "welcome", "intent_router", "loan_init",
        "account_init", "dap_init", "general_response"
    }
    actual_nodes = set(graph.nodes.keys())
    
    for node in expected_nodes:
        assert node in actual_nodes, f"Nodo '{node}' no encontrado en el grafo"
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/test_graph.py::test_flux_state_schema_has_required_fields tests/test_graph.py::test_graph_compiles_without_error tests/test_graph.py::test_graph_has_correct_nodes -v`

**Resultado esperado:** 3 tests `PASSED`.

---

### Prueba 4.B — Test de Integración: Clasificación de Intenciones

**Objetivo:** Verificar que el `INTENT_ROUTER_NODE` clasifica correctamente las intenciones más comunes.

```python
def test_intent_router_classifies_loan():
    """Verifica que un mensaje de crédito se clasifica como LOAN."""
    from langchain_core.messages import HumanMessage
    from app.graph.nodes.common import intent_router_node
    from app.graph.state import FluxState

    # Estado mínimo para la prueba
    state: FluxState = {
        "messages": [HumanMessage(content="Quiero solicitar un crédito de 3 millones")],
        "user_data": {"full_name": "Juan Test", "email": "test@flux.cl"},
        "session": {"conversation_id": "test-123", "current_node": "WELCOME"},
        "collected_data": {},
        "control_flags": {},
    }
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "LOAN"


def test_intent_router_classifies_account():
    """Verifica que un mensaje de cuenta se clasifica como ACCOUNT."""
    from langchain_core.messages import HumanMessage
    from app.graph.nodes.common import intent_router_node
    from app.graph.state import FluxState

    state: FluxState = {
        "messages": [HumanMessage(content="Quiero abrir una cuenta corriente")],
        "user_data": {}, "session": {}, "collected_data": {}, "control_flags": {},
    }
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "ACCOUNT"


def test_intent_router_classifies_dap():
    """Verifica que un mensaje de inversión se clasifica como DAP."""
    from langchain_core.messages import HumanMessage
    from app.graph.nodes.common import intent_router_node
    from app.graph.state import FluxState

    state: FluxState = {
        "messages": [HumanMessage(content="Quiero hacer un depósito a plazo de 5 millones")],
        "user_data": {}, "session": {}, "collected_data": {}, "control_flags": {},
    }
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "DAP"


def test_intent_router_classifies_general():
    """Verifica que un saludo se clasifica como GENERAL."""
    from langchain_core.messages import HumanMessage
    from app.graph.nodes.common import intent_router_node
    from app.graph.state import FluxState

    state: FluxState = {
        "messages": [HumanMessage(content="Hola, ¿cómo estás?")],
        "user_data": {}, "session": {}, "collected_data": {}, "control_flags": {},
    }
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "GENERAL"
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/test_graph.py -v -s`

**Resultado esperado:** Todos los tests `PASSED`. Los tests de intent_router hacen llamadas reales a Gemini.

**Interpretación:**
- Si `test_intent_router_classifies_loan` falla → Revisar el prompt de clasificación. El LLM no está respondiendo con el token esperado. Ajustar el `_INTENT_SYSTEM_PROMPT` y pedir aprobación antes de hacerlo.
- Si algún test falla con error de API → El problema está en la autenticación con Vertex AI (revisar Paso 3).

---

### Prueba 4.C — Test de Integración: Persistencia del Estado (Checkpointer)

**Objetivo:** Verificar que el grafo compilado persiste el estado en Supabase y puede recuperarlo con el mismo thread_id.

```python
def test_graph_state_persists_across_invocations():
    """
    Verifica que el grafo persiste el estado y que una segunda invocación
    con el mismo thread_id recupera el historial previo.
    ADVERTENCIA: Este test hace llamadas reales a Gemini y escribe en Supabase.
    """
    import uuid
    from langchain_core.messages import HumanMessage
    from app.graph.workflow import compiled_graph

    thread_id = f"test-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    # Primera invocación — estado inicial
    initial_state = {
        "messages": [HumanMessage(content="Quiero un crédito")],
        "user_data": {"full_name": "Ana Test", "email": "ana@flux.cl"},
        "session": {"conversation_id": thread_id, "current_node": "START"},
        "collected_data": {},
        "control_flags": {},
    }
    result1 = compiled_graph.invoke(initial_state, config=config)
    assert result1 is not None
    assert len(result1["messages"]) > 1  # El grafo agregó mensajes

    # Segunda invocación — el estado debe ser recuperado del checkpointer
    result2 = compiled_graph.invoke(
        {"messages": [HumanMessage(content="¿Cuánto me prestarían?")]},
        config=config
    )
    # El historial debe ser mayor que en la primera invocación (memoria persistida)
    assert len(result2["messages"]) > len(result1["messages"]), \
        "El checkpointer no persistió el estado correctamente"

    print(f"\nMensajes en sesión 1: {len(result1['messages'])}")
    print(f"Mensajes en sesión 2: {len(result2['messages'])}")
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/test_graph.py::test_graph_state_persists_across_invocations -v -s`

**Resultado esperado:** `PASSED`. El segundo número de mensajes debe ser mayor que el primero.

---

**[DETENCIÓN OBLIGATORIA — CIERRE PASO 4]**

Reporte Final en `CP-04-dev1-fase1.md`:
1. Resultado de cada prueba (nombres, estado, interpretación).
2. Fragmento de respuesta del bot para cada intención detectada (del output de los tests con `-s`).
3. Número de mensajes en sesión 1 y sesión 2 del test de persistencia.
4. Estado: PASO 4 COMPLETADO / PASO 4 BLOQUEADO.
5. Solicitar aprobación para iniciar el Paso 5.

---
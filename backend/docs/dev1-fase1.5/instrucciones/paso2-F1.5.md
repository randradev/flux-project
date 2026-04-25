## PASO 2 — Refactor de `common.py` {#paso-2}

### 2.1 Sub-paso: Modificar `welcome_node`

El cambio central es: al final de `welcome_node`, además de escribir `session`, ahora también escribe `preparation_data` con los datos procesados.

**Lógica de cálculo de edad:**
```python
from datetime import date

def _calculate_age(birth_date_str: str) -> int:
    """Calcula la edad en años completos a partir de una fecha ISO8601."""
    birth = date.fromisoformat(birth_date_str)
    today = date.today()
    return today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )
```

**Modificación del retorno de `welcome_node`:**

```python
# ANTES (v1.0):
return {
    "messages": [AIMessage(content=welcome_text)],
    "session": {**session, "current_node": "WELCOME_NODE"},
}

# DESPUÉS (v2.0):
# Calcular edad desde birth_date
birth_date_str = user.get("birth_date")
edad = _calculate_age(birth_date_str) if birth_date_str else 0

return {
    "messages": [AIMessage(content=welcome_text)],
    "session": {**session, "current_node": "WELCOME_NODE"},
    "preparation_data": {
        "nombre": full_name,
        "rut": user.get("rut", ""),
        "mail": user.get("email", ""),
        "edad": edad,
    },
}
```

### 2.2 Sub-paso: Código Completo del `welcome_node` Refactorizado

```python
# En app/graph/nodes/common.py

from datetime import date
from langchain_core.messages import AIMessage, SystemMessage
from app.graph.state import FluxState
from app.infra.supabase import get_user_by_email, update_conversation_node
from app.infra.gemini_client import get_chat_model


def _calculate_age(birth_date_str: str) -> int:
    """
    Calcula la edad en años completos a partir de una fecha ISO8601.

    INPUT:  birth_date_str — string ISO8601 (ej: "1990-05-15")
    OUTPUT: edad en años completos (int)
    EDGE CASE: Si el cumpleaños es hoy, ya cumplió → se cuenta el año.
    """
    birth = date.fromisoformat(birth_date_str)
    today = date.today()
    return today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )


def welcome_node(state: FluxState) -> dict:
    """
    Nodo de bienvenida, carga de perfil y preparación de datos universales.

    INPUT (State):
        - state["user_data"]: Perfil RAW del usuario desde DB.
        - state["session"]: Metadatos de sesión.
        - state["messages"]: Historial (vacío=nueva sesión, con contenido=reanudada).

    PROCESO:
        1. Detecta si es sesión nueva o reanudada.
        2. Calcula edad a partir de birth_date (centralizado aquí para toda la app).
        3. Genera mensaje de bienvenida personalizado.
        4. Actualiza GPS en Supabase.
        5. Escribe preparation_data con datos procesados.

    OUTPUT (campos del State que modifica):
        - messages: Agrega mensaje de bienvenida.
        - session["current_node"]: "WELCOME_NODE".
        - preparation_data: {nombre, rut, mail, edad}.
    """
    user = state.get("user_data", {})
    session = state.get("session", {})
    messages = state.get("messages", [])

    full_name = user.get("full_name", "")
    first_name = full_name.split()[0] if full_name else "amig@"

    # Calcular edad (responsabilidad centralizada en este nodo desde v2.0)
    birth_date_str = user.get("birth_date")
    edad = _calculate_age(birth_date_str) if birth_date_str else 0

    # Detectar si es sesión nueva o reanudada
    is_resumed = len(messages) > 0 and session.get("previous_node") is not None

    if is_resumed:
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
        # ── NUEVO en v2.0: preparation_data ──────────────────────
        "preparation_data": {
            "nombre": full_name,
            "rut": user.get("rut", ""),
            "mail": user.get("email", ""),
            "edad": edad,
        },
    }
```

### 2.3 Sub-paso: Verificación Post-Refactor

**Checklist de verificación manual:**
- [ ] Ejecutar el nodo en aislamiento (mock del state) y verificar que `preparation_data` aparece en el dict de retorno.
- [ ] Verificar que `edad` es un `int` (no un `float`, no un `str`).
- [ ] Verificar que el cálculo de edad es correcto para un usuario con cumpleaños hoy (debe sumar el año).
- [ ] Verificar que `user_data` NO es modificado por este nodo (solo lectura).
- [ ] Confirmar que `edges.py` sigue leyendo `state["session"]["product_intent"]` sin cambios.

### 2.4 Pruebas del Paso 2

```python
# tests/test_welcome_node_v2.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from langchain_core.messages import HumanMessage


def make_mock_state(birth_date="1990-06-15", previous_node=None, messages=None):
    """Helper para construir un FluxState mínimo para testing."""
    return {
        "user_data": {
            "full_name": "Ana García",
            "email": "ana@example.com",
            "rut": "12345678-9",
            "birth_date": birth_date,
        },
        "session": {
            "conversation_id": "test-conv-001",
            "previous_node": previous_node,
        },
        "messages": messages or [],
    }


@patch("app.infra.supabase.update_conversation_node")
def test_welcome_writes_preparation_data(mock_update):
    """Verifica que welcome_node escribe preparation_data correctamente."""
    from app.graph.nodes.common import welcome_node
    state = make_mock_state()
    result = welcome_node(state)

    assert "preparation_data" in result
    pd = result["preparation_data"]
    assert pd["nombre"] == "Ana García"
    assert pd["rut"] == "12345678-9"
    assert pd["mail"] == "ana@example.com"
    assert isinstance(pd["edad"], int)
    assert pd["edad"] >= 0


@patch("app.infra.supabase.update_conversation_node")
def test_age_calculation_before_birthday(mock_update):
    """Edad calculada correctamente cuando el cumpleaños aún no ha llegado este año."""
    from app.graph.nodes.common import welcome_node, _calculate_age
    today = date.today()
    # Cumpleaños en el futuro de este año
    future_bday = date(1990, today.month + 1 if today.month < 12 else 12, 15)
    age = _calculate_age(future_bday.isoformat())
    expected = today.year - 1990 - 1
    assert age == expected


@patch("app.infra.supabase.update_conversation_node")
def test_welcome_does_not_modify_user_data(mock_update):
    """user_data NO debe aparecer en el dict de retorno (no se modifica)."""
    from app.graph.nodes.common import welcome_node
    state = make_mock_state()
    result = welcome_node(state)
    assert "user_data" not in result


@patch("app.infra.supabase.update_conversation_node")
def test_welcome_resumed_session(mock_update):
    """Mensaje de bienvenida diferente para sesión reanudada."""
    from app.graph.nodes.common import welcome_node
    state = make_mock_state(
        previous_node="LOAN_COLLECTING_PROFILE",
        messages=[HumanMessage(content="quiero un crédito")]
    )
    result = welcome_node(state)
    welcome_msg = result["messages"][0].content
    assert "de nuevo" in welcome_msg.lower() or "reanud" in welcome_msg.lower()
```

**Documentación del Paso 2:**
> Se refactorizó `welcome_node` para: (1) extraer la función `_calculate_age` como utilidad privada del módulo, (2) agregar la escritura de `preparation_data` en el dict de retorno. El nodo ahora es el único punto del sistema donde se calcula la edad, eliminando cualquier recálculo en nodos posteriores. No se modificó la lógica de mensajes ni la integración con Supabase.

---
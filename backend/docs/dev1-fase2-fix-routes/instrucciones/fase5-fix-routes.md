## VI. Actualización de `common.py`: Inicialización de `progress`

**Archivo:** `app/graph/nodes/common.py`

El `welcome_node` en modo Bienvenida (sesión nueva) debe inicializar `progress: {}` en `session` para evitar que los nodos de recolección tengan que manejar la ausencia del campo.

**Cambio en el bloque `else` de `welcome_node`:**

```python
else:
    # MODO BIENVENIDA: sesión nueva, sin intención, sin historial
    welcome_text = (...)
    # ...
    return {
        "messages": [AIMessage(content=welcome_text)],
        "session": {
            **session,
            "current_node": "WELCOME_NODE",
            "progress": session.get("progress", {}),          # ← Inicializar si no existe
            "just_completed_step": None,                       # ← Siempre limpio al inicio
        },
        "preparation_data": preparation_data,
    }
```

En modo silencioso, `session` no se modifica, por lo que `progress` y `just_completed_step` del turno anterior se preservan correctamente.

---

### ✅ Tests de `common.py`

```python
# tests/unit/test_common_v22.py
from unittest.mock import patch
from app.graph.nodes.common import welcome_node


@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_welcome_initializes_progress_on_new_session(mock_conv, mock_sem):
    state = {
        "user_data": {"full_name": "Test User", "birth_date": "1990-01-01", "rut": "", "email": ""},
        "session": {"product_intent": None, "current_node": "", "conversation_id": None, "application_id": None},
        "messages": [],
    }
    result = welcome_node(state)
    assert "progress" in result["session"]
    assert result["session"]["just_completed_step"] is None


@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_welcome_silent_preserves_progress(mock_conv, mock_sem):
    """En modo silencioso, el progreso existente no debe borrarse."""
    from langchain_core.messages import HumanMessage
    state = {
        "user_data": {"full_name": "Test User", "birth_date": "1990-01-01", "rut": "", "email": ""},
        "session": {
            "product_intent": "LOAN",
            "current_node": "LOAN_COLLECTING_PROFILE",
            "progress": {"loan": {"profile_completed": True}},
            "just_completed_step": None,
        },
        "messages": [HumanMessage(content="hola")],
    }
    result = welcome_node(state)
    # En silencio, session NO se modifica
    assert "session" not in result
```

---
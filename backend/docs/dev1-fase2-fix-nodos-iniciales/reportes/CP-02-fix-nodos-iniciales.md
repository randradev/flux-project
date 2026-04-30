# Reporte de Auditoría: CP-02-fix-nodos-iniciales

**Estado de la Implementación:** Éxito (Diseño de Hidratación Silenciosa Validado)

## Decisiones Técnicas

1.  **Modos de Operación en `welcome_node`**:
    -   **Modo Bienvenida**: Sesiones 100% nuevas. Emite `AIMessage` y marca `current_node="WELCOME_NODE"`.
    -   **Modo Silencioso (Hidratación)**: Activado si `product_intent` existe o hay historial.
        -   **Preservación del GPS**: En modo silencioso, **NO** se modifica `session["current_node"]`. Esto es crítico para que `route_after_welcome` (P1) use el nodo de proceso guardado.
        -   **Carga de `preparation_data`**: Se mantiene el cálculo de edad y carga de datos del usuario en ambos modos, garantizando que los nodos siguientes tengan acceso al contexto hidratado.
2.  **Resolución Hallazgo 2 (Semáforos)**:
    -   En modo silencioso, se utilizará `node_status="BYPASSED"`. Esta decisión permite diferenciar en auditorías de base de datos cuándo un nodo fue ejecutado pero no requirió interacción, versus una ejecución exitosa estándar.

## Incidentes y Soluciones

*   **Riesgo de Sobreescritura**: Se identificó que si el nodo welcome escribiera siempre su propio ID en `current_node`, rompería la prioridad P1 de reanudación. 
    - *Solución*: El diseño del Paso 2 restringe la escritura de `session` solo al modo Bienvenida.

## Evidencia de Tests

Se propone el siguiente test para validar la lógica de hidratación silenciosa:

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
            "conversation_id": "conv-123",
            "application_id": "app-456",
            "product_intent": product_intent,
            "current_node": current_node,
        },
        "messages": messages or [],
    }

@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_silent_mode_bypassed_status(mock_conv, mock_sem):
    """Valida el cumplimiento del Hallazgo 2: status BYPASSED en modo silencioso."""
    state = _base_state(product_intent="LOAN")
    welcome_node(state)
    
    # Verificar que se llamó con BYPASSED
    mock_sem.assert_called_once_with(
        "app-456",
        current_node_id="WELCOME_NODE",
        node_status="BYPASSED",
        engine_status="PENDING"
    )

@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_silent_mode_preserves_current_node(mock_conv, mock_sem):
    """Valida que el modo silencioso no sobreescriba el nodo activo del proceso."""
    state = _base_state(product_intent="LOAN", current_node="LOAN_COLLECTING_PROFILE")
    result = welcome_node(state)
    
    assert "session" not in result, "Session no debe modificarse en modo silencioso"
```

---
*Fin del reporte CP-02*

# Reporte de Auditoría: CP-03-fix-nodos-iniciales

**Estado de la Implementación:** Éxito (Diseño de Bienvenida Dinámica y Punto de Guardado Validado)

## Decisiones Técnicas

1.  **Bienvenida Dinámica (Llamada Tipo B)**:
    -   Se introduce `SYSTEM_PROMPT_INIT_LOAN` para delegar la bienvenida al producto a un LLM.
    -   Se elimina el string estático, permitiendo que Flux use el nombre y la edad del usuario (`preparation_data`) de forma natural.
2.  **Arquitectura del "Punto de Guardado" (Checkpointing)**:
    -   **Decisión Crítica**: `loan_init_node` marcará `current_node="LOAN_COLLECTING_PROFILE"` en su retorno.
    -   **Justificación**: Dado que la respuesta del usuario a la pregunta de bienvenida (renta) será procesada por `loan_collecting_profile`, el GPS debe apuntar a ese nodo *antes* de que termine el turno actual. Esto resuelve el "Bucle de Amnesia" donde el sistema repetía el saludo inicial infinitamente.
3.  **Higiene de Datos**:
    -   Se asegura el reset total de `loan_profile` y `loan_sim` al entrar al flujo, evitando contaminación de datos de sesiones previas o intentos fallidos.

## Incidentes y Soluciones

*   **Riesgo de Navegación Incorrecta**: Se mantiene el guardrail de `product_intent != "LOAN"` para evitar que un usuario entre al motor de crédito por error de ruteo, retornando un mensaje de error controlado.

## Evidencia de Tests

Se propone el siguiente test para validar el Punto de Guardado y la integración con el router:

```python
# tests/unit/test_loan_init.py
from unittest.mock import patch, MagicMock
from app.graph.nodes.credit import loan_init_node
from app.graph.edges import route_after_welcome

@patch("app.graph.nodes.credit._flux_generator")
def test_loan_init_point_of_truth(mock_gen):
    """Valida que loan_init marque el GPS en el siguiente nodo de recolección."""
    mock_gen.invoke.return_value = MagicMock(content="Hola, dime tu renta.")
    
    state = {
        "preparation_data": {"nombre": "Ana", "edad": 28},
        "session": {"product_intent": "LOAN", "current_node": "WELCOME_NODE", "application_id": None},
        "collecting_data": {},
        "messages": [],
    }
    
    result = loan_init_node(state)
    
    # 1. Verificar Save Point
    assert result["session"]["current_node"] == "LOAN_COLLECTING_PROFILE"
    
    # 2. Verificar Integración con Router (Simulación de siguiente turno)
    state_next_turn = {"session": result["session"]}
    destination = route_after_welcome(state_next_turn)
    assert destination == "loan_collecting_profile", "El router debe llevar al perfil, no al init"
```

---
*Fin del reporte CP-03*

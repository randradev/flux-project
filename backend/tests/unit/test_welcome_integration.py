# tests/unit/test_welcome_integration.py
from app.graph.edges import route_after_welcome
from app.graph.nodes.common import welcome_node
from unittest.mock import patch

@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_welcome_silent_plus_route_resumes_correctly(mock_conv, mock_sem):
    """
    Verifica que cuando welcome es silencioso y current_node es LOAN_COLLECTING_PROFILE,
    el router lo detecta y devuelve el destino correcto.
    """
    # 1. Estado inicial simulado de re-entrada (ej: F5 o renacimiento de grafo)
    # product_intent ya existe, current_node apunta al proceso activo.
    state = {
        "user_data": {
            "full_name": "Juan Pérez",
            "birth_date": "1990-01-01",
        },
        "session": {
            "current_node": "LOAN_COLLECTING_PROFILE",
            "product_intent": "LOAN",
        },
        "messages": [], 
    }

    # 2. Ejecutar Welcome (debe ser silencioso e hidratar)
    result_welcome = welcome_node(state)
    
    # Validar que welcome hizo su trabajo técnico sin romper la sesión
    assert "messages" not in result_welcome
    assert "session" not in result_welcome
    assert "preparation_data" in result_welcome

    # 3. Simular el paso del State al Edge (LangGraph lo hace automáticamente)
    # Combinamos el estado original con el resultado del nodo
    state_for_edge = {**state, **result_welcome}
    
    # 4. Ejecutar el Router
    destination = route_after_welcome(state_for_edge)
    
    # Validar que el GPS funcionó
    assert destination == "loan_collecting_profile"

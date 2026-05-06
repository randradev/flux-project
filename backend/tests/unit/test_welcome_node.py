# tests/unit/test_welcome_node.py
from unittest.mock import patch, MagicMock
from app.graph.nodes.common import welcome_node
from langchain_core.messages import HumanMessage, AIMessage


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
def test_silent_when_product_intent_set(mock_conv, mock_sem):
    state = _base_state(product_intent="LOAN")
    result = welcome_node(state)
    assert "messages" not in result, "No debe emitir mensaje si hay product_intent"
    assert result["preparation_data"]["nombre"] == "Juan Pérez"
    # Verificar Hallazgo 2: status SUCCESS (fallback de BYPASSED)
    mock_sem.assert_called_with(
        "app-456",
        current_node_id="WELCOME_NODE",
        node_status="SUCCESS",
        engine_status="PENDING"
    )

@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_silent_when_has_history(mock_conv, mock_sem):
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

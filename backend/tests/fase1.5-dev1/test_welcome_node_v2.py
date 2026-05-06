import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage

# Mocking infra modules to avoid side effects during import
import sys
from unittest.mock import MagicMock
mock_supabase = MagicMock()
mock_gemini = MagicMock()

sys.modules["app.infra.supabase"] = mock_supabase
sys.modules["app.infra.gemini_client"] = mock_gemini

from app.graph.nodes.common import welcome_node

def make_mock_state(application_id="app-456", conversation_id="conv-123"):
    """Helper para construir un FluxState mínimo para testing."""
    return {
        "user_data": {
            "full_name": "Ana García",
            "email": "ana@example.com",
            "rut": "12345678-9",
            "birth_date": "1990-06-15",
        },
        "session": {
            "conversation_id": conversation_id,
            "application_id": application_id,
            "previous_node": None,
        },
        "messages": [],
    }

@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_welcome_node_updates_semaphores(mock_update_conv, mock_update_sem):
    """
    Verifica que welcome_node llama a update_application_semaphores
    con los parámetros correctos (SUCCESS y PENDING).
    """
    # GIVEN
    application_id = "test-app-id-001"
    state = make_mock_state(application_id=application_id)
    
    # WHEN
    result = welcome_node(state)
    
    # THEN
    # 1. Verificar que se llamó a la actualización de semáforos
    mock_update_sem.assert_called_once_with(
        application_id,
        current_node_id="WELCOME_NODE",
        node_status="SUCCESS",
        engine_status="PENDING"
    )
    
    # 2. Verificar que se llamó a la actualización de conversación (GPS)
    mock_update_conv.assert_called_once_with(state["session"]["conversation_id"], "WELCOME_NODE")
    
    # 3. Verificar retorno estructural
    assert "preparation_data" in result
    assert result["session"]["current_node"] == "WELCOME_NODE"

@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_welcome_node_no_application_id(mock_update_conv, mock_update_sem):
    """
    Verifica que no se llama a semáforos si no hay application_id.
    """
    # GIVEN
    state = make_mock_state(application_id=None)
    
    # WHEN
    welcome_node(state)
    
    # THEN
    mock_update_sem.assert_not_called()

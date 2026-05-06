# tests/unit/test_common_v22.py
import sys
from unittest.mock import MagicMock, patch

# Mock infra/config before any other imports
sys.modules["app.infra.gemini_client"] = MagicMock()
sys.modules["app.infra.supabase"] = MagicMock()
sys.modules["app.infra.checkpointer"] = MagicMock()
sys.modules["app.config"] = MagicMock()

from app.graph.nodes.common import welcome_node

@patch("app.graph.nodes.common.update_application_semaphores", return_value=None)
@patch("app.graph.nodes.common.update_conversation_node", return_value=None)
def test_welcome_initializes_progress_on_new_session(mock_conv, mock_sem):
    state = {
        "user_data": {"full_name": "Test User", "birth_date": "1990-01-01", "rut": "", "email": ""},
        "session": {"product_intent": None, "current_node": "", "conversation_id": None, "application_id": None},
        "messages": [],
    }
    result = welcome_node(state)
    assert "progress" in result["session"]
    assert result["session"]["progress"] == {}
    assert result["session"]["just_completed_step"] is None

@patch("app.graph.nodes.common.update_application_semaphores", return_value=None)
@patch("app.graph.nodes.common.update_conversation_node", return_value=None)
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
    # En silencio, session NO se modifica (la función retorna dict vacío o sin session)
    # Según common.py, si hay mensajes y product_intent, entra en modo silencioso y retorna {}
    assert "session" not in result or result.get("session") is None

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])

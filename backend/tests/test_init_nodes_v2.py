import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from app.graph.nodes.credit import loan_init_node
from app.graph.nodes.account import account_init_node
from app.graph.nodes.deposit import dap_init_node

def make_polluted_state():
    """State con datos residuales de múltiples productos (simula sesiones anteriores)."""
    return {
        "preparation_data": {
            "nombre": "Carlos López",
            "rut": "98765432-1",
            "mail": "carlos@example.com",
            "edad": 32,
        },
        "session": {
            "conversation_id": "test-002",
            "application_id": "app-abc-123",
            "product_intent": "LOAN",
        },
        "collecting_data": {
            "loan_profile": {"renta": 999999},
            "loan_sim": {"monto": 10000000},
            "account_profile": {"renta": 888888},
            "dap_params": {"monto": 5000000.0},
        },
        "messages": [],
    }

@patch("app.graph.nodes.credit.update_application_semaphores")
def test_loan_init_resets_and_notifies(mock_semaphore):
    """Verifica que loan_init_node resetea su namespace y notifica SUCCESS."""
    state = make_polluted_state()
    result = loan_init_node(state)

    # 1. Verificar Reset
    cd = result.get("collecting_data", {})
    assert cd.get("loan_profile") == {}
    assert cd.get("loan_sim") == {}
    
    # 2. Verificar Semáforos
    mock_semaphore.assert_called_once_with(
        application_id="app-abc-123",
        current_node_id="LOAN_INIT",
        node_status="SUCCESS",
        engine_status="PENDING"
    )
    
    # 3. Verificar Herencia de preparation_data
    welcome_msg = result["messages"][0].content
    assert "Carlos" in welcome_msg

@patch("app.graph.nodes.account.update_application_semaphores")
def test_account_init_resets_and_notifies(mock_semaphore):
    """Verifica que account_init_node resetea su namespace y notifica SUCCESS."""
    state = make_polluted_state()
    state["session"]["product_intent"] = "ACCOUNT"
    result = account_init_node(state)

    assert result["collecting_data"].get("account_profile") == {}
    mock_semaphore.assert_called_once_with(
        application_id="app-abc-123",
        current_node_id="ACCOUNT_INIT",
        node_status="SUCCESS",
        engine_status="PENDING"
    )

@patch("app.graph.nodes.deposit.update_application_semaphores")
def test_deposit_init_resets_and_notifies(mock_semaphore):
    """Verifica que dap_init_node resetea su namespace y notifica SUCCESS."""
    state = make_polluted_state()
    state["session"]["product_intent"] = "DAP"
    result = dap_init_node(state)

    assert result["collecting_data"].get("dap_params") == {}
    mock_semaphore.assert_called_once_with(
        application_id="app-abc-123",
        current_node_id="DAP_INIT",
        node_status="SUCCESS",
        engine_status="PENDING"
    )


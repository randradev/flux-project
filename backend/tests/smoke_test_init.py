
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from app.graph.workflow import build_graph
from langgraph.checkpoint.memory import MemorySaver

def get_mock_state(intent_msg):
    return {
        "messages": [HumanMessage(content=intent_msg)],
        "user_data": {
            "full_name": "Test User",
            "email": "test@test.com",
            "rut": "12345678-9",
            "birth_date": "1990-01-01",
        },
        "session": {
            "conversation_id": "00000000-0000-0000-0000-000000000001", # Valid UUID
            "application_id": "00000000-0000-0000-0000-000000000002", # Valid UUID
            "product_intent": None,
            "current_node": None,
        }
    }

# Patch everywhere the functions are imported
@patch("app.graph.nodes.common.update_conversation_node")
@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.credit.update_application_semaphores")
@patch("app.graph.nodes.deposit.update_application_semaphores")
@patch("app.graph.nodes.common.get_chat_model")
def test_smoke_loan(mock_model, mock_sem_dep, mock_sem_cred, mock_sem_com, mock_update):
    # Mock LLM response for intent classification
    mock_response = MagicMock()
    mock_response.content = "LOAN"
    mock_model.return_value.invoke.return_value = mock_response

    graph = build_graph().compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "test-loan"}}
    
    # Run the graph
    result = graph.invoke(get_mock_state("quiero un credito"), config)
    
    # 1. Verify intent_router set LOAN
    assert result["session"]["product_intent"] == "LOAN"
    
    # 2. Verify we reached the engine
    assert result["session"]["current_node"] == "LOAN_RISK_ENGINE"
    
    # 3. Verify final state has engine results
    assert "loan_engine" in result["evaluation_results"]
    print("Smoke Test LOAN: PASS")

@patch("app.graph.nodes.common.update_conversation_node")
@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.credit.update_application_semaphores")
@patch("app.graph.nodes.deposit.update_application_semaphores")
@patch("app.graph.nodes.common.get_chat_model")
def test_smoke_dap(mock_model, mock_sem_dep, mock_sem_cred, mock_sem_com, mock_update):
    # Mock LLM response for intent classification
    mock_response = MagicMock()
    mock_response.content = "DAP"
    mock_model.return_value.invoke.return_value = mock_response

    graph = build_graph().compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "test-dap"}}
    
    # Run the graph
    result = graph.invoke(get_mock_state("quiero un dap"), config)
    
    # 1. Verify intent_router set DAP
    assert result["session"]["product_intent"] == "DAP"
    
    # 2. Verify we reached the engine
    assert result["session"]["current_node"] == "DAP_INVESTMENT_ENGINE"
    
    # 3. Verify final state has engine results
    assert "dap_engine" in result["evaluation_results"]
    print("Smoke Test DAP: PASS")

@patch("app.graph.nodes.common.update_conversation_node")
@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.credit.update_application_semaphores")
@patch("app.graph.nodes.deposit.update_application_semaphores")
@patch("app.graph.nodes.account.update_application_semaphores")
@patch("app.graph.nodes.common.get_chat_model")
def test_smoke_account(mock_model, mock_sem_acc, mock_sem_dep, mock_sem_cred, mock_sem_com, mock_update):
    # Mock LLM response for intent classification
    mock_response = MagicMock()
    mock_response.content = "ACCOUNT"
    mock_model.return_value.invoke.return_value = mock_response

    graph = build_graph().compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "test-account"}}
    
    # Run the graph
    result = graph.invoke(get_mock_state("quiero una cuenta corriente"), config)
    
    # 1. Verify intent_router set ACCOUNT
    assert result["session"]["product_intent"] == "ACCOUNT"
    
    # 2. Verify we reached the engine
    assert result["session"]["current_node"] == "ACCOUNT_EVALUATION_ENGINE"
    
    # 3. Verify final state has engine results
    assert "account_engine" in result["evaluation_results"]
    print("Smoke Test ACCOUNT: PASS")

if __name__ == "__main__":
    pass

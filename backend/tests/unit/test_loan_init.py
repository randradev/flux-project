# tests/unit/test_loan_init.py
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from app.graph.nodes.credit import loan_init_node


def _loan_init_state(product_intent="LOAN"):
    return {
        "preparation_data": {"nombre": "Ana González", "rut": "9876543-2", "mail": "ana@test.com", "edad": 28},
        "session": {"product_intent": product_intent, "current_node": "WELCOME_NODE", "application_id": "app-123"},
        "collecting_data": {},
        "messages": [],
    }


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit.update_application_semaphores")
def test_loan_init_emits_message(mock_sem, mock_gen):
    mock_gen.invoke.return_value = MagicMock(content="¡Hola Ana! ¿Cuál es tu renta líquida?")
    result = loan_init_node(_loan_init_state())
    assert "messages" in result
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], AIMessage)

@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit.update_application_semaphores")
def test_loan_init_sets_current_node_to_collecting_profile(mock_sem, mock_gen):
    """PUNTO DE GUARDADO: current_node debe ser LOAN_COLLECTING_PROFILE, no LOAN_INIT."""
    mock_gen.invoke.return_value = MagicMock(content="Hola, cuéntame tu renta.")
    result = loan_init_node(_loan_init_state())
    assert result["session"]["current_node"] == "LOAN_COLLECTING_PROFILE"

@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit.update_application_semaphores")
def test_loan_init_resets_collecting_data(mock_sem, mock_gen):
    mock_gen.invoke.return_value = MagicMock(content="...")
    state = _loan_init_state()
    state["collecting_data"] = {"loan_profile": {"renta": 999999}, "loan_sim": {"monto_solicitado": 5000000}}
    result = loan_init_node(state)
    assert result["collecting_data"]["loan_profile"] == {}
    assert result["collecting_data"]["loan_sim"] == {}

@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit.update_application_semaphores")
def test_loan_init_wrong_intent_returns_error_message(mock_sem, mock_gen):
    result = loan_init_node(_loan_init_state(product_intent="DAP"))
    assert "error de navegación" in result["messages"][0].content.lower()
    mock_gen.invoke.assert_not_called()

@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit.update_application_semaphores")
def test_loan_init_llm_called_with_user_context(mock_sem, mock_gen):
    """El LLM debe recibir el nombre y edad del usuario en el contexto."""
    mock_gen.invoke.return_value = MagicMock(content="Hola Ana, cuéntame tu renta.")
    loan_init_node(_loan_init_state())
    call_args = mock_gen.invoke.call_args[0][0]
    # Buscar el mensaje del usuario en la lista de mensajes enviada al LLM
    user_message = next(m["content"] for m in call_args if m["role"] == "user")
    assert "Ana" in user_message
    assert "28" in user_message

@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit.update_application_semaphores")
def test_loan_init_integration_with_resumption_logic(mock_sem, mock_gen):
    """
    Simula el impacto del save point en el router.
    """
    from app.graph.edges import route_after_welcome
    mock_gen.invoke.return_value = MagicMock(content="¿Renta?")
    
    # Ejecutamos el nodo
    result = loan_init_node(_loan_init_state())
    
    # El estado resultante tiene el GPS apuntando a PROFILE
    state_next_turn = {"session": result["session"]}
    
    # El router debe devolver 'loan_collecting_profile'
    assert route_after_welcome(state_next_turn) == "loan_collecting_profile"

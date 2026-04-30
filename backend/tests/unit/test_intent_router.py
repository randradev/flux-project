# tests/unit/test_intent_router.py
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage
from app.graph.nodes.common import intent_router_node
from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema


def _make_state(user_msg: str):
    return {
        "messages": [HumanMessage(content=user_msg)],
        "session": {"current_node": "WELCOME_NODE", "product_intent": None},
    }


@patch("app.graph.nodes.common._intent_extractor")
def test_intent_router_sets_loan(mock_extractor):
    mock_extractor.invoke.return_value = IntentExtractionSchema(
        intencion="LOAN", razonamiento="Crédito", confianza="ALTA"
    )
    result = intent_router_node(_make_state("quiero un crédito"))
    assert result["session"]["product_intent"] == "LOAN"

@patch("app.graph.nodes.common._intent_extractor")
def test_intent_router_sets_current_node(mock_extractor):
    mock_extractor.invoke.return_value = IntentExtractionSchema(
        intencion="ACCOUNT", razonamiento="Cuenta"
    )
    result = intent_router_node(_make_state("quiero abrir cuenta"))
    assert result["session"]["current_node"] == "INTENT_ROUTER"

@patch("app.graph.nodes.common._intent_extractor")
def test_intent_router_no_message_defaults_general(mock_extractor):
    state = {"messages": [], "session": {"current_node": "WELCOME_NODE"}}
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "GENERAL"
    mock_extractor.invoke.assert_not_called()

@patch("app.graph.nodes.common._intent_extractor")
def test_intent_router_extractor_error_defaults_general(mock_extractor):
    """Si el extractor devuelve None (error), el nodo debe manejar gracefully."""
    mock_extractor.invoke.return_value = None
    result = intent_router_node(_make_state("algo raro"))
    assert result["session"]["product_intent"] == "GENERAL"

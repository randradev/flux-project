# tests/unit/test_edges.py
import pytest
from app.graph.edges import route_after_welcome, route_after_intent


def _make_state(current_node=None, product_intent=None):
    return {
        "session": {
            "current_node": current_node or "",
            "product_intent": product_intent,
        }
    }

# --- TEST 1.A: Jerarquía de prioridades de route_after_welcome ---

# Prioridad 1: current_node activo siempre gana
def test_p1_resume_loan_collecting_profile():
    state = _make_state(current_node="LOAN_COLLECTING_PROFILE", product_intent="LOAN")
    assert route_after_welcome(state) == "loan_collecting_profile"

def test_p1_resume_loan_collecting_simulation():
    state = _make_state(current_node="LOAN_COLLECTING_SIMULATION")
    assert route_after_welcome(state) == "loan_collecting_simulation"

def test_p1_resume_overrides_product_intent():
    """P1 debe ganarle a P2: aunque haya product_intent, si current_node indica
    reanudación profunda, ir ahí."""
    state = _make_state(current_node="LOAN_COLLECTING_PROFILE", product_intent="DAP")
    assert route_after_welcome(state) == "loan_collecting_profile"

# Prioridad 2: sin current_node activo, product_intent manda
def test_p2_product_intent_loan():
    state = _make_state(current_node="WELCOME_NODE", product_intent="LOAN")
    assert route_after_welcome(state) == "loan_init"

def test_p2_product_intent_account():
    state = _make_state(current_node="WELCOME_NODE", product_intent="ACCOUNT")
    assert route_after_welcome(state) == "account_init"

def test_p2_product_intent_dap():
    state = _make_state(current_node="WELCOME_NODE", product_intent="DAP")
    assert route_after_welcome(state) == "dap_init"

# Prioridad 3: sin señales, ir al clasificador
def test_p3_no_signals_go_to_intent_router():
    state = _make_state()
    assert route_after_welcome(state) == "intent_router"

def test_p3_general_intent_goes_to_intent_router():
    state = _make_state(current_node="WELCOME_NODE", product_intent="GENERAL")
    assert route_after_welcome(state) == "intent_router"

# Edge case: WELCOME_NODE y GENERAL_RESPONSE NO deben causar reanudación
def test_welcome_node_is_not_resumable():
    state = _make_state(current_node="WELCOME_NODE")
    assert route_after_welcome(state) == "intent_router"

def test_general_response_is_not_resumable():
    state = _make_state(current_node="GENERAL_RESPONSE")
    assert route_after_welcome(state) == "intent_router"


# --- TEST 1.B: route_after_intent ---

def test_route_after_intent_loan():
    state = {"session": {"product_intent": "LOAN"}}
    assert route_after_intent(state) == "loan_init"

def test_route_after_intent_fallback_to_general():
    state = {"session": {"product_intent": "GENERAL"}}
    assert route_after_intent(state) == "general_response"

def test_route_after_intent_unknown_falls_back():
    state = {"session": {"product_intent": "UNKNOWN_FUTURE"}}
    assert route_after_intent(state) == "general_response"

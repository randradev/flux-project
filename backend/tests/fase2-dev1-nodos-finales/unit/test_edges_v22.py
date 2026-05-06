# tests/unit/test_edges_v22.py
import pytest
from unittest.mock import MagicMock
from app.graph.edges import route_after_welcome
from app.graph.constants import CompletedStep


def _state(current_node="", product_intent=None, progress=None):
    return {
        "session": {
            "current_node": current_node,
            "product_intent": product_intent,
            "progress": progress or {},
        }
    }


# P0: Cambio de producto
def test_p0_product_switch_loan_to_account():
    """Usuario estaba en crédito y ahora quiere cuenta corriente."""
    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="ACCOUNT"
    )
    assert route_after_welcome(state) == "account_init"


def test_p0_same_product_does_not_trigger():
    """Mismo producto: no es cambio, P0 no activa."""
    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="LOAN",
        progress={}
    )
    # Debe ir a P2 (reanudación) porque product matches
    assert route_after_welcome(state) == "loan_collecting_profile"


# P1: Salto por éxito (seguridad inter-turno)
def test_p1_success_jump_profile_completed():
    """Perfil completado: P1 salta a simulación aunque current_node sea profile."""
    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="LOAN",
        progress={"loan": {"profile_completed": True}},
    )
    assert route_after_welcome(state) == "loan_collecting_simulation"


def test_p1_success_jump_simulation_completed():
    state = _state(
        current_node="LOAN_COLLECTING_SIMULATION",
        product_intent="LOAN",
        progress={"loan": {"profile_completed": True, "simulation_completed": True}},
    )
    assert route_after_welcome(state) == "loan_risk_engine"


def test_p1_not_triggered_when_progress_empty():
    """Sin progreso registrado, P1 no activa; se va a P2."""
    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="LOAN",
        progress={}
    )
    assert route_after_welcome(state) == "loan_collecting_profile"


# P2: Reanudación estándar (sin progreso que dispare P1)
def test_p2_resume_without_progress():
    state = _state(current_node="LOAN_COLLECTING_SIMULATION")
    assert route_after_welcome(state) == "loan_collecting_simulation"


# P3 y P4: sin cambios respecto a tests anteriores
def test_p3_product_intent_no_current_node():
    state = _state(current_node="WELCOME_NODE", product_intent="DAP")
    assert route_after_welcome(state) == "dap_init"


def test_p4_no_signals_intent_router():
    state = _state()
    assert route_after_welcome(state) == "intent_router"

# Test fallback
def test_p1_fallback_if_destination_not_valid():
    from app.graph import edges as edges_module
    original_valid = edges_module._VALID_DESTINATION_NODES
    edges_module._VALID_DESTINATION_NODES = frozenset()  # Vaciar para simular nodo faltante

    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="LOAN",
        progress={"loan": {"profile_completed": True}},
    )
    result = route_after_welcome(state)
    assert result == "intent_router" # Cambiado de end_fallback a intent_router

    edges_module._VALID_DESTINATION_NODES = original_valid  # Restaurar

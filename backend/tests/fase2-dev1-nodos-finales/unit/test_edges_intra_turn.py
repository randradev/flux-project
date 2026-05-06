# tests/unit/test_edges_intra_turn.py
from langgraph.graph import END
from app.graph.edges import (
    route_after_loan_collecting_profile,
    route_after_loan_collecting_sim,
)
from app.graph.constants import CompletedStep


def test_loan_profile_edge_jumps_when_complete():
    state = {"session": {"just_completed_step": CompletedStep.LOAN_PROFILE}}
    assert route_after_loan_collecting_profile(state) == "loan_collecting_simulation"


def test_loan_profile_edge_goes_to_end_when_incomplete():
    state = {"session": {"just_completed_step": None}}
    assert route_after_loan_collecting_profile(state) == END


def test_loan_sim_edge_jumps_when_complete():
    state = {"session": {"just_completed_step": CompletedStep.LOAN_SIMULATION}}
    assert route_after_loan_collecting_sim(state) == "loan_risk_engine"


def test_loan_sim_edge_goes_to_end_when_incomplete():
    state = {"session": {"just_completed_step": None}}
    assert route_after_loan_collecting_sim(state) == END


def test_loan_profile_edge_ignores_other_steps():
    """Pasos de otros productos no deben causar salto en el edge de perfil."""
    state = {"session": {"just_completed_step": CompletedStep.ACCOUNT_PROFILE}}
    assert route_after_loan_collecting_profile(state) == END

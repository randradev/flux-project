# tests/unit/test_state_v22.py
from app.graph.state import SessionData
from app.graph.constants import CompletedStep, ProductPrefix


def test_session_data_accepts_progress():
    """SessionData acepta los nuevos campos sin error de TypedDict."""
    session: SessionData = {
        "current_node": "LOAN_COLLECTING_PROFILE",
        "progress": {"loan": {"profile_completed": True}},
        "just_completed_step": CompletedStep.LOAN_PROFILE,
    }
    assert session["progress"]["loan"]["profile_completed"] is True
    assert session["just_completed_step"] == "LOAN_PROFILE"


def test_old_session_missing_progress_handled_gracefully():
    """Sesión antigua sin 'progress' ni 'just_completed_step' no falla."""
    old_session: SessionData = {
        "conversation_id": "abc",
        "current_node": "LOAN_COLLECTING_PROFILE",
        "product_intent": "LOAN",
    }
    progress = old_session.get("progress", {})
    jcs = old_session.get("just_completed_step")
    assert progress == {}
    assert jcs is None


def test_completed_step_constants_are_strings():
    assert isinstance(CompletedStep.LOAN_PROFILE, str)
    assert isinstance(CompletedStep.LOAN_SIMULATION, str)


def test_product_prefix_from_node():
    assert ProductPrefix.from_node("LOAN_COLLECTING_PROFILE") == "LOAN"
    assert ProductPrefix.from_node("ACCOUNT_INIT") == "ACCOUNT"
    assert ProductPrefix.from_node("DAP_COLLECT_DATA") == "DAP"
    assert ProductPrefix.from_node("WELCOME_NODE") is None
    assert ProductPrefix.from_node("GENERAL_RESPONSE") is None

# tests/unit/test_credit_nodes_v22.py
import sys
from unittest.mock import MagicMock, patch

# Mock infra/config before any other imports
sys.modules["app.infra.gemini_client"] = MagicMock()
sys.modules["app.infra.supabase"] = MagicMock()
sys.modules["app.config"] = MagicMock()

from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage
from app.graph.constants import CompletedStep

# Now we can import the nodes, but we need to deal with the decorators/calls inside credit.py
# Since we mocked sys.modules, we should be safe from real connection attempts.

from app.graph.nodes.credit import loan_collecting_profile_node, loan_collecting_sim_node


def _profile_state_complete():
    """State donde el perfil se completa en este turno."""
    return {
        "preparation_data": {"nombre": "Ana López", "edad": 30, "rut": "", "mail": ""},
        "session": {
            "product_intent": "LOAN",
            "current_node": "LOAN_COLLECTING_PROFILE",
            "application_id": None,
            "progress": {},
        },
        "collecting_data": {"loan_profile": {"renta": 1500000, "antiguedad_laboral": 24}, "loan_sim": {}},
        "messages": [HumanMessage(content="Tengo estudios universitarios")],
    }


@patch("app.graph.nodes.credit._profile_extractor")
def test_dual_flag_written_when_profile_completes(mock_extractor):
    from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        razonamiento="Nivel universitario detectado",
        nivel_estudios="UNIVERSITARIO",
    )
    result = loan_collecting_profile_node(_profile_state_complete())

    # Flag histórica
    assert result["session"]["progress"]["loan"]["profile_completed"] is True
    # Flag volátil
    assert result["session"]["just_completed_step"] == CompletedStep.LOAN_PROFILE
    # Sin mensajes (avance silencioso)
    assert "messages" not in result or result.get("messages") == []


@patch("app.graph.nodes.credit._profile_extractor")
def test_no_flags_written_when_profile_incomplete(mock_extractor):
    from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        razonamiento="Solo renta",
        renta=1500000,
    )
    state = _profile_state_complete()
    state["collecting_data"] = {"loan_profile": {}, "loan_sim": {}}  # Perfil vacío: solo se añade renta
    result = loan_collecting_profile_node(state)

    progress = result.get("session", {}).get("progress", {})
    jcs = result.get("session", {}).get("just_completed_step")
    assert not progress.get("loan", {}).get("profile_completed")
    assert jcs is None


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._sim_extractor")
def test_sim_node_skips_extractor_on_intra_turn_jump(mock_extractor, mock_gen):
    mock_gen.invoke.return_value = MagicMock(
        content="¡Perfecto, perfil listo! ¿Cuánto necesitas?"
    )

    state = {
        "preparation_data": {"nombre": "Carlos Vera", "edad": 35, "rut": "", "mail": ""},
        "session": {
            "current_node": "LOAN_COLLECTING_PROFILE",
            "just_completed_step": CompletedStep.LOAN_PROFILE,
            "progress": {"loan": {"profile_completed": True}},
            "application_id": None,
        },
        "collecting_data": {"loan_profile": {"renta": 2000000, "antiguedad_laboral": 36, "nivel_estudios": "UNIVERSITARIO"}, "loan_sim": {}},
        "messages": [HumanMessage(content="Tengo estudios universitarios")],
    }

    result = loan_collecting_sim_node(state)

    # Extractor NO debe llamarse (mensaje ya fue procesado por nodo anterior)
    mock_extractor.invoke.assert_not_called()
    # Generador SÍ debe llamarse (debe pedir el monto)
    mock_gen.invoke.assert_called_once()
    # just_completed_step debe limpiarse
    assert result["session"]["just_completed_step"] is None


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._sim_extractor")
def test_sim_node_cleans_flag_after_generation(mock_extractor, mock_gen):
    """La flag just_completed_step debe ser None en el return tras Llamada B."""
    from app.graph.nodes.schemas.loan_schemas import LoanSimExtraction

    mock_gen.invoke.return_value = MagicMock(content="¿Cuánto necesitas?")
    mock_extractor.invoke.return_value = LoanSimExtraction(
        intencion="OTRO", razonamiento="Saludo"
    )

    state = {
        "preparation_data": {"nombre": "María Torres", "edad": 28, "rut": "", "mail": ""},
        "session": {
            "current_node": "LOAN_COLLECTING_SIMULATION",
            "just_completed_step": None,
            "progress": {"loan": {"profile_completed": True}},
            "application_id": None,
        },
        "collecting_data": {"loan_profile": {"renta": 1000000, "antiguedad_laboral": 12, "nivel_estudios": "TECNICO"}, "loan_sim": {}},
        "messages": [HumanMessage(content="hola")],
    }

    result = loan_collecting_sim_node(state)
    assert result["session"]["just_completed_step"] is None


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._sim_extractor")
def test_sim_completion_sets_dual_flags(mock_extractor, mock_gen):
    """Cuando la simulación se completa, debe escribir ambas flags."""
    from app.graph.nodes.schemas.loan_schemas import LoanSimExtraction

    mock_extractor.invoke.return_value = LoanSimExtraction(
        intencion="DATO_FINANCIERO",
        razonamiento="Monto y plazo detectados",
        monto_solicitado=5000000,
        plazo_solicitado=24,
    )

    state = {
        "preparation_data": {"nombre": "Pedro Soto", "edad": 40, "rut": "", "mail": ""},
        "session": {
            "current_node": "LOAN_COLLECTING_SIMULATION",
            "just_completed_step": None,
            "progress": {"loan": {"profile_completed": True}},
            "application_id": None,
        },
        "collecting_data": {"loan_profile": {"renta": 3000000, "antiguedad_laboral": 60, "nivel_estudios": "POSTGRADO"}, "loan_sim": {}},
        "messages": [HumanMessage(content="quiero 5 palos en 24 cuotas")],
    }

    result = loan_collecting_sim_node(state)

    assert result["session"]["progress"]["loan"]["simulation_completed"] is True
    assert result["session"]["just_completed_step"] == CompletedStep.LOAN_SIMULATION
    assert "messages" not in result or not result.get("messages")
    mock_gen.invoke.assert_not_called()  # Avance silencioso: no se genera mensaje

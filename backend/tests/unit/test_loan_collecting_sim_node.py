# tests/unit/test_loan_collecting_sim_node.py
# Mockea ambos modelos para probar la lógica del nodo de simulación.

from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage
from app.graph.nodes.credit import loan_collecting_sim_node
from app.graph.nodes.schemas.loan_schemas import LoanSimExtraction


def make_state(user_msg: str, sim_data: dict = None):
    return {
        "messages":       [HumanMessage(content=user_msg)],
        "collecting_data": {"loan_profile": {}, "loan_sim": sim_data or {}},
        "session":        {"current_node": "LOAN_COLLECTING_SIMULATION", "application_id": None},
        "preparation_data": {"nombre": "Pedro Pérez"},
    }


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._sim_extractor")
def test_avance_silencioso_no_invoca_generador(mock_extractor, mock_generator):
    """Si monto y plazo están presentes, la Llamada B no debe ejecutarse."""
    mock_extractor.invoke.return_value = LoanSimExtraction(
        intencion="DATO_FINANCIERO",
        monto_solicitado=1_000_000,
        plazo_solicitado=12
    )
    
    result = loan_collecting_sim_node(
        make_state("Quiero 1 millon en 12 meses")
    )
    
    mock_generator.invoke.assert_not_called()
    assert result["collecting_data"]["loan_sim"]["monto_solicitado"] == 1_000_000
    assert result["collecting_data"]["loan_sim"]["plazo_solicitado"] == 12
    assert "messages" not in result or len(result.get("messages", [])) == 0


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._sim_extractor")
def test_saludo_no_contamina_state(mock_extractor, mock_generator):
    """Un saludo no debe modificar los datos de simulación ya existentes."""
    mock_extractor.invoke.return_value = LoanSimExtraction(intencion="SALUDO")
    mock_generator.invoke.return_value = MagicMock(content="¡Hola! ¿Cuánto dinero necesitas?")
    
    state = make_state("Hola!", sim_data={"monto_solicitado": 500_000})
    result = loan_collecting_sim_node(state)
    
    assert result["collecting_data"]["loan_sim"].get("monto_solicitado") == 500_000
    mock_generator.invoke.assert_called_once()
    assert len(result["messages"]) == 1


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._sim_extractor")
def test_centinelas_no_actualizan_sim(mock_extractor, mock_generator):
    """Valores 0 o None del extractor no deben sobreescribir datos válidos."""
    mock_extractor.invoke.return_value = LoanSimExtraction(
        intencion="DATO_FINANCIERO",
        monto_solicitado=None, # El extractor no lo encontró
        plazo_solicitado=0     # Pydantic normaliza a None
    )
    mock_generator.invoke.return_value = MagicMock(content="Perfecto. ¿En cuántas cuotas?")
    
    state = make_state("algo", sim_data={"monto_solicitado": 2_000_000})
    result = loan_collecting_sim_node(state)
    
    sim = result["collecting_data"]["loan_sim"]
    assert sim["monto_solicitado"] == 2_000_000, "El monto previo no debe borrarse"
    assert sim.get("plazo_solicitado") is None


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._sim_extractor")
def test_merge_acumulativo_sim(mock_extractor, mock_generator):
    """Se deben acumular monto y plazo de distintos turnos."""
    mock_extractor.invoke.return_value = LoanSimExtraction(
        intencion="DATO_FINANCIERO",
        plazo_solicitado=24
    )
    mock_generator.invoke.return_value = MagicMock(content="¡Anotado! 24 meses.")
    
    state = make_state("En 24 cuotas", sim_data={"monto_solicitado": 3_000_000})
    result = loan_collecting_sim_node(state)
    
    sim = result["collecting_data"]["loan_sim"]
    assert sim["monto_solicitado"] == 3_000_000
    assert sim["plazo_solicitado"] == 24


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._sim_extractor")
def test_un_solo_return_transaccional_sim(mock_extractor, mock_generator):
    """Verifica que el output contenga todas las llaves necesarias para el State."""
    mock_extractor.invoke.return_value = LoanSimExtraction(intencion="OTRO")
    mock_generator.invoke.return_value = MagicMock(content="Respuesta Flux")
    
    result = loan_collecting_sim_node(make_state("asdf"))
    
    assert "collecting_data" in result
    assert "session" in result
    assert result["session"]["current_node"] == "LOAN_COLLECTING_SIMULATION"

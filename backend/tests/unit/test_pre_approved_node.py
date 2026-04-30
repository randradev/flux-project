from unittest.mock import patch, MagicMock
from app.graph.nodes.credit import loan_pre_approved_node

def make_state_pre_approved():
    return {
        "session":          {"current_node": "LOAN_RISK_ENGINE", "application_id": None},
        "preparation_data": {"nombre": "Ana Torres", "edad": 28},
        "evaluation_results": {
            "loan_engine": {
                "status_proceso": "PRE_APPROVED",
                "monto_aprobado": 5_000_000,
                "plazo_aprobado": 24,
                "cuota_mensual": 250_000,
                "tasa_interes_mensual": 0.020,
                "cae": 0.268,
                "ctc": 6_000_000,
                "total_intereses": 1_000_000,
                "nivel_riesgo": "MEDIO",
            }
        },
        "offer_data": {"loan": {}},
        "messages": [],
    }

@patch("app.graph.nodes.credit._flux_generator")
def test_genera_mensaje_y_display_data(mock_generator):
    mock_generator.invoke.return_value = MagicMock(content="¡Felicitaciones Ana! Revisa tu oferta.")

    result = loan_pre_approved_node(make_state_pre_approved())

    assert "messages" in result and len(result["messages"]) > 0
    assert result["offer_data"]["loan"]["display_data"]["monto_aprobado"] == 5_000_000
    assert result["offer_data"]["loan"]["display_data"]["cuota_mensual"] == 250_000
    # pre_approval_status NO debe setearse en este nodo
    assert "pre_approval_status" not in result["offer_data"]["loan"]

@patch("app.graph.nodes.credit._flux_generator")
def test_flag_simulation_reseteado(mock_generator):
    mock_generator.invoke.return_value = MagicMock(content="Oferta lista.")
    state = make_state_pre_approved()
    state["session"]["simulation_just_completed"] = True

    result = loan_pre_approved_node(state)
    assert result["session"].get("simulation_just_completed") == False

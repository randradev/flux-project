from unittest.mock import patch, MagicMock
from app.graph.nodes.credit import loan_risk_engine_node

def make_state_for_engine():
    return {
        "session":         {"current_node": "LOAN_COLLECTING_SIMULATION", "application_id": None},
        "preparation_data": {"edad": 30, "nombre": "Test", "rut": "12.345.678-9", "mail": "t@t.cl"},
        "collecting_data": {
            "loan_profile": {"renta": 1_500_000, "antiguedad_laboral": 24, "nivel_estudios": "UNIVERSITARIO"},
            "loan_sim":     {"monto_solicitado": 5_000_000, "plazo_solicitado": 24},
        },
        "messages": [],
    }

def test_resultado_escrito_en_namespace_correcto():
    result = loan_risk_engine_node(make_state_for_engine())
    assert "evaluation_results" in result, "Debe usar el namespace evaluation_results"
    assert "loan_engine" in result["evaluation_results"], "Debe tener la sub-clave loan_engine"
    assert "engine_result" not in result, "No debe existir la clave engine_result raíz"

def test_pre_aprobado_tiene_campos_requeridos():
    result = loan_risk_engine_node(make_state_for_engine())
    engine = result["evaluation_results"]["loan_engine"]
    assert engine["status_proceso"] == "PRE_APPROVED"
    assert engine["cuota_mensual"] > 0
    assert engine["cae"] > 0

# tests/test_engines_v2.py
import pytest
from app.graph.nodes.credit import loan_risk_engine_node

def make_loan_ready_state():
    """State con datos completos para ejecutar el motor de crédito."""
    return {
        "preparation_data": {"nombre": "Pedro Soto", "rut": "11111111-1", "mail": "p@e.com", "edad": 30},
        "session": {"conversation_id": "c-003", "product_intent": "LOAN"},
        "collecting_data": {
            "loan_profile": {
                "renta": 2000000,
                "antiguedad_laboral": 18,
                "nivel_estudios": "UNIVERSITARIO",
            },
            "loan_sim": {
                "monto_solicitado": 5000000,
                "plazo_solicitado": 24,
            },
        },
        "evaluation_results": {},
        "messages": [],
    }


def test_loan_engine_writes_to_correct_namespace():
    """El motor escribe en evaluation_results["loan_engine"], no en otro lugar."""
    state = make_loan_ready_state()
    result = loan_risk_engine_node(state)

    assert "evaluation_results" in result
    assert "loan_engine" in result["evaluation_results"]
    # No escribe en account_engine ni dap_engine
    assert "account_engine" not in result["evaluation_results"]


def test_loan_engine_does_not_modify_state_namespaces_except_allowed():
    """El motor no debe modificar collecting_data ni preparation_data."""
    state = make_loan_ready_state()
    result = loan_risk_engine_node(state)
    
    # Solo debe retornar las llaves que actualiza
    assert "collecting_data" not in result
    assert "preparation_data" not in result
    assert "evaluation_results" in result
    assert "session" in result


def test_loan_engine_reads_from_correct_namespaces():
    """El motor lee datos desde preparation_data y collecting_data."""
    state = make_loan_ready_state()
    result = loan_risk_engine_node(state)
    
    # Verificamos que usó la renta (2M) para calcular cuota_maxima_permitida (2M * 0.3 = 600k)
    assert result["evaluation_results"]["loan_engine"]["cuota_maxima_permitida"] == 600000


def test_loan_engine_atomic_writing():
    """Verifica que el retorno de evaluation_results contiene solo el sub-cajón del motor."""
    state = make_loan_ready_state()
    result = loan_risk_engine_node(state)
    
    # El retorno debe ser un diccionario que solo contenga los cambios atómicos
    assert list(result["evaluation_results"].keys()) == ["loan_engine"]


def test_dap_engine_writes_to_correct_namespace():
    """El motor escribe en evaluation_results["dap_engine"], no en otro lugar."""
    from app.graph.nodes.deposit import dap_investment_engine_node
    state = {
        "preparation_data": {"edad": 25},
        "session": {"conversation_id": "c-004", "product_intent": "DAP"},
        "collecting_data": {
            "dap_params": {"monto": 1000000.0, "moneda": "CLP", "plazo": 180}
        },
        "evaluation_results": {},
        "messages": [],
    }
    result = dap_investment_engine_node(state)

    assert "evaluation_results" in result
    assert "dap_engine" in result["evaluation_results"]
    assert "loan_engine" not in result["evaluation_results"]


def test_dap_engine_term_premium_calculation():
    """Verifica la fórmula de term_premium: (plazo // 30) * 0.0005."""
    from app.graph.nodes.deposit import dap_investment_engine_node
    state = {
        "preparation_data": {"edad": 25},
        "session": {"conversation_id": "c-004", "product_intent": "DAP"},
        "collecting_data": {
            "dap_params": {"monto": 1000000.0, "moneda": "CLP", "plazo": 180}
        },
        "evaluation_results": {},
        "messages": [],
    }
    result = dap_investment_engine_node(state)
    # plazo=180, 180//30=6, 6*0.0005 = 0.003
    assert result["evaluation_results"]["dap_engine"]["term_premium"] == pytest.approx(0.003)


def test_account_engine_writes_to_correct_namespace():
    """El motor escribe en evaluation_results["account_engine"], no en otro lugar."""
    from app.graph.nodes.account import account_evaluation_engine_node
    state = {
        "preparation_data": {"edad": 35},
        "session": {"conversation_id": "c-005", "product_intent": "ACCOUNT"},
        "collecting_data": {
            "account_profile": {
                "renta": 1500000,
                "antiguedad_laboral": 24,
                "nivel_estudios": "POSTGRADO"
            }
        },
        "evaluation_results": {},
        "messages": [],
    }
    result = account_evaluation_engine_node(state)

    assert "evaluation_results" in result
    assert "account_engine" in result["evaluation_results"]
    assert "loan_engine" not in result["evaluation_results"]
    assert result["evaluation_results"]["account_engine"]["base_category"] == "ADVANCE"

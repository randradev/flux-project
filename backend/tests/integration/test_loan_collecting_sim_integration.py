# tests/integration/test_loan_collecting_sim_integration.py
# REQUIEREN credenciales reales de Vertex AI.
# Ejecutar con: pytest tests/integration/test_loan_collecting_sim_integration.py -v -m integration

import pytest
from langchain_core.messages import HumanMessage, AIMessage
from app.graph.nodes.credit import loan_collecting_sim_node


pytestmark = pytest.mark.integration


def make_state(messages: list, sim_data: dict = None) -> dict:
    return {
        "messages":        messages,
        "collecting_data": {"loan_profile": {}, "loan_sim": sim_data or {}},
        "session":         {"current_node": "LOAN_COLLECTING_SIMULATION", "application_id": None},
        "preparation_data": {"nombre": "Ana Torres"},
    }


class TestExtraccionNulosSim:
    """Verifica que el extractor no alucine datos en simulación."""
    
    def test_saludo_no_contamina_sim(self):
        state = make_state([
            AIMessage(content="¿Cuánto dinero necesitas y en cuántas cuotas?"),
            HumanMessage(content="Hola! ¿Cómo vas?"),
        ])
        result = loan_collecting_sim_node(state)
        sim = result["collecting_data"]["loan_sim"]
        
        assert sim == {}, "Un saludo no debe inyectar montos ni plazos."
        assert "messages" in result


class TestExtraccionPositivaSim:
    """Verifica la captura de jerga chilena y conversiones."""
    
    def test_monto_jerga_chilena(self):
        state = make_state([HumanMessage(content="Necesito unos 2 palitos y medio")])
        result = loan_collecting_sim_node(state)
        sim = result["collecting_data"]["loan_sim"]
        
        assert sim.get("monto_solicitado") == 2_500_000, \
            f"Debe extraer 2.500.000 de '2 palitos y medio'. Valor: {sim.get('monto_solicitado')}"
    
    def test_plazo_conversion_años(self):
        state = make_state([HumanMessage(content="Pagaría en 3 años")])
        result = loan_collecting_sim_node(state)
        sim = result["collecting_data"]["loan_sim"]
        
        assert sim.get("plazo_solicitado") == 36, \
            f"3 años debe ser 36 meses. Valor: {sim.get('plazo_solicitado')}"
    
    def test_datos_completos_avance_silencioso(self):
        state = make_state([HumanMessage(content="Quiero 5 palos a 2 años")])
        result = loan_collecting_sim_node(state)
        
        assert "messages" not in result or len(result.get("messages", [])) == 0, \
            "Debe avanzar silenciosamente si tiene ambos datos."
        
        sim = result["collecting_data"]["loan_sim"]
        assert sim["monto_solicitado"] == 5_000_000
        assert sim["plazo_solicitado"] == 24


class TestMergeAcumulativoSim:
    """Verifica que se acumulen datos entre turnos reales."""
    
    def test_monto_y_luego_plazo(self):
        # Turno 1: Ya dio el monto
        monto_previo = {"monto_solicitado": 1_000_000}
        state = make_state(
            messages=[
                AIMessage(content="¡Anotado! 1 millón. ¿En cuántas cuotas lo pagarías?"),
                HumanMessage(content="En unas 12 cuotas"),
            ],
            sim_data=monto_previo
        )
        result = loan_collecting_sim_node(state)
        sim = result["collecting_data"]["loan_sim"]
        
        assert sim["monto_solicitado"] == 1_000_000
        assert sim["plazo_solicitado"] == 12

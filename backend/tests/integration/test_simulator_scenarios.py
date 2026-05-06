# tests/integration/test_simulator_scenarios.py
"""
Suite de validación automática de los escenarios del simulador.
Usa MemorySaver directamente para no depender de Supabase.
"""
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage
from scripts.simulate_conversation import ConversationSimulator, MOCK_USER, MOCK_SESSION_NEW


def _mock_llm():
    """Mock del LLM para tests rápidos sin API."""
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content="Respuesta mockeada de Flux.")
    return mock


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
@patch("app.graph.nodes.common._intent_extractor")
@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_scenario_resume_preserves_current_node(
    mock_conv, mock_sem, mock_intent_ext, mock_profile_ext, mock_gen
):
    """
    INVARIANTE PRINCIPAL: En una sesión reanudada con current_node=LOAN_COLLECTING_PROFILE,
    el grafo no debe pasar por loan_init ni generar un segundo saludo.
    """
    from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema
    from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction

    mock_gen.invoke.return_value = MagicMock(content="¿Cuánto tiempo llevas en tu trabajo?")
    mock_profile_ext.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        razonamiento="Antigüedad detectada",
        antiguedad_laboral=36,
    )

    session_resumed = {
        **MOCK_SESSION_NEW,
        "current_node": "LOAN_COLLECTING_PROFILE",
        "product_intent": "LOAN",
    }
    sim = ConversationSimulator(MOCK_USER, session_resumed)
    result = sim.send("llevo 3 años trabajando")

    # Verificar que no hubo violaciones
    assert len(sim.validation_log) == 0, f"Violaciones detectadas: {sim.validation_log}"

    # Verificar que el current_node sigue en LOAN_COLLECTING_PROFILE
    final_cn = result.get("session", {}).get("current_node", "")
    assert final_cn == "LOAN_COLLECTING_PROFILE"


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_scenario_button_click_sets_punto_de_guardado(mock_conv, mock_sem, mock_gen):
    """
    Después del primer turno con product_intent=LOAN (clic de botón),
    el current_node debe quedar en LOAN_COLLECTING_PROFILE (Punto de Guardado).
    """
    mock_gen.invoke.return_value = MagicMock(content="Hola Juan! ¿Cuál es tu renta?")

    sim = ConversationSimulator(MOCK_USER, MOCK_SESSION_NEW)
    result = sim.send("", inject_product_intent="LOAN")

    current_node = result.get("session", {}).get("current_node", "")
    assert current_node == "LOAN_COLLECTING_PROFILE", (
        f"Punto de Guardado no establecido. current_node fue: {current_node}"
    )

# tests/integration/test_intra_turn_jump.py
import sys
from unittest.mock import MagicMock, patch

# Mock infra/config before any other imports
sys.modules["app.infra.gemini_client"] = MagicMock()
sys.modules["app.infra.supabase"] = MagicMock()
sys.modules["app.infra.checkpointer"] = MagicMock()
sys.modules["app.config"] = MagicMock()

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from app.graph.workflow import build_graph
from app.graph.constants import CompletedStep

@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
@patch("app.graph.nodes.common.update_application_semaphores", return_value=None)
@patch("app.graph.nodes.common.update_conversation_node", return_value=None)
def test_intra_turn_jump_profile_to_sim(mock_conv, mock_sem, mock_profile_ext, mock_gen):
    from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction
    
    # Mocking extractor
    mock_profile_ext.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        razonamiento="Nivel estudios detectado",
        nivel_estudios="UNIVERSITARIO",
    )
    # Mocking generator
    mock_gen.invoke.return_value = MagicMock(
        content="¡Listo tu perfil! Ahora, ¿cuánto necesitas?"
    )

    # Building graph with memory checkpointer
    graph = build_graph().compile(checkpointer=MemorySaver())
    thread_cfg = {"configurable": {"thread_id": "test-intra-01"}}

    state_input = {
        "messages": [HumanMessage(content="Soy ingeniero civil")],
        "user_data": {"full_name": "Luis Morales", "birth_date": "1988-03-10", "rut": "", "email": ""},
        "session": {
            "product_intent": "LOAN",
            "current_node": "LOAN_COLLECTING_PROFILE",
            "progress": {"loan": {"profile_completed": False}},
            "application_id": None,
        },
        "preparation_data": {"nombre": "Luis Morales", "edad": 36, "rut": "", "mail": ""},
        "collecting_data": {
            "loan_profile": {"renta": 2500000, "antiguedad_laboral": 48},  # Solo falta nivel_estudios
            "loan_sim": {}
        },
    }

    result = graph.invoke(state_input, config=thread_cfg)

    # 1. Verificar que se saltó a simulación (Llamada B de simulación generó mensaje)
    # loan_collecting_profile (silencioso) -> loan_collecting_simulation (generador)
    messages = result.get("messages", [])
    ai_messages = [m for m in messages if isinstance(m, AIMessage)]
    assert len(ai_messages) >= 1
    assert "cuánto necesitas" in ai_messages[-1].content

    # 2. Verificar estado final
    final_session = result.get("session", {})
    assert final_session.get("current_node") == "LOAN_COLLECTING_SIMULATION"
    # El nodo simulación debe limpiar la flag al final de su ejecución
    assert final_session.get("just_completed_step") is None
    assert final_session.get("progress", {}).get("loan", {}).get("profile_completed") is True

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])

import pytest
import sys
from unittest.mock import MagicMock, patch

# ======================================================================================================
# MOCK DE INFRAESTRUCTURA (Antes de importar la App)
# ======================================================================================================

# Mock de Supabase para evitar inicialización de red/keys
mock_supabase_lib = MagicMock()
sys.modules["supabase"] = mock_supabase_lib

# Mock de LangChain Vertex para evitar validación de credenciales Google
sys.modules["langchain_google_vertexai"] = MagicMock()

from langchain_core.messages import AIMessage, HumanMessage
from app.graph.nodes.credit import loan_collecting_profile_node, loan_collecting_simulation_node
from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction, LoanSimExtraction

# ======================================================================================================
# FIXTURES Y MOCKS
# ======================================================================================================

@pytest.fixture
def base_state():
    """Estado inicial limpio para las pruebas."""
    return {
        "messages": [],
        "user_data": {
            "full_name": "Juan Perez",
            "birth_date": "1990-01-01"
        },
        "session": {
            "application_id": "test-app-123",
            "current_node": "WELCOME_NODE"
        },
        "preparation_data": {
            "nombre": "Juan Perez",
            "rut": "12.345.678-9",
            "mail": "juan@perez.cl",
            "edad": 34
        },
        "collecting_data": {
            "loan_profile": {},
            "loan_sim": {}
        }
    }

def mock_profile_response(renta=None, ant=None, estudios=None):
    return LoanProfileExtraction(
        renta=renta,
        antiguedad_laboral=ant,
        nivel_estudios=estudios,
        datos_completos=(renta is not None and ant is not None and estudios is not None)
    )

def mock_sim_response(monto=None, plazo=None):
    return LoanSimExtraction(
        monto_solicitado=monto,
        plazo_solicitado=plazo,
        datos_completos=(monto is not None and plazo is not None)
    )

# ======================================================================================================
# TESTS DE AUDITORÍA TÉCNICA (EXTRACCIÓN Y ESTADO)
# ======================================================================================================

@patch("app.graph.nodes.credit.update_application_semaphores")
@patch("app.graph.nodes.credit._profile_extractor")
def test_2_1_profile_extraction_complete(mock_extractor, mock_semaforo, base_state):
    """
    AUDITORÍA: Extracción completa en un solo mensaje.
    Input: 'Gano 1 millón y medio, llevo 3 años en la pega y soy universitario'
    Expectativa: Renta=1.5M, Ant=36, Estudios=UNIVERSITARIO. Avance silencioso.
    """
    base_state["messages"].append(HumanMessage(content="Gano 1 millón y medio, llevo 3 años en la pega y soy universitario"))
    
    # Simular lo que Gemini extraería tras procesar el prompt con reglas Flux
    mock_extractor.invoke.return_value = mock_profile_response(renta=1500000, ant=36, estudios="UNIVERSITARIO")
    
    result = loan_collecting_profile_node(base_state)
    
    profile = result["collecting_data"]["loan_profile"]
    assert profile["renta"] == 1500000
    assert profile["antiguedad_laboral"] == 36
    assert profile["nivel_estudios"] == "UNIVERSITARIO"
    assert "messages" not in result  # No debe haber mensaje de re-pregunta
    assert mock_semaforo.called

@patch("app.graph.nodes.credit.update_application_semaphores")
@patch("app.graph.nodes.credit._profile_extractor")
def test_2_2_profile_extraction_partial(mock_extractor, mock_semaforo, base_state):
    """
    AUDITORÍA: Extracción parcial y re-pregunta Flux.
    Input: 'Gano 800 lucas'
    Expectativa: Renta=800K, Re-pregunta por antigüedad y estudios.
    """
    base_state["messages"].append(HumanMessage(content="Gano 800 lucas"))
    
    mock_extractor.invoke.return_value = mock_profile_response(renta=800000)
    
    result = loan_collecting_profile_node(base_state)
    
    assert result["collecting_data"]["loan_profile"]["renta"] == 800000
    assert "messages" in result
    msg_content = result["messages"][0].content
    assert "renta de $800,000" in msg_content
    assert "hace cuánto trabajas" in msg_content  # Label amigable de antigüedad
    assert "estudios" in msg_content

@patch("app.graph.nodes.credit.update_application_semaphores")
@patch("app.graph.nodes.credit._profile_extractor")
def test_2_3_profile_merge_logic(mock_extractor, mock_semaforo, base_state):
    """
    AUDITORÍA: Merge defensivo (Persistencia).
    Contexto: El usuario ya dio la renta. Ahora da la antigüedad.
    Expectativa: El estado debe conservar la renta previa y agregar la antigüedad.
    """
    # Estado previo con renta
    base_state["collecting_data"]["loan_profile"] = {"renta": 900000}
    base_state["messages"].append(HumanMessage(content="Llevo 8 meses en la pega"))
    
    # Gemini extrae solo lo nuevo
    mock_extractor.invoke.return_value = mock_profile_response(ant=8)
    
    result = loan_collecting_profile_node(base_state)
    
    profile = result["collecting_data"]["loan_profile"]
    assert profile["renta"] == 900000  # CRÍTICO: No se borró
    assert profile["antiguedad_laboral"] == 8
    assert "estudios" in result["messages"][0].content

@patch("app.graph.nodes.credit.update_application_semaphores")
@patch("app.graph.nodes.credit._sim_extractor")
def test_2_4_simulation_extraction_complete(mock_extractor, mock_semaforo, base_state):
    """
    AUDITORÍA: Extracción de Simulación.
    Input: 'Necesito 5 palos a 2 años'
    Expectativa: Monto=5M, Plazo=24. Avance a LOAN_COLLECTING_SIMULATION.
    """
    base_state["messages"].append(HumanMessage(content="Necesito 5 palos a 2 años"))
    
    mock_extractor.invoke.return_value = mock_sim_response(monto=5000000, plazo=24)
    
    result = loan_collecting_simulation_node(base_state)
    
    sim = result["collecting_data"]["loan_sim"]
    assert sim["monto_solicitado"] == 5000000
    assert sim["plazo_solicitado"] == 24
    assert result["session"]["current_node"] == "LOAN_COLLECTING_SIMULATION"
    assert "messages" not in result

@patch("app.graph.nodes.credit.update_application_semaphores")
@patch("app.graph.nodes.credit._profile_extractor")
def test_2_5_ambiguous_input(mock_extractor, mock_semaforo, base_state):
    """
    AUDITORÍA: Manejo de ambigüedad.
    Input: 'No sé, lo que sea'
    Expectativa: Todo None, re-pregunta general de Flux.
    """
    base_state["messages"].append(HumanMessage(content="No sé, lo que sea"))
    
    mock_extractor.invoke.return_value = mock_profile_response() # Todo None
    
    result = loan_collecting_profile_node(base_state)
    
    assert result["collecting_data"]["loan_profile"] == {}
    assert "¡Ya! Para seguir con tu perfil" in result["messages"][0].content

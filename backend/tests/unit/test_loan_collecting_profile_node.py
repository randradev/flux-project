# tests/unit/test_loan_collecting_profile_node.py
# No requiere credenciales de Vertex AI — mockea ambos modelos.

from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from app.graph.nodes.credit import loan_collecting_profile_node
from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction


def make_state(user_msg: str, profile: dict = None):
    return {
        "messages":       [HumanMessage(content=user_msg)],
        "collecting_data": {"loan_profile": profile or {}, "loan_sim": {}},
        "session":        {"current_node": "LOAN_COLLECTING_PROFILE", "application_id": None},
        "preparation_data": {"nombre": "Juan Pérez", "edad": 30},
    }


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_avance_silencioso_no_invoca_generador(mock_extractor, mock_generator):
    """Con perfil completo: Llamada B (generador) NO debe invocarse."""
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        renta=2_000_000,
        antiguedad_laboral=36,
        nivel_estudios="UNIVERSITARIO"
    )
    
    result = loan_collecting_profile_node(
        make_state("Gano 2 millones, llevo 3 años, soy universitario")
    )
    
    mock_generator.invoke.assert_not_called()  # ← La prueba crítica
    assert "messages" not in result or len(result.get("messages", [])) == 0
    assert result["collecting_data"]["loan_profile"]["renta"] == 2_000_000


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_saludo_no_contamina_state(mock_extractor, mock_generator):
    """Un saludo no debe modificar el loan_profile."""
    mock_extractor.invoke.return_value = LoanProfileExtraction(intencion="SALUDO")
    mock_generator.invoke.return_value = MagicMock(content="¡Hola! Estamos en tu solicitud de crédito. ¿Cuál es tu renta?")
    
    state = make_state("Hola!", profile={"renta": 1_000_000})  # Renta ya conocida
    result = loan_collecting_profile_node(state)
    
    # El perfil no debe haber cambiado
    assert result["collecting_data"]["loan_profile"].get("renta") == 1_000_000
    # El generador sí debe haberse invocado
    mock_generator.invoke.assert_called_once()
    # El resultado debe tener un mensaje
    assert "messages" in result and len(result["messages"]) > 0


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_centinelas_pydantic_no_actualizan_perfil(mock_extractor, mock_generator):
    """Si el LLM alucina centinelas, Pydantic los normaliza a None y el perfil no se contamina."""
    # Simular que el LLM retornó valores centinela que Pydantic ya normalizó
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        renta=None,               # Pydantic normalizó 0 a None
        antiguedad_laboral=None,  # Pydantic normalizó -1 a None
        nivel_estudios="MEDIA"    # Válido
    )
    mock_generator.invoke.return_value = MagicMock(content="Casi listo, solo me falta tu renta y antigüedad.")
    
    state = make_state("algo irrelevante")
    result = loan_collecting_profile_node(state)
    
    profile = result["collecting_data"]["loan_profile"]
    assert profile.get("renta") is None,              "renta=0 no debe escribirse"
    assert profile.get("antiguedad_laboral") is None,  "ant=-1 no debe escribirse"
    assert profile.get("nivel_estudios") == "MEDIA",   "MEDIA sí debe escribirse"


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_merge_acumulativo_entre_turnos(mock_extractor, mock_generator):
    """Los datos de turnos anteriores se preservan cuando llegan datos nuevos."""
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        antiguedad_laboral=24  # Solo antigüedad nueva
    )
    mock_generator.invoke.return_value = MagicMock(content="¡Anotado! ¿Y tu nivel de estudios?")
    
    # Estado previo: ya tiene renta
    state = make_state("Llevo 2 años trabajando", profile={"renta": 1_500_000})
    result = loan_collecting_profile_node(state)
    
    profile = result["collecting_data"]["loan_profile"]
    assert profile.get("renta") == 1_500_000,         "La renta previa debe conservarse"
    assert profile.get("antiguedad_laboral") == 24,    "La nueva antigüedad debe guardarse"


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_un_solo_return_transaccional(mock_extractor, mock_generator):
    """El nodo debe retornar siempre los tres campos del State en un solo dict."""
    mock_extractor.invoke.return_value = LoanProfileExtraction(intencion="SALUDO")
    mock_generator.invoke.return_value = MagicMock(content="Hola, retomemos.")
    
    result = loan_collecting_profile_node(make_state("Hola"))
    
    assert "collecting_data" in result, "collecting_data debe estar siempre en el output"
    assert "session" in result,         "session debe estar siempre en el output"
    assert result["session"]["current_node"] == "LOAN_COLLECTING_PROFILE"

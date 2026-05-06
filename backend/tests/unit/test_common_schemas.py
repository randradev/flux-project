# tests/unit/test_common_schemas.py
import pytest
from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema


def test_valid_intent_loan():
    schema = IntentExtractionSchema(intencion="LOAN", razonamiento="Es un crédito")
    assert schema.intencion == "LOAN"

def test_valid_intent_general():
    schema = IntentExtractionSchema(intencion="GENERAL", razonamiento="Saludo")
    assert schema.intencion == "GENERAL"

def test_unknown_intent_normalized_to_general():
    # El validador normalize_intent debe forzar GENERAL si no está en el set
    schema = IntentExtractionSchema(intencion="UNKNOWN_PRODUCT", razonamiento="")
    assert schema.intencion == "GENERAL"

def test_placeholder_normalization():
    # Caso: El LLM devuelve un placeholder de Vertex AI
    schema = IntentExtractionSchema(intencion="NULL", razonamiento="", confianza="NONE")
    assert schema.intencion == "GENERAL"
    assert schema.confianza == "BAJA"

def test_lowercase_intent_normalized():
    schema = IntentExtractionSchema(intencion="loan", razonamiento="")
    assert schema.intencion == "LOAN"

def test_default_confianza_is_media():
    schema = IntentExtractionSchema(intencion="LOAN", razonamiento="")
    assert schema.confianza == "MEDIA"

def test_invalid_confianza_normalized_to_baja():
    # Según el código del usuario, valores inválidos en confianza retornan BAJA
    schema = IntentExtractionSchema(intencion="LOAN", razonamiento="", confianza="MUY_ALTA")
    assert schema.confianza == "BAJA"

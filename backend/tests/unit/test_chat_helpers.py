import sys
from unittest.mock import MagicMock

# Mocking dependencies that might be missing or trigger complex imports
mock_modules = [
    'app.api.deps',
    'app.graph.workflow',
    'app.infra.threading',
    'app.infra.supabase',
    'langchain_core.messages',
    'fastapi',
    'fastapi.responses'
]

for module in mock_modules:
    sys.modules[module] = MagicMock()

import pytest
from app.api.v1.chat import build_node_transition_payload, enrich_payload_with_labels

def test_build_node_transition_payload_basic():
    """Valida que se construya el payload básico correctamente."""
    node_output = {
        "session": {
            "current_node": "LOAN_INIT",
            "product_intent": "LOAN",
            "application_id": "test-app-123"
        }
    }
    payload = build_node_transition_payload("loan_init", node_output)
    
    assert payload["type"] == "node_transition"
    assert payload["node"] == "LOAN_INIT"
    assert payload["product_intent"] == "LOAN"
    assert payload["application_id"] == "test-app-123"
    assert payload["node_status"] == "SUCCESS"

def test_build_node_transition_payload_with_namespaces():
    """Valida que se incluyan solo los namespaces presentes en el output."""
    node_output = {
        "session": {"current_node": "LOAN_PRE_APPROVED"},
        "transparency_data": {"loan": {"monto": "$5M"}},
        "collecting_data": None,
        "evaluation_results": {"score": 700}
    }
    payload = build_node_transition_payload("pre_approved", node_output)
    
    assert "transparency_data" in payload
    assert "evaluation_results" in payload
    assert "collecting_data" not in payload
    assert payload["transparency_data"]["loan"]["monto"] == "$5M"

def test_enrich_payload_with_labels():
    """Valida que se agreguen las etiquetas correctas desde el diccionario maestro."""
    payload = {
        "node": "LOAN_COLLECTING_PROFILE"
    }
    enriched = enrich_payload_with_labels(payload)
    
    assert enriched["friendly_label"] == "Perfil financiero"
    assert enriched["progress_percent"] == 20

def test_enrich_payload_unknown_node():
    """Valida el fallback para nodos no mapeados."""
    payload = {
        "node": "UNKNOWN_NODE"
    }
    enriched = enrich_payload_with_labels(payload)
    
    assert enriched["friendly_label"] == "UNKNOWN_NODE"
    assert enriched["progress_percent"] is None

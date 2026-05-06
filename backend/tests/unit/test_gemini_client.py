# tests/unit/test_gemini_client.py
# (Prueba de configuración, no de comportamiento del modelo)

from unittest.mock import patch, MagicMock
from app.infra.gemini_client import get_structured_model, get_generation_model
from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction

def test_get_structured_model_retorna_objeto_invocable():
    """Verifica que la función retorna sin error y el objeto tiene .invoke()"""
    with patch("app.infra.gemini_client._init_global"):
        with patch("app.infra.gemini_client.ChatVertexAI") as MockChat:
            mock_instance = MagicMock()
            mock_instance.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_instance
            
            model = get_structured_model(LoanProfileExtraction)
            
            # Verificar que se llamó con temperature=0.0
            call_kwargs = MockChat.call_args.kwargs
            assert call_kwargs["temperature"] == 0.0, \
                f"El extractor debe usar temperature=0.0, recibió {call_kwargs['temperature']}"
            
            # Verificar que se usó function_calling
            mock_instance.with_structured_output.assert_called_once_with(
                LoanProfileExtraction, method="function_calling"
            )

def test_get_generation_model_usa_temperatura_mayor():
    with patch("app.infra.gemini_client._init_global"):
        with patch("app.infra.gemini_client.ChatVertexAI") as MockChat:
            MockChat.return_value = MagicMock()
            get_generation_model()
            call_kwargs = MockChat.call_args.kwargs
            assert call_kwargs["temperature"] == 0.7, \
                f"El generador debe usar temperature=0.7, recibió {call_kwargs['temperature']}"

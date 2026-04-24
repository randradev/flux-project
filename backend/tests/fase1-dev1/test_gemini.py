"""Tests de integración para el cliente de Vertex AI."""
import pytest


def test_gemini_client_imports_without_error():
    """Verifica que el módulo gemini_client se importa sin lanzar excepción."""
    from app.infra import gemini_client
    assert gemini_client is not None


def test_chat_model_responds_to_simple_prompt():
    """
    Verifica conectividad real con Vertex AI enviando un prompt simple.
    ADVERTENCIA: Este test hace una llamada real a la API. Requiere
    credenciales válidas en /secrets/gcp-service-account.json.
    """
    from app.infra.gemini_client import get_chat_model
    from langchain_core.messages import HumanMessage

    model = get_chat_model()
    response = model.invoke([HumanMessage(content="Di solo la palabra: FLUX")])

    assert response is not None
    assert response.content is not None
    assert len(response.content) > 0
    # El modelo debería responder algo relacionado con "FLUX"
    print(f"\nRespuesta de Gemini: {response.content}")


def test_embeddings_model_generates_vector():
    """
    Verifica que el modelo de embeddings genera un vector de dimensión correcta.
    ADVERTENCIA: Este test hace una llamada real a la API.
    """
    from app.infra.gemini_client import get_embeddings_model

    model = get_embeddings_model()
    embedding = model.embed_query("crédito de consumo")

    assert embedding is not None
    assert isinstance(embedding, list)
    assert len(embedding) > 0  # text-embedding-004 genera vectores de 768 dimensiones
    assert len(embedding) == 768, f"Dimensión esperada 768, obtenida {len(embedding)}"
    print(f"\nDimensión del vector: {len(embedding)}")


def test_credentials_are_not_api_key():
    """
    Verifica que el sistema usa ADC (archivo JSON) y no GOOGLE_API_KEY.
    Esta es una restricción de seguridad del proyecto.
    """
    from app.infra import gemini_client  # Importación para activar la inyección de env vars
    import os
    assert "GOOGLE_API_KEY" not in os.environ, \
        "ERROR: Se detectó GOOGLE_API_KEY en el entorno. El proyecto debe usar ADC (JSON de cuenta de servicio)."
    assert "GOOGLE_APPLICATION_CREDENTIALS" in os.environ, \
        "ERROR: GOOGLE_APPLICATION_CREDENTIALS no está configurada."
    cred_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    assert cred_path.endswith(".json"), \
        "GOOGLE_APPLICATION_CREDENTIALS debe apuntar a un archivo .json"
    assert os.path.exists(cred_path), \
        f"El archivo de credenciales no existe en: {cred_path}"
"""Tests unitarios para la carga de configuración."""
import pytest
from pydantic import ValidationError


def test_settings_load_successfully():
    """Verifica que Settings carga sin errores con un .env válido."""
    from app.config import settings
    assert settings.app_name == "FLUX-Backend"
    assert settings.google_cloud_location == "us-central1"
    assert settings.debug is True  # Según el .env de desarrollo


def test_settings_has_required_fields():
    """Verifica que todos los campos requeridos están presentes y no son None."""
    from app.config import settings
    assert settings.supabase_url is not None
    assert settings.supabase_anon_key is not None
    assert settings.database_url is not None
    assert settings.google_cloud_project_id is not None


def test_settings_missing_required_field_raises_error():
    """
    Verifica que pydantic-settings lanza ValidationError si falta un campo requerido.
    Este test usa monkeypatch para simular un .env incompleto.
    """
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, {}, clear=True):
        # En Pydantic V2, ValidationError es el estándar.
        with pytest.raises((ValidationError, Exception)):
            from pydantic_settings import BaseSettings
            class BrokenSettings(BaseSettings):
                supabase_url: str  # Sin valor por defecto → debe fallar
                model_config = {"env_file": "/nonexistent/.env"}
            BrokenSettings()


def test_health_endpoint_returns_200():
    """Verifica que GET /health devuelve 200 y el JSON esperado."""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service"] == "FLUX-Backend"
    assert "engine" in data


def test_health_endpoint_structure():
    """Verifica que el JSON de /health contiene todos los campos definidos."""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/health")
    data = response.json()

    required_fields = ["status", "service", "version", "engine", "debug_mode"]
    for field in required_fields:
        assert field in data, f"Campo '{field}' ausente en la respuesta de /health"

# ── PRUEBA 5.A | Test de Integración: Validación de JWT ──────────────────

# Objetivo: Verificar que get_current_user acepta tokens válidos y rechaza inválidos.

"""Tests de autenticación."""
import pytest
from fastapi.testclient import TestClient


def test_protected_endpoint_rejects_missing_token():
    """
    Verifica que un endpoint protegido rechaza requests sin token.
    Para esta prueba, se agrega un endpoint de test temporal a la app.
    """
    from main import app
    from fastapi import Depends
    from app.api.deps import get_current_user

    # Endpoint de prueba (solo para testing)
    @app.get("/test-auth-only")
    async def test_auth_endpoint(user=Depends(get_current_user)):
        return {"user_id": user["user_id"]}

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/test-auth-only")
    # Sin token → debe retornar 403 (HTTPBearer) o 401
    assert response.status_code in [401, 403]


def test_protected_endpoint_rejects_invalid_token():
    """Verifica que un token malformado es rechazado."""
    from main import app
    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        "/test-auth-only",
        headers={"Authorization": "Bearer token_invalido_definitivamente"}
    )
    assert response.status_code in [401, 403]

# ── PRUEBA 5.B | Test Unitario: Thread ID ──────────────────

def test_get_langgraph_config_format():
    """Verifica que get_langgraph_config retorna el formato correcto."""
    from app.infra.threading import get_langgraph_config
    import uuid

    thread_id = str(uuid.uuid4())
    config = get_langgraph_config(thread_id)

    assert "configurable" in config
    assert "thread_id" in config["configurable"]
    assert config["configurable"]["thread_id"] == thread_id


def test_get_or_create_thread_creates_new_conversation():
    """
    Verifica que get_or_create_thread crea una conversación nueva en la DB.
    Requiere un usuario de prueba en la DB.
    """
    from app.infra.supabase import supabase_client
    from app.infra.threading import get_or_create_thread

    users = supabase_client.table("users").select("id").limit(1).execute()
    if not users.data:
        pytest.skip("No hay usuarios en la DB.")

    user_id = users.data[0]["id"]
    thread_id = get_or_create_thread(user_id=user_id)

    assert thread_id is not None
    assert len(thread_id) == 36  # Formato UUID

    # Limpieza
    supabase_client.table("conversations").delete().eq("id", thread_id).execute()
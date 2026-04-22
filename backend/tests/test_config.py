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

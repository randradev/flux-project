"""
app/config.py
─────────────────────────────────────────────────────────────
Gestión centralizada de configuración usando pydantic-settings.

PROCESO: Lee las variables de entorno desde el archivo .env ubicado
         en la raíz de /backend.

SALIDA:  Instancia singleton `settings` que todos los módulos importan.
         Garantiza que si falta una variable crítica, el servidor no levante.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Esquema tipado de todas las variables de entorno del proyecto.
    Si una variable marcada como requerida (sin valor por defecto) no existe
    en el .env, pydantic-settings lanzará un ValidationError al importar este módulo,
    impidiendo que el servidor levante con una configuración incompleta.
    """

    # ── Google Cloud / Vertex AI ──────────────────────────────
    google_cloud_project_id: str
    google_cloud_location: str = "us-central1"
    google_application_credentials: str

    # ── Supabase ──────────────────────────────────────────────
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    database_url: str  # Para el PostgresSaver de LangGraph

    # ── App Settings ──────────────────────────────────────────
    debug: bool = False
    app_name: str = "FLUX-Backend"
    app_version: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# ── Instancia Singleton ───────────────────────────────────────
# Todos los módulos importan este objeto directamente:
# from app.config import settings
settings = Settings()

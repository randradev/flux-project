"""
app/infra/gemini_client.py
─────────────────────────────────────────────────────────────
Cliente centralizado para interacción con Vertex AI (Gemini).

PROCESO: Implementa la estrategia Dual-Init para evitar errores 404:
  - Brazo Regional (us-central1): Para modelos de Embeddings.
    El modelo `text-embedding-004` solo está disponible regionalmente.
  - Brazo Global (aiplatform): Para Chat y Extracción.
    El modelo `gemini-2.0-flash` usa el endpoint global de aiplatform.

AUTENTICACIÓN: Usa Application Default Credentials (ADC) apuntando al
  archivo JSON de cuenta de servicio en /secrets/. No se usa API Key.

SALIDA:  Funciones y modelos listos para ser importados por los nodos
         del grafo. No se instancian conexiones hasta que se llaman.
"""

import os
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from langchain_google_vertexai import ChatVertexAI, VertexAIEmbeddings

from app.config import settings

# ── Inyección de Credenciales ADC ────────────────────────────
# Se hace aquí, al nivel del módulo, para garantizar que el SDK
# de Google encuentra las credenciales antes de cualquier llamada.
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
os.environ["GOOGLE_CLOUD_PROJECT"] = settings.google_cloud_project_id

# ── Modelos ───────────────────────────────────────────────────

def get_chat_model() -> ChatVertexAI:
    """
    Retorna el modelo de chat para los nodos conversacionales del grafo.
    Usa configuración explícita para evitar conflictos con el RAG.
    """
    return ChatVertexAI(
        model_name="gemini-3-flash-preview",
        project=settings.google_cloud_project_id,
        location="us-central1",
        api_endpoint="aiplatform.googleapis.com", # <--- OBLIGATORIO
        temperature=0.3,
        max_output_tokens=2048,
    )


def get_structured_model(schema) -> ChatVertexAI:
    """
    Llamada A — Extractor de entidades financieras.
    Usa el endpoint global de forma explícita para evitar conflictos con embeddings.
    """
    return ChatVertexAI(
        model_name="gemini-3-flash-preview",
        project=settings.google_cloud_project_id,
        location="us-central1",
        api_endpoint="aiplatform.googleapis.com", # <--- Forzamos el endpoint correcto aquí
        temperature=0,
    ).with_structured_output(schema)

def get_generation_model() -> ChatVertexAI:
    """
    Llamada B — Generador de respuestas naturales (Persona Flux).
    """
    return ChatVertexAI(
        model_name="gemini-3-flash-preview",
        project=settings.google_cloud_project_id,
        location="us-central1",
        api_endpoint="aiplatform.googleapis.com", # <--- Forzamos el endpoint correcto aquí
        temperature=0.2,
        max_output_tokens=2048,
    )

def get_embeddings_model() -> VertexAIEmbeddings:
    """
    Retorna el modelo de embeddings para el sistema RAG de forma aislada.
    """
    # Mantenemos tu hack de SafetySettingsType por compatibilidad de versiones
    from langchain_google_vertexai import embeddings as v_embeddings
    if not hasattr(v_embeddings, "SafetySettingsType"):
        from typing import Any
        setattr(v_embeddings, "SafetySettingsType", Any)
    
    try:
        VertexAIEmbeddings.model_rebuild()
    except Exception:
        pass

    return VertexAIEmbeddings(
        model_name="text-embedding-004",
        project=settings.google_cloud_project_id,
        location=settings.google_cloud_location, # <--- Usará el endpoint regional por defecto
    )

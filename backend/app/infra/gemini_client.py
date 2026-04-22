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


# ── Inicialización Regional (Embeddings) ─────────────────────
def _init_regional():
    """
    Inicializa Vertex AI apuntando a la región us-central1.
    Necesario para acceder al modelo de embeddings.
    """
    vertexai.init(
        project=settings.google_cloud_project_id,
        location=settings.google_cloud_location,
    )


# ── Inicialización Global (Chat / Extracción) ────────────────
def _init_global():
    """
    Inicializa Vertex AI con el endpoint global de aiplatform.
    El modelo gemini-3-flash-preview requiere este endpoint específico.
    """
    vertexai.init(
        project=settings.google_cloud_project_id,
        location="us-central1",
        api_endpoint="aiplatform.googleapis.com"
    )



# ── Modelos ───────────────────────────────────────────────────

def get_chat_model() -> ChatVertexAI:
    """
    Retorna el modelo de chat para los nodos conversacionales del grafo.

    INPUT:  Ninguno.
    PROCESO: Inicializa el brazo global y retorna ChatVertexAI con el modelo flash.
    OUTPUT: Instancia de ChatVertexAI lista para invocación.

    Uso en nodos: `model = get_chat_model(); response = model.invoke(messages)`
    """
    _init_global()
    return ChatVertexAI(
        model_name="gemini-3-flash-preview",
        project=settings.google_cloud_project_id,
        location=settings.google_cloud_location,  # Restauramos la referencia lógica
        api_endpoint="aiplatform.googleapis.com", # <--- OBLIGATORIO para evitar el 404
        temperature=0.3,   # Baja para respuestas más deterministas en extracción
        max_output_tokens=2048,
    )


def get_structured_model(schema) -> ChatVertexAI:
    """
    Retorna el modelo de chat con salida estructurada (for entity extraction).

    INPUT:  schema — Pydantic BaseModel o TypedDict que define la estructura esperada.
    PROCESO: Usa with_structured_output para que el LLM devuelva JSON validado.
    OUTPUT: Modelo con structured output configurado.

    Uso en nodos de recolección: `model = get_structured_model(RentaSchema)`
    """
    _init_global()
    base_model = ChatVertexAI(
        model_name="gemini-3-flash-preview",
        project=settings.google_cloud_project_id,
        location=settings.google_cloud_location,  # Restauramos la referencia lógica
        api_endpoint="aiplatform.googleapis.com", # <--- OBLIGATORIO para evitar el 404
        temperature=0.1,  # Mínima temperatura para extracción precisa
    )
    return base_model.with_structured_output(schema)


def get_embeddings_model() -> VertexAIEmbeddings:
    """
    Retorna el modelo de embeddings para el sistema RAG.

    INPUT:  Ninguno.
    PROCESO: Inicializa el brazo regional y retorna VertexAIEmbeddings.
    OUTPUT: Instancia de VertexAIEmbeddings lista para generar vectores.
    """
    _init_regional()
    return VertexAIEmbeddings(
        model_name="text-embedding-004",
        project=settings.google_cloud_project_id,
        location=settings.google_cloud_location,
    )
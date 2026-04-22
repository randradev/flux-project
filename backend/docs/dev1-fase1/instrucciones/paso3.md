# PASO 3 — Configuración de Vertex AI (Gemini)

**Objetivo:** Implementar el cliente de Gemini con la estrategia Dual-Init, configurar las credenciales de Application Default Credentials (ADC) y verificar conectividad real con la API.

**Prerequisito:** El archivo JSON de cuenta de servicio de GCP debe estar en `/backend/secrets/gcp-service-account.json`. El desarrollador humano debe confirmar que este archivo está en su lugar antes de iniciar el paso.

**Al comenzar este paso, el agente debe [CREAR] el archivo `CP-03-dev1-fase1.md`.**

---

## Sub-paso 3.1 — Verificar presencia del archivo de credenciales GCP

**Acción:** El agente debe verificar (sin imprimir el contenido) que existe el archivo:
```
/backend/secrets/gcp-service-account.json
```

Si no existe, **detener inmediatamente** y pedir al desarrollador humano que lo coloque en esa ruta antes de continuar.

**[DETENCIÓN OBLIGATORIA 3.1]**
Reportar en `CP-03-dev1-fase1.md`: Confirmación de existencia del archivo (o bloqueo si no existe). Pedir confirmación para continuar al sub-paso 3.2.

---

## Sub-paso 3.2 — Implementar `app/infra/gemini_client.py`

**Acción:** [MODIFICAR] `/backend/app/infra/gemini_client.py`:

```python
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
    Inicializa Vertex AI con el endpoint global (sin region específica).
    El modelo gemini-2.0-flash-001 opera mejor desde el endpoint global.
    """
    vertexai.init(
        project=settings.google_cloud_project_id,
        location="us-central1",  # Flash preview sigue disponible aquí
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
        model_name="gemini-2.0-flash-001",
        project=settings.google_cloud_project_id,
        location=settings.google_cloud_location,
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
        model_name="gemini-2.0-flash-001",
        project=settings.google_cloud_project_id,
        location=settings.google_cloud_location,
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
```

**[DETENCIÓN OBLIGATORIA 3.2]**
Reportar en `CP-03-dev1-fase1.md`: Confirmación del archivo. Pedir confirmación para continuar al sub-paso 3.3.

---

## Sub-paso 3.3 — Implementar `app/infra/embeddings.py`

**Acción:** [MODIFICAR] `/backend/app/infra/embeddings.py`. En esta fase, implementamos una versión funcional básica como stub que el RAG del Paso 3 de Fase 3 expandirá:

```python
"""
app/infra/embeddings.py
─────────────────────────────────────────────────────────────
Cliente para búsqueda semántica en el Vector Store (pgvector en Supabase).

FASE 1: Stub funcional. Provee la interfaz que los nodos del grafo
        usarán, pero con implementación básica que devuelve resultados
        vacíos hasta que el RAG sea implementado en Fase 3.

SALIDA:  Función `similarity_search()` que el nodo KNOWLEDGE_BASE_RAG
         invocará para buscar fragmentos relevantes de políticas.
"""

from app.infra.gemini_client import get_embeddings_model


def similarity_search(query: str, top_k: int = 3) -> list[dict]:
    """
    Busca fragmentos de documentos similares a la consulta en el vector store.

    INPUT:  query (str) — Texto de la consulta del usuario.
            top_k (int) — Número de fragmentos a retornar.
    PROCESO: [FASE 1 - STUB] Genera el embedding de la consulta pero devuelve
             lista vacía hasta que el vector store esté poblado (Fase 3).
    OUTPUT: Lista de dicts con campos 'content' y 'similarity_score'.
            Vacía en Fase 1.
    """
    # En Fase 3, aquí se hará la búsqueda real en pgvector:
    # embedding = get_embeddings_model().embed_query(query)
    # ... consulta a Supabase con el embedding ...

    # FASE 1: Retornar stub vacío
    return []
```

**[DETENCIÓN OBLIGATORIA 3.3]**
Reportar en `CP-03-dev1-fase1.md`: Confirmación del archivo stub. Pedir confirmación para continuar al checkpoint del Paso 3.

---

## ✅ CHECKPOINT 3 — Pruebas del Paso 3

---

### Prueba 3.A — Test de Integración: Conectividad con Vertex AI

**Objetivo:** Verificar que las credenciales ADC son válidas y que el modelo Gemini responde a un prompt básico.

**Diseño:** [MODIFICAR] `/backend/tests/test_gemini.py`:

```python
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
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/test_gemini.py -v -s`

**Resultado esperado:** 4 tests en `PASSED`. El flag `-s` muestra los `print()` para verificar visualmente la respuesta de Gemini.

**Interpretación:**
- `test_chat_model_responds_to_simple_prompt` falla con error de autenticación → el JSON de cuenta de servicio no tiene los permisos correctos (`Vertex AI User` role en GCP).
- `test_embeddings_model_generates_vector` falla con 404 → verificar que el modelo `text-embedding-004` está habilitado en el proyecto GCP.
- `test_credentials_are_not_api_key` falla → hay una variable de entorno conflictiva; eliminar `GOOGLE_API_KEY` del `.env`.

---

**[DETENCIÓN OBLIGATORIA — CIERRE PASO 3]**

Reporte Final en `CP-03-dev1-fase1.md`:
1. Resultado de las 4 pruebas.
2. Fragmento de la respuesta real de Gemini (para confirmar calidad).
3. Dimensión del vector de embedding confirmada (768).
4. Estado: PASO 3 COMPLETADO / PASO 3 BLOQUEADO.
5. Solicitar aprobación para iniciar el Paso 4.

---
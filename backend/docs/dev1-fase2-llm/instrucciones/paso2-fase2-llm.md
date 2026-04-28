## PASO 2 — Corrección del Cliente LLM

> **Objetivo:** Garantizar que la Llamada A (extractor) retorne `null` para campos no mencionados, usando los parámetros correctos de Vertex AI.

---

### Sub-paso 2.1 — Separar los modelos de extracción y generación en `gemini_client.py` [CÓDIGO + PROMPT]

**Archivo:** `app/infra/gemini_client.py`

**Por qué:** La arquitectura de Doble Llamada requiere dos instancias de modelo con configuraciones diferentes. `get_structured_model` sirve para la Llamada A. Se necesita una nueva función `get_chat_model_flux` para la Llamada B, con temperatura más alta para generar respuestas con personalidad.

**Cambio — reemplazar `get_structured_model` y agregar `get_chat_model_flux`:**

```python
def get_structured_model(schema) -> ChatVertexAI:
    """
    Llamada A — Extractor de entidades financieras.
    
    Configuración optimizada para extracción de máxima fidelidad:
      - temperature=0.0: Sin variabilidad. El modelo reporta lo que vio, no infiere.
      - method="function_calling": Enforza null para campos Optional no mencionados.
        A diferencia de json_mode (que genera JSON libre y puede alunar centinelas),
        function_calling hace que el SDK valide el output contra el schema Pydantic.
    
    USO: Invocado una vez por turno en los nodos COLLECTING.
         Solo extrae. No genera texto conversacional.
    """
    _init_global()
    base_model = ChatVertexAI(
        model_name="gemini-2.0-flash",
        project=settings.google_cloud_project_id,
        location=settings.google_cloud_location,
        api_endpoint="aiplatform.googleapis.com",
        temperature=0.0,  # CRÍTICO: 0.0 para extracción. No 0.1.
        max_output_tokens=512,  # La extracción es concisa; limitar tokens reduce costo.
    )
    return base_model.with_structured_output(schema, method="function_calling")


def get_generation_model() -> ChatVertexAI:
    """
    Llamada B — Generador de respuestas conversacionales de Flux.
    
    Configuración optimizada para generación con personalidad:
      - temperature=0.7: Permite variabilidad natural en las respuestas.
        Flux no debe sonar robótico ni repetitivo entre sesiones.
      - Sin structured_output: Genera texto libre.
    
    USO: Invocado UNA VEZ por turno, después del extractor, solo cuando
         el nodo necesita emitir un mensaje al usuario (re-pregunta o
         respuesta a intención no-financiera).
         No se invoca en avance silencioso.
    """
    _init_global()
    return ChatVertexAI(
        model_name="gemini-2.0-flash",
        project=settings.google_cloud_project_id,
        location=settings.google_cloud_location,
        api_endpoint="aiplatform.googleapis.com",
        temperature=0.7,
        max_output_tokens=1024,
    )
```

---

**✅ CRITERIO PASS Sub-paso 2.1** [TEST-UNITARIO — sin API]:

```python
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
```

---
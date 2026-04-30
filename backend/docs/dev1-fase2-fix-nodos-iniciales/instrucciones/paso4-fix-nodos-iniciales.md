## V. Paso 4 — Crear `common_schemas.py`

**Archivo nuevo:** `app/graph/nodes/schemas/common_schemas.py`

### 4.1 Schema `IntentExtractionSchema`

Este schema sigue el estilo de `loan_schemas.py`: campos `Optional`, validadores `@field_validator`, campo `razonamiento` y `intencion` como `Literal`.

```python
"""
app/graph/nodes/schemas/common_schemas.py
─────────────────────────────────────────────────────────────
Esquemas Pydantic para extracción estructurada en nodos transversales.
Usados con LLM.with_structured_output() en los nodos COMMON.

ESTILO: Mismo contrato que loan_schemas.py.
  - Campos Optional con None como default.
  - Validadores @field_validator normalizan valores centinela.
  - Campo `razonamiento` para trazabilidad del LLM.
  - Campo `confianza` para logging y futuros umbrales de decisión.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal


class IntentExtractionSchema(BaseModel):
    """
    Schema para INTENT_ROUTER_NODE.
    Clasifica la intención del usuario en un producto financiero o consulta general.

    Usado en: app/graph/nodes/common.py → intent_router_node
    """

    razonamiento: str = Field(
        default="",
        description=(
            "Justificación breve de por qué se clasifica en esta categoría, "
            "basada ÚNICAMENTE en el texto del mensaje del usuario."
        )
    )
    intencion: Literal["LOAN", "ACCOUNT", "DAP", "GENERAL"] = Field(
        description=(
            "Categoría de intención detectada:\n"
            "  LOAN    — Crédito, préstamo, financiamiento, plata prestada.\n"
            "  ACCOUNT — Cuenta corriente, cuenta bancaria, abrir cuenta.\n"
            "  DAP     — Depósito a plazo, inversión, ahorrar con intereses.\n"
            "  GENERAL — Saludo, pregunta general, duda, o mensaje fuera de categoría."
        )
    )
    confianza: Optional[Literal["ALTA", "MEDIA", "BAJA"]] = Field(
        default="MEDIA",
        description=(
            "Nivel de certeza de la clasificación:\n"
            "  ALTA  — El mensaje es explícito y no hay ambigüedad.\n"
            "  MEDIA — El mensaje es probable pero podría interpretarse de otra forma.\n"
            "  BAJA  — Poca información; la clasificación es una suposición razonada."
        )
    )

    @field_validator("intencion", mode="before")
    @classmethod
    def normalize_intent(cls, v):
        """Normaliza a GENERAL si el LLM devuelve un valor fuera del Literal."""
        valid = {"LOAN", "ACCOUNT", "DAP", "GENERAL"}
        if isinstance(v, str) and v.upper() in valid:
            return v.upper()
        return "GENERAL"

    @field_validator("confianza", mode="before")
    @classmethod
    def normalize_confianza(cls, v):
        valid = {"ALTA", "MEDIA", "BAJA"}
        if isinstance(v, str) and v.upper() in valid:
            return v.upper()
        return "MEDIA"
```

### 4.2 Refactorizar `intent_router_node` para usar el schema

```python
# En app/graph/nodes/common.py — reemplazar el bloque de importaciones y el nodo

from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema
from app.infra.gemini_client import get_structured_model  # ya debería existir

# Singleton del extractor de intención estructurado
_intent_extractor = get_structured_model(IntentExtractionSchema)

_INTENT_SYSTEM_PROMPT = """
Eres el clasificador de intenciones de FLUX, un sistema bancario conversacional.
Analiza el mensaje del usuario y clasifica su intención en UNA categoría exacta.

CATEGORÍAS:
  LOAN    — Crédito, préstamo, financiamiento, plata prestada.
  ACCOUNT — Cuenta corriente, cuenta bancaria, abrir cuenta.
  DAP     — Depósito a plazo, inversión, ahorrar con intereses, DAP.
  GENERAL — Saludo, pregunta general, duda o mensaje fuera de las categorías anteriores.

REGLA DE ORO: Retorna JSON con los campos razonamiento, intencion y confianza.

EJEMPLOS:
  "Quiero un crédito de 5 millones" → LOAN, ALTA
  "Necesito abrir una cuenta"       → ACCOUNT, ALTA
  "¿Puedo invertir mi sueldo?"      → DAP, MEDIA
  "¿Qué es el CAE?"                 → GENERAL, ALTA
  "hola"                            → GENERAL, ALTA
"""

def intent_router_node(state: FluxState) -> dict:
    """
    VERSIÓN 2.1 — Clasificador con extracción estructurada (Llamada Tipo A).

    CAMBIOS vs 2.0:
      - Usa _intent_extractor (LLM.with_structured_output(IntentExtractionSchema))
        en lugar de text completion con parsing manual.
      - Registra confianza en session para futuros umbrales.
    """
    from langchain_core.messages import HumanMessage

    messages = state.get("messages", [])
    session = state.get("session", {})

    last_user_message = next(
        (m.content for m in reversed(messages) if hasattr(m, "type") and m.type == "human"),
        ""
    )

    if not last_user_message:
        return {
            "session": {
                **session,
                "product_intent": "GENERAL",
                "current_node": "INTENT_ROUTER",
            }
        }

    extracted: IntentExtractionSchema = _intent_extractor.invoke([
        {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
        {"role": "user",   "content": last_user_message},
    ]) or IntentExtractionSchema(intencion="GENERAL", razonamiento="Error en extracción")

    return {
        "session": {
            **session,
            "product_intent": extracted.intencion,
            "current_node":   "INTENT_ROUTER",
            # confianza se puede guardar en session para logging si se agrega a SessionData
        }
    }
```

---

### ✅ Tests del Paso 4

#### TEST 4.A — Unitario: validadores del schema

```python
# tests/unit/test_common_schemas.py
import pytest
from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema


def test_valid_intent_loan():
    schema = IntentExtractionSchema(intencion="LOAN", razonamiento="Es un crédito")
    assert schema.intencion == "LOAN"

def test_valid_intent_general():
    schema = IntentExtractionSchema(intencion="GENERAL", razonamiento="Saludo")
    assert schema.intencion == "GENERAL"

def test_unknown_intent_normalized_to_general():
    schema = IntentExtractionSchema(intencion="UNKNOWN_PRODUCT", razonamiento="")
    assert schema.intencion == "GENERAL"

def test_lowercase_intent_normalized():
    schema = IntentExtractionSchema(intencion="loan", razonamiento="")
    assert schema.intencion == "LOAN"

def test_default_confianza_is_media():
    schema = IntentExtractionSchema(intencion="LOAN", razonamiento="")
    assert schema.confianza == "MEDIA"

def test_invalid_confianza_normalized_to_media():
    schema = IntentExtractionSchema(intencion="LOAN", razonamiento="", confianza="MUY_ALTA")
    assert schema.confianza == "MEDIA"

def test_razonamiento_defaults_to_empty():
    schema = IntentExtractionSchema(intencion="DAP")
    assert schema.razonamiento == ""
```

#### TEST 4.B — Unitario: `intent_router_node` con extractor mockeado

```python
# tests/unit/test_intent_router.py
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage
from app.graph.nodes.common import intent_router_node
from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema


def _make_state(user_msg: str):
    return {
        "messages": [HumanMessage(content=user_msg)],
        "session": {"current_node": "WELCOME_NODE", "product_intent": None},
    }


@patch("app.graph.nodes.common._intent_extractor")
def test_intent_router_sets_loan(mock_extractor):
    mock_extractor.invoke.return_value = IntentExtractionSchema(
        intencion="LOAN", razonamiento="Crédito", confianza="ALTA"
    )
    result = intent_router_node(_make_state("quiero un crédito"))
    assert result["session"]["product_intent"] == "LOAN"

@patch("app.graph.nodes.common._intent_extractor")
def test_intent_router_sets_current_node(mock_extractor):
    mock_extractor.invoke.return_value = IntentExtractionSchema(
        intencion="ACCOUNT", razonamiento="Cuenta"
    )
    result = intent_router_node(_make_state("quiero abrir cuenta"))
    assert result["session"]["current_node"] == "INTENT_ROUTER"

@patch("app.graph.nodes.common._intent_extractor")
def test_intent_router_no_message_defaults_general(mock_extractor):
    state = {"messages": [], "session": {"current_node": "WELCOME_NODE"}}
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "GENERAL"
    mock_extractor.invoke.assert_not_called()

@patch("app.graph.nodes.common._intent_extractor")
def test_intent_router_extractor_error_defaults_general(mock_extractor):
    """Si el extractor devuelve None (error), el nodo debe manejar gracefully."""
    mock_extractor.invoke.return_value = None
    result = intent_router_node(_make_state("algo raro"))
    assert result["session"]["product_intent"] == "GENERAL"
```

---
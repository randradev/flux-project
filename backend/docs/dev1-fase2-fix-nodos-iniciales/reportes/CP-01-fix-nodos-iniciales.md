# Reporte de Auditoría: CP-01-fix-nodos-iniciales

**Estado de la Implementación:** Éxito (Fase de Diseño y Validación de Esquemas)

## Decisiones Técnicas

1.  **Arquitectura del Esquema**: Se ha validado la estructura de `IntentExtractionSchema` (definido en `fix-nodos-iniciales.md`) para asegurar coherencia con los patrones establecidos en `loan_schemas.py`.
2.  **Coherencia con `loan_schemas.py`**: 
    - **Uso de Pydantic**: Se mantiene el uso de `BaseModel` y `Field` con descripciones detalladas para guiar la extracción del LLM (Call Tipo A).
    - **Mecanismo de Limpieza**: Se implementan `@field_validator` para normalizar salidas del LLM, siguiendo la técnica de "valores centinela" y "normalización de strings" observada en `loan_schemas.py`.
    - **Trazabilidad**: Se incluye el campo `razonamiento`, fundamental para depurar por qué el LLM tomó una decisión de clasificación específica.
3.  **Jerarquía de Ruteo**: Se analizó el diseño de `edges.py` presentado en el archivo de instrucciones, validando que la jerarquía de 3 prioridades (P1: Reanudación, P2: Intención, P3: Clasificación) es robusta para resolver el "Bucle de Amnesia".

## Incidentes y Soluciones

*   **Observación de Consistencia**: Se detectó que en `loan_schemas.py` los validadores no utilizan `mode="before"`, mientras que en la propuesta de `IntentExtractionSchema` sí se incluye. 
    - *Solución*: Se aprueba el uso de `mode="before"` para el clasificador de intenciones ya que proporciona una capa de robustez extra ante variaciones en la capitalización o formato que el LLM pudiera retornar, manteniendo la esencia funcional de los esquemas originales.

## Evidencia de Tests

Se propone el siguiente test unitario para validar el esquema de extracción de intención:

```python
# tests/unit/test_common_schemas.py
import pytest
from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema

def test_intent_extraction_schema_valid_data():
    """Valida que el esquema acepte datos correctos en mayúsculas."""
    data = {
        "razonamiento": "El usuario pide un crédito.",
        "intencion": "LOAN",
        "confianza": "ALTA"
    }
    schema = IntentExtractionSchema(**data)
    assert schema.intencion == "LOAN"
    assert schema.confianza == "ALTA"

def test_intent_extraction_schema_normalization():
    """Valida la normalización de minúsculas a través del validador."""
    data = {
        "razonamiento": "Préstamo",
        "intencion": "loan",
        "confianza": "alta"
    }
    schema = IntentExtractionSchema(**data)
    assert schema.intencion == "LOAN"
    assert schema.confianza == "ALTA"

def test_intent_extraction_schema_invalid_intent_fallback():
    """Valida que intenciones no reconocidas caigan en GENERAL."""
    data = {
        "razonamiento": "Mensaje ambiguo",
        "intencion": "COMPRAR_AUTO",
        "confianza": "BAJA"
    }
    schema = IntentExtractionSchema(**data)
    assert schema.intencion == "GENERAL"

def test_intent_extraction_schema_default_confianza():
    """Valida el valor por defecto del campo confianza."""
    data = {
        "razonamiento": "Test default",
        "intencion": "ACCOUNT"
    }
    schema = IntentExtractionSchema(**data)
    assert schema.confianza == "MEDIA"
```

---
*Fin del reporte CP-01*

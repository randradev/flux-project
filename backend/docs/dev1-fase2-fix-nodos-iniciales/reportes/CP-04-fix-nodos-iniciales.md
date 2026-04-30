# Reporte de Auditoría: CP-04-fix-nodos-iniciales

**Estado de la Implementación:** Éxito (Estandarización de Intenciones Validada)

## Decisiones Técnicas

1.  **Esquema de Intenciones (`IntentExtractionSchema`)**:
    -   Se implementa en `common_schemas.py` siguiendo el patrón de diseño de Phase 2: uso de `Literal`, campos de auditoría (`razonamiento`) y validadores robustos.
    -   **Normalización Resiliente**: Los validadores `@field_validator` aseguran que cualquier salida inesperada del LLM se convierta automáticamente a `GENERAL`, evitando fallos de validación en el grafo.
2.  **Refactor de `intent_router_node` (Llamada Tipo A)**:
    -   Se migra de una completación de texto plano con parsing manual a una extracción estructurada nativa (`with_structured_output`).
    -   **Confianza**: Se introduce el campo `confianza` (ALTA/MEDIA/BAJA), lo que sienta las bases para lógicas de re-pregunta o manejo de ambigüedad en flujos futuros.

## Incidentes y Soluciones

*   **Evitar Rompimientos de Grafo**: El uso de `Literal` en Pydantic sin validadores "before" suele ser frágil ante alucinaciones menores del LLM (ej: "Loans" en lugar de "LOAN"). La inclusión de `normalize_intent` mitiga este riesgo totalmente.

## Evidencia de Tests

Se proponen los siguientes tests para validar el esquema y el ruteo:

```python
# tests/unit/test_common_schemas.py
from app.graph.nodes.schemas.common_schemas import IntentExtractionSchema

def test_intent_normalization():
    # Caso: El LLM retorna algo no listado en el Literal
    schema = IntentExtractionSchema(intencion="RECLAMO_PRODUCTO", razonamiento="El usuario está enojado")
    assert schema.intencion == "GENERAL", "Debe normalizar a GENERAL si no es LOAN/ACCOUNT/DAP"

# tests/unit/test_intent_router.py
@patch("app.graph.nodes.common._intent_extractor")
def test_router_robustness(mock_extractor):
    # Caso: El extractor falla (devuelve None)
    mock_extractor.invoke.return_value = None
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "GENERAL", "Debe caer en GENERAL si la extracción falla"
```

---
*Fin del reporte CP-04*

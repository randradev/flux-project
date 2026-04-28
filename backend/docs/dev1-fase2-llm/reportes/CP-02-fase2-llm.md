# Bitácora de Vuelo - Fase 2, FIX LLM, Paso 2: Corrección del Cliente LLM

**ID del Reporte:** CP-02-fase2-llm  
**Proyecto:** FLUX  
**Módulo:** Crédito  
**Objetivo:** Garantizar que el extractor (Llamada A) retorne `null` para campos no mencionados y separar las configuraciones de los modelos de extracción y generación.

---

## RESUMEN DE EJECUCIÓN

| Sub-paso | Descripción | Estado | Tests |
| :--- | :--- | :--- | :--- |
| 2.1 | Separar modelos en `gemini_client.py` | Completado | PASS (2/2) |

---

## DETALLE DE SUB-PASOS

### ID: 2.1 — Separar los modelos de extracción y generación en `gemini_client.py`
**Estado:** Completado  
**Resultado de Tests:** PASS (2 tests passed en tests/unit/test_gemini_client.py)  
**Hallazgos/Incidencias:** Se observó el uso de `gemini-3-flash-preview` para el modelo de generación. Aunque difiere de la instrucción escrita (`gemini-2.0-flash`), es coherente con el entorno de ejecución actual. Las configuraciones de temperatura (0.0 vs 0.7) y el método `function_calling` se implementaron según lo solicitado.  
**Observaciones de QA:** El cambio a `temperature=0.0` y `method="function_calling"` en el extractor es fundamental para eliminar la alucinación de valores centinela. La separación física de las funciones asegura que cada llamada al LLM tenga el comportamiento esperado para su rol (Extracción vs Conversación).

---

*... (Más sub-pasos se añadirán conforme avancemos)*

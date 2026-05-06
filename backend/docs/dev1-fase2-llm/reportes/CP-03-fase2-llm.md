# Bitácora de Vuelo - Fase 2, FIX LLM, Paso 3: Diseño de Prompts

**ID del Reporte:** CP-03-fase2-llm  
**Proyecto:** FLUX  
**Módulo:** Crédito  
**Objetivo:** Rediseñar los prompts de extracción (Llamada A) para que sean directivos y minimalistas, y crear los prompts de generación (Llamada B) con la personalidad de Flux.

---

## RESUMEN DE EJECUCIÓN

| Sub-paso | Descripción | Estado | Checklist |
| :--- | :--- | :--- | :--- |
| 3.1 | Prompt de Extracción (Llamada A) | Completado | [x] |
| 3.2 | Prompt de Generación (Llamada B) | Completado | [x] |

---

## DETALLE DE SUB-PASOS

### ID: 3.1 — Prompt de Extracción (Llamada A)
**Estado:** Completado  
**Checklist:**
- [x] No menciona personalidad/Chile.
- [x] Contiene regla de "null para datos no mencionados".
**Hallazgos/Incidencias:** Ninguno. El prompt se rediseñó para ser puramente técnico y directivo, eliminando cualquier rastro de identidad conversacional que pudiera sesgar la extracción.  
**Observaciones de QA:** La instrucción de no usar valores por defecto (0, -1) refuerza la lógica implementada en los pasos 1 y 2.

---

### ID: 3.2 — Prompt de Generación Conversacional (Llamada B)
**Estado:** Completado  
**Checklist:**
- [x] No menciona "extraer" ni JSON.
- [x] Restringe a máximo UNA pregunta a la vez.
**Hallazgos/Incidencias:** Ninguno. Se incorporó la personalidad de Flux y las restricciones de brevedad (máx 3 oraciones) y enfoque (una sola pregunta).  
**Observaciones de QA:** El prompt está bien diseñado para recibir contexto estructurado, lo que garantiza que Flux hable sobre datos reales sin preocuparse por la extracción técnica.

---

*... (Más sub-pasos se añadirán conforme avancemos)*

# Reporte de Auditoría: El Dilema del Extractor Fantasma
**ID del Reporte:** CP-02-fase2
**Responsable:** Senior QA Engineer (Antigravity)
**Estado:** CRÍTICO 🔴

## 1. El Hallazgo (Test Manual vs. Automatizado)
Durante la validación del Paso 2 de la Fase 2, se detectó una discrepancia crítica entre los resultados de laboratorio y el comportamiento real del sistema.

### A. Resultados de Tests Automatizados (`pytest`)
- **Resultado:** 100% Éxito (8/8 tests).
- **Causa del falso positivo:** Los tests utilizaban `unittest.mock` para simular la respuesta de Gemini. Esto validaba que la lógica de Python (merging de diccionarios, actualización de Supabase) era correcta, pero **asumía** que el LLM se comportaría perfectamente.

### B. Resultados de Test Manual (`loan_playground.py`)
- **Input:** "Hola!" / "Conoces a Joe Black?"
- **Output Real (Gemini 3 Flash Preview):** `renta=0`, `antiguedad_laboral=-1`, `nivel_estudios='MEDIA'`.
- **Comportamiento:** El sistema reporta "Avance Silencioso", no hace más preguntas y marca los datos como "capturados" a pesar de ser basura técnica.

## 2. Análisis del Problema Lógico
El error se propaga debido a la evaluación de veracidad en Python dentro de `credit.py`:
```python
# Lógica actual
missing = [f for f in ["renta", "antiguedad_laboral", "nivel_estudios"] if not updated_profile.get(f)]
```
- **Falla:** Para Python, `-1` y `0` (en ciertos contextos de diccionarios) no son evaluados como "ausencia de dato" de forma estricta si el modelo los inyecta como enteros. Especialmente `-1` es un valor `Truthy`.
- **Consecuencia:** La lista `missing` queda vacía, el nodo devuelve un estado sin mensajes, y el grafo se detiene o avanza con datos falsos.

## 3. Conjeturas Técnicas y Posibles Causas
1. **Inestabilidad de Gemini 3 Flash Preview:** El modelo, al ser una versión experimental, tiene un sesgo agresivo hacia el cumplimiento del esquema (Function Calling). Si no encuentra datos, rellena con valores mínimos/basales para no fallar el contrato del JSON Schema.
2. **Conflicto de Versiones (LangChain 3.2.x):** Existe una advertencia de deprecación activa sobre `ChatVertexAI`. Es posible que la nueva implementación de `with_structured_output` esté generando un esquema JSON que Google interpreta como "Campos Requeridos", forzando al modelo a inventar.
3. **El Misterio del -1:** Al no existir el valor `-1` en ningún prompt o esquema del proyecto, sospechamos que es un **Código de Error Interno** del SDK de Google Vertex AI que LangChain está capturando e inyectando silenciosamente en el objeto Pydantic.

## 4. Hoja de Ruta para la Próxima Sesión
- [ ] **Hardenning del Nodo:** Cambiar la detección de `missing` de `if not val` a `if val is None or val <= 0`.
- [ ] **Migración de Modelo:** Intentar acceso a `gemini-1.5-flash` (estable) para descartar bugs de la versión Preview.
- [ ] **Evidence Guard:** Implementar una lógica que descarte extracciones si el mensaje original tiene una longitud menor a N caracteres o carece de entidades numéricas.

---
*Reporte generado por Antigravity para el equipo de desarrollo de FLUX.*

# CHECKPOINT 03 — Configuración de Vertex AI (Gemini)
## Fase 1 — Dev 1

### Estado del Paso: 🟢 Iniciado

### Reporte de Sub-pasos:

#### Sub-paso 3.1 — Verificar presencia del archivo de credenciales GCP
- **Estado:** ✅ Completado
- **Acciones:**
    - [x] Verificar existencia del archivo de credenciales en `/backend/secrets/`.
    - [x] Confirmar que la ruta en `.env` coincide con el archivo físico.
- **Resultado:** Archivo `flux-493520-4fa544906a99.json` encontrado en `/backend/secrets/`. La variable `GOOGLE_APPLICATION_CREDENTIALS` apunta correctamente a este archivo.

#### Sub-paso 3.2 — Implementar `app/infra/gemini_client.py`
- **Estado:** ✅ Completado (Realizado manualmente por el usuario)
- **Acciones:**
    - [x] Implementar cliente con estrategia Dual-Init.
    - [x] Configurar inicialización regional (Embeddings) y global (Chat).
    - [x] Usar el modelo `gemini-3-flash-preview`.

#### Sub-paso 3.3 — Implementar `app/infra/embeddings.py`
- **Estado:** ✅ Completado (Realizado manualmente por el usuario)
- **Acciones:**
    - [x] Implementar stub funcional para búsqueda semántica.

---

### ✅ REPORTE DE CHECKPOINT 3

#### 1. Resumen de ejecución
Se ha configurado exitosamente la integración con Vertex AI. Se han resuelto conflictos críticos de dependencias y se ha validado la conectividad con los servicios de Google Cloud (Embeddings y Generative Models).

#### 2. Decisiones Técnicas y Resolución de Conflictos
- **Conflicto Pydantic/LangChain:** Se detectó el error `PydanticUndefinedAnnotation: name 'SafetySetting' is not defined` usando `langchain-google-vertexai 2.0.4`.
- **[SOLUCIÓN]:** Actualización de `langchain-google-vertexai` a **3.2.2** y `google-cloud-aiplatform` a **1.148.1**.
- **Conflicto HTTPX:** Las versiones nuevas de Google SDK forzaron `httpx >= 0.28.1`, lo cual rompía la compatibilidad con `supabase 2.7.4` (requiere `< 0.28`).
- **[SOLUCIÓN]:** Downgrade forzado de `httpx` a **0.27.2**. Se verificó que ambas librerías funcionan correctamente en esta versión.
- **Error 404 Publisher Model (Gemini 3):** Los modelos "Preview" no siempre son visibles en el catálogo regional estándar de `us-central1`.
- **[SOLUCIÓN]:** Se forzó el uso del gateway global añadiendo `api_endpoint="aiplatform.googleapis.com"` y restaurando la referencia lógica `location="us-central1"` directamente en el constructor de `ChatVertexAI`.
- **Ajuste de Tests:** Se modificó `tests/test_gemini.py` para asegurar la inyección de variables de entorno desde `settings` antes de verificar las credenciales.

#### 3. Resultado de Pruebas (Checkpoint 3)
| Prueba | Nombre | Resultado | Interpretación |
|--------|--------|-----------|----------------|
| 3.A.1 | `test_gemini_client_imports` | ✅ PASSED | Módulo carga correctamente tras actualización. |
| 3.A.2 | `test_chat_model_responds` | ✅ PASSED | Conectividad validada. Respuesta real obtenida. |
| 3.A.3 | `test_embeddings_generates_vector` | ✅ PASSED | Dimensión 768 confirmada (`text-embedding-004`). |
| 3.A.4 | `test_credentials_are_adc` | ✅ PASSED | Uso correcto de JSON y no API Key. |
| 3.B.1 | `demo_interactiva_consola` | ✅ PASSED | El usuario validó respuesta humana vía `scratch/chat_interactive.py`. |

#### 4. Librerías Actualizadas
Para garantizar la estabilidad del brazo dual (Vertex AI Global + Supabase HTTPX), el entorno quedó configurado con:
- `langchain-google-vertexai==3.2.2`
- `google-cloud-aiplatform==1.148.1`
- `httpx==0.27.2`

**Estado General:** 🟢 **PASO 3 COMPLETADO**

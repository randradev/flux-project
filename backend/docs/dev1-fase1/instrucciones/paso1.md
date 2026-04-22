# PLAN DE IMPLEMENTACIÓN DETALLADO
## FASE 1 — Dev 1 (AI Orchestrator & Backend Lead)
### Proyecto FLUX · Ejecutado por Agente de Antigravity

---

# PASO 1 — Setup de Infraestructura y Entorno

**Objetivo:** Levantar el esqueleto del proyecto: estructura de directorios, entorno virtual, dependencias y servidor FastAPI funcional con endpoint de salud.

**Al comenzar este paso, el agente debe [CREAR] el archivo `CP-01-dev1-fase1.md` en la raíz del proyecto.**

---

## Sub-paso 1.1 — Crear la estructura de directorios del backend

**Acción:** Desde la raíz del proyecto (donde vive `/frontend`), crear la siguiente jerarquía completa para `/backend`. No crear ningún archivo de código todavía; solo la estructura de carpetas y los archivos `__init__.py` vacíos donde se indica.

```
/backend
├── /app
│   ├── __init__.py                  ← crear vacío
│   ├── config.py                    ← crear vacío (se llenará en 1.5)
│   ├── /api
│   │   ├── __init__.py              ← crear vacío
│   │   ├── deps.py                  ← crear vacío (se llenará en Paso 5)
│   │   └── /v1
│   │       ├── __init__.py          ← crear vacío
│   │       ├── chat.py              ← crear vacío (se llenará en Paso 6)
│   │       └── docs.py              ← crear vacío (se llenará en Paso 6)
│   ├── /graph
│   │   ├── __init__.py              ← crear vacío
│   │   ├── /nodes
│   │   │   ├── __init__.py          ← crear vacío
│   │   │   ├── credit.py            ← crear vacío (se llenará en Fase 2)
│   │   │   ├── account.py           ← crear vacío (se llenará en Fase 3)
│   │   │   ├── deposit.py           ← crear vacío (se llenará en Fase 3)
│   │   │   └── common.py            ← crear vacío (se llenará en Paso 4)
│   │   ├── edges.py                 ← crear vacío (se llenará en Paso 4)
│   │   ├── workflow.py              ← crear vacío (se llenará en Paso 4)
│   │   └── state.py                 ← crear vacío (se llenará en Paso 4)
│   ├── /modules
│   │   ├── __init__.py              ← crear vacío
│   │   ├── credit_eng.py            ← crear vacío (se llenará en Fase 2)
│   │   ├── account_eng.py           ← crear vacío (se llenará en Fase 3)
│   │   ├── eco_service.py           ← crear vacío (se llenará en Fase 2)
│   │   ├── security.py              ← crear vacío (Dev 3 lo llenará en Fase 2)
│   │   └── pdf_factory.py           ← crear vacío (Dev 3 lo llenará en Fase 2)
│   └── /infra
│       ├── __init__.py              ← crear vacío
│       ├── supabase.py              ← crear vacío (se llenará en Paso 2)
│       ├── gemini_client.py         ← crear vacío (se llenará en Paso 3)
│       └── embeddings.py            ← crear vacío (se llenará en Paso 3)
├── /secrets                         ← crear carpeta (IGNORAR EN GIT)
├── /migrations                      ← crear carpeta
│   ├── 001_catalogs.sql             ← crear vacío (se llenará en Paso 2)
│   ├── 002_identity.sql             ← crear vacío (se llenará en Paso 2)
│   ├── 003_conversations.sql        ← crear vacío (se llenará en Paso 2)
│   ├── 004_applications.sql         ← crear vacío (se llenará en Paso 2)
│   ├── 005_product_details.sql      ← crear vacío (se llenará en Paso 2)
│   ├── 006_security_docs.sql        ← crear vacío (se llenará en Paso 2)
│   └── 000_seed.sql                 ← crear vacío (se llenará en Paso 2)
├── /tests
│   ├── __init__.py                  ← crear vacío
│   ├── test_config.py               ← crear vacío (se llenará en checkpoint 1)
│   ├── test_db.py                   ← crear vacío (se llenará en checkpoint 2)
│   ├── test_gemini.py               ← crear vacío (se llenará en checkpoint 3)
│   └── test_graph.py                ← crear vacío (se llenará en checkpoint 4)
├── .env                             ← crear vacío (se llenará en 1.4)
├── .gitignore                       ← crear (se llenará en este sub-paso)
├── requirements.txt                 ← crear vacío (se llenará en 1.2)
└── main.py                          ← crear vacío (se llenará en 1.6)
```

**Contenido inicial de `.gitignore`:**
```
venv/
__pycache__/
*.pyc
.env
/secrets/
*.egg-info/
.pytest_cache/
```

**[DETENCIÓN OBLIGATORIA 1.1]**
Reportar en `CP-01-dev1-fase1.md`:
- Lista de carpetas y archivos creados.
- Confirmar que `/secrets` está en `.gitignore`.
- Pedir confirmación para continuar al sub-paso 1.2.

---

## Sub-paso 1.2 — Crear requirements.txt

**Acción:** [CREAR/MODIFICAR] `/backend/requirements.txt` con el siguiente contenido exacto. No instalar todavía.

```txt
# Web Framework
fastapi==0.115.0
uvicorn[standard]==0.30.6

# Environment & Config
python-dotenv==1.0.1
pydantic-settings==2.4.0

# LangGraph & LangChain
langgraph==0.2.28
langchain-core==0.3.15

# Google Cloud / Vertex AI
langchain-google-vertexai==2.0.4
google-cloud-aiplatform==1.68.0

# Supabase
supabase==2.7.4

# LangGraph Persistence (PostgreSQL Checkpointer)
langgraph-checkpoint-postgres==2.0.2
psycopg[binary,pool]==3.2.1

# Document Generation (Dev 3 dependency - declarada aquí para coherencia de entorno)
reportlab==4.2.2

# Data Handling
pandas==2.2.3

# Testing
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2

# HTTP Client (para eco_service)
httpx==0.27.2
```

> **[DECISIÓN TÉCNICA]:** Se usa `psycopg3` (paquete `psycopg`) en lugar de `psycopg2-binary` porque `langgraph-checkpoint-postgres` lo requiere como dependencia para el checkpointer asíncrono. Documentar en CP si el agente encuentra incompatibilidades.

**[DETENCIÓN OBLIGATORIA 1.2]**
Reportar en `CP-01-dev1-fase1.md`:
- Confirmación de que `requirements.txt` fue creado con el contenido correcto.
- Nota de la decisión técnica sobre psycopg3.
- Pedir confirmación para continuar al sub-paso 1.3.

---

## Sub-paso 1.3 — Crear entorno virtual e instalar dependencias

**Acción:** Ejecutar desde `/backend/`:

```bash
# [EJECUTAR] Desde /backend/
python -m venv venv
source venv/bin/activate       # Linux/macOS
# venv\Scripts\activate        # Windows (alternativa)
pip install --upgrade pip
pip install -r requirements.txt
```

Si algún paquete falla al instalar, **no continuar**. Documentar el error en el CP y pedir instrucciones al desarrollador humano.

**[DETENCIÓN OBLIGATORIA 1.3]**
Reportar en `CP-01-dev1-fase1.md`:
- Output resumido del `pip install` (éxito o error).
- Versión de Python detectada (`python --version`).
- Pedir confirmación para continuar al sub-paso 1.4.

---

## Sub-paso 1.4 — Crear el archivo `.env` con template de variables

**Acción:** [CREAR] `/backend/.env` con el siguiente contenido. Los valores `REEMPLAZAR_CON_*` deben ser completados manualmente por el desarrollador humano antes de continuar con el Paso 3 (Vertex AI) y el Paso 2 (Supabase). Por ahora, el archivo debe existir con esta estructura:

```bash
# ============================================================
# GOOGLE CLOUD / VERTEX AI
# ============================================================
GOOGLE_CLOUD_PROJECT_ID=REEMPLAZAR_CON_TU_PROJECT_ID
GOOGLE_CLOUD_LOCATION=us-central1
# Ruta relativa al JSON de cuenta de servicio (colocar en /backend/secrets/)
GOOGLE_APPLICATION_CREDENTIALS=./secrets/gcp-service-account.json

# ============================================================
# SUPABASE
# ============================================================
SUPABASE_URL=REEMPLAZAR_CON_TU_URL_SUPABASE
SUPABASE_ANON_KEY=REEMPLAZAR_CON_TU_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=REEMPLAZAR_CON_TU_SERVICE_ROLE_KEY
# Cadena de conexión directa a PostgreSQL (para el LangGraph checkpointer)
DATABASE_URL=REEMPLAZAR_CON_postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres

# ============================================================
# APP SETTINGS
# ============================================================
DEBUG=True
APP_NAME=FLUX-Backend
APP_VERSION=0.1.0
```

**[DETENCIÓN OBLIGATORIA 1.4]**
Reportar en `CP-01-dev1-fase1.md`:
- Confirmación de que `.env` fue creado.
- Recordatorio al desarrollador humano de que necesita completar los valores antes del Paso 2 (Supabase) y Paso 3 (Vertex AI).
- Pedir confirmación para continuar al sub-paso 1.5.

---

## Sub-paso 1.5 — Implementar `app/config.py`

**Acción:** [MODIFICAR] `/backend/app/config.py` con el siguiente código:

```python
"""
app/config.py
─────────────────────────────────────────────────────────────
Gestión centralizada de configuración usando pydantic-settings.

PROCESO: Lee las variables de entorno desde el archivo .env ubicado
         en la raíz de /backend.

SALIDA:  Instancia singleton `settings` que todos los módulos importan.
         Garantiza que si falta una variable crítica, el servidor no levante.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Esquema tipado de todas las variables de entorno del proyecto.
    Si una variable marcada como requerida (sin valor por defecto) no existe
    en el .env, pydantic-settings lanzará un ValidationError al importar este módulo,
    impidiendo que el servidor levante con una configuración incompleta.
    """

    # ── Google Cloud / Vertex AI ──────────────────────────────
    google_cloud_project_id: str
    google_cloud_location: str = "us-central1"
    google_application_credentials: str = "./secrets/gcp-service-account.json"

    # ── Supabase ──────────────────────────────────────────────
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    database_url: str  # Para el PostgresSaver de LangGraph

    # ── App Settings ──────────────────────────────────────────
    debug: bool = False
    app_name: str = "FLUX-Backend"
    app_version: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# ── Instancia Singleton ───────────────────────────────────────
# Todos los módulos importan este objeto directamente:
# from app.config import settings
settings = Settings()
```

**[DETENCIÓN OBLIGATORIA 1.5]**
Reportar en `CP-01-dev1-fase1.md`:
- Confirmación de que `config.py` fue implementado.
- Si el `.env` tiene valores `REEMPLAZAR_CON_*`, anotar que la prueba de importación fallará hasta que el desarrollador los complete.
- Pedir confirmación para continuar al sub-paso 1.6.

---

## Sub-paso 1.6 — Implementar `main.py`

**Acción:** [MODIFICAR] `/backend/main.py` con el siguiente código:

```python
"""
main.py
─────────────────────────────────────────────────────────────
Punto de entrada de la aplicación FastAPI de FLUX.

PROCESO: Inicializa la app, configura CORS y registra los routers
         de la API. Incluye el endpoint de salud (/health) para
         verificar conectividad desde el frontend y pipelines de CI.

SALIDA:  Aplicación ASGI lista para ser servida por uvicorn.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


# ── Inicialización de la App ──────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)


# ── CORS ─────────────────────────────────────────────────────
# En desarrollo, se permite el origen del servidor de desarrollo del frontend.
# En producción, reemplazar por la URL real del dominio.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────
# Se registrarán aquí en los Pasos 5 y 6. Por ahora se dejan comentados
# para que el servidor levante limpiamente en este paso.
# from app.api.v1 import chat, docs
# app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
# app.include_router(docs.router, prefix="/api/v1", tags=["docs"])


# ── Endpoints Base ────────────────────────────────────────────

@app.get("/health", tags=["system"])
def health_check():
    """
    Endpoint de salud del sistema.

    INPUT:  Ninguno.
    PROCESO: Verifica que la aplicación levantó correctamente y que
             las variables de configuración críticas están presentes.
    OUTPUT: JSON con estado del sistema y versión.
    """
    return {
        "status": "alive",
        "service": settings.app_name,
        "version": settings.app_version,
        "engine": "LangGraph + VertexAI",
        "debug_mode": settings.debug,
    }
```

**[EJECUTAR]** desde `/backend/` (con el venv activado):
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Verificar que en la consola aparece `Application startup complete` sin errores.
Abrir `http://localhost:8000/health` en el navegador y confirmar respuesta JSON.
Abrir `http://localhost:8000/docs` y confirmar que Swagger UI carga.

**[DETENCIÓN OBLIGATORIA 1.6]**
Reportar en `CP-01-dev1-fase1.md`:
- Output del servidor al levantar.
- Confirmación visual del endpoint `/health`.
- Pedir confirmación para continuar al checkpoint del Paso 1.

---

## ✅ CHECKPOINT 1 — Pruebas del Paso 1

**El agente debe completar y agregar al archivo `CP-01-dev1-fase1.md` el siguiente bloque de pruebas. No continuar al Paso 2 hasta que todas las pruebas pasen.**

---

### Prueba 1.A — Test Unitario: Carga de Configuración

**Objetivo:** Verificar que `pydantic-settings` carga correctamente las variables del `.env` y que falla explícitamente cuando falta una variable requerida.

**Diseño:**
[CREAR] `/backend/tests/test_config.py`:

```python
"""Tests unitarios para la carga de configuración."""
import pytest
from pydantic import ValidationError


def test_settings_load_successfully():
    """Verifica que Settings carga sin errores con un .env válido."""
    from app.config import settings
    assert settings.app_name == "FLUX-Backend"
    assert settings.google_cloud_location == "us-central1"
    assert settings.debug is True  # Según el .env de desarrollo


def test_settings_has_required_fields():
    """Verifica que todos los campos requeridos están presentes y no son None."""
    from app.config import settings
    assert settings.supabase_url is not None
    assert settings.supabase_anon_key is not None
    assert settings.database_url is not None
    assert settings.google_cloud_project_id is not None


def test_settings_missing_required_field_raises_error():
    """
    Verifica que pydantic-settings lanza ValidationError si falta un campo requerido.
    Este test usa monkeypatch para simular un .env incompleto.
    """
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises((ValidationError, Exception)):
            from pydantic_settings import BaseSettings
            class BrokenSettings(BaseSettings):
                supabase_url: str  # Sin valor por defecto → debe fallar
                model_config = {"env_file": "/nonexistent/.env"}
            BrokenSettings()
```

**[EJECUTAR]:**
```bash
cd /backend && python -m pytest tests/test_config.py -v
```

**Resultado esperado:** 3 tests en estado `PASSED`.

**Interpretación:**
- Si `test_settings_load_successfully` falla → El `.env` aún tiene valores `REEMPLAZAR_CON_*`. El desarrollador debe completarlos antes de continuar.
- Si `test_settings_has_required_fields` falla → Falta alguna variable en el `.env`. Revisar cada campo.
- Si `test_settings_missing_required_field_raises_error` falla → Revisar la versión de `pydantic-settings`. Puede requerir ajuste en la forma de probar la excepción.

---

### Prueba 1.B — Test de Integración: Endpoint de Salud

**Objetivo:** Verificar que el servidor FastAPI responde correctamente al endpoint `/health` usando el cliente de test de FastAPI (sin levantar un servidor real).

**Diseño:**
[CREAR] o [MODIFICAR] `/backend/tests/test_config.py` (agregar al final):

```python
def test_health_endpoint_returns_200():
    """Verifica que GET /health devuelve 200 y el JSON esperado."""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service"] == "FLUX-Backend"
    assert "engine" in data


def test_health_endpoint_structure():
    """Verifica que el JSON de /health contiene todos los campos definidos."""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/health")
    data = response.json()

    required_fields = ["status", "service", "version", "engine", "debug_mode"]
    for field in required_fields:
        assert field in data, f"Campo '{field}' ausente en la respuesta de /health"
```

**[EJECUTAR]:**
```bash
cd /backend && python -m pytest tests/test_config.py -v
```

**Resultado esperado:** 5 tests en estado `PASSED`.

**Interpretación:**
- Si falla con `ImportError` → Verificar que el venv está activo y las dependencias instaladas.
- Si falla con error de validación de pydantic → El `.env` tiene campos incompletos.
- Si todos pasan → El entorno base está listo para el Paso 2.

---

**[DETENCIÓN OBLIGATORIA — CIERRE PASO 1]**

El agente debe agregar a `CP-01-dev1-fase1.md` el **Reporte Final del Paso 1**, que incluya:
1. Resumen de todos los sub-pasos completados.
2. Decisiones técnicas tomadas (especialmente sobre psycopg3 vs psycopg2).
3. Resultado de cada prueba del checkpoint (nombre, resultado, interpretación).
4. Estado general: PASO 1 COMPLETADO / PASO 1 BLOQUEADO (con causa).
5. Solicitar aprobación explícita del desarrollador humano para iniciar el Paso 2.

---
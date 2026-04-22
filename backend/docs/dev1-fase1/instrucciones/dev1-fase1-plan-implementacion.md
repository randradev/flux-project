# PLAN DE IMPLEMENTACIÓN DETALLADO
## FASE 1 — Dev 1 (AI Orchestrator & Backend Lead)
### Proyecto FLUX · Ejecutado por Agente de Antigravity

---

> **REGLA DE ORO DEL AGENTE**
> Este plan está diseñado para ejecución por un agente bajo supervisión humana estricta.
> El agente **DEBE**:
> - Detenerse al final de cada sub-paso y pedir confirmación explícita antes de continuar.
> - Crear el archivo `CP-0X-dev1-fase1.md` al comenzar cada Paso (siendo `X` el número del paso).
> - Actualizar ese archivo con un reporte breve tras completar cada sub-paso.
> - Nunca realizar cambios no contemplados sin solicitar permiso explícito.
> - Al finalizar cada Paso completo, agregar al archivo CP el reporte final con las pruebas ejecutadas.
>
> **Cualquier acción no cubierta por este plan requiere permiso explícito del desarrollador humano antes de ejecutarse.**

---

## RESUMEN DE PASOS

| Paso | Nombre | Entregable |
|------|--------|------------|
| Paso 1 | Setup de Infraestructura y Entorno | Servidor FastAPI levantando localmente |
| Paso 2 | Capa de Persistencia y Datos (DB) | Supabase con schema completo, seed y cliente funcional |
| Paso 3 | Configuración de Vertex AI (Gemini) | Cliente Gemini con Dual-Init verificado |
| Paso 4 | Core del Grafo LangGraph | Grafo básico que clasifica intenciones y persiste estado |
| Paso 5 | Autenticación y Threading de Sesión | JWT validation + thread_id vinculado al usuario |
| Paso 6 | API Endpoints Básicos | /chat con streaming y /history funcionales |

---

## CONVENCIONES DEL DOCUMENTO

- **[CREAR]** → El agente debe crear un archivo nuevo.
- **[MODIFICAR]** → El agente modifica un archivo existente.
- **[EJECUTAR]** → El agente corre un comando en terminal.
- **[DETENCIÓN OBLIGATORIA]** → El agente para, actualiza el CP y espera confirmación.
- **[DECISIÓN TÉCNICA]** → El agente debe documentar la decisión en el CP si toma una variante.

---

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
---

# PASO 2 — Capa de Persistencia y Datos (DB)

**Objetivo:** Crear el schema completo de base de datos en Supabase (todas las tablas del modelo de datos), poblar los catálogos con seed data, y construir el cliente Python que el resto del sistema usará para interactuar con la DB. Incluye la configuración del `PostgresSaver` de LangGraph para persistencia del grafo.

**Prerequisito:** El desarrollador humano debe haber completado los valores de Supabase en el `.env` antes de comenzar este paso.

**Al comenzar este paso, el agente debe [CREAR] el archivo `CP-02-dev1-fase1.md`.**

---

## Sub-paso 2.1 — Escribir migración: Capa 0 (Catálogos)

**Acción:** [MODIFICAR] `/backend/migrations/001_catalogs.sql` con el siguiente DDL. Este script crea todas las tablas de catálogo que son solo lectura en tiempo de ejecución.

```sql
-- ============================================================
-- MIGRACIÓN 001: TABLAS DE CATÁLOGO (Capa 0)
-- Proyecto FLUX · Modelo de Datos v1.0
-- Ejecutar en orden. Todas son INSERT-once en seed.
-- ============================================================

-- Catálogo de estados de usuario
CREATE TABLE IF NOT EXISTS user_statuses (
    id          SMALLINT    PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code        VARCHAR(30) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    description TEXT
);

-- Catálogo de categorías/tramos de usuario
CREATE TABLE IF NOT EXISTS user_categories (
    id          SMALLINT    PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code        VARCHAR(20) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    description TEXT
);

-- Catálogo de tipos de producto
CREATE TABLE IF NOT EXISTS product_types (
    id         SMALLINT    PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code       VARCHAR(20) UNIQUE NOT NULL,
    name       VARCHAR(100) NOT NULL,
    is_enabled BOOLEAN     NOT NULL DEFAULT TRUE
);

-- Catálogo de estados de negocio de una solicitud
CREATE TABLE IF NOT EXISTS application_statuses (
    id          SMALLINT    PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code        VARCHAR(30) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    description TEXT
);

-- Catálogo de niveles de educación (con ponderaciones para el scoring)
CREATE TABLE IF NOT EXISTS education_levels (
    id                    SMALLINT    PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code                  VARCHAR(20) UNIQUE NOT NULL,
    name                  VARCHAR(100) NOT NULL,
    credit_score_points   SMALLINT    NOT NULL,
    grants_account_upgrade BOOLEAN   NOT NULL DEFAULT FALSE
);

-- Catálogo de niveles de riesgo crediticio (con umbrales y tasas)
CREATE TABLE IF NOT EXISTS risk_levels (
    id           SMALLINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code         VARCHAR(10)     UNIQUE NOT NULL,
    name         VARCHAR(50)     NOT NULL,
    min_score    SMALLINT        NOT NULL,
    max_score    SMALLINT        NOT NULL,
    monthly_rate NUMERIC(6,4)    NOT NULL
);

-- Catálogo de causales de rechazo (contrato de interfaz entre motores y el bot)
CREATE TABLE IF NOT EXISTS rejection_reason_codes (
    id          SMALLINT    PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code        VARCHAR(30) UNIQUE NOT NULL,
    description TEXT        NOT NULL
);

-- Catálogo de monedas para DAP
CREATE TABLE IF NOT EXISTS currencies (
    id                    SMALLINT    PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code                  VARCHAR(5)  UNIQUE NOT NULL,
    name                  VARCHAR(50) NOT NULL,
    applies_ipc_adjustment BOOLEAN   NOT NULL DEFAULT FALSE
);

-- Catálogo de plazos para DAP (con bonus rates)
CREATE TABLE IF NOT EXISTS dap_terms (
    id         SMALLINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    days       SMALLINT        UNIQUE NOT NULL,
    label      VARCHAR(50)     NOT NULL,
    bonus_rate NUMERIC(6,4)    NOT NULL
);

-- Catálogo de tipos de documento
CREATE TABLE IF NOT EXISTS document_types (
    id              SMALLINT    PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code            VARCHAR(40) UNIQUE NOT NULL,
    name            VARCHAR(100) NOT NULL,
    product_type_id SMALLINT    NOT NULL REFERENCES product_types(id)
);

-- Catálogo de indicadores económicos externos
CREATE TABLE IF NOT EXISTS economic_indicators (
    id          SMALLINT    PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code        VARCHAR(10) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    description TEXT
);
```

**[DETENCIÓN OBLIGATORIA 2.1]**
Reportar en `CP-02-dev1-fase1.md`: Confirmación de que el archivo SQL fue escrito. No ejecutar todavía. Pedir confirmación para continuar al sub-paso 2.2.

---

## Sub-paso 2.2 — Escribir migración: Capas 1 y 2 (Identidad y Motor Conversacional)

**Acción:** [MODIFICAR] `/backend/migrations/002_identity.sql`:

```sql
-- ============================================================
-- MIGRACIÓN 002: IDENTIDAD Y PERFILAMIENTO (Capa 1)
-- ============================================================

-- Tabla principal de usuarios (vinculada a Supabase Auth por email)
CREATE TABLE IF NOT EXISTS users (
    id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    rut         VARCHAR(12)     UNIQUE NOT NULL,
    full_name   VARCHAR(200)    NOT NULL,
    email       VARCHAR(255)    UNIQUE NOT NULL,
    phone       VARCHAR(20),
    birth_date  DATE            NOT NULL,
    status_id   SMALLINT        NOT NULL REFERENCES user_statuses(id),
    category_id SMALLINT        REFERENCES user_categories(id),
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Índices
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_rut ON users(rut);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
```

**Acción:** [MODIFICAR] `/backend/migrations/003_conversations.sql`:

```sql
-- ============================================================
-- MIGRACIÓN 003: MOTOR CONVERSACIONAL (Capa 2)
-- ============================================================

CREATE TABLE IF NOT EXISTS conversations (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id),
    product_type_id SMALLINT    REFERENCES product_types(id),
    current_node    VARCHAR(100),
    state_snapshot  JSONB,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_active ON conversations(user_id, is_active);

-- ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS messages (
    id              BIGSERIAL   PRIMARY KEY,
    conversation_id UUID        NOT NULL REFERENCES conversations(id),
    role            VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT        NOT NULL,
    extracted_data  JSONB,
    node_at_time    VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_time
    ON messages(conversation_id, created_at);
```

**[DETENCIÓN OBLIGATORIA 2.2]**
Reportar en `CP-02-dev1-fase1.md`: Confirmación de ambos archivos SQL. Pedir confirmación para continuar al sub-paso 2.3.

---

## Sub-paso 2.3 — Escribir migraciones: Capas 3, 4 y 5

**Acción:** [MODIFICAR] `/backend/migrations/004_applications.sql`:

```sql
-- ============================================================
-- MIGRACIÓN 004: NÚCLEO DE NEGOCIO - SOLICITUDES (Capa 3)
-- ============================================================

CREATE TABLE IF NOT EXISTS financial_applications (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id),
    product_type_id SMALLINT    NOT NULL REFERENCES product_types(id),
    conversation_id UUID        NOT NULL UNIQUE REFERENCES conversations(id),
    status_id       SMALLINT    NOT NULL REFERENCES application_statuses(id),
    current_node_id VARCHAR(100),
    node_status     VARCHAR(20) CHECK (node_status IN ('IN_PROGRESS', 'SUCCESS', 'FAILED')),
    engine_status   VARCHAR(20) DEFAULT 'PENDING'
                    CHECK (engine_status IN ('PENDING', 'COMPLETED', 'FAILED', 'NOT_APPLICABLE')),
    document_status VARCHAR(20) DEFAULT 'PENDING'
                    CHECK (document_status IN ('PENDING', 'GENERATED')),
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER update_financial_applications_updated_at
    BEFORE UPDATE ON financial_applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX IF NOT EXISTS idx_applications_user_id ON financial_applications(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_applications_conversation_id
    ON financial_applications(conversation_id);
```

**Acción:** [MODIFICAR] `/backend/migrations/005_product_details.sql`:

```sql
-- ============================================================
-- MIGRACIÓN 005: DETALLES MODULARES POR PRODUCTO (Capa 4)
-- ============================================================

-- Detalle de solicitudes de crédito
CREATE TABLE IF NOT EXISTS loan_details (
    application_id              UUID            PRIMARY KEY REFERENCES financial_applications(id),
    -- INPUTS DEL USUARIO
    requested_amount            NUMERIC(14,2)   NOT NULL CHECK (requested_amount BETWEEN 100000 AND 30000000),
    term_months                 SMALLINT        NOT NULL CHECK (term_months BETWEEN 6 AND 48),
    monthly_income              NUMERIC(14,2)   NOT NULL,
    employment_seniority_months SMALLINT        NOT NULL,
    education_level_id          SMALLINT        NOT NULL REFERENCES education_levels(id),
    -- OUTPUTS DEL MOTOR DE RIESGO
    risk_score                  NUMERIC(5,2)    CHECK (risk_score BETWEEN 0 AND 100),
    risk_level_id               SMALLINT        REFERENCES risk_levels(id),
    applied_monthly_rate        NUMERIC(6,4),
    monthly_payment             NUMERIC(14,2),
    max_allowed_payment         NUMERIC(14,2),
    payment_capacity_valid      BOOLEAN,
    total_credit_cost           NUMERIC(14,2),
    total_interest              NUMERIC(14,2),
    cae                         NUMERIC(8,6),
    approved_amount             NUMERIC(14,2),
    approved_term_months        SMALLINT,
    amortization_schedule       JSONB,
    -- AUDITORÍA
    rejection_reason_id         SMALLINT        REFERENCES rejection_reason_codes(id),
    calculated_at               TIMESTAMPTZ,
    calculation_log             TEXT
);

-- Detalle de solicitudes de cuenta corriente
CREATE TABLE IF NOT EXISTS account_details (
    application_id              UUID            PRIMARY KEY REFERENCES financial_applications(id),
    monthly_income              NUMERIC(14,2)   NOT NULL,
    employment_seniority_months SMALLINT        NOT NULL,
    education_level_id          SMALLINT        NOT NULL REFERENCES education_levels(id),
    base_plan_id                SMALLINT        REFERENCES user_categories(id),
    has_education_upgrade       BOOLEAN         NOT NULL DEFAULT FALSE,
    final_plan_id               SMALLINT        REFERENCES user_categories(id),
    credit_line_amount          NUMERIC(14,2)   NOT NULL DEFAULT 0,
    rejection_reason_id         SMALLINT        REFERENCES rejection_reason_codes(id),
    evaluated_at                TIMESTAMPTZ,
    evaluation_log              TEXT,
    metadata                    JSONB
);

-- Detalle de solicitudes de DAP
CREATE TABLE IF NOT EXISTS dap_details (
    application_id          UUID            PRIMARY KEY REFERENCES financial_applications(id),
    investment_amount       NUMERIC(14,2)   NOT NULL,
    investment_amount_clp   NUMERIC(14,2)   NOT NULL,
    currency_id             SMALLINT        NOT NULL REFERENCES currencies(id),
    term_id                 SMALLINT        NOT NULL REFERENCES dap_terms(id),
    base_rate               NUMERIC(6,4)    NOT NULL,
    bonus_rate              NUMERIC(6,4)    NOT NULL,
    ipc_adjustment          NUMERIC(6,4)    NOT NULL DEFAULT 0,
    ipc_value_used          NUMERIC(8,4),
    total_monthly_rate      NUMERIC(8,6)    NOT NULL,
    period_rate             NUMERIC(8,6)    NOT NULL,
    index_value_at_start    NUMERIC(14,6),
    projected_gain          NUMERIC(14,2)   NOT NULL,
    final_amount            NUMERIC(14,2)   NOT NULL,
    rejection_reason_id     SMALLINT        REFERENCES rejection_reason_codes(id),
    calculated_at           TIMESTAMPTZ,
    calculation_log         TEXT,
    metadata                JSONB
);
```

**Acción:** [MODIFICAR] `/backend/migrations/006_security_docs.sql`:

```sql
-- ============================================================
-- MIGRACIÓN 006: SEGURIDAD, INTEGRIDAD Y AUDITORÍA (Capa 5)
-- ============================================================

-- Gestión del ciclo de vida de OTPs (nunca en texto plano)
CREATE TABLE IF NOT EXISTS security_otp (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id    UUID        NOT NULL UNIQUE REFERENCES financial_applications(id),
    otp_hash          VARCHAR(64) NOT NULL,
    attempts          SMALLINT    NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    last_failed_hash  VARCHAR(64),
    is_verified       BOOLEAN     NOT NULL DEFAULT FALSE,
    expires_at        TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_otp_application_id ON security_otp(application_id);

-- ─────────────────────────────────────────────────────────────

-- Registro de contratos PDF generados
CREATE TABLE IF NOT EXISTS documents (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id   UUID        NOT NULL REFERENCES financial_applications(id),
    document_type_id SMALLINT    NOT NULL REFERENCES document_types(id),
    storage_path     VARCHAR(500) NOT NULL,
    sha256_hash      VARCHAR(64) NOT NULL,
    is_active        BOOLEAN     NOT NULL DEFAULT TRUE,
    generated_at     TIMESTAMPTZ NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    external_error_log TEXT
);

CREATE INDEX IF NOT EXISTS idx_documents_app_active
    ON documents(application_id, is_active);

-- ─────────────────────────────────────────────────────────────

-- Caché de indicadores económicos externos (UF, USD, IPC)
CREATE TABLE IF NOT EXISTS economic_history (
    id           BIGSERIAL       PRIMARY KEY,
    indicator_id SMALLINT        NOT NULL REFERENCES economic_indicators(id),
    value        NUMERIC(14,6)   NOT NULL,
    date         DATE            NOT NULL,
    UNIQUE (indicator_id, date)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_economic_history_indicator_date
    ON economic_history(indicator_id, date);
```

**[DETENCIÓN OBLIGATORIA 2.3]**
Reportar en `CP-02-dev1-fase1.md`: Confirmación de que los 3 archivos SQL fueron escritos. Pedir confirmación para continuar al sub-paso 2.4.

---

## Sub-paso 2.4 — Escribir el seed de catálogos

**Acción:** [MODIFICAR] `/backend/migrations/000_seed.sql` con los datos iniciales para todas las tablas de catálogo:

```sql
-- ============================================================
-- SEED 000: DATOS INICIALES DE CATÁLOGOS
-- Ejecutar DESPUÉS de todas las migraciones de estructura.
-- ============================================================

-- user_statuses
INSERT INTO user_statuses (code, name, description) VALUES
    ('ACTIVE',            'Activo',             'Usuario puede operar normalmente en el sistema.'),
    ('BLOCKED_SECURITY',  'Bloqueado por Seguridad', 'El Security Watchdog bloqueó al usuario por intentos fallidos de OTP. No puede iniciar ningún flujo.'),
    ('PROSPECT',          'Prospecto',           'Usuario registrado que aún no ha completado ningún proceso.')
ON CONFLICT (code) DO NOTHING;

-- user_categories
INSERT INTO user_categories (code, name, description) VALUES
    ('START',   'Start',   'Categoría básica. Sin línea de crédito asociada a cuenta corriente.'),
    ('MEDIUM',  'Medium',  'Categoría media. Línea de crédito = renta × 0.50 si antigüedad ≥ 12 meses.'),
    ('ADVANCE', 'Advance', 'Categoría avanzada. Línea de crédito = renta × 0.50 si antigüedad ≥ 12 meses.')
ON CONFLICT (code) DO NOTHING;

-- product_types
INSERT INTO product_types (code, name, is_enabled) VALUES
    ('LOAN',    'Crédito de Consumo',   TRUE),
    ('ACCOUNT', 'Cuenta Corriente',     TRUE),
    ('DAP',     'Depósito a Plazo',     TRUE)
ON CONFLICT (code) DO NOTHING;

-- application_statuses
INSERT INTO application_statuses (code, name, description) VALUES
    ('IN_PROGRESS',    'En Progreso',         'El usuario está actualmente completando el flujo.'),
    ('PRE_APPROVED',   'Pre-Aprobado',        'El motor de cálculo aprobó la solicitud. Esperando aceptación del usuario.'),
    ('REJECTED',       'Rechazado',           'La solicitud fue rechazada por políticas de riesgo o elegibilidad.'),
    ('COMPLETED',      'Completado',          'El flujo terminó exitosamente. Contrato generado y firmado.'),
    ('CLOSED_BY_USER', 'Cerrado por Usuario', 'El usuario abandonó voluntariamente el proceso.')
ON CONFLICT (code) DO NOTHING;

-- education_levels
INSERT INTO education_levels (code, name, credit_score_points, grants_account_upgrade) VALUES
    ('POSTGRADO',     'Postgrado',     20, TRUE),
    ('UNIVERSITARIO', 'Universitario', 15, TRUE),
    ('TECNICO',       'Técnico',       10, FALSE),
    ('MEDIA',         'Enseñanza Media', 5, FALSE)
ON CONFLICT (code) DO NOTHING;

-- risk_levels
INSERT INTO risk_levels (code, name, min_score, max_score, monthly_rate) VALUES
    ('BAJO',  'Riesgo Bajo',  81, 100, 0.0120),
    ('MEDIO', 'Riesgo Medio', 50,  80, 0.0200),
    ('ALTO',  'Riesgo Alto',   0,  49, 0.0350)
ON CONFLICT (code) DO NOTHING;

-- rejection_reason_codes
INSERT INTO rejection_reason_codes (code, description) VALUES
    ('ERR_EDAD',           'El usuario tiene menos de 18 años. Política de elegibilidad: no se otorgan créditos a menores de edad.'),
    ('ERR_RENTA',          'La renta declarada es inferior al mínimo legal o al umbral mínimo de la política de crédito.'),
    ('ERR_ANTIGUEDAD',     'El usuario lleva menos de 6 meses en su trabajo actual. Política de estabilidad laboral mínima.'),
    ('ERR_SCORING',        'El puntaje total de scoring es inferior al mínimo requerido (< 50 puntos equivale a rechazo por política).'),
    ('ERR_CAPACIDAD_PAGO', 'La cuota mensual calculada supera el 30% de la renta declarada. Límite de endeudamiento responsable.'),
    ('ERR_MONTO',          'El monto de inversión en DAP no se encuentra dentro del rango permitido ($50.000 – $50.000.000 CLP).')
ON CONFLICT (code) DO NOTHING;

-- currencies
INSERT INTO currencies (code, name, applies_ipc_adjustment) VALUES
    ('CLP', 'Peso Chileno',   TRUE),
    ('UF',  'Unidad de Fomento', FALSE),
    ('USD', 'Dólar Americano', FALSE)
ON CONFLICT (code) DO NOTHING;

-- dap_terms
INSERT INTO dap_terms (days, label, bonus_rate) VALUES
    (7,   '7 días',    0.0000),
    (14,  '14 días',   0.0000),
    (30,  '30 días',   0.0005),
    (180, '180 días',  0.0030),
    (360, '360 días',  0.0060)
ON CONFLICT (days) DO NOTHING;

-- document_types (depende de product_types ya insertado)
INSERT INTO document_types (code, name, product_type_id)
SELECT 'CONTRATO_CREDITO', 'Contrato de Crédito de Consumo', id FROM product_types WHERE code = 'LOAN'
ON CONFLICT (code) DO NOTHING;

INSERT INTO document_types (code, name, product_type_id)
SELECT 'CONTRATO_CUENTA', 'Contrato de Apertura de Cuenta Corriente', id FROM product_types WHERE code = 'ACCOUNT'
ON CONFLICT (code) DO NOTHING;

INSERT INTO document_types (code, name, product_type_id)
SELECT 'CONTRATO_DAP', 'Contrato de Depósito a Plazo', id FROM product_types WHERE code = 'DAP'
ON CONFLICT (code) DO NOTHING;

-- economic_indicators
INSERT INTO economic_indicators (code, name, description) VALUES
    ('UF',  'Unidad de Fomento', 'Unidad monetaria reajustable chilena. Se consulta diariamente desde la API del Banco Central o mindicador.cl'),
    ('USD', 'Dólar Americano',   'Tipo de cambio CLP/USD. Se consulta diariamente.'),
    ('IPC', 'Índice de Precios al Consumidor', 'Indicador de inflación mensual. Se usa para ajustar la tasa del DAP en CLP.')
ON CONFLICT (code) DO NOTHING;
```

**[DETENCIÓN OBLIGATORIA 2.4]**
Reportar en `CP-02-dev1-fase1.md`: Confirmación del seed. Pedir confirmación para continuar al sub-paso 2.5.

---

## Sub-paso 2.5 — Ejecutar migraciones y seed en Supabase

**Acción:** Las migraciones deben ejecutarse en el **SQL Editor** del dashboard de Supabase, en el siguiente orden estricto:

1. `001_catalogs.sql`
2. `002_identity.sql`
3. `003_conversations.sql`
4. `004_applications.sql`
5. `005_product_details.sql`
6. `006_security_docs.sql`
7. `000_seed.sql` (seed siempre último)

**El agente debe presentar cada script al desarrollador humano indicando cuál ejecutar a continuación.** No ejecutar el siguiente hasta confirmar que el anterior terminó sin errores en el dashboard de Supabase.

Si algún script falla, **no continuar**. Reportar el error SQL exacto en el CP y esperar instrucciones.

**[DETENCIÓN OBLIGATORIA 2.5]**
Reportar en `CP-02-dev1-fase1.md`:
- Confirmación de cada migración ejecutada.
- Número de filas insertadas en el seed (verificar con `SELECT COUNT(*) FROM user_statuses` etc.).
- Pedir confirmación para continuar al sub-paso 2.6.

---

## Sub-paso 2.6 — Implementar `app/infra/supabase.py`

**Acción:** [MODIFICAR] `/backend/app/infra/supabase.py`:

```python
"""
app/infra/supabase.py
─────────────────────────────────────────────────────────────
Cliente centralizado para interacción con Supabase.

PROCESO: Inicializa el cliente de Supabase usando las variables de
         entorno. Expone funciones helper para las operaciones de DB
         más frecuentes del sistema.

SALIDA:  Instancias `supabase_client` (para operaciones CRUD) y
         `supabase_admin` (para operaciones que requieren service_role).
         Funciones de acceso a datos para conversations y messages.
"""

from supabase import create_client, Client
from app.config import settings


# ── Clientes ─────────────────────────────────────────────────

# Cliente estándar (anon key) — para operaciones del grafo
supabase_client: Client = create_client(
    settings.supabase_url,
    settings.supabase_anon_key
)

# Cliente admin (service role) — para operaciones privilegiadas (Auth, etc.)
supabase_admin: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key
)


# ── Helpers de Usuario ────────────────────────────────────────

def get_user_by_email(email: str) -> dict | None:
    """
    Recupera los datos de un usuario desde la tabla `users` por email.

    INPUT:  email (str) — correo del usuario autenticado via Supabase Auth.
    PROCESO: Consulta la tabla `users` con JOIN a `user_statuses`.
    OUTPUT: Diccionario con los campos del usuario, o None si no existe.
    """
    response = (
        supabase_client
        .table("users")
        .select("*, user_statuses(code)")
        .eq("email", email)
        .maybe_single()
        .execute()
    )
    return response.data


def get_user_by_id(user_id: str) -> dict | None:
    """
    Recupera los datos de un usuario desde la tabla `users` por UUID.

    INPUT:  user_id (str) — UUID del usuario.
    OUTPUT: Diccionario con los campos del usuario, o None si no existe.
    """
    response = (
        supabase_client
        .table("users")
        .select("*, user_statuses(code)")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return response.data


# ── Helpers de Conversación ───────────────────────────────────

def create_conversation(user_id: str, product_type_code: str | None = None) -> dict:
    """
    Crea un nuevo hilo de conversación en la tabla `conversations`.

    INPUT:  user_id (str) — UUID del usuario.
            product_type_code (str | None) — Código del producto si ya se conoce.
    PROCESO: Si se provee product_type_code, resuelve su ID desde `product_types`.
             Crea el registro en `conversations`.
    OUTPUT: Diccionario con los datos de la conversación creada (incluye el `id` = thread_id).
    """
    data = {"user_id": user_id, "is_active": True}

    if product_type_code:
        pt = (
            supabase_client
            .table("product_types")
            .select("id")
            .eq("code", product_type_code)
            .single()
            .execute()
        )
        if pt.data:
            data["product_type_id"] = pt.data["id"]

    response = supabase_client.table("conversations").insert(data).execute()
    return response.data[0]


def save_message(conversation_id: str, role: str, content: str,
                 node_at_time: str | None = None,
                 extracted_data: dict | None = None) -> dict:
    """
    Persiste un mensaje en la tabla `messages`.

    INPUT:  conversation_id (str) — UUID de la conversación.
            role (str) — 'user', 'assistant' o 'system'.
            content (str) — Texto del mensaje.
            node_at_time (str | None) — Nodo de LangGraph activo al generarse el mensaje.
            extracted_data (dict | None) — Entidades extraídas por el LLM (si aplica).
    OUTPUT: Diccionario con el registro del mensaje creado.
    """
    data = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
    }
    if node_at_time:
        data["node_at_time"] = node_at_time
    if extracted_data:
        data["extracted_data"] = extracted_data

    response = supabase_client.table("messages").insert(data).execute()
    return response.data[0]


def get_conversation_messages(conversation_id: str) -> list[dict]:
    """
    Recupera todos los mensajes de una conversación en orden cronológico.

    INPUT:  conversation_id (str) — UUID de la conversación.
    PROCESO: Consulta la tabla `messages` ordenada por `created_at ASC`.
    OUTPUT: Lista de diccionarios con los mensajes.
    """
    response = (
        supabase_client
        .table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []


def update_conversation_node(conversation_id: str, current_node: str,
                              state_snapshot: dict | None = None) -> None:
    """
    Actualiza el nodo activo y el snapshot de estado de una conversación.

    INPUT:  conversation_id (str) — UUID de la conversación.
            current_node (str) — Nombre del nodo LangGraph activo.
            state_snapshot (dict | None) — Estado serializado del grafo.
    PROCESO: UPDATE en la tabla `conversations`. El trigger updated_at se dispara automáticamente.
    OUTPUT: None. Lanza excepción si falla.
    """
    data = {"current_node": current_node}
    if state_snapshot:
        data["state_snapshot"] = state_snapshot

    supabase_client.table("conversations").update(data).eq("id", conversation_id).execute()
```

**[DETENCIÓN OBLIGATORIA 2.6]**
Reportar en `CP-02-dev1-fase1.md`: Confirmación del archivo. Pedir confirmación para continuar al sub-paso 2.7.

---

## Sub-paso 2.7 — Configurar el PostgresSaver (Checkpointer de LangGraph)

**Acción:** [CREAR] `/backend/app/infra/checkpointer.py`:

```python
"""
app/infra/checkpointer.py
─────────────────────────────────────────────────────────────
Configuración del checkpointer de LangGraph usando PostgreSQL (Supabase).

PROCESO: El PostgresSaver permite que LangGraph persista el estado del
         grafo (State) en la base de datos de Supabase después de cada
         paso del grafo, usando el `thread_id` como clave de recuperación.

         Esto es lo que permite al RESUME_HANDLER reanudar una sesión
         exactamente donde el usuario la dejó, incluso días después.

SALIDA:  Función `get_checkpointer()` que retorna una instancia del saver
         lista para ser pasada al `StateGraph.compile()`.

NOTA:    Usa la cadena de conexión DATABASE_URL (PostgreSQL directo),
         no el cliente HTTP de Supabase, porque el checkpointer necesita
         acceso de bajo nivel a las tablas internas de LangGraph.
"""

from langgraph.checkpoint.postgres import PostgresSaver
from app.config import settings


def get_checkpointer() -> PostgresSaver:
    """
    Retorna una instancia del PostgresSaver configurada con la conexión a Supabase.

    INPUT:  Ninguno (lee DATABASE_URL desde settings).
    PROCESO: Crea el saver y llama a setup() para crear las tablas internas
             de LangGraph (checkpoints, checkpoint_blobs, checkpoint_writes)
             si no existen aún.
    OUTPUT: Instancia de PostgresSaver lista para compilación del grafo.
    """
    saver = PostgresSaver.from_conn_string(settings.database_url)
    # Crea las tablas internas de LangGraph en Supabase (idempotente)
    saver.setup()
    return saver
```

**[DETENCIÓN OBLIGATORIA 2.7]**
Reportar en `CP-02-dev1-fase1.md`: Confirmación del archivo. Pedir confirmación para continuar al checkpoint del Paso 2.

---

## ✅ CHECKPOINT 2 — Pruebas del Paso 2

**El agente debe completar las siguientes pruebas y documentar resultados en `CP-02-dev1-fase1.md`.**

---

### Prueba 2.A — Test de Integración: Conectividad con Supabase

**Objetivo:** Verificar que el cliente de Supabase se inicializa correctamente y puede realizar una consulta básica.

**Diseño:** [MODIFICAR] `/backend/tests/test_db.py`:

```python
"""Tests de integración para la capa de persistencia."""
import pytest


def test_supabase_client_initializes():
    """Verifica que el cliente Supabase se crea sin errores."""
    from app.infra.supabase import supabase_client
    assert supabase_client is not None


def test_supabase_can_read_catalog():
    """Verifica conectividad real consultando la tabla de catálogo user_statuses."""
    from app.infra.supabase import supabase_client

    response = supabase_client.table("user_statuses").select("code").execute()
    assert response.data is not None
    codes = [row["code"] for row in response.data]
    assert "ACTIVE" in codes
    assert "BLOCKED_SECURITY" in codes
    assert "PROSPECT" in codes


def test_seed_data_completeness():
    """Verifica que todos los catálogos tienen los registros del seed."""
    from app.infra.supabase import supabase_client

    catalogs = {
        "user_statuses": 3,
        "user_categories": 3,
        "product_types": 3,
        "application_statuses": 5,
        "education_levels": 4,
        "risk_levels": 3,
        "rejection_reason_codes": 6,
        "currencies": 3,
        "dap_terms": 5,
        "document_types": 3,
        "economic_indicators": 3,
    }

    for table, expected_count in catalogs.items():
        response = supabase_client.table(table).select("id", count="exact").execute()
        actual_count = response.count
        assert actual_count == expected_count, \
            f"Tabla '{table}': esperaba {expected_count} filas, encontré {actual_count}"
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/test_db.py::test_supabase_client_initializes tests/test_db.py::test_supabase_can_read_catalog tests/test_db.py::test_seed_data_completeness -v`

**Resultado esperado:** 3 tests `PASSED`.

**Interpretación:** Si falla `test_supabase_client_initializes` → problema con las credenciales en `.env`. Si falla `test_seed_data_completeness` → alguna migración o seed no se ejecutó correctamente; revisar el SQL Editor de Supabase.

---

### Prueba 2.B — Test de Integración: Helpers de Conversación

**Objetivo:** Verificar el ciclo de vida básico de una conversación en la DB (crear → guardar mensajes → recuperar).

**Diseño:** Agregar al final de `/backend/tests/test_db.py`:

```python
def test_conversation_lifecycle():
    """
    Prueba el ciclo completo: crear conversación, guardar mensajes, recuperarlos.
    NOTA: Este test crea datos reales en Supabase. Requiere un user_id válido.
          Si no existe un usuario de prueba, el test se saltará con una advertencia.
    """
    from app.infra.supabase import supabase_client, create_conversation, save_message, get_conversation_messages

    # Verificar si hay al least un usuario de prueba disponible
    users = supabase_client.table("users").select("id").limit(1).execute()
    if not users.data:
        pytest.skip("No hay usuarios en la DB. Insertar un usuario de prueba para ejecutar este test.")

    test_user_id = users.data[0]["id"]

    # Crear conversación
    conv = create_conversation(user_id=test_user_id)
    assert conv is not None
    assert "id" in conv
    conversation_id = conv["id"]

    # Guardar mensajes
    msg1 = save_message(conversation_id, "user", "Hola, quiero un crédito", node_at_time="INTENT_ROUTER")
    msg2 = save_message(conversation_id, "assistant", "¡Perfecto! Te ayudaré con eso.", node_at_time="WELCOME_NODE")

    assert msg1["role"] == "user"
    assert msg2["role"] == "assistant"

    # Recuperar mensajes
    messages = get_conversation_messages(conversation_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

    # Limpieza (opcional, pero recomendable para no contaminar la DB)
    supabase_client.table("messages").delete().eq("conversation_id", conversation_id).execute()
    supabase_client.table("conversations").delete().eq("id", conversation_id).execute()
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/test_db.py -v`

**Resultado esperado:** Todos los tests en `PASSED` (o el último en `SKIPPED` si no hay usuario de prueba en la DB).

---

### Prueba 2.C — Test de Integración: PostgresSaver (Checkpointer)

**Objetivo:** Verificar que el PostgresSaver puede conectarse a Supabase y crear sus tablas internas.

**Diseño:** Agregar al final de `/backend/tests/test_db.py`:

```python
def test_checkpointer_setup():
    """
    Verifica que el PostgresSaver se inicializa y ejecuta setup() sin errores.
    Setup() es idempotente: si las tablas ya existen, no falla.
    """
    from app.infra.checkpointer import get_checkpointer
    checkpointer = get_checkpointer()
    assert checkpointer is not None
    # Si llegamos aquí sin excepción, la conexión y el setup fueron exitosos
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/test_db.py::test_checkpointer_setup -v`

**Resultado esperado:** `PASSED`.

**Interpretación:** Si falla → Verificar que `DATABASE_URL` en `.env` es la cadena de conexión directa de Supabase (no el endpoint REST). Se obtiene desde el dashboard de Supabase en `Project Settings → Database → Connection string → URI`.

---

**[DETENCIÓN OBLIGATORIA — CIERRE PASO 2]**

El agente debe agregar a `CP-02-dev1-fase1.md` el **Reporte Final del Paso 2**, incluyendo:
1. Resumen de todas las migraciones ejecutadas con su estado.
2. Resultado de cada prueba del checkpoint.
3. Número de tablas creadas y registros seed insertados.
4. Estado general: PASO 2 COMPLETADO / PASO 2 BLOQUEADO.
5. Solicitar aprobación explícita para iniciar el Paso 3.

---
---

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
---

# PASO 4 — Core del Grafo LangGraph

**Objetivo:** Definir el esquema de estado global del grafo, implementar los nodos fundamentales (`WELCOME_NODE` e `INTENT_ROUTER`), configurar el `workflow.py` y compilar el grafo con el checkpointer de Supabase.

**Al comenzar este paso, el agente debe [CREAR] el archivo `CP-04-dev1-fase1.md`.**

---

## Sub-paso 4.1 — Definir el StateSchema en `app/graph/state.py`

**Acción:** [MODIFICAR] `/backend/app/graph/state.py`:

```python
"""
app/graph/state.py
─────────────────────────────────────────────────────────────
Definición del Estado Global del Grafo (The Single Source of Truth).

REGLA DE ORO #1: Este archivo es la única fuente de verdad del sistema.
Ningún desarrollador puede modificarlo sin aprobación del Dev 1 (Orchestrator).

PROCESO: Define el TypedDict FluxState que LangGraph usa como contenedor
         de información entre nodos. Cada clave tiene un propósito específico
         y su escritura está reservada a los nodos indicados en los comentarios.

SALIDA:  Clase FluxState importada por workflow.py y todos los nodos.
"""

from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages


class UserData(TypedDict, total=False):
    """
    Datos del usuario cargados desde la DB al iniciar el grafo.
    Estos campos son inmutables durante la sesión; solo WELCOME_NODE los escribe.
    """
    user_id: str           # UUID del usuario en la tabla `users`
    full_name: str         # Nombre completo para personalización de mensajes
    email: str             # Correo para envío de OTP
    rut: str               # RUT (sin puntos, con guión)
    birth_date: str        # Fecha de nacimiento ISO8601 (para cálculo de edad)
    user_status: str       # Código de estado: ACTIVE, BLOCKED_SECURITY, PROSPECT
    user_category: str | None  # START, MEDIUM, ADVANCE o None


class SessionData(TypedDict, total=False):
    """
    Datos de la sesión conversacional activa.
    Estos campos los escriben los nodos de orquestación.
    """
    conversation_id: str       # UUID de la conversación = thread_id de LangGraph
    application_id: str | None # UUID de la solicitud en financial_applications
    product_intent: str | None # Intención detectada: LOAN, ACCOUNT, DAP, GENERAL
    current_node: str          # Nombre del nodo activo (para el GPS visual del FE)
    previous_node: str | None  # Nodo previo (para retorno desde transversales)
    is_transversal_active: bool  # True si el flujo está en un nodo transversal


class FluxState(TypedDict):
    """
    Estado global del Grafo FLUX.
    
    Es el TypedDict raíz que LangGraph serializa y persiste en el
    checkpointer de Supabase después de cada transición de nodo.

    CAMPOS:
    - messages: Historial de mensajes LangChain (acumulativo, no reemplazable).
                Usa `add_messages` como reducer para que cada nodo agregue
                mensajes sin sobreescribir el historial anterior.
    - user_data: Perfil del usuario cargado desde la DB.
    - session:   Metadatos de la sesión activa (IDs, intención, nodo GPS).
    - collected_data: Datos recolectados por los nodos de extracción.
                      Es un dict flexible para acomodar los distintos productos.
    - control_flags: Flags de control del flujo del grafo.
    """

    # ── Mensajes (reducer acumulativo) ───────────────────────
    messages: Annotated[list, add_messages]

    # ── Datos del Usuario (escritura única: WELCOME_NODE) ────
    user_data: UserData

    # ── Sesión Activa ─────────────────────────────────────────
    session: SessionData

    # ── Datos Recolectados (escritura: nodos de extracción) ──
    # Estructura flexible: cada producto agrega sus llaves sin conflicto.
    # Ejemplo LOAN: {"renta": 1500000, "antiguedad": 12, "nivel_estudios": "UNIVERSITARIO"}
    # Ejemplo DAP:  {"monto_inversion": 5000000, "moneda": "CLP", "plazo_dias": 180}
    collected_data: dict

    # ── Flags de Control del Flujo ────────────────────────────
    # Escritura reservada a nodos de seguridad y manejo de errores.
    control_flags: dict
    # Estructura esperada de control_flags:
    # {
    #   "security_blocked": bool,    # True si SECURITY_WATCHDOG bloqueó el flujo
    #   "service_error": bool,       # True si un servicio externo falló
    #   "otp_attempts": int,         # Contador de intentos de OTP (0-3)
    #   "error_detail": str | None,  # Descripción técnica del error para logging
    # }
```

**[DETENCIÓN OBLIGATORIA 4.1]**
Reportar en `CP-04-dev1-fase1.md`: Confirmación del StateSchema. Si el agente considera que falta algún campo basado en los documentos de referencia (credito-datos.md, estados-transversales.md), debe documentarlo como nota técnica y pedir instrucciones. Pedir confirmación para continuar al sub-paso 4.2.

---

## Sub-paso 4.2 — Implementar `WELCOME_NODE` en `app/graph/nodes/common.py`

**Acción:** [MODIFICAR] `/backend/app/graph/nodes/common.py`:

```python
"""
app/graph/nodes/common.py
─────────────────────────────────────────────────────────────
Nodos transversales y utilitarios del Grafo FLUX.

Contiene los nodos compartidos por todos los flujos de producto:
- WELCOME_NODE: Saludo inicial y carga del perfil de usuario.
- INTENT_ROUTER_NODE: Clasificador de intención del primer mensaje.

Fase 3 agregará aquí: KNOWLEDGE_BASE_RAG, AMBIGUITY_HANDLER,
SERVICE_ERROR_HANDLER, SECURITY_WATCHDOG, GLOBAL_END, RESUME_HANDLER.
"""

from langchain_core.messages import AIMessage, SystemMessage
from app.graph.state import FluxState
from app.infra.supabase import get_user_by_email, update_conversation_node
from app.infra.gemini_client import get_chat_model


# ── WELCOME_NODE ──────────────────────────────────────────────

def welcome_node(state: FluxState) -> dict:
    """
    Nodo de bienvenida y carga de perfil de usuario.

    INPUT (State):
        - state["session"]["conversation_id"]: UUID de la conversación activa.
        - state["user_data"]["email"]: Email del usuario autenticado.
        - state["messages"]: Historial de mensajes (puede estar vacío en sesión nueva
          o contener historial en sesión reanudada).

    PROCESO:
        1. Verifica si es una sesión nueva o reanudada basándose en
           la presencia de mensajes previos en el historial.
        2. Si es nueva: saluda al usuario por su nombre.
        3. Si es reanudada: genera un saludo de continuación referenciando
           el punto donde se abandonó la sesión (previous_node).
        4. Actualiza el `current_node` en la DB (GPS del frontend).

    OUTPUT (campos del State que modifica):
        - messages: Agrega el mensaje de bienvenida del asistente.
        - session["current_node"]: Actualizado a "WELCOME_NODE".
    """
    user = state.get("user_data", {})
    session = state.get("session", {})
    messages = state.get("messages", [])
    full_name = user.get("full_name", "")
    first_name = full_name.split()[0] if full_name else "amig@"

    # Determinar si es sesión nueva o reanudada
    is_resumed = len(messages) > 0 and session.get("previous_node") is not None

    if is_resumed:
        previous_node = session.get("previous_node", "")
        welcome_text = (
            f"¡Hola de nuevo, {first_name}! 👋 Veo que nos habíamos quedado a mitad del camino. "
            f"No te preocupes, tu progreso está guardado. ¿Continuamos donde lo dejamos?"
        )
    else:
        welcome_text = (
            f"¡Hola, {first_name}! 👋 Soy Flux, tu asistente financiero. "
            f"Estoy aquí para ayudarte a solicitar un **Crédito de Consumo**, "
            f"abrir una **Cuenta Corriente**, o contratar un **Depósito a Plazo**. "
            f"¿Con qué te puedo ayudar hoy?"
        )

    # Actualizar GPS en la DB
    conversation_id = session.get("conversation_id")
    if conversation_id:
        update_conversation_node(conversation_id, "WELCOME_NODE")

    return {
        "messages": [AIMessage(content=welcome_text)],
        "session": {**session, "current_node": "WELCOME_NODE"},
    }


# ── INTENT_ROUTER_NODE ────────────────────────────────────────

_INTENT_SYSTEM_PROMPT = """
Eres el clasificador de intenciones de FLUX, un sistema bancario conversacional.
Tu única función es analizar el mensaje del usuario y clasificar su intención
en UNA de las siguientes categorías exactas. Responde SOLO con la categoría, sin explicaciones.

CATEGORÍAS:
- LOAN: El usuario quiere solicitar un crédito, préstamo, financiamiento o dinero prestado.
- ACCOUNT: El usuario quiere abrir una cuenta corriente, cuenta bancaria o cuenta de cheques.
- DAP: El usuario quiere invertir, hacer un depósito a plazo, ahorrar con intereses o un DAP.
- GENERAL: El usuario tiene una pregunta general, duda, saludo, o algo que no encaja en las categorías anteriores.

EJEMPLOS:
"Quiero un crédito de 5 millones" → LOAN
"Necesito abrir una cuenta" → ACCOUNT
"¿Puedo invertir mi sueldo?" → DAP
"¿Cómo funciona esto?" → GENERAL
"hola" → GENERAL
"¿Qué es el CAE?" → GENERAL
"""


def intent_router_node(state: FluxState) -> dict:
    """
    Nodo clasificador de la intención inicial del usuario.

    INPUT (State):
        - state["messages"]: Último mensaje del usuario.
        - state["session"]: Datos de sesión actuales.

    PROCESO:
        1. Extrae el último mensaje del usuario del historial.
        2. Envía el mensaje al LLM con el prompt de clasificación.
        3. Parsea la respuesta para obtener el código de intención (LOAN, ACCOUNT, DAP, GENERAL).
        4. Actualiza el product_intent en el estado.

    OUTPUT (campos del State que modifica):
        - session["product_intent"]: Código de intención detectada.
        - session["current_node"]: Actualizado a "INTENT_ROUTER".
    """
    from langchain_core.messages import HumanMessage

    messages = state.get("messages", [])
    session = state.get("session", {})

    # Obtener el último mensaje del usuario
    last_user_message = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_message = msg.content
            break

    if not last_user_message:
        # Si no hay mensaje del usuario, asumir intención GENERAL
        intent = "GENERAL"
    else:
        model = get_chat_model()
        classification_messages = [
            SystemMessage(content=_INTENT_SYSTEM_PROMPT),
            HumanMessage(content=last_user_message),
        ]
        response = model.invoke(classification_messages)
        raw_intent = response.content.strip().upper()

        # Validar que la respuesta es una categoría válida
        valid_intents = {"LOAN", "ACCOUNT", "DAP", "GENERAL"}
        intent = raw_intent if raw_intent in valid_intents else "GENERAL"

    return {
        "session": {
            **session,
            "product_intent": intent,
            "current_node": "INTENT_ROUTER",
        }
    }
```

**[DETENCIÓN OBLIGATORIA 4.2]**
Reportar en `CP-04-dev1-fase1.md`: Confirmación de los nodos. Pedir confirmación para continuar al sub-paso 4.3.

---

## Sub-paso 4.3 — Implementar `app/graph/edges.py`

**Acción:** [MODIFICAR] `/backend/app/graph/edges.py`:

```python
"""
app/graph/edges.py
─────────────────────────────────────────────────────────────
Lógica de ruteo condicional entre nodos del Grafo FLUX.

PROCESO: Define las funciones que LangGraph usa como Conditional Edges
         para decidir, basándose en el State, qué nodo ejecutar a continuación.

SALIDA:  Funciones que retornan el nombre del próximo nodo como string.
"""

from app.graph.state import FluxState


def route_after_welcome(state: FluxState) -> str:
    """
    Función de ruteo ejecutada después de WELCOME_NODE.

    INPUT (State): state["session"]["product_intent"]
    PROCESO: Si ya se detectó una intención (sesión reanudada), redirigir
             directamente al nodo de entrada del producto. Si no, ir al router.
    OUTPUT: Nombre del nodo destino como string.
    """
    session = state.get("session", {})
    product_intent = session.get("product_intent")

    # Si ya había intención detectada (sesión reanudada), reanudar el flujo
    if product_intent == "LOAN":
        return "loan_entry"   # Placeholder: en Fase 2 será LOAN_INIT
    elif product_intent == "ACCOUNT":
        return "account_entry"  # Placeholder: en Fase 3 será ACCOUNT_INIT
    elif product_intent == "DAP":
        return "dap_entry"    # Placeholder: en Fase 3 será DAP_INIT

    # Sin intención previa → ir al clasificador
    return "intent_router"


def route_after_intent(state: FluxState) -> str:
    """
    Función de ruteo ejecutada después de INTENT_ROUTER_NODE.

    INPUT (State): state["session"]["product_intent"]
    PROCESO: Dirige al nodo de entrada del producto correspondiente.
             En Fase 1, los nodos de producto son stubs que solo confirman
             la intención detectada.
    OUTPUT: Nombre del nodo destino como string.
    """
    session = state.get("session", {})
    product_intent = session.get("product_intent", "GENERAL")

    if product_intent == "LOAN":
        return "loan_entry"
    elif product_intent == "ACCOUNT":
        return "account_entry"
    elif product_intent == "DAP":
        return "dap_entry"
    else:
        return "general_response"
```

**[DETENCIÓN OBLIGATORIA 4.3]**
Reportar en `CP-04-dev1-fase1.md`: Confirmación del archivo. Pedir confirmación para continuar al sub-paso 4.4.

---

## Sub-paso 4.4 — Crear stubs de nodos de producto en credit.py, account.py, deposit.py

**Acción:** [MODIFICAR] los tres archivos con stubs funcionales que confirman la intención y esperan implementación en fases futuras.

**`/backend/app/graph/nodes/credit.py`:**
```python
"""
app/graph/nodes/credit.py
─────────────────────────────────────────────────────────────
Nodos del flujo de Crédito de Consumo.
FASE 1: Solo contiene el nodo de entrada (stub).
FASE 2: Se implementarán todos los nodos del flujo completo.
"""
from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def loan_entry_node(state: FluxState) -> dict:
    """
    INPUT: state["session"]["product_intent"] == "LOAN"
    PROCESO: [STUB FASE 1] Confirma la intención y avisa que el flujo completo viene en Fase 2.
    OUTPUT: messages (confirmación), session["current_node"] = "LOAN_ENTRY_STUB"
    """
    user_data = state.get("user_data", {})
    first_name = user_data.get("full_name", "").split()[0] or "amig@"
    msg = (
        f"¡Perfecto, {first_name}! Entendido, quieres solicitar un **Crédito de Consumo**. "
        f"El flujo completo estará disponible muy pronto. ¡Gracias por tu paciencia!"
    )
    session = state.get("session", {})
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "LOAN_ENTRY_STUB"},
    }
```

**`/backend/app/graph/nodes/account.py`:**
```python
"""
app/graph/nodes/account.py
FASE 1: Stub. FASE 3: Implementación completa.
"""
from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def account_entry_node(state: FluxState) -> dict:
    """
    INPUT: state["session"]["product_intent"] == "ACCOUNT"
    PROCESO: [STUB FASE 1]
    OUTPUT: messages (confirmación stub)
    """
    session = state.get("session", {})
    msg = "Entendido, quieres abrir una **Cuenta Corriente**. El flujo completo estará disponible en Fase 3."
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "ACCOUNT_ENTRY_STUB"},
    }
```

**`/backend/app/graph/nodes/deposit.py`:**
```python
"""
app/graph/nodes/deposit.py
FASE 1: Stub. FASE 3: Implementación completa.
"""
from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def deposit_entry_node(state: FluxState) -> dict:
    """
    INPUT: state["session"]["product_intent"] == "DAP"
    PROCESO: [STUB FASE 1]
    OUTPUT: messages (confirmación stub)
    """
    session = state.get("session", {})
    msg = "Entendido, quieres contratar un **Depósito a Plazo**. El flujo completo estará disponible en Fase 3."
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "DAP_ENTRY_STUB"},
    }
```

Agregar también un nodo de respuesta general en `/backend/app/graph/nodes/common.py` (al final del archivo):

```python
def general_response_node(state: FluxState) -> dict:
    """
    INPUT: state["messages"] (último mensaje del usuario con intención GENERAL)
    PROCESO: Genera una respuesta empática para preguntas generales o saludos,
             redirigiendo al usuario hacia los productos disponibles.
    OUTPUT: messages (respuesta general)
    """
    session = state.get("session", {})
    msg = (
        "¡Hola! Estoy aquí para ayudarte. Puedo asistirte con:\n\n"
        "• 💳 **Crédito de Consumo** — Financiamiento para lo que necesitas\n"
        "• 🏦 **Cuenta Corriente** — Abre tu cuenta hoy\n"
        "• 📈 **Depósito a Plazo** — Haz crecer tu dinero\n\n"
        "¿Con cuál de estos productos te puedo ayudar?"
    )
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "GENERAL_RESPONSE"},
    }
```

**[DETENCIÓN OBLIGATORIA 4.4]**
Reportar en `CP-04-dev1-fase1.md`: Confirmación de los 4 archivos. Pedir confirmación para continuar al sub-paso 4.5.

---

## Sub-paso 4.5 — Compilar el Grafo en `app/graph/workflow.py`

**Acción:** [MODIFICAR] `/backend/app/graph/workflow.py`:

```python
"""
app/graph/workflow.py
─────────────────────────────────────────────────────────────
Definición, compilación y exposición del Grafo de Estados FLUX.

PROCESO: Instancia el StateGraph, registra todos los nodos y aristas,
         y compila el grafo con el checkpointer de Supabase.
         El resultado es `compiled_graph`, el objeto que los endpoints
         de FastAPI invocan para procesar mensajes.

SALIDA:  `compiled_graph` — instancia de CompiledGraph lista para invoke/stream.
"""

from langgraph.graph import StateGraph, END

from app.graph.state import FluxState
from app.graph.nodes.common import (
    welcome_node,
    intent_router_node,
    general_response_node,
)
from app.graph.nodes.credit import loan_entry_node
from app.graph.nodes.account import account_entry_node
from app.graph.nodes.deposit import deposit_entry_node
from app.graph.edges import route_after_welcome, route_after_intent
from app.infra.checkpointer import get_checkpointer


# ── Construcción del Grafo ────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Construye y retorna el StateGraph sin compilar.
    Útil para testing de la estructura del grafo.

    INPUT:  Ninguno.
    PROCESO: Crea un StateGraph con FluxState, agrega nodos y aristas.
    OUTPUT: Instancia de StateGraph sin compilar.
    """
    graph = StateGraph(FluxState)

    # ── Registro de Nodos ─────────────────────────────────────
    graph.add_node("welcome",          welcome_node)
    graph.add_node("intent_router",    intent_router_node)
    graph.add_node("loan_entry",       loan_entry_node)
    graph.add_node("account_entry",    account_entry_node)
    graph.add_node("dap_entry",        deposit_entry_node)
    graph.add_node("general_response", general_response_node)

    # ── Punto de Entrada ──────────────────────────────────────
    graph.set_entry_point("welcome")

    # ── Aristas Condicionales ─────────────────────────────────
    # Después de WELCOME: redirigir según intención (nueva o reanudada)
    graph.add_conditional_edges(
        "welcome",
        route_after_welcome,
        {
            "intent_router":  "intent_router",
            "loan_entry":     "loan_entry",
            "account_entry":  "account_entry",
            "dap_entry":      "dap_entry",
        }
    )

    # Después de INTENT_ROUTER: redirigir al producto correspondiente
    graph.add_conditional_edges(
        "intent_router",
        route_after_intent,
        {
            "loan_entry":       "loan_entry",
            "account_entry":    "account_entry",
            "dap_entry":        "dap_entry",
            "general_response": "general_response",
        }
    )

    # ── Aristas Finales (todos los stubs terminan por ahora) ──
    graph.add_edge("loan_entry",       END)
    graph.add_edge("account_entry",    END)
    graph.add_edge("dap_entry",        END)
    graph.add_edge("general_response", END)

    return graph


def get_compiled_graph():
    """
    Compila el grafo con el checkpointer de Supabase.

    INPUT:  Ninguno.
    PROCESO: Llama a build_graph() y compile() con el PostgresSaver.
    OUTPUT: CompiledGraph listo para invoke/astream.

    NOTA: El checkpointer.setup() se llama dentro de get_checkpointer(),
          lo que garantiza que las tablas internas de LangGraph existen en Supabase.
    """
    graph = build_graph()
    checkpointer = get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


# ── Instancia Singleton del Grafo Compilado ───────────────────
# Los endpoints de FastAPI importan directamente este objeto.
compiled_graph = get_compiled_graph()
```

**[DETENCIÓN OBLIGATORIA 4.5]**
Reportar en `CP-04-dev1-fase1.md`: Confirmación del archivo. Pedir confirmación para continuar al checkpoint del Paso 4.

---

## ✅ CHECKPOINT 4 — Pruebas del Paso 4

---

### Prueba 4.A — Test Unitario: Validación del StateSchema

**Objetivo:** Verificar que el StateSchema tiene todos los campos requeridos por el sistema.

**Diseño:** [MODIFICAR] `/backend/tests/test_graph.py`:

```python
"""Tests del Grafo LangGraph."""
import pytest


def test_flux_state_schema_has_required_fields():
    """Verifica que FluxState define todos los campos necesarios."""
    from app.graph.state import FluxState
    import typing
    
    hints = typing.get_type_hints(FluxState)
    required_fields = ["messages", "user_data", "session", "collected_data", "control_flags"]
    
    for field in required_fields:
        assert field in hints, f"Campo requerido '{field}' no encontrado en FluxState"


def test_graph_compiles_without_error():
    """Verifica que el StateGraph se compila sin lanzar excepciones."""
    from app.graph.workflow import build_graph
    graph = build_graph()
    # Si llegamos aquí, el grafo se construyó sin error
    assert graph is not None


def test_graph_has_correct_nodes():
    """Verifica que el grafo tiene registrados todos los nodos esperados para Fase 1."""
    from app.graph.workflow import build_graph
    graph = build_graph()
    
    expected_nodes = {
        "welcome", "intent_router", "loan_entry",
        "account_entry", "dap_entry", "general_response"
    }
    actual_nodes = set(graph.nodes.keys())
    
    for node in expected_nodes:
        assert node in actual_nodes, f"Nodo '{node}' no encontrado en el grafo"
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/test_graph.py::test_flux_state_schema_has_required_fields tests/test_graph.py::test_graph_compiles_without_error tests/test_graph.py::test_graph_has_correct_nodes -v`

**Resultado esperado:** 3 tests `PASSED`.

---

### Prueba 4.B — Test de Integración: Clasificación de Intenciones

**Objetivo:** Verificar que el `INTENT_ROUTER_NODE` clasifica correctamente las intenciones más comunes.

```python
def test_intent_router_classifies_loan():
    """Verifica que un mensaje de crédito se clasifica como LOAN."""
    from langchain_core.messages import HumanMessage
    from app.graph.nodes.common import intent_router_node
    from app.graph.state import FluxState

    # Estado mínimo para la prueba
    state: FluxState = {
        "messages": [HumanMessage(content="Quiero solicitar un crédito de 3 millones")],
        "user_data": {"full_name": "Juan Test", "email": "test@flux.cl"},
        "session": {"conversation_id": "test-123", "current_node": "WELCOME"},
        "collected_data": {},
        "control_flags": {},
    }
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "LOAN"


def test_intent_router_classifies_account():
    """Verifica que un mensaje de cuenta se clasifica como ACCOUNT."""
    from langchain_core.messages import HumanMessage
    from app.graph.nodes.common import intent_router_node
    from app.graph.state import FluxState

    state: FluxState = {
        "messages": [HumanMessage(content="Quiero abrir una cuenta corriente")],
        "user_data": {}, "session": {}, "collected_data": {}, "control_flags": {},
    }
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "ACCOUNT"


def test_intent_router_classifies_dap():
    """Verifica que un mensaje de inversión se clasifica como DAP."""
    from langchain_core.messages import HumanMessage
    from app.graph.nodes.common import intent_router_node
    from app.graph.state import FluxState

    state: FluxState = {
        "messages": [HumanMessage(content="Quiero hacer un depósito a plazo de 5 millones")],
        "user_data": {}, "session": {}, "collected_data": {}, "control_flags": {},
    }
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "DAP"


def test_intent_router_classifies_general():
    """Verifica que un saludo se clasifica como GENERAL."""
    from langchain_core.messages import HumanMessage
    from app.graph.nodes.common import intent_router_node
    from app.graph.state import FluxState

    state: FluxState = {
        "messages": [HumanMessage(content="Hola, ¿cómo estás?")],
        "user_data": {}, "session": {}, "collected_data": {}, "control_flags": {},
    }
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "GENERAL"
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/test_graph.py -v -s`

**Resultado esperado:** Todos los tests `PASSED`. Los tests de intent_router hacen llamadas reales a Gemini.

**Interpretación:**
- Si `test_intent_router_classifies_loan` falla → Revisar el prompt de clasificación. El LLM no está respondiendo con el token esperado. Ajustar el `_INTENT_SYSTEM_PROMPT` y pedir aprobación antes de hacerlo.
- Si algún test falla con error de API → El problema está en la autenticación con Vertex AI (revisar Paso 3).

---

### Prueba 4.C — Test de Integración: Persistencia del Estado (Checkpointer)

**Objetivo:** Verificar que el grafo compilado persiste el estado en Supabase y puede recuperarlo con el mismo thread_id.

```python
def test_graph_state_persists_across_invocations():
    """
    Verifica que el grafo persiste el estado y que una segunda invocación
    con el mismo thread_id recupera el historial previo.
    ADVERTENCIA: Este test hace llamadas reales a Gemini y escribe en Supabase.
    """
    import uuid
    from langchain_core.messages import HumanMessage
    from app.graph.workflow import compiled_graph

    thread_id = f"test-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    # Primera invocación — estado inicial
    initial_state = {
        "messages": [HumanMessage(content="Quiero un crédito")],
        "user_data": {"full_name": "Ana Test", "email": "ana@flux.cl"},
        "session": {"conversation_id": thread_id, "current_node": "START"},
        "collected_data": {},
        "control_flags": {},
    }
    result1 = compiled_graph.invoke(initial_state, config=config)
    assert result1 is not None
    assert len(result1["messages"]) > 1  # El grafo agregó mensajes

    # Segunda invocación — el estado debe ser recuperado del checkpointer
    result2 = compiled_graph.invoke(
        {"messages": [HumanMessage(content="¿Cuánto me prestarían?")]},
        config=config
    )
    # El historial debe ser mayor que en la primera invocación (memoria persistida)
    assert len(result2["messages"]) > len(result1["messages"]), \
        "El checkpointer no persistió el estado correctamente"

    print(f"\nMensajes en sesión 1: {len(result1['messages'])}")
    print(f"Mensajes en sesión 2: {len(result2['messages'])}")
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/test_graph.py::test_graph_state_persists_across_invocations -v -s`

**Resultado esperado:** `PASSED`. El segundo número de mensajes debe ser mayor que el primero.

---

**[DETENCIÓN OBLIGATORIA — CIERRE PASO 4]**

Reporte Final en `CP-04-dev1-fase1.md`:
1. Resultado de cada prueba (nombres, estado, interpretación).
2. Fragmento de respuesta del bot para cada intención detectada (del output de los tests con `-s`).
3. Número de mensajes en sesión 1 y sesión 2 del test de persistencia.
4. Estado: PASO 4 COMPLETADO / PASO 4 BLOQUEADO.
5. Solicitar aprobación para iniciar el Paso 5.

---
---

# PASO 5 — Autenticación y Threading de Sesión

**Objetivo:** Implementar la validación de JWT de Supabase Auth en los endpoints de FastAPI y la lógica de `thread_id` vinculado al `user_id` + `conversation_id`. Esto garantiza que cada petición al grafo esté autenticada y que el checkpointer recupere exactamente el estado del usuario correcto.

**Al comenzar este paso, el agente debe [CREAR] el archivo `CP-05-dev1-fase1.md`.**

---

## Sub-paso 5.1 — Implementar la inyección de dependencias en `app/api/deps.py`

**Acción:** [MODIFICAR] `/backend/app/api/deps.py`:

```python
"""
app/api/deps.py
─────────────────────────────────────────────────────────────
Inyección de dependencias para los endpoints de FastAPI.

PROCESO: Provee funciones reutilizables que FastAPI resuelve automáticamente
         en cada request mediante el sistema de Depends().

SALIDA:
  - get_current_user(): Valida el JWT de Supabase y retorna el user_id.
  - get_verified_user(): Extiende get_current_user() verificando que el
    usuario existe en la tabla `users` y no está bloqueado.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.infra.supabase import supabase_admin, get_user_by_email

# Esquema de seguridad Bearer Token (JWT de Supabase Auth)
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    """
    Valida el JWT de Supabase Auth incluido en el header Authorization.

    INPUT:  Bearer token en el header de la request.
    PROCESO:
        1. Extrae el JWT del header Authorization: Bearer <token>.
        2. Llama a supabase_admin.auth.get_user(token) para validar el token.
        3. Si el token es inválido o expiró, retorna 401.
        4. Si es válido, retorna el diccionario con los datos del usuario Auth.
    OUTPUT: dict con {user_id, email} del usuario autenticado.

    RAISES: HTTPException 401 si el token es inválido o expirado.
    """
    token = credentials.credentials

    try:
        # Validar el JWT contra Supabase Auth (hace una llamada al servidor de Auth)
        auth_response = supabase_admin.auth.get_user(token)
        if not auth_response or not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = auth_response.user
        return {"user_id": user.id, "email": user.email}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error de autenticación: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_verified_user(
    auth_user: dict = Depends(get_current_user)
) -> dict:
    """
    Extiende get_current_user() verificando el estado del usuario en la DB de negocio.

    INPUT:  auth_user (dict) — usuario autenticado provisto por get_current_user().
    PROCESO:
        1. Busca el usuario en la tabla `users` por email.
        2. Si no existe en la tabla `users` (es un usuario Auth pero sin perfil),
           retorna 403 con mensaje instructivo.
        3. Si el usuario tiene estado BLOCKED_SECURITY, retorna 403.
        4. Si está activo, retorna el perfil completo.
    OUTPUT: dict con el perfil completo del usuario desde la tabla `users`.

    RAISES: HTTPException 403 si el usuario no tiene perfil o está bloqueado.
    """
    email = auth_user.get("email")
    user_profile = get_user_by_email(email)

    if not user_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No se encontró un perfil de usuario asociado a esta cuenta. Contacta a soporte.",
        )

    user_status = user_profile.get("user_statuses", {}).get("code", "")
    if user_status == "BLOCKED_SECURITY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta ha sido bloqueada temporalmente por razones de seguridad. Contacta a soporte.",
        )

    return user_profile
```

**[DETENCIÓN OBLIGATORIA 5.1]**
Reportar en `CP-05-dev1-fase1.md`: Confirmación del archivo. Pedir confirmación para continuar al sub-paso 5.2.

---

## Sub-paso 5.2 — Implementar la lógica de Thread ID

**Acción:** [CREAR] `/backend/app/infra/threading.py`:

```python
"""
app/infra/threading.py
─────────────────────────────────────────────────────────────
Gestión del thread_id de LangGraph y su vinculación con el usuario.

PROCESO: En LangGraph, el `thread_id` es la clave que el checkpointer
         usa para almacenar y recuperar el estado del grafo.
         En FLUX, el thread_id equivale al UUID de la conversación,
         que a su vez pertenece a un usuario específico.
         Esta vinculación es lo que garantiza que un usuario solo
         pueda acceder a sus propias conversaciones.

SALIDA:  Funciones para crear o recuperar el thread_id de una sesión.
"""

from app.infra.supabase import supabase_client, create_conversation


def get_or_create_thread(user_id: str, conversation_id: str | None = None) -> str:
    """
    Retorna un thread_id válido para la sesión del usuario.

    INPUT:  user_id (str) — UUID del usuario autenticado.
            conversation_id (str | None) — UUID de conversación existente
              para reanudar, o None para crear una nueva.
    PROCESO:
        1. Si conversation_id es None: crea una nueva conversación en la DB
           y retorna su UUID como thread_id.
        2. Si conversation_id es provisto: verifica que la conversación
           pertenece al user_id (seguridad). Si la verificación pasa,
           retorna el conversation_id como thread_id.
    OUTPUT: thread_id (str) — UUID de la conversación = thread_id de LangGraph.

    RAISES: ValueError si el conversation_id no pertenece al user_id.
    """
    if conversation_id is None:
        # Crear nueva conversación
        new_conv = create_conversation(user_id=user_id)
        return new_conv["id"]
    else:
        # Verificar propiedad de la conversación (CRÍTICO para seguridad)
        response = (
            supabase_client
            .table("conversations")
            .select("id, user_id, is_active")
            .eq("id", conversation_id)
            .eq("user_id", user_id)  # Doble filtro: id Y user_id deben coincidir
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise ValueError(
                f"La conversación {conversation_id} no existe o no pertenece al usuario {user_id}."
            )
        return conversation_id


def get_langgraph_config(thread_id: str) -> dict:
    """
    Retorna el dict de configuración que LangGraph requiere para el checkpointer.

    INPUT:  thread_id (str) — UUID de la conversación.
    OUTPUT: dict {"configurable": {"thread_id": thread_id}}
            Listo para pasar como `config=` en compiled_graph.invoke() / astream().
    """
    return {"configurable": {"thread_id": thread_id}}
```

**[DETENCIÓN OBLIGATORIA 5.2]**
Reportar en `CP-05-dev1-fase1.md`: Confirmación del archivo. Pedir confirmación para continuar al checkpoint del Paso 5.

---

## ✅ CHECKPOINT 5 — Pruebas del Paso 5

---

### Prueba 5.A — Test de Integración: Validación de JWT

**Objetivo:** Verificar que `get_current_user` acepta tokens válidos y rechaza inválidos.

**Diseño:** Agregar a `/backend/tests/test_config.py` (o crear `/backend/tests/test_auth.py`):

```python
"""Tests de autenticación."""
import pytest
from fastapi.testclient import TestClient


def test_protected_endpoint_rejects_missing_token():
    """
    Verifica que un endpoint protegido rechaza requests sin token.
    Para esta prueba, se agrega un endpoint de test temporal a la app.
    """
    from main import app
    from fastapi import Depends
    from app.api.deps import get_current_user

    # Endpoint de prueba (solo para testing)
    @app.get("/test-auth-only")
    async def test_auth_endpoint(user=Depends(get_current_user)):
        return {"user_id": user["user_id"]}

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/test-auth-only")
    # Sin token → debe retornar 403 (HTTPBearer) o 401
    assert response.status_code in [401, 403]


def test_protected_endpoint_rejects_invalid_token():
    """Verifica que un token malformado es rechazado."""
    from main import app
    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        "/test-auth-only",
        headers={"Authorization": "Bearer token_invalido_definitivamente"}
    )
    assert response.status_code in [401, 403]
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/test_auth.py -v`

**Resultado esperado:** 2 tests `PASSED`.

---

### Prueba 5.B — Test Unitario: Thread ID

```python
def test_get_langgraph_config_format():
    """Verifica que get_langgraph_config retorna el formato correcto."""
    from app.infra.threading import get_langgraph_config
    import uuid

    thread_id = str(uuid.uuid4())
    config = get_langgraph_config(thread_id)

    assert "configurable" in config
    assert "thread_id" in config["configurable"]
    assert config["configurable"]["thread_id"] == thread_id


def test_get_or_create_thread_creates_new_conversation():
    """
    Verifica que get_or_create_thread crea una conversación nueva en la DB.
    Requiere un usuario de prueba en la DB.
    """
    from app.infra.supabase import supabase_client
    from app.infra.threading import get_or_create_thread

    users = supabase_client.table("users").select("id").limit(1).execute()
    if not users.data:
        pytest.skip("No hay usuarios en la DB.")

    user_id = users.data[0]["id"]
    thread_id = get_or_create_thread(user_id=user_id)

    assert thread_id is not None
    assert len(thread_id) == 36  # Formato UUID

    # Limpieza
    supabase_client.table("conversations").delete().eq("id", thread_id).execute()
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/ -k "test_get_langgraph_config or test_get_or_create" -v`

---

**[DETENCIÓN OBLIGATORIA — CIERRE PASO 5]**

Reporte Final en `CP-05-dev1-fase1.md`:
1. Resultado de todas las pruebas.
2. Estado: PASO 5 COMPLETADO / PASO 5 BLOQUEADO.
3. Solicitar aprobación para iniciar el Paso 6.

---
---

# PASO 6 — API Endpoints Básicos

**Objetivo:** Exponer el grafo de LangGraph a través de endpoints FastAPI. Implementar el endpoint `/chat` con `StreamingResponse` (HTTP Server-Sent Events) y el endpoint `/history` para recuperación del historial de mensajes.

**Al comenzar este paso, el agente debe [CREAR] el archivo `CP-06-dev1-fase1.md`.**

---

## Sub-paso 6.1 — Implementar el endpoint `/chat` en `app/api/v1/chat.py`

**Acción:** [MODIFICAR] `/backend/app/api/v1/chat.py`:

```python
"""
app/api/v1/chat.py
─────────────────────────────────────────────────────────────
Endpoint principal del sistema FLUX.

PROCESO: Recibe un mensaje del usuario (autenticado), lo inyecta en el
         grafo de LangGraph y transmite la respuesta del asistente en
         tiempo real usando HTTP StreamingResponse (Server-Sent Events).

INPUT:   POST /api/v1/chat con body JSON y JWT en Authorization header.
OUTPUT:  StreamingResponse con eventos SSE. Cada evento contiene un fragmento
         del mensaje del asistente o metadatos de nodo.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from app.api.deps import get_verified_user
from app.graph.workflow import compiled_graph
from app.infra.threading import get_or_create_thread, get_langgraph_config
from app.infra.supabase import save_message, update_conversation_node


router = APIRouter()


# ── Modelos de Request/Response ───────────────────────────────

class ChatRequest(BaseModel):
    """Cuerpo del request POST /chat."""
    message: str                    # Texto del usuario
    conversation_id: str | None = None  # None = nueva conversación; UUID = reanudar


class ChatMetadata(BaseModel):
    """Metadatos opcionales incluidos en los eventos SSE."""
    node: str | None = None
    conversation_id: str | None = None
    product_intent: str | None = None


# ── Generador de Streaming ────────────────────────────────────

async def stream_graph_response(
    user_message: str,
    user_profile: dict,
    thread_id: str,
):
    """
    Generador asíncrono que ejecuta el grafo y emite eventos SSE.

    INPUT:  user_message (str) — Texto del usuario.
            user_profile (dict) — Perfil del usuario desde la DB.
            thread_id (str) — UUID de la conversación (thread del checkpointer).
    PROCESO:
        1. Construye el estado inicial con el mensaje del usuario y el perfil.
        2. Invoca compiled_graph.astream() para streaming asíncrono.
        3. Por cada evento del grafo, emite un evento SSE formateado.
        4. Persiste el mensaje del usuario y la respuesta del asistente en la DB.
    OUTPUT: Genera strings con formato SSE: "data: {json}\n\n"
    """
    config = get_langgraph_config(thread_id)

    # Persistir mensaje del usuario en la DB
    save_message(
        conversation_id=thread_id,
        role="user",
        content=user_message,
    )

    # Estado inicial para el grafo
    initial_state = {
        "messages": [HumanMessage(content=user_message)],
        "user_data": {
            "user_id": str(user_profile.get("id", "")),
            "full_name": user_profile.get("full_name", ""),
            "email": user_profile.get("email", ""),
            "rut": user_profile.get("rut", ""),
            "birth_date": str(user_profile.get("birth_date", "")),
            "user_status": user_profile.get("user_statuses", {}).get("code", "ACTIVE"),
            "user_category": user_profile.get("user_categories", {}).get("code") if user_profile.get("user_categories") else None,
        },
        "session": {
            "conversation_id": thread_id,
            "current_node": "START",
            "is_transversal_active": False,
        },
        "collected_data": {},
        "control_flags": {
            "security_blocked": False,
            "service_error": False,
            "otp_attempts": 0,
            "error_detail": None,
        },
    }

    full_assistant_response = ""
    last_node = "START"

    try:
        # Streaming del grafo: cada evento es una transición de nodo
        async for event in compiled_graph.astream(initial_state, config=config):
            for node_name, node_output in event.items():
                last_node = node_name

                # Extraer mensajes del asistente del output del nodo
                messages = node_output.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "type") and msg.type == "ai":
                        content = msg.content
                        full_assistant_response += content

                        # Emitir evento SSE con el contenido del mensaje
                        sse_data = json.dumps({
                            "type": "message",
                            "content": content,
                            "node": node_name,
                        })
                        yield f"data: {sse_data}\n\n"

                # Emitir metadato de transición de nodo (para el Progress Monitor del FE)
                session_update = node_output.get("session", {})
                if session_update.get("current_node"):
                    meta_data = json.dumps({
                        "type": "node_transition",
                        "node": session_update["current_node"],
                        "product_intent": session_update.get("product_intent"),
                    })
                    yield f"data: {meta_data}\n\n"

        # Persistir respuesta del asistente en la DB
        if full_assistant_response:
            save_message(
                conversation_id=thread_id,
                role="assistant",
                content=full_assistant_response,
                node_at_time=last_node,
            )

        # Señal de fin del stream
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': thread_id})}\n\n"

    except Exception as e:
        error_data = json.dumps({"type": "error", "detail": str(e)})
        yield f"data: {error_data}\n\n"


# ── Endpoint Principal ────────────────────────────────────────

@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    user_profile: dict = Depends(get_verified_user),
):
    """
    Endpoint principal de chat. Procesa un mensaje y transmite la respuesta.

    INPUT:  POST body con {message, conversation_id?} + JWT en Authorization header.
    PROCESO:
        1. Valida el usuario mediante JWT (get_verified_user).
        2. Resuelve o crea el thread_id de la conversación.
        3. Inicia el streaming del grafo.
    OUTPUT: StreamingResponse con eventos SSE.
    """
    user_id = str(user_profile.get("id"))

    try:
        thread_id = get_or_create_thread(
            user_id=user_id,
            conversation_id=request.conversation_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return StreamingResponse(
        stream_graph_response(
            user_message=request.message,
            user_profile=user_profile,
            thread_id=thread_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Deshabilita buffering en nginx
            "X-Conversation-Id": thread_id,
        },
    )
```

**[DETENCIÓN OBLIGATORIA 6.1]**
Reportar en `CP-06-dev1-fase1.md`: Confirmación del endpoint. Pedir confirmación para continuar al sub-paso 6.2.

---

## Sub-paso 6.2 — Implementar el endpoint `/history` en `app/api/v1/docs.py`

**Acción:** [MODIFICAR] `/backend/app/api/v1/docs.py`:

```python
"""
app/api/v1/docs.py
─────────────────────────────────────────────────────────────
Endpoints para recuperación de historial y gestión de documentos.

En Fase 1: Solo el endpoint /history para el historial de conversaciones.
En Fase 2+: Se agregan endpoints para descarga de contratos PDF y verificación de hash.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_verified_user
from app.infra.supabase import supabase_client, get_conversation_messages

router = APIRouter()


@router.get("/history")
async def get_conversation_history(
    user_profile: dict = Depends(get_verified_user),
):
    """
    Recupera todas las conversaciones del usuario con sus últimos mensajes.

    INPUT:  JWT en Authorization header (usuario autenticado).
    PROCESO:
        1. Consulta la tabla `conversations` del usuario, ordenadas por created_at DESC.
        2. Para cada conversación, incluye el último mensaje como preview.
    OUTPUT: Lista de conversaciones con metadatos para el Sidebar del FE.
    """
    user_id = str(user_profile.get("id"))

    response = (
        supabase_client
        .table("conversations")
        .select("id, product_type_id, current_node, is_active, created_at, updated_at, product_types(name)")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(20)
        .execute()
    )

    return {"conversations": response.data or []}


@router.get("/history/{conversation_id}")
async def get_messages_by_conversation(
    conversation_id: str,
    user_profile: dict = Depends(get_verified_user),
):
    """
    Recupera todos los mensajes de una conversación específica.

    INPUT:  conversation_id (str) — UUID de la conversación.
            JWT en Authorization header.
    PROCESO:
        1. Verifica que la conversación pertenece al usuario autenticado.
        2. Recupera todos los mensajes ordenados cronológicamente.
    OUTPUT: Lista de mensajes para reconstruir el hilo en el chat.
    """
    user_id = str(user_profile.get("id"))

    # Verificar propiedad
    conv = (
        supabase_client
        .table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    if not conv.data:
        raise HTTPException(
            status_code=404,
            detail="Conversación no encontrada o no tienes acceso a ella."
        )

    messages = get_conversation_messages(conversation_id)
    return {"conversation_id": conversation_id, "messages": messages}
```

**[DETENCIÓN OBLIGATORIA 6.2]**
Reportar en `CP-06-dev1-fase1.md`: Confirmación del endpoint. Pedir confirmación para continuar al sub-paso 6.3.

---

## Sub-paso 6.3 — Registrar los routers en `main.py`

**Acción:** [MODIFICAR] `/backend/main.py`. Descomentar las líneas de los routers y agregar los imports:

```python
# Agregar estos imports al inicio del archivo (después de los imports existentes):
from app.api.v1 import chat, docs

# Reemplazar las líneas comentadas de routers por:
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(docs.router, prefix="/api/v1", tags=["documents"])
```

**[EJECUTAR]:** Reiniciar el servidor y verificar que `/docs` de Swagger muestra los nuevos endpoints:
```bash
uvicorn main:app --reload
```
Abrir `http://localhost:8000/docs` y confirmar que aparecen:
- `POST /api/v1/chat`
- `GET /api/v1/history`
- `GET /api/v1/history/{conversation_id}`

**[DETENCIÓN OBLIGATORIA 6.3]**
Reportar en `CP-06-dev1-fase1.md`: Screenshot/descripción de los endpoints visibles en Swagger. Pedir confirmación para continuar al checkpoint del Paso 6.

---

## ✅ CHECKPOINT 6 — Pruebas del Paso 6

---

### Prueba 6.A — Test de Integración: Endpoint `/chat` sin autenticación

**Objetivo:** Verificar que el endpoint protegido rechaza requests sin token.

```python
def test_chat_endpoint_requires_auth():
    """POST /chat sin token debe retornar 401/403."""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/v1/chat", json={"message": "Hola"})
    assert response.status_code in [401, 403]


def test_history_endpoint_requires_auth():
    """GET /history sin token debe retornar 401/403."""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/history")
    assert response.status_code in [401, 403]
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/ -k "requires_auth" -v`

**Resultado esperado:** 2 tests `PASSED`.

---

### Prueba 6.B — Test de Integración End-to-End: Flujo completo de mensaje

**Objetivo:** Verificar el flujo completo desde HTTP hasta la DB, usando un usuario de prueba real en Supabase.

> **NOTA IMPORTANTE:** Esta prueba requiere:
> 1. Un usuario creado en Supabase Auth.
> 2. Un registro correspondiente en la tabla `users` con el mismo email.
> 3. El token JWT del usuario de prueba (se obtiene llamando al login de Supabase Auth).
>
> Si no existe un usuario de prueba, el agente debe **reportarlo en el CP y pedir al desarrollador humano que lo cree** antes de continuar.

```python
def test_e2e_chat_flow():
    """
    Test end-to-end: POST /chat → grafo LangGraph → respuesta streamed → DB.
    REQUIERE: Usuario de prueba con JWT válido.
    Ver instrucciones en el comentario de la prueba para obtener el token.
    """
    import os
    import httpx

    # El token de prueba debe estar en una variable de entorno de test
    test_token = os.getenv("FLUX_TEST_JWT_TOKEN")
    if not test_token:
        import pytest
        pytest.skip(
            "FLUX_TEST_JWT_TOKEN no configurado. "
            "Para configurarlo: crear usuario en Supabase Auth, "
            "hacer login y copiar el access_token al .env de test."
        )

    # Hacer request al endpoint usando httpx (soporta streaming)
    with httpx.Client() as client:
        with client.stream(
            "POST",
            "http://localhost:8000/api/v1/chat",
            json={"message": "Hola, quiero un crédito"},
            headers={"Authorization": f"Bearer {test_token}"},
            timeout=30.0,
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            events = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    event_data = json.loads(line[6:])
                    events.append(event_data)
                    if event_data.get("type") == "done":
                        break

    # Verificar que se recibieron eventos
    assert len(events) > 0, "No se recibieron eventos SSE"

    # Verificar que hay al menos un evento de mensaje
    message_events = [e for e in events if e.get("type") == "message"]
    assert len(message_events) > 0, "No se recibió ningún mensaje del asistente"

    # Verificar que hay un evento de finalización
    done_events = [e for e in events if e.get("type") == "done"]
    assert len(done_events) == 1, "No se recibió el evento 'done'"

    conversation_id = done_events[0].get("conversation_id")
    assert conversation_id is not None

    print(f"\nConversation ID creado: {conversation_id}")
    print(f"Total de eventos recibidos: {len(events)}")
    print(f"Respuesta del asistente: {' '.join([e['content'] for e in message_events])}")
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/ -k "test_e2e_chat_flow" -v -s`

**Resultado esperado:** `PASSED` o `SKIPPED` (si no hay token configurado).

---

### Prueba 6.C — Test de Integración: Mensajes persistidos en DB post-chat

**Objetivo:** Verificar que los mensajes del usuario y el asistente se guardan correctamente en la tabla `messages` después de completar un turno de conversación.

```python
def test_messages_persist_after_chat():
    """
    Verifica que tras un turno de chat, los mensajes se guardan en la DB.
    Simula la lógica del stream_graph_response directamente (sin HTTP).
    """
    import uuid
    from app.infra.supabase import supabase_client, save_message, get_conversation_messages, create_conversation

    # Verificar si hay usuario de prueba
    users = supabase_client.table("users").select("id").limit(1).execute()
    if not users.data:
        import pytest
        pytest.skip("No hay usuarios de prueba en la DB.")

    user_id = users.data[0]["id"]

    # Crear conversación de prueba
    conv = create_conversation(user_id=user_id)
    conv_id = conv["id"]

    # Simular guardado de mensajes
    save_message(conv_id, "user", "Quiero abrir una cuenta")
    save_message(conv_id, "assistant", "¡Claro! Te ayudo con tu Cuenta Corriente.", node_at_time="WELCOME_NODE")

    # Verificar persistencia
    messages = get_conversation_messages(conv_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["node_at_time"] == "WELCOME_NODE"

    # Limpieza
    supabase_client.table("messages").delete().eq("conversation_id", conv_id).execute()
    supabase_client.table("conversations").delete().eq("id", conv_id).execute()

    print(f"\nMensajes persistidos y verificados correctamente.")
```

**[EJECUTAR]:** `cd /backend && python -m pytest tests/ -k "test_messages_persist" -v -s`

**Resultado esperado:** `PASSED`.

---

**[DETENCIÓN OBLIGATORIA — CIERRE PASO 6]**

Reporte Final en `CP-06-dev1-fase1.md`:
1. Resultado de todas las pruebas del checkpoint.
2. Output de la consola del servidor al recibir el request de chat (si se ejecutó el E2E).
3. Respuesta completa del asistente recibida en el test E2E.
4. Estado general: PASO 6 COMPLETADO / PASO 6 BLOQUEADO.

---
---

# ENTREGABLE FINAL — FASE 1, DEV 1

Al completar los 6 pasos y sus checkpoints, el entregable es:

## Servidor FastAPI Funcional

Un servidor en `http://localhost:8000` con:

| Capacidad | Descripción |
|-----------|-------------|
| ✅ Levanta sin errores | `uvicorn main:app --reload` inicia sin excepciones |
| ✅ Conectado a Supabase | Schema completo, seed de catálogos, helpers de CRUD |
| ✅ Conectado a Vertex AI | Cliente Gemini Dual-Init con ADC verificado |
| ✅ Grafo LangGraph activo | Detecta intenciones LOAN / ACCOUNT / DAP / GENERAL |
| ✅ Estado persistente | PostgresSaver guarda el estado en Supabase entre sesiones |
| ✅ Autenticación JWT | Todos los endpoints validan el token de Supabase Auth |
| ✅ Streaming de respuestas | POST /chat devuelve SSE en tiempo real |
| ✅ Historial de chats | GET /history recupera conversaciones del usuario |

## Archivos de Checkpoint Generados

```
/backend/
├── CP-01-dev1-fase1.md   ← Setup de infraestructura
├── CP-02-dev1-fase1.md   ← Capa de persistencia
├── CP-03-dev1-fase1.md   ← Vertex AI
├── CP-04-dev1-fase1.md   ← Core del Grafo
├── CP-05-dev1-fase1.md   ← Autenticación
└── CP-06-dev1-fase1.md   ← API Endpoints
```

## Precondición para Fase 2

Antes de iniciar la Fase 2 (Crédito de Consumo), el agente debe confirmar con el desarrollador humano que:

1. El servidor levanta limpiamente en el ambiente del equipo.
2. Todos los checkpoints tienen estado `COMPLETADO`.
3. El Dev 3 (Trust & Fulfillment) tiene acceso al entorno para implementar `security.py` y `pdf_factory.py`.
4. El token JWT de prueba está configurado para los tests E2E.

---

> **FIN DEL PLAN DE IMPLEMENTACIÓN · FASE 1 · DEV 1 (AI)**
> Versión 1.0 · Proyecto FLUX
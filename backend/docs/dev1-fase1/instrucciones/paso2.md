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
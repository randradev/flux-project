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

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

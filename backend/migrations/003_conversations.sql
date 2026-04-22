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

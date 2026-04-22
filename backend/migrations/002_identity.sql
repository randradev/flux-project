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

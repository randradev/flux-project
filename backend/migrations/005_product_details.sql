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

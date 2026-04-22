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

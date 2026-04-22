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

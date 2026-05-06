# tests/unit/test_loan_schemas.py

from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction, LoanSimExtraction

def test_renta_cero_normalizada_a_none():
    m = LoanProfileExtraction(intencion="DATO_FINANCIERO", renta=0)
    assert m.renta is None

def test_antiguedad_negativa_normalizada_a_none():
    m = LoanProfileExtraction(intencion="DATO_FINANCIERO", antiguedad_laboral=-1)
    assert m.antiguedad_laboral is None

def test_antiguedad_cero_conservada():
    """0 meses es válido semánticamente — no debe normalizarse."""
    m = LoanProfileExtraction(intencion="DATO_FINANCIERO", antiguedad_laboral=0)
    assert m.antiguedad_laboral == 0

def test_valores_validos_conservados():
    m = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        renta=1_500_000,
        antiguedad_laboral=36,
        nivel_estudios="UNIVERSITARIO"
    )
    assert m.renta == 1_500_000
    assert m.antiguedad_laboral == 36
    assert m.nivel_estudios == "UNIVERSITARIO"

def test_todos_los_campos_pueden_ser_none():
    """Un mensaje tipo SALUDO debe producir todos los campos None."""
    m = LoanProfileExtraction(intencion="SALUDO")
    assert m.renta is None
    assert m.antiguedad_laboral is None
    assert m.nivel_estudios is None

def test_sim_schema_monto_negativo_normalizado():
    m = LoanSimExtraction(intencion="DATO_FINANCIERO", monto_solicitado=-500)
    assert m.monto_solicitado is None

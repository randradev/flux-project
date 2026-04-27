import pytest
import math
from app.modules.credit_eng import (
    CreditEngine, 
    PolicyRejectionError, 
    PaymentCapacityError
)

def test_case_1_pre_approved_bajo_riesgo():
    """
    Caso 1 — PASS: Pre-aprobado con riesgo Bajo
    Input ajustado para > 80 pts: 
    edad=30 (20), renta=2.000.000 (25), ant=36m (20), estudios=POSTGRADO (20)
    Total = 85 pts -> Bajo.
    """
    prep = {"edad": 30, "nombre": "Test", "rut": "1-9", "mail": "test@test.cl"}
    profile = {"renta": 2000000, "antiguedad_laboral": 36, "nivel_estudios": "POSTGRADO"}
    sim = {"monto_solicitado": 5000000, "plazo_solicitado": 24}
    
    engine = CreditEngine(prep, profile, sim)
    result = engine.run()
    
    assert result["status_proceso"] == "PRE_APPROVED"
    assert result["nivel_riesgo"] == "Bajo"
    assert result["tasa_interes_mensual"] == 0.012
    assert result["capacidad_pago_valida"] is True
    assert result["monto_aprobado"] == 5000000

def test_case_2_pre_approved_alto_riesgo():
    """
    Caso 2 — PASS: Pre-aprobado con riesgo Alto
    Input: edad=20 (5), renta=700.000 (10), ant=7m (5), estudios=MEDIA (5)
    Total = 25 pts -> Alto.
    """
    prep = {"edad": 20, "nombre": "Test", "rut": "1-9", "mail": "test@test.cl"}
    profile = {"renta": 700000, "antiguedad_laboral": 7, "nivel_estudios": "MEDIA"}
    sim = {"monto_solicitado": 1000000, "plazo_solicitado": 12}
    
    engine = CreditEngine(prep, profile, sim)
    result = engine.run()
    
    assert result["nivel_riesgo"] == "Alto"
    assert result["tasa_interes_mensual"] == 0.035

def test_case_3_reject_edad():
    """Caso 3 — PASS: Rechazo por ERR_EDAD"""
    prep = {"edad": 17, "nombre": "Test", "rut": "1-9", "mail": "test@test.cl"}
    profile = {"renta": 1000000, "antiguedad_laboral": 12, "nivel_estudios": "TECNICO"}
    sim = {"monto_solicitado": 1000000, "plazo_solicitado": 12}
    
    engine = CreditEngine(prep, profile, sim)
    with pytest.raises(PolicyRejectionError) as excinfo:
        engine.run()
    assert excinfo.value.motivo == "ERR_EDAD"

def test_case_4_reject_renta():
    """Caso 4 — PASS: Rechazo por ERR_RENTA"""
    prep = {"edad": 25, "nombre": "Test", "rut": "1-9", "mail": "test@test.cl"}
    profile = {"renta": 400000, "antiguedad_laboral": 12, "nivel_estudios": "TECNICO"}
    sim = {"monto_solicitado": 1000000, "plazo_solicitado": 12}
    
    engine = CreditEngine(prep, profile, sim)
    with pytest.raises(PolicyRejectionError) as excinfo:
        engine.run()
    assert excinfo.value.motivo == "ERR_RENTA"

def test_case_5_reject_antiguedad():
    """Caso 5 — PASS: Rechazo por ERR_ANTIGUEDAD"""
    prep = {"edad": 25, "nombre": "Test", "rut": "1-9", "mail": "test@test.cl"}
    profile = {"renta": 1000000, "antiguedad_laboral": 5, "nivel_estudios": "TECNICO"}
    sim = {"monto_solicitado": 1000000, "plazo_solicitado": 12}
    
    engine = CreditEngine(prep, profile, sim)
    with pytest.raises(PolicyRejectionError) as excinfo:
        engine.run()
    assert excinfo.value.motivo == "ERR_ANTIGUEDAD"

def test_case_6_reject_capacidad_pago():
    """Caso 6 — PASS: Rechazo por ERR_CAPACIDAD_PAGO"""
    prep = {"edad": 25, "nombre": "Test", "rut": "1-9", "mail": "test@test.cl"}
    # Renta baja, monto altísimo, plazo corto -> Cuota supera el 30%
    profile = {"renta": 500100, "antiguedad_laboral": 12, "nivel_estudios": "MEDIA"}
    sim = {"monto_solicitado": 28000000, "plazo_solicitado": 6}
    
    engine = CreditEngine(prep, profile, sim)
    with pytest.raises(PaymentCapacityError):
        engine.run()

def test_case_7_cuota_matematica():
    """
    Caso 7 — PASS: Verificación matemática de cuota francesa
    Monto=1.000.000, Tasa=0.020, Plazo=12
    Cálculo: 1000000 * (0.02 * 1.02^12) / (1.02^12 - 1) = 94,559.59...
    math.ceil -> 94,560
    """
    prep = {"edad": 30, "nombre": "Test", "rut": "1-9", "mail": "test@test.cl"}
    profile = {"renta": 2000000, "antiguedad_laboral": 24, "nivel_estudios": "UNIVERSITARIO"}
    sim = {"monto_solicitado": 1000000, "plazo_solicitado": 12}
    
    engine = CreditEngine(prep, profile, sim)
    result = engine.run()
    
    assert result["cuota_mensual"] == 94560

def test_case_8_cae_calculo():
    """
    Caso 8 — PASS: CAE para tasa baja
    Tasa=0.012 -> CAE = (1.012)^12 - 1 = 0.1538946...
    Expected round(cae, 6) -> 0.153895
    """
    prep = {"edad": 30, "nombre": "Test", "rut": "1-9", "mail": "test@test.cl"}
    profile = {"renta": 3100000, "antiguedad_laboral": 36, "nivel_estudios": "POSTGRADO"}
    sim = {"monto_solicitado": 5000000, "plazo_solicitado": 12}
    
    engine = CreditEngine(prep, profile, sim)
    result = engine.run()
    
    # round((1.012**12)-1, 6) = 0.153895
    assert result["cae"] == 0.153895
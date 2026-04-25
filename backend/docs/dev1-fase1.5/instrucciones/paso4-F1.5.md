## PASO 4 — Mapeo de Motores a `evaluation_results` {#paso-4}

### 4.1 Convención de Escritura de Motores

Cada motor financiero (nodo de servicio automático) escribe **únicamente** en su sub-cajón de `evaluation_results`. No lee ni escribe en `collecting_data` de forma directa: recibe sus inputs del State.

**Patrón de escritura:**
```python
return {
    "evaluation_results": {
        "loan_engine": {   # <-- solo el sub-cajón del motor, no todo evaluation_results
            "status_proceso": "PRE_APPROVED",
            "scoring_puntos": 78,
            # ... resto de outputs ...
        }
    },
    "session": {**session, "current_node": "LOAN_RISK_ENGINE"},
}
```

### 4.2 Stub del Motor LOAN_RISK_ENGINE

```python
# app/graph/nodes/credit.py (agregar función)

def loan_risk_engine_node(state: FluxState) -> dict:
    """
    Nodo LOAN_RISK_ENGINE: motor de riesgo para crédito de consumo.

    INPUT (State leído):
        - state["collecting_data"]["loan_profile"]: renta, antiguedad_laboral, nivel_estudios
        - state["collecting_data"]["loan_sim"]: monto_solicitado, plazo_solicitado
        - state["preparation_data"]["edad"]: edad del usuario

    PROCESO:
        1. Extraer inputs de los namespaces correctos.
        2. Ejecutar motor de scoring y cálculo financiero.
        3. Escribir todos los outputs en evaluation_results["loan_engine"].

    OUTPUT (campos del State que modifica):
        - evaluation_results["loan_engine"]: Resultado completo del motor.
        - session["current_node"]: "LOAN_RISK_ENGINE".

    NOTA FASE 2: Implementar la lógica del motor aquí.
    Este stub demuestra el patrón de lectura/escritura correcto.
    """
    session = state.get("session", {})
    prep = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})

    # ── Lectura de inputs desde los namespaces correctos ──────────
    loan_profile = collecting.get("loan_profile", {})
    loan_sim = collecting.get("loan_sim", {})

    renta = loan_profile.get("renta", 0)
    antiguedad_laboral = loan_profile.get("antiguedad_laboral", 0)
    nivel_estudios = loan_profile.get("nivel_estudios", "")
    monto_solicitado = loan_sim.get("monto_solicitado", 0)
    plazo_solicitado = loan_sim.get("plazo_solicitado", 0)
    edad = prep.get("edad", 0)

    # ── Lógica del motor (implementar en Fase 2) ──────────────────
    # TODO: Implementar scoring, cálculo de cuota (fórmula francesa),
    #       CAE, CTc, validación de capacidad de pago, etc.
    # Por ahora, stub que retorna PRE_APPROVED para testing.
    engine_result = {
        "status_proceso": "PRE_APPROVED",  # Stub
        "scoring_puntos": 0,
        "nivel_riesgo": "",
        "tasa_interes_mensual": 0.0,
        "cuota_mensual": 0,
        "cuota_maxima_permitida": int(renta * 0.30),
        "capacidad_pago_valida": True,
        "ctc": 0,
        "total_intereses": 0,
        "cae": 0.0,
        "monto_aprobado": monto_solicitado,
        "plazo_aprobado": plazo_solicitado,
        "motivo_rechazo": None,
    }

    return {
        "evaluation_results": {
            "loan_engine": engine_result,
        },
        "session": {**session, "current_node": "LOAN_RISK_ENGINE"},
    }
```

### 4.3 Stub del Motor DAP_INVESTMENT_ENGINE

```python
# app/graph/nodes/deposit.py (agregar función)

def dap_investment_engine_node(state: FluxState) -> dict:
    """
    Nodo DAP_INVESTMENT_ENGINE: motor de cálculo de inversión.

    INPUT (State leído):
        - state["collecting_data"]["dap_params"]: monto, moneda, plazo
        - state["preparation_data"]["edad"]: edad del usuario
        - (Fase 2) eco_service: valor_uf, valor_usd, valor_ipc desde API externa

    PROCESO:
        1. Extraer inputs.
        2. Consultar eco_service para conversion_rate y ipc.
        3. Calcular term_premium, monthly_rate_total, period_rate, estimated_gain, total_return.
        4. Validar elegibilidad.
        5. Escribir en evaluation_results["dap_engine"].

    OUTPUT:
        - evaluation_results["dap_engine"]: Resultado completo.
        - session["current_node"]: "DAP_INVESTMENT_ENGINE".
    """
    session = state.get("session", {})
    prep = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})

    dap_params = collecting.get("dap_params", {})
    monto = dap_params.get("monto", 0.0)
    moneda = dap_params.get("moneda", "CLP")
    plazo = dap_params.get("plazo", 0)
    edad = prep.get("edad", 0)

    # TODO Fase 2: Consultar eco_service para rates y calcular el motor completo.
    # Stub para testing del patrón de escritura.
    engine_result = {
        "status_proceso": "PRE_APPROVED",
        "is_elegible": True,
        "conversion_rate_used": 1.0,
        "ipc_applied": 0.0,
        "term_premium": (plazo // 30) * 0.0005,
        "monthly_rate_total": 0.0,
        "period_rate": 0.0,
        "estimated_gain": 0.0,
        "total_return": monto,
        "motivo_rechazo": None,
    }

    return {
        "evaluation_results": {
            "dap_engine": engine_result,
        },
        "session": {**session, "current_node": "DAP_INVESTMENT_ENGINE"},
    }
```

### 4.4 Sub-paso: Verificación Post-Implementación

**Checklist de verificación manual:**
- [ ] Ejecutar un motor stub con un state válido y verificar que el retorno tiene la estructura `{"evaluation_results": {"loan_engine": {...}}}`.
- [ ] Verificar que el motor NO escribe en `collecting_data` (solo lectura).
- [ ] Verificar que los nombres de los campos en `loan_engine` corresponden exactamente a `LoanEngineResult` del nuevo `state.py`.
- [ ] Verificar que `motivo_rechazo` es `None` en el camino feliz (no un string vacío).

### 4.5 Pruebas del Paso 4

```python
# tests/test_engines_v2.py
import pytest


def make_loan_ready_state():
    """State con datos completos para ejecutar el motor de crédito."""
    return {
        "preparation_data": {"nombre": "Pedro Soto", "rut": "11111111-1", "mail": "p@e.com", "edad": 30},
        "session": {"conversation_id": "c-003", "product_intent": "LOAN"},
        "collecting_data": {
            "loan_profile": {
                "renta": 2000000,
                "antiguedad_laboral": 18,
                "nivel_estudios": "UNIVERSITARIO",
            },
            "loan_sim": {
                "monto_solicitado": 5000000,
                "plazo_solicitado": 24,
            },
        },
        "evaluation_results": {},
        "messages": [],
    }


def test_loan_engine_writes_to_correct_namespace():
    """El motor escribe en evaluation_results["loan_engine"], no en otro lugar."""
    from app.graph.nodes.credit import loan_risk_engine_node
    state = make_loan_ready_state()
    result = loan_risk_engine_node(state)

    assert "evaluation_results" in result
    assert "loan_engine" in result["evaluation_results"]
    # No escribe en account_engine ni dap_engine
    assert "account_engine" not in result["evaluation_results"]


def test_loan_engine_does_not_write_to_collecting_data():
    """El motor no debe modificar collecting_data."""
    from app.graph.nodes.credit import loan_risk_engine_node
    state = make_loan_ready_state()
    result = loan_risk_engine_node(state)
    assert "collecting_data" not in result


def test_loan_engine_reads_from_preparation_data():
    """El motor lee edad desde preparation_data, no desde user_data."""
    from app.graph.nodes.credit import loan_risk_engine_node
    state = make_loan_ready_state()
    # No hay user_data en el state; si el motor falla aquí, está leyendo del lugar incorrecto
    result = loan_risk_engine_node(state)
    assert result["evaluation_results"]["loan_engine"]["cuota_maxima_permitida"] == int(2000000 * 0.30)


def test_dap_engine_term_premium_calculation():
    """Verifica la fórmula de term_premium: (plazo // 30) * 0.0005."""
    from app.graph.nodes.deposit import dap_investment_engine_node
    state = {
        "preparation_data": {"edad": 25},
        "session": {"conversation_id": "c-004", "product_intent": "DAP"},
        "collecting_data": {
            "dap_params": {"monto": 1000000.0, "moneda": "CLP", "plazo": 180}
        },
        "evaluation_results": {},
        "messages": [],
    }
    result = dap_investment_engine_node(state)
    # plazo=180, 180//30=6, 6*0.0005 = 0.003
    assert result["evaluation_results"]["dap_engine"]["term_premium"] == pytest.approx(0.003)
```

**Documentación del Paso 4:**
> Se estableció el patrón de escritura para los motores financieros: cada motor lee sus inputs desde `collecting_data` y `preparation_data`, y escribe sus outputs **exclusivamente** en su sub-cajón de `evaluation_results`. Los motores no tienen acceso de escritura a `collecting_data`. Se crearon stubs de `loan_risk_engine_node` y `dap_investment_engine_node` que implementan el patrón correcto de I/O, listos para recibir la lógica de negocio en Fase 2.

---
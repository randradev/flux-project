## PASO 3 — Cableado del Grafo (Actualización del Plan Original)

> **Contexto:** El plan original `fase-2.md` definía la estructura del grafo pero está parcialmente desactualizado. Este paso lo reemplaza completamente con el conjunto de nodos correcto, incorporando el patrón determinista.

### Sub-paso 3.1 — Registrar todos los nodos en `workflow.py` [GRAFO]

**Archivo:** `app/graph/workflow.py`

Agregar al bloque de registro de nodos de Crédito de Consumo en `build_graph()`:

```python
# Nodos de Recolección (ya existentes — NO modificar)
graph.add_node("loan_collecting_profile",    loan_collecting_profile_node)
graph.add_node("loan_collecting_simulation", loan_collecting_sim_node)

# Nodos de Evaluación y Oferta (NUEVOS)
graph.add_node("loan_pre_approved",          loan_pre_approved_node)

# Nodos Deterministas (NUEVOS — sin extracción LLM)
graph.add_node("loan_otp_validation",        loan_otp_validation_node)
graph.add_node("loan_formalization",         loan_formalization_node)
graph.add_node("loan_completed",             loan_completed_node)

# Nodos de Cierre de Error (NUEVOS)
graph.add_node("loan_rejected_policy",       loan_rejected_policy_node)
graph.add_node("loan_security_block",        loan_security_block_node)
graph.add_node("loan_closed_by_user",        loan_closed_by_user_node)
```

**Actualizar las aristas de crédito** para reemplazar las conexiones antiguas (stub → END):

```python
# ── CRÉDITO DE CONSUMO — Flujo completo ───────────────────────

# Recolección → Motor
graph.add_edge("loan_init",                 "loan_collecting_profile")

# El loop de re-pregunta lo manejan las aristas condicionales en edges.py
graph.add_conditional_edges(
    "loan_collecting_profile",
    route_after_loan_collecting_profile,
    {
        "loan_collecting_simulation": "loan_collecting_simulation",
        "loan_collecting_profile":    "loan_collecting_profile",
    }
)
graph.add_conditional_edges(
    "loan_collecting_simulation",
    route_after_loan_collecting_simulation,
    {
        "loan_risk_engine":           "loan_risk_engine",
        "loan_collecting_simulation": "loan_collecting_simulation",
    }
)

# Motor → Oferta o Rechazo
graph.add_conditional_edges(
    "loan_risk_engine",
    route_after_loan_risk_engine,
    {
        "loan_pre_approved":   "loan_pre_approved",
        "loan_rejected_policy": "loan_rejected_policy",
    }
)

# Pre-aprobado → OTP o Rechazo voluntario
graph.add_conditional_edges(
    "loan_pre_approved",
    route_after_loan_pre_approved,
    {
        "loan_otp_validation": "loan_otp_validation",
        "loan_closed_by_user": "loan_closed_by_user",
        "loan_pre_approved":   "loan_pre_approved",   # loop: esperando decisión
    }
)

# OTP → Formalización o Bloqueo
graph.add_conditional_edges(
    "loan_otp_validation",
    route_after_loan_otp_validation,
    {
        "loan_formalization":  "loan_formalization",
        "loan_otp_validation": "loan_otp_validation",  # loop: reintento
        "loan_security_block": "loan_security_block",
    }
)

# Formalización → Completado (o loop por error técnico)
graph.add_conditional_edges(
    "loan_formalization",
    route_after_loan_formalization,
    {
        "loan_completed":      "loan_completed",
        "loan_formalization":  "loan_formalization",  # loop: esperando firma
    }
)

# Terminales → END
graph.add_edge("loan_completed",       END)
graph.add_edge("loan_rejected_policy", END)
graph.add_edge("loan_security_block",  END)
graph.add_edge("loan_closed_by_user",  END)
```

---

### Sub-paso 3.2 — Implementar funciones de ruteo en `edges.py` [GRAFO]

**Archivo:** `app/graph/edges.py`

Agregar al final del archivo. No modificar las funciones existentes.

```python
# ═══════════════════════════════════════════════════════════════
# RUTAS DE CRÉDITO DE CONSUMO
# Nota: Las rutas de collecting (profile y simulation) leen los
# namespaces del State directamente, sin lógica de negocio.
# ═══════════════════════════════════════════════════════════════

def route_after_loan_collecting_profile(state: FluxState) -> str:
    """
    Ruta después de LOAN_COLLECTING_PROFILE.
    Lee collecting_data["loan_profile"] y verifica completitud.
    """
    profile  = state.get("collecting_data", {}).get("loan_profile", {})
    required = ["renta", "antiguedad_laboral", "nivel_estudios"]
    valid_estudios = {"POSTGRADO", "UNIVERSITARIO", "TECNICO", "MEDIA"}

    renta   = profile.get("renta")
    ant     = profile.get("antiguedad_laboral")
    estudios = profile.get("nivel_estudios")

    profile_ok = (
        renta is not None and renta > 0 and
        ant is not None and ant >= 0 and
        estudios in valid_estudios
    )
    return "loan_collecting_simulation" if profile_ok else "loan_collecting_profile"


def route_after_loan_collecting_simulation(state: FluxState) -> str:
    """
    Ruta después de LOAN_COLLECTING_SIMULATION.
    Lee collecting_data["loan_sim"] y verifica completitud.
    """
    sim = state.get("collecting_data", {}).get("loan_sim", {})
    monto = sim.get("monto_solicitado")
    plazo = sim.get("plazo_solicitado")

    sim_ok = (
        monto is not None and monto > 0 and
        plazo is not None and plazo > 0
    )
    return "loan_risk_engine" if sim_ok else "loan_collecting_simulation"


def route_after_loan_risk_engine(state: FluxState) -> str:
    """
    Ruta después de LOAN_RISK_ENGINE.
    Lee evaluation_results["loan_engine"]["status_proceso"].
    """
    loan_engine = state.get("evaluation_results", {}).get("loan_engine", {})
    status      = loan_engine.get("status_proceso", "ERROR")

    if status == "PRE_APPROVED":
        return "loan_pre_approved"
    else:
        # REJECTED (PolicyRejectionError, PaymentCapacityError) o ERROR
        return "loan_rejected_policy"


def route_after_loan_pre_approved(state: FluxState) -> str:
    """
    Ruta después de LOAN_PRE_APPROVED.
    Lee offer_data["loan"]["pre_approval_status"].
    
    LÓGICA DE TRES ESTADOS:
      - ACCEPTED   : El frontend envió payload de botón "Acepto" → avanzar a OTP.
      - REJECTED   : El frontend envió payload de botón "Rechazo" → cierre voluntario.
      - None/vacío : Tarjeta mostrada, esperando decisión → loop (el nodo ya emitió la tarjeta).
    """
    offer_status = state.get("offer_data", {}).get("loan", {}).get("pre_approval_status")

    if offer_status == "ACCEPTED":
        return "loan_otp_validation"
    elif offer_status == "REJECTED":
        return "loan_closed_by_user"
    else:
        return "loan_pre_approved"  # Loop: tarjeta mostrada, esperando botón


def route_after_loan_otp_validation(state: FluxState) -> str:
    """
    Ruta después de LOAN_OTP_VALIDATION.
    Lee auth_control para determinar el resultado de la validación.
    
    LÓGICA:
      - security_blocked = True  → bloqueo definitivo.
      - otp_verified = True      → avanzar a formalización.
      - Sin resultado aún        → loop (usuario aún no envió el código).
    """
    auth = state.get("auth_control", {})

    if auth.get("security_blocked"):
        return "loan_security_block"
    if auth.get("otp_verified"):
        return "loan_formalization"
    return "loan_otp_validation"  # Loop: esperando código del frontend


def route_after_loan_formalization(state: FluxState) -> str:
    """
    Ruta después de LOAN_FORMALIZATION.
    Lee offer_data["loan"]["contract_status"].
    
    LÓGICA:
      - SIGNED_AND_STAMPED : Contrato generado y aceptado → flujo completado.
      - Cualquier otro     : Pendiente (loop en espera del payload del botón).
    """
    contract_status = state.get("offer_data", {}).get("loan", {}).get("contract_status")

    if contract_status == "SIGNED_AND_STAMPED":
        return "loan_completed"
    return "loan_formalization"  # Loop: esperando firma del frontend
```

---

**✅ CRITERIO PASS Sub-paso 3.2** [TEST-UNIT]:

```python
# tests/unit/test_edges_credit.py
from app.graph.edges import (
    route_after_loan_collecting_profile,
    route_after_loan_collecting_simulation,
    route_after_loan_risk_engine,
    route_after_loan_pre_approved,
    route_after_loan_otp_validation,
    route_after_loan_formalization,
)

def test_profile_completo_avanza():
    state = {"collecting_data": {"loan_profile": {
        "renta": 1_500_000, "antiguedad_laboral": 24, "nivel_estudios": "UNIVERSITARIO"
    }}}
    assert route_after_loan_collecting_profile(state) == "loan_collecting_simulation"

def test_profile_incompleto_hace_loop():
    state = {"collecting_data": {"loan_profile": {"renta": 1_000_000}}}
    assert route_after_loan_collecting_profile(state) == "loan_collecting_profile"

def test_sim_completa_avanza():
    state = {"collecting_data": {"loan_sim": {"monto_solicitado": 5_000_000, "plazo_solicitado": 24}}}
    assert route_after_loan_collecting_simulation(state) == "loan_risk_engine"

def test_engine_pre_aprobado_va_a_oferta():
    state = {"evaluation_results": {"loan_engine": {"status_proceso": "PRE_APPROVED"}}}
    assert route_after_loan_risk_engine(state) == "loan_pre_approved"

def test_engine_rechazado_va_a_rechazo():
    state = {"evaluation_results": {"loan_engine": {"status_proceso": "REJECTED"}}}
    assert route_after_loan_risk_engine(state) == "loan_rejected_policy"

def test_pre_aprobado_sin_decision_hace_loop():
    state = {"offer_data": {"loan": {}}}
    assert route_after_loan_pre_approved(state) == "loan_pre_approved"

def test_otp_verified_va_a_formalizacion():
    state = {"auth_control": {"otp_verified": True, "security_blocked": False}}
    assert route_after_loan_otp_validation(state) == "loan_formalization"

def test_otp_bloqueado_va_a_bloqueo():
    state = {"auth_control": {"security_blocked": True}}
    assert route_after_loan_otp_validation(state) == "loan_security_block"
```

---
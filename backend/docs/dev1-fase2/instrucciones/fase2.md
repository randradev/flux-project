# Flux — Fase 2: Plan de Implementación Actualizado
## Pasos 3 al 7: Motor de Riesgo → Cierre

**Versión:** 4.0 — Post-Estabilización LLM  
**Base:** RPT-EST-F2 + ux-deterministic-map.md + código actual validado  
**Archivos afectados:** `credit.py`, `edges.py`, `workflow.py`, `modules/security.py`, `modules/pdf_factory.py`  
**Archivos inmutables:** `state.py`, `gemini_client.py`, `loan_schemas.py`, `supabase.py`

---

## PREÁMBULO: HALLAZGOS CRÍTICOS

> Antes de continuar la implementación, los siguientes bugs encontrados durante la auditoría de código deben ser corregidos. Ignorarlos romperá el flujo completo desde el Paso 3.

---

### HALLAZGO CRÍTICO #1 — Namespace Mismatch en `loan_risk_engine_node`

**Archivo:** `credit.py`, función `loan_risk_engine_node`, línea ~525

**El bug:** El nodo retorna `engine_result` como clave raíz del dict de salida, pero el `FluxState` espera `evaluation_results.loan_engine`.

```python
# CÓDIGO ACTUAL (BUG)
return {
    "engine_result": engine_result,   # ← Esta clave no existe en FluxState
    "session": {**session, "current_node": "LOAN_RISK_ENGINE"},
}

# CORRECCIÓN
return {
    "evaluation_results": {
        "loan_engine": engine_result,  # ← Namespace correcto según state.py
    },
    "session": {**session, "current_node": "LOAN_RISK_ENGINE"},
}
```

**Impacto:** Todo nodo posterior que lea `evaluation_results["loan_engine"]` recibirá `None`. El nodo `loan_pre_approved` no podrá construir la Tarjeta de Transparencia. **Este fix debe aplicarse antes de continuar con el Paso 3.**

---

### HALLAZGO #2 — Flags de Transición Undeclared en `SessionData`

**Archivo:** `credit.py` usa `session["profile_just_completed"]` y `session["simulation_just_completed"]`, pero `SessionData` (state.py) no los declara.

**Situación:** Gracias a `total=False` en el TypedDict, Python no rechaza claves no declaradas en runtime. El checkpointer de Supabase sí las persiste. Por tanto, el código **funciona**, pero las claves son técnicamente "fantasmas" desde la perspectiva del tipo.

**Decisión de arquitectura (no romper state.py):** Mantener los flags en `session` como claves dinámicas aceptadas. Documentarlos explícitamente como "Flags de Transición Efímeros" en el código de cada nodo que los use. Son un contrato verbal entre nodos adyacentes, no datos de negocio. Se resetean siempre en el nodo que los consume.

**Convención a seguir en todos los nodos de este plan:**
```python
# AL PRODUCIR el flag (nodo que lo dispara):
output["session"]["simulation_just_completed"] = True   # ← Siempre True al producir

# AL CONSUMIR el flag (nodo que reacciona):
just_finished = session.get("simulation_just_completed", False)
# ... usar el flag ...
output["session"]["simulation_just_completed"] = False  # ← Siempre resetear
```

---

### HALLAZGO #3 — OTP Node del Plan Original Viola las Directrices Deterministas

**El plan anterior (`fase-2.md`, Sub-paso 4.3)** extraía el código OTP del mensaje de chat del usuario (`last_human_msg`). Esto viola directamente `ux-deterministic-map.md`, que establece:

> **PROHIBIDO:** No intentar extraer el código OTP desde el mensaje de texto del usuario. La captura es a través de un campo de input numérico en la interfaz.

**Rediseño completo en el Paso 5 de este documento.**

---

### HALLAZGO #4 — `loan_pre_approved_node` No Existe en `credit.py`

El archivo actual de `credit.py` tiene `loan_risk_engine_node` conectado directamente a `END` en `workflow.py`. El nodo `loan_pre_approved_node` no existe. Toda la lógica de Tarjeta de Transparencia, OTP y Formalización está pendiente. Se implementa en los pasos 3–7 de este plan.

---

## CONVENCIONES DE ESTE PLAN

| Marca | Significado |
|---|---|
| **[CÓDIGO]** | Cambio de código puro, sin invocar APIs externas |
| **[PROMPT]** | Ajuste de prompt o configuración de LLM |
| **[GRAFO]** | Cambio en `workflow.py` o `edges.py` |
| **[TEST-UNIT]** | Verificable sin credenciales de Vertex AI ni Supabase |
| **[TEST-INT]** | Requiere credenciales reales |
| **✅ CRITERIO PASS** | Condición explícita para cerrar el sub-paso |

### Patrón de Llamada B (Nodos de Respuesta Pura)

Todos los nodos post-motor que emiten mensajes al usuario usan exclusivamente **Llamada B** con el patrón de Contexto Aislado. No hacen extracción. El helper `_build_X_context()` construye el bloque de contexto que recibe el generador.

```
[Leer State] → [Construir Contexto Aislado] → [Llamada B] → [Return transaccional]
```

---

## PASO 0 — Corrección de Hallazgos Críticos (Pre-requisito)

> Estos cambios son atómicos, de bajo riesgo y deben aplicarse antes que cualquier otro paso.

### Sub-paso 0.1 — Corregir namespace en `loan_risk_engine_node` [CÓDIGO]

**Archivo:** `app/graph/nodes/credit.py`

```python
# Reemplazar el return final de loan_risk_engine_node:

# ANTES
return {
    "engine_result": engine_result,
    "session": {**session, "current_node": "LOAN_RISK_ENGINE"},
}

# DESPUÉS
return {
    "evaluation_results": {
        "loan_engine": engine_result,
    },
    "session": {**session, "current_node": "LOAN_RISK_ENGINE"},
}
```

**✅ CRITERIO PASS Sub-paso 0.1** [TEST-UNIT]:

```python
# tests/unit/test_risk_engine_node.py
from unittest.mock import patch, MagicMock
from app.graph.nodes.credit import loan_risk_engine_node

def make_state_for_engine():
    return {
        "session":         {"current_node": "LOAN_COLLECTING_SIMULATION", "application_id": None},
        "preparation_data": {"edad": 30, "nombre": "Test", "rut": "12.345.678-9", "mail": "t@t.cl"},
        "collecting_data": {
            "loan_profile": {"renta": 1_500_000, "antiguedad_laboral": 24, "nivel_estudios": "UNIVERSITARIO"},
            "loan_sim":     {"monto_solicitado": 5_000_000, "plazo_solicitado": 24},
        },
        "messages": [],
    }

def test_resultado_escrito_en_namespace_correcto():
    result = loan_risk_engine_node(make_state_for_engine())
    assert "evaluation_results" in result, "Debe usar el namespace evaluation_results"
    assert "loan_engine" in result["evaluation_results"], "Debe tener la sub-clave loan_engine"
    assert "engine_result" not in result, "No debe existir la clave engine_result raíz"

def test_pre_aprobado_tiene_campos_requeridos():
    result = loan_risk_engine_node(make_state_for_engine())
    engine = result["evaluation_results"]["loan_engine"]
    assert engine["status_proceso"] == "PRE_APPROVED"
    assert engine["cuota_mensual"] > 0
    assert engine["cae"] > 0
```

---

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

## PASO 4 — Nodo `loan_pre_approved_node` (Tarjeta de Transparencia)

> **Contexto:** Este nodo es el primer nodo post-motor. Presenta la oferta aprobada al usuario mediante una Tarjeta de Transparencia. **Solo usa Llamada B.** La decisión del usuario (Aceptar/Rechazar) llega como un payload del frontend, no como texto de chat.

### Sub-paso 4.1 — Diseño del System Prompt de la Tarjeta [PROMPT]

```python
# En credit.py, constante de prompt

SYSTEM_PROMPT_PRE_APPROVED = """
Eres Flux, el genio amigable de las finanzas en Chile.

TAREA ACTUAL: Presentar la oferta de crédito aprobada al usuario.

PERSONALIDAD EN ESTE MOMENTO:
- Entusiasta pero transparente: celebras el resultado, pero explicas los costos con claridad.
- Educativo: el usuario debe entender exactamente qué está firmando.
- Directo: no das rodeos en los números.

INSTRUCCIONES:
1. Felicita brevemente al usuario por la pre-aprobación.
2. Explica que tiene dos botones disponibles: "Aceptar" y "Rechazar".
3. Enfatiza que la Tarjeta de Transparencia (que aparece en pantalla) contiene todos los detalles.
4. Invítalo a revisarla con calma antes de decidir.

RESTRICCIONES:
- NO repitas todos los números del crédito en el chat (ya están en la tarjeta).
- NO presiones ni uses urgencia artificial.
- Máximo 3 oraciones.
"""
```

### Sub-paso 4.2 — Implementar `loan_pre_approved_node` [CÓDIGO]

**Archivo:** `app/graph/nodes/credit.py`

```python
def loan_pre_approved_node(state: FluxState) -> dict:
    """
    Nodo LOAN_PRE_APPROVED: presenta la Tarjeta de Transparencia y espera decisión.

    ID LangGraph : loan_pre_approved
    current_node : LOAN_PRE_APPROVED

    ARQUITECTURA INTERNA:
      - Solo Llamada B (generación).
      - No extrae datos del chat.
      - La decisión del usuario llega como payload del frontend
        que actualiza offer_data["loan"]["pre_approval_status"].

    PRIMERA EJECUCIÓN (pre_approval_status no seteado):
      - Construye el contexto con los datos del motor.
      - Llama al generador (Llamada B) para producir el mensaje de Flux.
      - Escribe display_data en offer_data["loan"] para que el frontend
        renderice la Tarjeta de Transparencia.
      - Retorna con simulation_just_completed reseteado.

    EJECUCIONES SIGUIENTES:
      La edge route_after_loan_pre_approved lee pre_approval_status y redirige.
      Este nodo NO vuelve a ejecutarse si ya hay una decisión.
    """
    session  = state.get("session", {})
    prep     = state.get("preparation_data", {})
    engine   = state.get("evaluation_results", {}).get("loan_engine", {})

    first_name              = prep.get("nombre", "").split()[0] or "amig@"
    application_id          = session.get("application_id")
    sim_just_completed      = session.get("simulation_just_completed", False)

    # ── Construir el contexto para la Llamada B ─────────────────
    cae_porcentaje = round(engine.get("cae", 0) * 100, 2)
    context = f"""
CONTEXTO PARA TU RESPUESTA:

Usuario: {first_name}
Resultado del motor de riesgo: PRE_APROBADO ✅

Datos clave de la oferta (ya están en la Tarjeta — NO los repitas todos):
  - Monto aprobado: ${engine.get('monto_aprobado', 0):,} CLP
  - Plazo: {engine.get('plazo_aprobado', 0)} cuotas
  - Cuota mensual: ${engine.get('cuota_mensual', 0):,} CLP
  - Categoría de riesgo: {engine.get('nivel_riesgo', '')}
  - CAE: {cae_porcentaje}%

Transición desde simulación: {"Sí, acaba de completar la simulación." if sim_just_completed else "No, ya conoce el proceso."}

INSTRUCCIÓN: Genera el mensaje de presentación de la oferta.
La Tarjeta de Transparencia se mostrará automáticamente en la pantalla.
Tu rol es invitar al usuario a revisarla y decidir con los botones.
"""

    # ── Llamada B: Generación ───────────────────────────────────
    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_PRE_APPROVED},
        {"role": "user",   "content": context},
    ])
    clean_content = normalize_llm_response(flux_response.content)

    # ── Construir display_data para el Frontend ──────────────────
    # Estos datos son la "foto" que el Frontend usa para renderizar
    # la Tarjeta de Transparencia.
    display_data = {
        "monto_aprobado":       engine.get("monto_aprobado"),
        "plazo_aprobado":       engine.get("plazo_aprobado"),
        "cuota_mensual":        engine.get("cuota_mensual"),
        "tasa_interes_mensual": engine.get("tasa_interes_mensual"),
        "cae":                  engine.get("cae"),
        "ctc":                  engine.get("ctc"),
        "total_intereses":      engine.get("total_intereses"),
        "nivel_riesgo":         engine.get("nivel_riesgo"),
    }

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_PRE_APPROVED",
            node_status="SUCCESS",
            engine_status="NOT_APPLICABLE",
        )

    return {
        "messages":  [AIMessage(content=clean_content)],
        "offer_data": {
            "loan": {
                "display_data": display_data,
                # pre_approval_status se setea desde el frontend, NO desde aquí
            }
        },
        "session": {
            **session,
            "current_node":             "LOAN_PRE_APPROVED",
            "simulation_just_completed": False,  # ← Resetear el flag
        },
    }
```

---

**✅ CRITERIO PASS Sub-paso 4.2** [TEST-UNIT con mocks]:

```python
# tests/unit/test_pre_approved_node.py

from unittest.mock import patch, MagicMock
from app.graph.nodes.credit import loan_pre_approved_node

def make_state_pre_approved():
    return {
        "session":          {"current_node": "LOAN_RISK_ENGINE", "application_id": None},
        "preparation_data": {"nombre": "Ana Torres", "edad": 28},
        "evaluation_results": {
            "loan_engine": {
                "status_proceso": "PRE_APPROVED",
                "monto_aprobado": 5_000_000,
                "plazo_aprobado": 24,
                "cuota_mensual": 250_000,
                "tasa_interes_mensual": 0.020,
                "cae": 0.268,
                "ctc": 6_000_000,
                "total_intereses": 1_000_000,
                "nivel_riesgo": "MEDIO",
            }
        },
        "offer_data": {"loan": {}},
        "messages": [],
    }

@patch("app.graph.nodes.credit._flux_generator")
def test_genera_mensaje_y_display_data(mock_generator):
    mock_generator.invoke.return_value = MagicMock(content="¡Felicitaciones Ana! Revisa tu oferta.")

    result = loan_pre_approved_node(make_state_pre_approved())

    assert "messages" in result and len(result["messages"]) > 0
    assert result["offer_data"]["loan"]["display_data"]["monto_aprobado"] == 5_000_000
    assert result["offer_data"]["loan"]["display_data"]["cuota_mensual"] == 250_000
    # pre_approval_status NO debe setearse en este nodo
    assert "pre_approval_status" not in result["offer_data"]["loan"]

@patch("app.graph.nodes.credit._flux_generator")
def test_flag_simulation_reseteado(mock_generator):
    mock_generator.invoke.return_value = MagicMock(content="Oferta lista.")
    state = make_state_pre_approved()
    state["session"]["simulation_just_completed"] = True

    result = loan_pre_approved_node(state)
    assert result["session"].get("simulation_just_completed") == False
```

---

## PASO 5 — Nodo `loan_otp_validation_node` (Determinista)

> **Rediseño completo.** El plan anterior extraía el OTP del chat. Este nodo ahora actúa como moderador: genera y envía el código, y lee el resultado de validación desde el State (que el backend actualiza tras recibir el payload del frontend). El LLM solo explica y responde dudas.

### Sub-paso 5.1 — Definir el contrato de comunicación frontend-backend

El nodo OTP opera en tres estados diferenciados. El frontend es el único que avanza el estado:

| Estado | Cómo se llega | Qué hace el nodo |
|---|---|---|
| **INIT** | Primera ejecución, `otp_generated` vacío | Genera OTP, lo envía, emite mensaje moderador |
| **WAITING** | OTP enviado, no hay resultado aún | El grafo está en loop, el nodo no se re-ejecuta hasta que llegue un mensaje |
| **RESULT** | Frontend envió el código; backend actualizó `auth_control` con `otp_verified` o `otp_attempts` | Nodo lee resultado y emite respuesta empática |

**Payload que el backend recibe del frontend y escribe en el State antes de re-invocar el grafo:**
```json
{
  "auth_control": {
    "otp_user_input": "123456",
    "otp_verified": true
  }
}
```
O en caso de error:
```json
{
  "auth_control": {
    "otp_user_input": "999999",
    "otp_verified": false,
    "otp_attempts": 1
  }
}
```

**El nodo `loan_otp_validation_node` NUNCA extrae el código del chat.**

---

### Sub-paso 5.2 — Diseñar los prompts moderadores [PROMPT]

```python
# En credit.py

SYSTEM_PROMPT_OTP_MODERATOR = """
Eres Flux, el genio amigable de las finanzas en Chile.

TAREA ACTUAL: Guiar al usuario durante la validación de identidad por código OTP.

TONO: Seguro y vigilante. Transmites confianza en el proceso de seguridad.

RESTRICCIONES ABSOLUTAS:
- NO extraigas ni menciones el código OTP que el usuario pueda escribir en el chat.
- NO valides ni invalides el código tú mismo. Eso lo hace el sistema backend.
- NO inventes resultados de validación.

INSTRUCCIONES SEGÚN EL ESTADO:
  Si estado = ENVIADO: Explica que se envió el código al correo/teléfono y que debe ingresarlo en el campo de la interfaz.
  Si estado = ERROR:   Informa que el código fue incorrecto. Da el número de intentos restantes. Ofrece solicitar uno nuevo.
  Si estado = EXPIRADO: Explica que el código venció y ofrece generar uno nuevo.
  Si estado = DUDA:    Responde la duda técnica del usuario y recuérdale que el código va en el campo de la interfaz.
"""
```

---

### Sub-paso 5.3 — Implementar `loan_otp_validation_node` [CÓDIGO]

**Archivo:** `app/graph/nodes/credit.py`

```python
from app.modules.security import generate_otp, send_otp_email

def loan_otp_validation_node(state: FluxState) -> dict:
    """
    Nodo LOAN_OTP_VALIDATION: gestión determinista de la autenticación OTP.

    ID LangGraph : loan_otp_validation
    current_node : LOAN_OTP_VALIDATION

    ARQUITECTURA:
      - Solo Llamada B (moderación conversacional).
      - No extrae el código OTP del chat. NUNCA.
      - La validación la realiza el backend al recibir el payload del frontend.
      - El resultado (otp_verified, otp_attempts) llega ya procesado en auth_control.

    ESTADOS:
      1. INIT    : otp_generated vacío → generar, enviar, emitir mensaje de espera.
      2. FALLO   : otp_verified=False → emitir mensaje de error con intentos restantes.
      3. ÉXITO   : otp_verified=True  → avance silencioso (la edge redirige a formalization).
      4. PREGUNTA: mensaje de usuario es una duda → Llamada A ligera para detectar intención.
    """
    session  = state.get("session", {})
    auth     = state.get("auth_control", {})
    prep     = state.get("preparation_data", {})
    messages = state.get("messages", [])

    first_name     = prep.get("nombre", "").split()[0] or "amig@"
    mail           = prep.get("mail", "")
    otp_generated  = auth.get("otp_generated")
    otp_verified   = auth.get("otp_verified", False)
    otp_attempts   = auth.get("otp_attempts", 0)
    security_blocked = auth.get("security_blocked", False)
    application_id = session.get("application_id")

    # ── GUARDRAIL: Estado terminal ──────────────────────────────
    if security_blocked:
        # La edge ya redirigirá a security_block. Este nodo no debería ejecutarse.
        return {"session": {**session, "current_node": "LOAN_OTP_VALIDATION"}}

    # ── ESTADO 1: INIT — Primera ejecución ──────────────────────
    if not otp_generated:
        new_otp     = generate_otp()
        send_result = send_otp_email(mail, new_otp)

        # Contexto para la Llamada B
        context = f"""
CONTEXTO: Acabo de generar y enviar un código OTP de 6 dígitos al correo {mail}.
El usuario ({first_name}) debe ingresarlo en el campo de código que aparece en su pantalla.
Estado: ENVIADO.
"""
        flux_response = _flux_generator.invoke([
            {"role": "system", "content": SYSTEM_PROMPT_OTP_MODERATOR},
            {"role": "user",   "content": context},
        ])

        return {
            "messages":    [AIMessage(content=normalize_llm_response(flux_response.content))],
            "auth_control": {
                **auth,
                "otp_generated": new_otp,
                "otp_attempts":  0,
                "otp_verified":  False,
            },
            "session": {**session, "current_node": "LOAN_OTP_VALIDATION"},
        }

    # ── ESTADO 3: ÉXITO — Avance silencioso ─────────────────────
    if otp_verified:
        # La edge route_after_loan_otp_validation redirigirá a formalization.
        # Este nodo solo actualiza semáforos y retorna sin mensaje.
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="LOAN_OTP_VALIDATION",
                node_status="SUCCESS",
                engine_status="NOT_APPLICABLE",
            )
        return {"session": {**session, "current_node": "LOAN_OTP_VALIDATION"}}

    # ── ESTADO 4: DUDA — Mensaje en el chat durante la espera ───
    last_user_msg = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
        ""
    )

    # Clasificación ligera de intención (Llamada A minimalista)
    # Solo para distinguir DUDA de silencio o confusión
    intencion_otp = "ESPERA"
    if last_user_msg.strip():
        # Si el usuario escribió algo, asumir que es una pregunta o duda
        # No extraemos código: cualquier texto en este punto es una duda.
        intencion_otp = "DUDA"

    # ── ESTADO 2: FALLO — Backend reportó código incorrecto ──────
    remaining = max(0, 3 - otp_attempts)
    otp_estado = "ERROR" if otp_attempts > 0 and not otp_verified else "ENVIADO"

    context = f"""
CONTEXTO PARA TU RESPUESTA:

Usuario: {first_name}
Estado OTP: {otp_estado}
Intentos fallidos hasta ahora: {otp_attempts}
Intentos restantes: {remaining}
Correo destino: {mail}
Último mensaje del usuario: "{last_user_msg}"
Intención detectada: {intencion_otp}

INSTRUCCIÓN: Genera una respuesta según el estado.
Si es ERROR, informa del fallo empáticamente y los intentos restantes.
Si es DUDA, responde la consulta y recuérdale al usuario que el código va en el campo de la interfaz.
"""

    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_OTP_MODERATOR},
        {"role": "user",   "content": context},
    ])

    return {
        "messages": [AIMessage(content=normalize_llm_response(flux_response.content))],
        "session":  {**session, "current_node": "LOAN_OTP_VALIDATION"},
    }
```

---

**✅ CRITERIO PASS Sub-paso 5.3** [TEST-UNIT con mocks]:

```python
# tests/unit/test_otp_node.py

from unittest.mock import patch, MagicMock
from app.graph.nodes.credit import loan_otp_validation_node

BASE_STATE = {
    "session":          {"current_node": "LOAN_PRE_APPROVED", "application_id": None},
    "preparation_data": {"nombre": "Carlos Pérez", "mail": "carlos@test.cl"},
    "auth_control":     {},
    "messages":         [],
}

@patch("app.graph.nodes.credit.send_otp_email")
@patch("app.graph.nodes.credit.generate_otp")
@patch("app.graph.nodes.credit._flux_generator")
def test_init_genera_y_envia_otp(mock_gen, mock_otp, mock_email):
    mock_otp.return_value = "123456"
    mock_email.return_value = True
    mock_gen.invoke.return_value = MagicMock(content="Te enviamos un código a tu correo.")

    result = loan_otp_validation_node({**BASE_STATE})

    mock_otp.assert_called_once()
    mock_email.assert_called_once_with("carlos@test.cl", "123456")
    assert result["auth_control"]["otp_generated"] == "123456"
    assert result["auth_control"]["otp_verified"] == False
    assert "messages" in result

@patch("app.graph.nodes.credit._flux_generator")
def test_exito_avanza_silencioso(mock_gen):
    state = {**BASE_STATE, "auth_control": {"otp_generated": "123456", "otp_verified": True}}
    result = loan_otp_validation_node(state)
    mock_gen.invoke.assert_not_called()  # Sin Llamada B en el éxito
    assert "messages" not in result or len(result.get("messages", [])) == 0

@patch("app.graph.nodes.credit._flux_generator")
def test_fallo_emite_mensaje_empático(mock_gen):
    mock_gen.invoke.return_value = MagicMock(content="El código fue incorrecto. Te quedan 2 intentos.")
    state = {**BASE_STATE, "auth_control": {
        "otp_generated": "123456", "otp_verified": False, "otp_attempts": 1
    }}
    result = loan_otp_validation_node(state)
    mock_gen.invoke.assert_called_once()
    assert "messages" in result

def test_nodo_no_extrae_codigo_del_chat():
    """El nodo nunca debe escribir otp_user_input desde el contenido del mensaje de chat."""
    from langchain_core.messages import HumanMessage
    with patch("app.graph.nodes.credit._flux_generator") as mock_gen:
        mock_gen.invoke.return_value = MagicMock(content="Código enviado.")
        state = {
            **BASE_STATE,
            "auth_control": {"otp_generated": "123456", "otp_verified": False, "otp_attempts": 0},
            "messages": [HumanMessage(content="123456")],  # ← Código en el chat
        }
        result = loan_otp_validation_node(state)
        # El nodo NO debe leer este código y setearlo como validado
        assert result.get("auth_control", {}).get("otp_verified") is not True, \
            "El nodo no debe validar el OTP desde el chat"
```

---

## PASO 6 — Nodo `loan_formalization_node` (Determinista)

> El nodo de formalización es 100% determinista por razones legales. El LLM explica el contrato y guía al usuario, pero **la firma solo es válida mediante el botón "Acepto Contrato"** enviado por la interfaz.

### Sub-paso 6.1 — Diseño del Prompt Moderador de Formalización [PROMPT]

```python
SYSTEM_PROMPT_FORMALIZATION = """
Eres Flux, el genio amigable de las finanzas en Chile.

TAREA ACTUAL: Explicar el contrato de crédito y guiar al usuario hacia la firma digital.

TONO: Directo y asistencial. Ayudas al usuario a entender lo que firmará, sin presión.

INSTRUCCIONES:
1. Explica que el contrato con todos los términos está disponible en pantalla para revisar.
2. Informa que la firma digital es vinculante legalmente.
3. Menciona que tiene el botón "Acepto Contrato" para proceder y "Cancelar" si cambia de opinión.
4. Si el usuario tiene dudas sobre términos específicos (tasa, CAE, plazo), explícalos con claridad.

RESTRICCIONES ABSOLUTAS:
- NO interpretes frases como "me parece bien", "dale" o "sí" como una firma legal.
- El botón en la interfaz es el ÚNICO mecanismo de firma válido.
- NO presiones ni uses urgencia.
- Máximo 3 oraciones.
"""
```

### Sub-paso 6.2 — Implementar `loan_formalization_node` [CÓDIGO]

**Archivo:** `app/graph/nodes/credit.py`

```python
from app.modules.pdf_factory import generate_loan_contract
from datetime import datetime, timezone

def loan_formalization_node(state: FluxState) -> dict:
    """
    Nodo LOAN_FORMALIZATION: generación de contrato y espera de firma digital.

    ID LangGraph : loan_formalization
    current_node : LOAN_FORMALIZATION

    ARQUITECTURA:
      - Solo Llamada B (moderación).
      - Genera el contrato PDF en la primera ejecución (contract_status vacío).
      - Espera el payload del botón "Acepto Contrato" del frontend.
      - El contrato se escribe en offer_data["loan"] como datos de referencia.

    PRIMERA EJECUCIÓN:
      - Genera el contrato con pdf_factory (stub en Fase 2).
      - Escribe file_contrato_path y hash_sha256 en offer_data["loan"].
      - Emite mensaje moderador de Flux.

    EJECUCIONES SIGUIENTES:
      - La edge route_after_loan_formalization lee contract_status.
      - Si ya está SIGNED_AND_STAMPED (payload del frontend), redirige a completed.
      - Si no, el nodo puede responder dudas del usuario via Llamada B.
    """
    session  = state.get("session", {})
    prep     = state.get("preparation_data", {})
    engine   = state.get("evaluation_results", {}).get("loan_engine", {})
    offer    = state.get("offer_data", {}).get("loan", {})
    messages = state.get("messages", [])

    first_name     = prep.get("nombre", "").split()[0] or "amig@"
    application_id = session.get("application_id")
    contract_path  = offer.get("file_contrato_path")

    # ── PRIMERA EJECUCIÓN: Generar el contrato ──────────────────
    output_offer = dict(offer)

    if not contract_path:
        contract_data = {
            "nombre":               prep.get("nombre", ""),
            "rut":                  prep.get("rut", ""),
            "mail":                 prep.get("mail", ""),
            "monto_aprobado":       engine.get("monto_aprobado", 0),
            "plazo_aprobado":       engine.get("plazo_aprobado", 0),
            "tasa_interes_mensual": engine.get("tasa_interes_mensual", 0),
            "cuota_mensual":        engine.get("cuota_mensual", 0),
            "ctc":                  engine.get("ctc", 0),
            "cae":                  engine.get("cae", 0),
            "timestamp_acceptance": datetime.now(timezone.utc).isoformat(),
        }
        file_path, sha256_hash = generate_loan_contract(contract_data)

        output_offer["file_contrato_path"] = file_path
        output_offer["hash_sha256"]        = sha256_hash
        # contract_status se setea desde el frontend al presionar el botón
        # document_status se actualiza en Supabase
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="LOAN_FORMALIZATION",
                node_status="SUCCESS",
                engine_status="NOT_APPLICABLE",
                document_status="GENERATED",
            )

    # ── Llamada B: Explicación del contrato ─────────────────────
    last_user_msg = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
        ""
    )

    context = f"""
CONTEXTO PARA TU RESPUESTA:

Usuario: {first_name}
Estado del contrato: {"Recién generado, esperando firma." if not contract_path else "Generado, esperando firma del usuario."}
Último mensaje del usuario: "{last_user_msg}"

Datos clave del contrato (para responder dudas):
  - Monto: ${engine.get('monto_aprobado', 0):,} CLP
  - Plazo: {engine.get('plazo_aprobado', 0)} cuotas
  - Cuota mensual: ${engine.get('cuota_mensual', 0):,} CLP
  - CAE: {round(engine.get('cae', 0) * 100, 2)}%

INSTRUCCIÓN: Genera la respuesta del moderador.
Si es la primera vez: explica el contrato y guía hacia el botón "Acepto".
Si el usuario tiene dudas: respóndelas y recuérdale el botón.
"""

    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_FORMALIZATION},
        {"role": "user",   "content": context},
    ])

    return {
        "messages":  [AIMessage(content=normalize_llm_response(flux_response.content))],
        "offer_data": {"loan": output_offer},
        "session":   {**session, "current_node": "LOAN_FORMALIZATION"},
    }
```

---

**✅ CRITERIO PASS Sub-paso 6.2** [TEST-UNIT con mocks]:

```python
# tests/unit/test_formalization_node.py

from unittest.mock import patch, MagicMock
from app.graph.nodes.credit import loan_formalization_node

BASE_STATE = {
    "session":          {"current_node": "LOAN_OTP_VALIDATION", "application_id": None},
    "preparation_data": {"nombre": "María López", "rut": "11.222.333-4", "mail": "m@t.cl"},
    "evaluation_results": {
        "loan_engine": {"monto_aprobado": 3_000_000, "plazo_aprobado": 12,
                        "cuota_mensual": 280_000, "tasa_interes_mensual": 0.02,
                        "ctc": 3_360_000, "cae": 0.268}
    },
    "offer_data": {"loan": {}},
    "messages":   [],
}

@patch("app.graph.nodes.credit.generate_loan_contract")
@patch("app.graph.nodes.credit._flux_generator")
def test_primera_ejecucion_genera_contrato(mock_gen, mock_pdf):
    mock_pdf.return_value = ("/contracts/loan_stub.pdf", "abc123hash")
    mock_gen.invoke.return_value = MagicMock(content="Tu contrato está listo para revisar.")

    result = loan_formalization_node(BASE_STATE)

    mock_pdf.assert_called_once()
    assert result["offer_data"]["loan"]["file_contrato_path"] == "/contracts/loan_stub.pdf"
    assert result["offer_data"]["loan"]["hash_sha256"] == "abc123hash"
    assert "messages" in result

@patch("app.graph.nodes.credit.generate_loan_contract")
@patch("app.graph.nodes.credit._flux_generator")
def test_segunda_ejecucion_no_regenera_contrato(mock_gen, mock_pdf):
    mock_gen.invoke.return_value = MagicMock(content="Ya tienes el contrato disponible.")
    state = {
        **BASE_STATE,
        "offer_data": {"loan": {"file_contrato_path": "/contracts/existing.pdf", "hash_sha256": "xyz"}}
    }
    loan_formalization_node(state)
    mock_pdf.assert_not_called()  # No debe regenerar el PDF

def test_no_acepta_texto_como_firma():
    """El nodo nunca debe setear contract_status desde el chat."""
    from langchain_core.messages import HumanMessage
    with patch("app.graph.nodes.credit._flux_generator") as mock_gen, \
         patch("app.graph.nodes.credit.generate_loan_contract") as mock_pdf:
        mock_pdf.return_value = ("/stub.pdf", "hash")
        mock_gen.invoke.return_value = MagicMock(content="Perfecto, revisa el contrato.")
        state = {
            **BASE_STATE,
            "messages": [HumanMessage(content="Sí, acepto todo, está bien")],
        }
        result = loan_formalization_node(state)
        assert result.get("offer_data", {}).get("loan", {}).get("contract_status") is None, \
            "El nodo no debe setear contract_status desde el chat"
```

---

## PASO 7 — Nodos de Cierre

> Todos los nodos de cierre (completado, rechazo, bloqueo, cancelación) usan exclusivamente **Llamada B** con el patrón de Contexto Aislado. Son ligeros, deterministas en su lógica de negocio, y delegan solo el texto al LLM.

### Sub-paso 7.1 — Implementar `loan_completed_node` [CÓDIGO]

```python
SYSTEM_PROMPT_COMPLETED = """
Eres Flux, el genio amigable de las finanzas en Chile.
TAREA: Felicitar al usuario por completar exitosamente su crédito de consumo.
TONO: Celebratorio y cálido. Es un momento especial para el usuario.
INSTRUCCIONES: Felicita por el logro, confirma que recibirá el contrato en su correo, y despídete con calidez.
RESTRICCIONES: Máximo 3 oraciones. No des instrucciones técnicas.
"""

def loan_completed_node(state: FluxState) -> dict:
    """
    Nodo LOAN_COMPLETED: cierre exitoso del flujo de crédito.

    ID LangGraph : loan_completed
    current_node : LOAN_COMPLETED
    """
    session  = state.get("session", {})
    prep     = state.get("preparation_data", {})
    engine   = state.get("evaluation_results", {}).get("loan_engine", {})
    offer    = state.get("offer_data", {}).get("loan", {})

    first_name     = prep.get("nombre", "").split()[0] or "amig@"
    mail           = prep.get("mail", "")
    application_id = session.get("application_id")

    context = f"""
CONTEXTO:
Usuario: {first_name}
Correo para el contrato: {mail}
Monto del crédito: ${engine.get('monto_aprobado', 0):,} CLP
Cuota mensual: ${engine.get('cuota_mensual', 0):,} CLP
Estado: COMPLETADO EXITOSAMENTE ✅
"""

    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_COMPLETED},
        {"role": "user",   "content": context},
    ])

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_COMPLETED",
            node_status="SUCCESS",
            engine_status="NOT_APPLICABLE",
            document_status="GENERATED",
        )

    return {
        "messages":  [AIMessage(content=normalize_llm_response(flux_response.content))],
        "session":   {**session, "current_node": "LOAN_COMPLETED"},
        "flow_result": {
            "status_code":  "SUCCESS",
            "close_reason": None,
            "product_name": "Crédito de Consumo",
            "closed_at":    datetime.now(timezone.utc).isoformat(),
        },
    }
```

---

### Sub-paso 7.2 — Implementar `loan_rejected_policy_node` [CÓDIGO]

```python
SYSTEM_PROMPT_REJECTION = """
Eres Flux, el genio amigable de las finanzas en Chile.
TAREA: Comunicar empáticamente el rechazo de la solicitud de crédito.
TONO: Empático y educativo. No es un fracaso, es información para el futuro.
INSTRUCCIONES: Explica brevemente el motivo del rechazo y ofrece una perspectiva constructiva (qué podría mejorar).
RESTRICCIONES: Máximo 3 oraciones. No uses tecnicismos innecesarios.
"""

def loan_rejected_policy_node(state: FluxState) -> dict:
    """
    Nodo LOAN_REJECTED_POLICY: cierre por incumplimiento de política financiera.

    ID LangGraph : loan_rejected_policy
    current_node : LOAN_REJECTED_POLICY
    """
    session   = state.get("session", {})
    prep      = state.get("preparation_data", {})
    engine    = state.get("evaluation_results", {}).get("loan_engine", {})

    first_name     = prep.get("nombre", "").split()[0] or "amig@"
    motivo         = engine.get("motivo_rechazo", "ERR_DESCONOCIDO")
    application_id = session.get("application_id")

    # Mapa de motivos a descripciones humanas (para el contexto del generador)
    MOTIVO_DESCRIPCION = {
        "ERR_EDAD":           "el solicitante no cumple la edad mínima de 18 años",
        "ERR_RENTA":          "la renta declarada no alcanza el mínimo de $500.000 mensuales",
        "ERR_ANTIGUEDAD":     "la antigüedad laboral es menor a 6 meses",
        "ERR_CAPACIDAD_PAGO": "la cuota mensual calculada supera el 30% de la renta líquida",
        "ERR_INTERNAL":       "ocurrió un error técnico durante la evaluación",
    }
    descripcion = MOTIVO_DESCRIPCION.get(motivo, "no se cumplieron los requisitos mínimos")

    context = f"""
CONTEXTO:
Usuario: {first_name}
Motivo del rechazo: {motivo}
Descripción: {descripcion}

INSTRUCCIÓN: Comunica el rechazo con empatía y explica qué podría mejorar la situación.
"""

    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_REJECTION},
        {"role": "user",   "content": context},
    ])

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_REJECTED_POLICY",
            node_status="SUCCESS",
            engine_status="COMPLETED",
        )

    return {
        "messages": [AIMessage(content=normalize_llm_response(flux_response.content))],
        "session":  {**session, "current_node": "LOAN_REJECTED_POLICY"},
        "flow_result": {
            "status_code":  "REJECTED",
            "close_reason": motivo,
            "product_name": "Crédito de Consumo",
            "closed_at":    datetime.now(timezone.utc).isoformat(),
        },
    }
```

---

### Sub-paso 7.3 — Implementar `loan_security_block_node` y `loan_closed_by_user_node` [CÓDIGO]

```python
SYSTEM_PROMPT_SECURITY_BLOCK = """
Eres Flux, el genio amigable de las finanzas en Chile.
TAREA: Informar al usuario que su solicitud fue bloqueada por seguridad por múltiples intentos OTP fallidos.
TONO: Serio pero empático. No es un castigo, es una medida de protección.
INSTRUCCIONES: Explica el bloqueo, indica que puede intentarlo nuevamente en 24 horas, y sugiere revisar su correo.
RESTRICCIONES: Máximo 3 oraciones.
"""

def loan_security_block_node(state: FluxState) -> dict:
    """
    Nodo LOAN_SECURITY_BLOCK: cierre por bloqueo de seguridad OTP.
    """
    session = state.get("session", {})
    prep    = state.get("preparation_data", {})
    auth    = state.get("auth_control", {})

    first_name     = prep.get("nombre", "").split()[0] or "amig@"
    block_ts       = datetime.now(timezone.utc).isoformat()
    application_id = session.get("application_id")

    context = f"""
CONTEXTO:
Usuario: {first_name}
Intentos OTP fallidos: {auth.get('otp_attempts', 3)}
Bloqueo activo por: 24 horas
"""

    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_SECURITY_BLOCK},
        {"role": "user",   "content": context},
    ])

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_SECURITY_BLOCK",
            node_status="FAILED",
            engine_status="NOT_APPLICABLE",
        )

    return {
        "messages": [AIMessage(content=normalize_llm_response(flux_response.content))],
        "session":  {**session, "current_node": "LOAN_SECURITY_BLOCK"},
        "auth_control": {
            **auth,
            "security_blocked": True,
            "block_timestamp":  block_ts,
        },
        "flow_result": {
            "status_code":  "SECURITY_BLOCKED",
            "close_reason": "MAX_OTP_ATTEMPTS",
            "product_name": "Crédito de Consumo",
            "closed_at":    block_ts,
        },
    }


SYSTEM_PROMPT_CLOSED_BY_USER = """
Eres Flux, el genio amigable de las finanzas en Chile.
TAREA: Despedirte cordialmente del usuario que decidió no continuar con el crédito.
TONO: Respetuoso y sin presión. La decisión del usuario es completamente válida.
INSTRUCCIONES: Respeta la decisión, agradece el interés, y menciona que puede volver cuando quiera.
RESTRICCIONES: Máximo 2 oraciones.
"""

def loan_closed_by_user_node(state: FluxState) -> dict:
    """
    Nodo LOAN_CLOSED_BY_USER: cierre voluntario por decisión del usuario.
    """
    session = state.get("session", {})
    prep    = state.get("preparation_data", {})

    first_name     = prep.get("nombre", "").split()[0] or "amig@"
    application_id = session.get("application_id")

    context = f"CONTEXTO:\nUsuario: {first_name}\nDecisión: Rechazó la oferta de crédito voluntariamente."

    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_CLOSED_BY_USER},
        {"role": "user",   "content": context},
    ])

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_CLOSED_BY_USER",
            node_status="SUCCESS",
            engine_status="NOT_APPLICABLE",
        )

    return {
        "messages": [AIMessage(content=normalize_llm_response(flux_response.content))],
        "session":  {**session, "current_node": "LOAN_CLOSED_BY_USER"},
        "flow_result": {
            "status_code":  "CLOSED_BY_USER",
            "close_reason": "USER_REJECTED_OFFER",
            "product_name": "Crédito de Consumo",
            "closed_at":    datetime.now(timezone.utc).isoformat(),
        },
    }
```

---

**✅ CRITERIO PASS Paso 7** [TEST-UNIT con mocks]:

```python
# tests/unit/test_closing_nodes.py

from unittest.mock import patch, MagicMock
from app.graph.nodes.credit import (
    loan_completed_node,
    loan_rejected_policy_node,
    loan_security_block_node,
    loan_closed_by_user_node,
)

BASE = {
    "session": {"current_node": "PREV", "application_id": None},
    "preparation_data": {"nombre": "Javier Muñoz", "mail": "j@t.cl"},
    "evaluation_results": {"loan_engine": {
        "motivo_rechazo": None, "monto_aprobado": 5_000_000,
        "cuota_mensual": 250_000, "status_proceso": "PRE_APPROVED"
    }},
    "offer_data": {"loan": {}},
    "auth_control": {"otp_attempts": 3},
    "messages": [],
}

@patch("app.graph.nodes.credit._flux_generator")
def test_completed_escribe_flow_result_success(mock_gen):
    mock_gen.invoke.return_value = MagicMock(content="¡Felicitaciones!")
    result = loan_completed_node(BASE)
    assert result["flow_result"]["status_code"] == "SUCCESS"
    assert result["session"]["current_node"] == "LOAN_COMPLETED"

@patch("app.graph.nodes.credit._flux_generator")
def test_rejected_escribe_motivo_rechazo(mock_gen):
    mock_gen.invoke.return_value = MagicMock(content="Lo sentimos.")
    state = {**BASE, "evaluation_results": {"loan_engine": {"motivo_rechazo": "ERR_RENTA"}}}
    result = loan_rejected_policy_node(state)
    assert result["flow_result"]["status_code"] == "REJECTED"
    assert result["flow_result"]["close_reason"] == "ERR_RENTA"

@patch("app.graph.nodes.credit._flux_generator")
def test_security_block_setea_blocked_y_timestamp(mock_gen):
    mock_gen.invoke.return_value = MagicMock(content="Bloqueado por seguridad.")
    result = loan_security_block_node(BASE)
    assert result["auth_control"]["security_blocked"] == True
    assert result["auth_control"]["block_timestamp"] is not None
    assert result["flow_result"]["status_code"] == "SECURITY_BLOCKED"

@patch("app.graph.nodes.credit._flux_generator")
def test_closed_by_user_flow_result(mock_gen):
    mock_gen.invoke.return_value = MagicMock(content="Hasta luego.")
    result = loan_closed_by_user_node(BASE)
    assert result["flow_result"]["status_code"] == "CLOSED_BY_USER"
```

---

## PASO 8 — Test de Integración E2E y Checklist de Cierre

### Sub-paso 8.1 — Test E2E con mocks [TEST-UNIT]

```python
# tests/integration/test_e2e_loan_flow.py
"""
Test E2E del flujo completo de crédito usando mocks de LLM.
Valida que el grafo navega correctamente entre todos los nodos.

REQUIERE: LangGraph compilado pero con checkpointer en memoria (MemorySaver).
NO REQUIERE: Credenciales de Vertex AI ni Supabase.
"""

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from app.graph.workflow import build_graph


@pytest.fixture
def compiled_graph_mock():
    """Compila el grafo con checkpointer en memoria."""
    graph    = build_graph()
    memory   = MemorySaver()
    return graph.compile(checkpointer=memory)


def test_ruta_feliz_completa(compiled_graph_mock):
    """
    Simula el flujo completo desde loan_init hasta loan_completed
    con todos los nodos intermedios mockeados.
    El test valida que el grafo recorre el camino correcto sin errores.
    """
    # Esta prueba se implementa con los mocks apropiados tras completar
    # los sub-pasos anteriores. Aquí se documenta el esqueleto.
    pass  # TODO: implementar tras Sub-paso 7.3
```

### Sub-paso 8.2 — Checklist de Cierre de la Fase 2 Completa

```
HALLAZGOS RESUELTOS
[x] HALLAZGO #1: engine_result → evaluation_results["loan_engine"] corregido (Paso 0)
[x] HALLAZGO #2: Flags de transición documentados como efímeros
[x] HALLAZGO #3: OTP determinista, sin extracción del chat (Paso 5)
[x] HALLAZGO #4: loan_pre_approved_node implementado (Paso 4)

NODOS IMPLEMENTADOS
[ ] loan_pre_approved_node    (Paso 4)
[ ] loan_otp_validation_node  (Paso 5 — rediseñado como determinista)
[ ] loan_formalization_node   (Paso 6 — determinista)
[ ] loan_completed_node       (Paso 7.1)
[ ] loan_rejected_policy_node (Paso 7.2)
[ ] loan_security_block_node  (Paso 7.3)
[ ] loan_closed_by_user_node  (Paso 7.3)

GRAFO ACTUALIZADO
[ ] workflow.py: Todos los nodos registrados
[ ] edges.py: Todas las funciones de ruteo agregadas
[ ] Conexiones antiguas (stub → END) eliminadas

STUBS EN VIGOR (Swap pendiente para Fase 3)
[ ] app/modules/security.py    → generate_otp(), send_otp_email()
[ ] app/modules/pdf_factory.py → generate_loan_contract()

TESTS PASANDO
[ ] pytest tests/unit/test_risk_engine_node.py       → 2/2 PASS
[ ] pytest tests/unit/test_edges_credit.py           → 8/8 PASS
[ ] pytest tests/unit/test_pre_approved_node.py      → 2/2 PASS
[ ] pytest tests/unit/test_otp_node.py               → 4/4 PASS
[ ] pytest tests/unit/test_formalization_node.py     → 3/3 PASS
[ ] pytest tests/unit/test_closing_nodes.py          → 4/4 PASS

PRINCIPIOS DE ESTABILIZACIÓN APLICADOS
[ ] Todos los nodos de respuesta usan solo Llamada B
[ ] Ningún nodo post-motor hace extracción con Llamada A
[ ] OTP y Formalización son deterministas (sin LLM para decisiones legales)
[ ] Todos los flags de transición son reseteados en el nodo que los consume
[ ] Todos los returns son transaccionales (un solo return al final)
```

---

## APÉNDICE A: Tabla de Semáforos Completa

| Nodo (UPPER_CASE)               | `node_status` | `engine_status`  | `document_status` |
|---------------------------------|---------------|------------------|-------------------|
| `LOAN_INIT`                     | `SUCCESS`     | `PENDING`        | —                 |
| `LOAN_COLLECTING_PROFILE`       | `SUCCESS`     | `PENDING`        | —                 |
| `LOAN_COLLECTING_SIMULATION`    | `SUCCESS`     | `PENDING`        | —                 |
| `LOAN_RISK_ENGINE`              | `SUCCESS`     | `COMPLETED`      | —                 |
| `LOAN_PRE_APPROVED`             | `SUCCESS`     | `NOT_APPLICABLE` | —                 |
| `LOAN_OTP_VALIDATION` (éxito)   | `SUCCESS`     | `NOT_APPLICABLE` | —                 |
| `LOAN_FORMALIZATION`            | `SUCCESS`     | `NOT_APPLICABLE` | `GENERATED`       |
| `LOAN_COMPLETED`                | `SUCCESS`     | `NOT_APPLICABLE` | `GENERATED`       |
| `LOAN_REJECTED_POLICY`          | `SUCCESS`     | `COMPLETED`      | —                 |
| `LOAN_SECURITY_BLOCK`           | `FAILED`      | `NOT_APPLICABLE` | —                 |
| `LOAN_CLOSED_BY_USER`           | `SUCCESS`     | `NOT_APPLICABLE` | —                 |

---

## APÉNDICE B: Mapa de Inputs UI vs LLM (Síntesis de `ux-deterministic-map.md`)

| Nodo               | LLM hace                                      | UI captura                              |
|--------------------|-----------------------------------------------|-----------------------------------------|
| `collecting_profile` | Extrae renta, antigüedad, estudios (Llamada A+B) | Chat de texto libre                  |
| `collecting_simulation` | Extrae monto, plazo (Llamada A+B)          | Chat de texto libre                  |
| `pre_approved`     | Explica la oferta (solo Llamada B)            | Botón "Acepto" / "Rechazo"             |
| `otp_validation`   | Modera y responde dudas (solo Llamada B)      | Campo numérico de 6 dígitos            |
| `formalization`    | Explica el contrato (solo Llamada B)          | Botón "Acepto Contrato" / "Cancelar"   |
| `completed`        | Felicita y despide (solo Llamada B)           | —                                       |
| `rejected_policy`  | Comunica rechazo con empatía (solo Llamada B) | —                                       |
| `security_block`   | Informa el bloqueo (solo Llamada B)           | —                                       |

---

## APÉNDICE C: Mapa de Archivos Finales de la Fase 2

```
app/
├── graph/
│   ├── nodes/
│   │   ├── credit.py              ← MODIFICADO: Pasos 0, 4, 5, 6, 7
│   │   └── schemas/
│   │       └── loan_schemas.py    ← ESTABLE (v2.1 post-estabilización)
│   ├── state.py                   ← INMUTABLE
│   ├── workflow.py                ← MODIFICADO: Sub-paso 3.1
│   └── edges.py                   ← MODIFICADO: Sub-paso 3.2
├── infra/
│   ├── gemini_client.py           ← ESTABLE (v2.1 post-estabilización)
│   └── supabase.py                ← INMUTABLE
└── modules/
    ├── credit_eng.py              ← ESTABLE (Fase 2, Paso 1)
    ├── security.py                ← STUB (swap en Fase 3)
    └── pdf_factory.py             ← STUB (swap en Fase 3)

tests/
├── unit/
│   ├── test_risk_engine_node.py   ← NUEVO (Paso 0)
│   ├── test_edges_credit.py       ← NUEVO (Paso 3)
│   ├── test_pre_approved_node.py  ← NUEVO (Paso 4)
│   ├── test_otp_node.py           ← NUEVO (Paso 5)
│   ├── test_formalization_node.py ← NUEVO (Paso 6)
│   └── test_closing_nodes.py      ← NUEVO (Paso 7)
└── integration/
    └── test_e2e_loan_flow.py      ← NUEVO (Paso 8)
```

---

*Documento generado para Flux — Fase 2, Plan Actualizado v4.0*  
*Reemplaza los Pasos 3 y 4 del plan anterior (fase-2.md) en su totalidad.*
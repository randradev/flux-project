# Flux — Fase 2: Plan de Implementación v5.0
## Cableado Definitivo del Flujo de Crédito

**Versión:** 5.0 — Cableado Completo Post-Estabilización de Ruteo  
**Sustituye:** `fase2.md` v4.0 (Pasos 3–7) y `fix-routes.md` (referencias a stubs pendientes)  
**Estado del Proyecto al momento de este plan:** fix-routes completado; `loan_risk_engine` apunta a `END` (invariante no cerrado)  
**Archivos afectados:** `credit.py`, `edges.py`, `workflow.py`, `constants.py`, `modules/security.py`, `modules/pdf_factory.py`  
**Archivos inmutables:** `state.py`, `gemini_client.py`, `loan_schemas.py`, `supabase.py`

---

## I. RECONCILIACIÓN CON PLANES ANTERIORES

### 1.1 Qué queda obsoleto de `fase2.md` v4.0

| Sección | Estado | Razón |
|---|---|---|
| Hallazgo #1 (namespace mismatch) | ✅ **RESUELTO** | `credit.py` actual usa `evaluation_results.loan_engine` correctamente |
| Hallazgo #2 (flags undeclared) | ✅ **RESUELTO** | `state.py` declara `progress` y `just_completed_step` en `SessionData` |
| Hallazgo #3 (OTP desde chat) | ✅ **RESUELTO** | Directriz determinista vigente desde fix-routes |
| Hallazgo #4 (loan_pre_approved no existe) | ⚠️ **VIGENTE** | Nodo aún no implementado — objeto de este plan |
| Sub-paso 3.1 (registro de nodos en workflow) | ⚠️ **PARCIALMENTE VIGENTE** | workflow.py actual tiene `loan_risk_engine → END`; falta todo lo demás |
| Sub-paso 4.2 `loan_pre_approved_node` | ❌ **REEMPLAZADO** | La implementación de v4.0 no conoce la arquitectura de `just_completed_step` ni `_SUCCESS_MAP` |
| Sub-paso 5.3 OTP moderador | ❌ **REEMPLAZADO** | La lógica OTP se rediseña aquí bajo el invariante determinista completo |
| Tabla de semáforos | ✅ **VIGENTE** | Se extiende en este documento |

### 1.2 Qué queda obsoleto de `fix-routes.md`

| Item | Estado |
|---|---|
| Nota "loan_risk_engine no tiene respuesta, habilitar salto con precaución" | ✅ **OBSOLETO** — El invariante cierra esto |
| Stubs `loan_pre_approved_node` y `loan_rejected_policy_node` en v5.0 | ✅ **REEMPLAZADOS** — Implementación completa aquí |
| Checklist §VIII ítems `[INVARIANTE]` | ✅ **SE CIERRAN** en este plan |

### 1.3 Qué hereda este plan sin cambios

- Arquitectura de Doble Llamada (Extractor + Generador)
- Sistema `just_completed_step` + `progress` (escritura dual)
- Jerarquía P0-P4 de `route_after_welcome`
- `_RESUME_MAP`, `_SUCCESS_MAP`, `_VALID_DESTINATION_NODES` (se extienden, no se reescriben)
- Patrón de Contexto Aislado (`_build_X_context`) para Llamada B
- Interacción determinista: botones y campos UI para OTP/Formalización

---

## II. HALLAZGOS PROPIOS DE ESTE PLAN

### HALLAZGO A — `otp_verified` no existe en `AuthControl`

**Archivo:** `state.py` (inmutable)

`AuthControl` tiene `otp_generated`, `otp_user_input`, `otp_attempts` y `security_blocked`, pero no un campo `otp_verified` explícito. El backend que procesa el payload de la UI debe escribir el resultado en el State. Dado que `state.py` es inmutable, la verificación se deriva en el edge: `otp_user_input and otp_user_input == otp_generated`.

**Decisión:** La función `route_after_loan_otp_validation` en `edges.py` implementa esta derivación. El nodo `loan_otp_validation_node` no valida el código directamente; solo modera la conversación y lee el State que el backend actualizó.

---

### HALLAZGO B — `loan_risk_engine_node` no escribe `just_completed_step`

El motor de riesgo actual retorna `evaluation_results` y `session` pero no escribe `just_completed_step = CompletedStep.LOAN_RISK_EVALUATED`. Sin este flag, `route_after_loan_risk_engine` igual funciona (lee `status_proceso` del motor directamente), pero el `_SUCCESS_MAP` inter-turno de P1 no puede recuperar una sesión bloqueada en `LOAN_RISK_ENGINE`.

**Decisión:** Agregar escritura dual en `loan_risk_engine_node` (caso `PRE_APPROVED`) y extender `_SUCCESS_MAP`. Para `REJECTED` y `ERROR`, no tiene sentido la recuperación —son estados terminales— así que no se agrega progreso para ellos.

---

### HALLAZGO C — `CompletedStep` en `constants.py` no cubre los nuevos hitos

Los valores actuales (`LOAN_PROFILE`, `LOAN_SIMULATION`, `ACCOUNT_PROFILE`, `DAP_DATA`) no incluyen `LOAN_RISK_EVALUATED`. Se necesita para que P1 pueda rescatar sesiones que quedaron en `LOAN_RISK_ENGINE`.

---

### HALLAZGO D — `loan_service_error_node` no está registrado en ningún archivo

`credito-datos.md` §V refiere a `SERVICE_ERROR_HANDLER` como nodo transversal. Dado que es Fase 3, se implementa como stub terminal en `credit.py` según el lineamiento #6 del encargo.

---

## III. ARQUITECTURA DEL FLUJO COMPLETO

### 3.1 Mapa de flujo definitivo

```
welcome (silencioso salvo sesión nueva)
  ↓ route_after_welcome [P0-P4]
loan_init → (edge fijo) → loan_collecting_profile
  ↓ route_after_loan_collecting_profile
  ├── [perfil incompleto] ──→ END (esperar usuario)
  └── [perfil completo]   ──→ loan_collecting_simulation (intra-turno)
        ↓ route_after_loan_collecting_sim
        ├── [sim incompleta] ──→ END (esperar usuario)
        └── [sim completa]   ──→ loan_risk_engine (intra-turno)
              ↓ route_after_loan_risk_engine  [INVARIANTE: nunca END]
              ├── PRE_APPROVED ──→ loan_pre_approved
              │     ↓ route_after_loan_pre_approved
              │     ├── None      ──→ loan_pre_approved (loop: esperar botón)
              │     ├── ACCEPTED  ──→ loan_otp_validation
              │     │     ↓ route_after_loan_otp_validation
              │     │     ├── pendiente   ──→ loan_otp_validation (loop)
              │     │     ├── verified    ──→ loan_formalization
              │     │     │     ↓ route_after_loan_formalization
              │     │     │     ├── pendiente        ──→ loan_formalization (loop)
              │     │     │     ├── SIGNED_AND_STAMPED ──→ loan_completed → END
              │     │     │     └── GENERATION_FAILED  ──→ loan_service_error → END
              │     │     └── blocked     ──→ loan_security_block → END
              │     └── REJECTED  ──→ loan_closed_by_user → END
              ├── REJECTED ──→ loan_rejected_policy → END
              └── ERROR    ──→ loan_service_error → END
```

### 3.2 Principios de diseño de los nuevos nodos

| Nodo | Tipo | Llamada LLM | Input decisional |
|---|---|---|---|
| `loan_pre_approved` | Moderador + loop | Solo B | Botón UI → `offer_data.loan.pre_approval_status` |
| `loan_rejected_policy` | Terminal | Solo B | `motivo_rechazo` del motor |
| `loan_otp_validation` | Moderador + loop | Solo B | Campo UI → `auth_control.otp_user_input` |
| `loan_formalization` | Moderador + generador PDF | Solo B | Botón UI → `offer_data.loan.contract_status` |
| `loan_completed` | Terminal | Solo B | — |
| `loan_security_block` | Terminal | Solo B | — |
| `loan_closed_by_user` | Terminal | Solo B | — |
| `loan_service_error` | Terminal | Hardcoded (stub) | — |

---

## IV. CÓDIGO — PASO 1: `constants.py`

Agregar un valor al enum `CompletedStep`. **No modificar nada más.**

```python
# app/graph/constants.py
# v5.1 — CAMBIO MÍNIMO: más líneas en CompletedStep para nodos post-recolección

class CompletedStep:
    """
    Valores válidos para session["just_completed_step"].
    Flag volátil: vive exactamente un turno.
    Se setea al completar un paso; se consume en el nodo receptor o en P1.
    """
    LOAN_PROFILE        = "LOAN_PROFILE"
    LOAN_SIMULATION     = "LOAN_SIMULATION"
    LOAN_RISK_EVALUATED = "LOAN_RISK_EVALUATED"  # Conservado — compatibilidad regresiva
    LOAN_ENGINE         = "LOAN_ENGINE"          # ← NUEVO v5.1 — motor de riesgo aprobado
    LOAN_PRE_APPROVED   = "LOAN_PRE_APPROVED"    # ← NUEVO v5.1 — tarjeta de transparencia mostrada
    LOAN_OTP            = "LOAN_OTP"             # ← NUEVO v5.1 — OTP validado exitosamente
    LOAN_FORMALIZATION  = "LOAN_FORMALIZATION"   # ← NUEVO v5.1 — contrato PDF generado
    ACCOUNT_PROFILE     = "ACCOUNT_PROFILE"
    DAP_DATA            = "DAP_DATA"


class ProductPrefix:
    """
    Prefijos de producto para inferir el producto desde current_node.
    Usados en route_after_welcome para detectar cambio de intención (P0).
    """
    LOAN    = "LOAN"
    ACCOUNT = "ACCOUNT"
    DAP     = "DAP"

    NODE_TO_PRODUCT: dict[str, str] = {
        "LOAN":    LOAN,
        "ACCOUNT": ACCOUNT,
        "DAP":     DAP,
    }

    @classmethod
    def from_node(cls, current_node: str) -> str | None:
        """Infiere el producto desde el current_node. Ej: 'LOAN_COLLECTING_PROFILE' → 'LOAN'."""
        for prefix, product in cls.NODE_TO_PRODUCT.items():
            if current_node.startswith(prefix):
                return product
        return None
```

---

## V. CÓDIGO — PASO 2: `edges.py` (extensión)

Los cambios son **aditivos**: se extienden los mapas existentes y se agregan las nuevas funciones de edge al final del archivo. La jerarquía P0-P4 y las funciones existentes no se tocan.

### 5.1 Extensión de mapas

```python
# ── CAMBIOS EN MAPAS EXISTENTES ─────────────────────────────────────────────
# Agregar estas entradas en sus respectivos diccionarios

# En _RESUME_MAP — agregar las claves nuevas:
_RESUME_MAP = {
    # ... entradas existentes sin cambio ...
    "LOAN_INIT":                   "loan_init",
    "LOAN_COLLECTING_PROFILE":     "loan_collecting_profile",
    "LOAN_COLLECTING_SIMULATION":  "loan_collecting_simulation",
    "LOAN_RISK_ENGINE":            "loan_risk_engine",        # ← NUEVO
    "LOAN_PRE_APPROVED":           "loan_pre_approved",       # ← NUEVO
    "LOAN_OTP_VALIDATION":         "loan_otp_validation",     # ← NUEVO
    "LOAN_FORMALIZATION":          "loan_formalization",       # ← NUEVO
    "ACCOUNT_INIT":                "account_init",
    "ACCOUNT_COLLECTING_PROFILE":  "account_collecting_profile",
    "DAP_INIT":                    "dap_init",
    "DAP_COLLECT_DATA":            "dap_collect_data",
}

# En _SUCCESS_MAP["LOAN"] — agregar hitos post-recolección:
_SUCCESS_MAP = {
    "LOAN": {
        CompletedStep.LOAN_PROFILE:       "loan_collecting_simulation",
        CompletedStep.LOAN_SIMULATION:    "loan_risk_engine",
        CompletedStep.LOAN_RISK_EVALUATED: "loan_pre_approved",  # v5.0 — conservado
        CompletedStep.LOAN_ENGINE:        "loan_pre_approved",   # ← NUEVO v5.1
        CompletedStep.LOAN_PRE_APPROVED:  "loan_pre_approved",   # ← NUEVO v5.1
        CompletedStep.LOAN_OTP:           "loan_formalization",  # ← NUEVO v5.1
        CompletedStep.LOAN_FORMALIZATION: "loan_formalization",  # ← NUEVO v5.1
    },
    "ACCOUNT": {
        CompletedStep.ACCOUNT_PROFILE: "account_evaluation_engine",
    },
    "DAP": {
        CompletedStep.DAP_DATA: "dap_investment_engine",
    },
}

# En _VALID_DESTINATION_NODES — agregar los nuevos nodos:
_VALID_DESTINATION_NODES: frozenset[str] = frozenset({
    "loan_collecting_profile",
    "loan_collecting_simulation",
    "loan_risk_engine",
    "loan_pre_approved",          # ← NUEVO
    "loan_otp_validation",        # ← NUEVO
    "loan_formalization",         # ← NUEVO
    "loan_completed",             # ← NUEVO
    "loan_rejected_policy",       # ← NUEVO
    "loan_security_block",        # ← NUEVO
    "loan_closed_by_user",        # ← NUEVO
    "loan_service_error",         # ← NUEVO
    "account_collecting_profile",
    "account_evaluation_engine",
    "dap_collect_data",
    "dap_investment_engine",
    "intent_router",
    "general_response",
})
```

### 5.2 Nuevas funciones de edge

Agregar **al final** de `edges.py`, después de `route_after_account_collecting_profile`.

```python
# ──────────────────────────────────────────────────────────────────────────────
# EDGES DEL FLUJO DE CRÉDITO — NODOS POST-MOTOR
# ──────────────────────────────────────────────────────────────────────────────

def route_after_loan_risk_engine(state: FluxState) -> str:
    """
    Decisión de arista post-LOAN_RISK_ENGINE.

    INVARIANTE: Esta función NUNCA retorna END.
    Todos los caminos terminan en un nodo generador de respuesta.

    Lee: evaluation_results["loan_engine"]["status_proceso"]
    Retorna: "loan_pre_approved" | "loan_rejected_policy" | "loan_service_error"
    """
    engine = state.get("evaluation_results", {}).get("loan_engine", {})
    status = engine.get("status_proceso", "ERROR")

    if status == "PRE_APPROVED":
        return "loan_pre_approved"
    elif status == "REJECTED":
        return "loan_rejected_policy"
    else:
        # ERROR o cualquier valor inesperado → stub de error de servicio
        return "loan_service_error"


def route_after_loan_pre_approved(state: FluxState) -> str:
    """
    Decisión de arista post-LOAN_PRE_APPROVED.

    El nodo loan_pre_approved genera la Tarjeta de Transparencia y espera
    la decisión del usuario mediante botones en la UI.
    El frontend actualiza offer_data["loan"]["pre_approval_status"].

    Estados:
      None / ausente  → loop (tarjeta mostrada, aún sin decisión)
      "ACCEPTED"      → avanzar a OTP
      "REJECTED"      → cierre voluntario

    Lee: offer_data["loan"]["pre_approval_status"]
    """
    status = state.get("offer_data", {}).get("loan", {}).get("pre_approval_status")

    if status == "ACCEPTED":
        return "loan_otp_validation"
    elif status == "REJECTED":
        return "loan_closed_by_user"
    else:
        return "loan_pre_approved"   # Loop: tarjeta mostrada, esperando botón


def route_after_loan_otp_validation(state: FluxState) -> str:
    """
    Decisión de arista post-LOAN_OTP_VALIDATION.

    La validación OTP es determinista: el backend compara el código
    ingresado en la UI con el generado, y escribe el resultado en auth_control.

    Derivación de otp_verified (no existe en AuthControl):
      otp_verified = otp_user_input != "" and otp_user_input == otp_generated

    Prioridad: security_blocked > verified > loop

    Lee: auth_control["security_blocked"], ["otp_user_input"], ["otp_generated"]
    """
    auth = state.get("auth_control", {})

    if auth.get("security_blocked"):
        return "loan_security_block"

    otp_generated  = auth.get("otp_generated", "")
    otp_user_input = auth.get("otp_user_input", "")
    otp_verified   = bool(otp_user_input) and otp_user_input == otp_generated

    if otp_verified:
        return "loan_formalization"

    return "loan_otp_validation"   # Loop: código no validado o aún no ingresado


def route_after_loan_formalization(state: FluxState) -> str:
    """
    Decisión de arista post-LOAN_FORMALIZATION.

    El nodo genera el contrato PDF (stub en Fase 2) y espera la firma
    mediante el botón "Acepto Contrato" de la UI.
    El frontend escribe offer_data["loan"]["contract_status"].

    Estados:
      None / ausente       → loop (contrato generado, esperando firma)
      "SIGNED_AND_STAMPED" → flujo completado
      "GENERATION_FAILED"  → error de servicio

    Lee: offer_data["loan"]["contract_status"]
    """
    contract_status = (
        state.get("offer_data", {}).get("loan", {}).get("contract_status")
    )

    if contract_status == "SIGNED_AND_STAMPED":
        return "loan_completed"
    elif contract_status == "GENERATION_FAILED":
        return "loan_service_error"
    else:
        return "loan_formalization"   # Loop: esperando firma del frontend
```

---

## VI. CÓDIGO — PASO 3: `credit.py` (extensión)

### 6.1 Actualizar `loan_risk_engine_node` — escritura dual

Reemplazar el bloque `return` final del nodo con la versión extendida que escribe `just_completed_step` y `progress` cuando el motor aprueba.

```python
# En loan_risk_engine_node, reemplazar el return final:

    # 3. ------ PERSISTENCIA Y SEMÁFOROS ------
    application_id = session.get("application_id")
    if application_id:
        engine_status = "SUCCESS" if engine_result.get("status_proceso") != "ERROR" else "FAILED"
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_RISK_ENGINE",
            node_status="SUCCESS",
            engine_status=engine_status,
        )

    # 4. ------ ESCRITURA DUAL (solo si aprobado) ------
    # La flag just_completed_step dispara el salto intra-turno a loan_pre_approved.
    # Para REJECTED y ERROR no aplica: son caminos terminales.
    updated_session = {**session, "current_node": "LOAN_RISK_ENGINE"}

    if engine_result.get("status_proceso") == "PRE_APPROVED":
        current_progress = session.get("progress", {})
        loan_progress    = current_progress.get("loan", {})
        updated_session.update({
            "progress": {
                **current_progress,
                "loan": {**loan_progress, "risk_evaluated": True},
            },
            "just_completed_step": CompletedStep.LOAN_RISK_EVALUATED,
        })

    return {
        "evaluation_results": {
            "loan_engine": engine_result,
        },
        "session": updated_session,
    }
```

---

### 6.2 Prompts de los nuevos nodos

```python
# ── PROMPTS DE NODOS POST-MOTOR ──────────────────────────────────────────────
# Todos son Solo Llamada B: no extraen datos, solo generan respuesta.

SYSTEM_PROMPT_PRE_APPROVED = """
Eres Flux, el genio amigable de las finanzas en Chile.

TAREA: Presentar la oferta pre-aprobada al usuario de forma entusiasta y transparente.

TONO: Entusiasta pero honesto. Celebras el resultado sin exagerar; el usuario
debe sentir que tomará una decisión informada, no que lo están presionando.

INSTRUCCIONES:
1. Felicita brevemente por la pre-aprobación.
2. Indica que la Tarjeta de Transparencia aparece en pantalla con todos los detalles.
3. Invita a revisarla con calma y a usar los botones "Aceptar" o "Rechazar".

RESTRICCIONES:
- NO repitas todos los números del crédito en el chat (ya están en la Tarjeta).
- NO uses urgencia artificial ("¡Solo por hoy!", "¡Última oportunidad!").
- Máximo 3 oraciones.
- Si el usuario escribe en el chat en lugar de usar los botones, responde con
  empatía y recuérdale que la decisión va por los botones de la interfaz.
"""

SYSTEM_PROMPT_OTP_MODERATOR = """
Eres Flux, el genio amigable de las finanzas en Chile.

TAREA: Guiar al usuario durante la validación OTP (autenticación por código).

TONO: Seguro y tranquilizador. El proceso de seguridad es normal y protege al usuario.

INSTRUCCIONES SEGÚN EL ESTADO QUE RECIBES:
- ENVIADO    : Explica que se envió un código de 6 dígitos al correo y que debe
               ingresarlo en el campo que aparece en la pantalla (no en el chat).
- FALLO      : Informa del error de forma empática, indica los intentos restantes
               y recuerda que el código va en el campo de la interfaz.
- PREGUNTA   : Responde la duda y cierra recordando dónde ingresar el código.

RESTRICCIONES ABSOLUTAS:
- NUNCA extraigas el código OTP de un mensaje de chat.
- NUNCA valides ni invalides el código tú mismo.
- NUNCA digas qué código fue ingresado ni el generado.
- Máximo 2 oraciones.
"""

SYSTEM_PROMPT_FORMALIZATION = """
Eres Flux, el genio amigable de las finanzas en Chile.

TAREA: Explicar el contrato de crédito y guiar al usuario hacia la firma digital.

TONO: Directo y asistencial. Ayudas al usuario a entender qué firmará, sin presión.

INSTRUCCIONES:
1. Explica que el contrato con todos los términos está disponible para revisar.
2. Menciona que la firma es legalmente vinculante.
3. Indica que el botón "Acepto Contrato" es el único mecanismo de firma válido.
4. Si el usuario tiene dudas sobre términos (tasa, CAE, plazo), explícalos con claridad.

RESTRICCIONES ABSOLUTAS:
- NUNCA interpretes frases como "me parece bien", "dale" o "sí" como una firma legal.
- NUNCA digas que el contrato se firmó si no llegó el payload del botón.
- Máximo 3 oraciones.
"""

SYSTEM_PROMPT_COMPLETED = """
Eres Flux, el genio amigable de las finanzas en Chile.

TAREA: Felicitar al usuario por completar exitosamente su Crédito de Consumo.

TONO: Celebratorio y cálido. Es un momento especial; el usuario logró algo concreto.

INSTRUCCIONES:
1. Felicita con genuina emoción (sin ser exagerado).
2. Confirma que recibirá el contrato en su correo y puede descargarlo desde la app.
3. Despídete con calidez y menciona que Flux siempre estará disponible.

RESTRICCIONES: Máximo 3 oraciones. No des instrucciones técnicas.
"""

SYSTEM_PROMPT_REJECTED_POLICY = """
Eres Flux, el genio amigable de las finanzas en Chile.

TAREA: Comunicar empáticamente el rechazo de la solicitud de crédito por política.

TONO: Empático, sin condescendencia. No es un fracaso; es información para el futuro.

INSTRUCCIONES:
1. Comunica el rechazo con claridad y sin rodeos.
2. Explica el motivo en lenguaje humano (usa el motivo del contexto).
3. Ofrece una perspectiva constructiva: qué podría mejorar la situación en el futuro.

RESTRICCIONES: Máximo 3 oraciones. No uses tecnicismos regulatorios.
"""

SYSTEM_PROMPT_SECURITY_BLOCK = """
Eres Flux, el genio amigable de las finanzas en Chile.

TAREA: Informar al usuario que su solicitud fue bloqueada por seguridad.

TONO: Serio pero empático. No es un castigo; es protección ante intentos fallidos.

INSTRUCCIONES:
1. Explica el bloqueo con claridad (3 intentos OTP fallidos).
2. Indica que puede intentarlo nuevamente en 24 horas.
3. Sugiere revisar su correo o contactar al soporte si tuvo un problema técnico.

RESTRICCIONES: Máximo 2 oraciones. No acuses al usuario de intento de fraude.
"""

SYSTEM_PROMPT_CLOSED_BY_USER = """
Eres Flux, el genio amigable de las finanzas en Chile.

TAREA: Despedirte cordialmente del usuario que decidió no continuar.

TONO: Respetuoso y sin presión. La decisión del usuario es completamente válida.

INSTRUCCIONES:
1. Respeta la decisión sin cuestionarla.
2. Agradece el interés y menciona que puede volver cuando quiera.

RESTRICCIONES: Máximo 2 oraciones. NUNCA preguntes por qué rechazó.
"""
```

---

### 6.3 Nodo `loan_pre_approved_node`

```python
def loan_pre_approved_node(state: FluxState) -> dict:
    """
    Nodo LOAN_PRE_APPROVED: presenta la Tarjeta de Transparencia y espera decisión.

    ID LangGraph : loan_pre_approved
    current_node : LOAN_PRE_APPROVED

    ARQUITECTURA: Solo Llamada B. No extrae datos del chat.

    PRIMERA EJECUCIÓN (pre_approval_status vacío):
      - Construye el contexto con los datos del motor.
      - Genera mensaje de presentación (Llamada B).
      - Escribe display_data en offer_data["loan"] para que el frontend
        renderice la Tarjeta de Transparencia.
      - Resetea just_completed_step.

    EJECUCIONES EN LOOP (botón aún no presionado):
      - Si el usuario escribe en el chat, genera respuesta empática
        recordando el uso de los botones.
      - No modifica offer_data ni collecting_data.

    TRANSICIÓN: La edge route_after_loan_pre_approved lee pre_approval_status
      y redirige. Este nodo nunca setea pre_approval_status; eso lo hace el frontend.
    """
    from datetime import datetime, timezone
    from langchain_core.messages import SystemMessage

    session  = state.get("session", {})
    prep     = state.get("preparation_data", {})
    engine   = state.get("evaluation_results", {}).get("loan_engine", {})
    offer    = state.get("offer_data", {}).get("loan", {})
    messages = state.get("messages", [])

    first_name     = (prep.get("nombre", "") or "").split()[0] or "amig@"
    application_id = session.get("application_id")

    # Derivar si ya se mostró la tarjeta (no es primera ejecución)
    tarjeta_ya_mostrada = bool(offer.get("display_data"))

    # ── Construir contexto para Llamada B ──────────────────────
    last_user_msg = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )

    cae_pct = round(engine.get("cae", 0) * 100, 2)
    context = f"""
CONTEXTO PARA TU RESPUESTA:
Usuario: {first_name}
Estado: PRE-APROBADO ✅
{"Esta es la PRIMERA vez que el usuario ve la oferta." if not tarjeta_ya_mostrada else "El usuario ya vio la Tarjeta. Está esperando que presione un botón."}

Datos de la oferta (ya están en la Tarjeta — NO los repitas todos):
  - Monto aprobado: ${engine.get('monto_aprobado', 0):,} CLP
  - Cuota mensual : ${engine.get('cuota_mensual', 0):,} CLP
  - Nivel riesgo  : {engine.get('nivel_riesgo', '')}
  - CAE           : {cae_pct}%

Último mensaje del usuario (si escribió en el chat): "{last_user_msg}"

INSTRUCCIÓN:
{"Preséntale la oferta y recuérdale los botones Aceptar/Rechazar." if not tarjeta_ya_mostrada else "El usuario escribió en el chat. Responde con empatía y recuérdale que la decisión va por los botones."}
"""

    flux_response = _flux_generator.invoke([
        SystemMessage(content=SYSTEM_PROMPT_PRE_APPROVED),
        HumanMessage(content=context),
    ])
    clean_content = normalize_llm_response(flux_response.content)

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_PRE_APPROVED",
            node_status="SUCCESS",
            engine_status="NOT_APPLICABLE",
        )

    # ── Construir display_data para el Frontend ──────────────────
    # Solo se escribe en la primera ejecución para no sobreescribir la
    # decisión del usuario si el loop se re-ejecuta.
    output_offer = dict(state.get("offer_data", {}))
    if not tarjeta_ya_mostrada:
        output_offer["loan"] = {
            **offer,
            "display_data": {
                "monto_aprobado":       engine.get("monto_aprobado"),
                "plazo_aprobado":       engine.get("plazo_aprobado"),
                "cuota_mensual":        engine.get("cuota_mensual"),
                "tasa_interes_mensual": engine.get("tasa_interes_mensual"),
                "cae":                  engine.get("cae"),
                "ctc":                  engine.get("ctc"),
                "total_intereses":      engine.get("total_intereses"),
                "nivel_riesgo":         engine.get("nivel_riesgo"),
            },
        }

    return {
        "messages":   [AIMessage(content=clean_content)],
        "offer_data": output_offer,
        "session": {
            **session,
            "current_node":        "LOAN_PRE_APPROVED",
            "just_completed_step": None,   # ← Consumir y limpiar el flag del motor
        },
    }
```

---

### 6.4 Nodo `loan_rejected_policy_node`

```python
def loan_rejected_policy_node(state: FluxState) -> dict:
    """
    Nodo LOAN_REJECTED_POLICY: cierre por incumplimiento de política financiera.

    ID LangGraph : loan_rejected_policy
    current_node : LOAN_REJECTED_POLICY
    Terminal     : sí → END

    ARQUITECTURA: Solo Llamada B. Lee motivo_rechazo del motor y genera mensaje empático.
    """
    from datetime import datetime, timezone
    from langchain_core.messages import SystemMessage

    session   = state.get("session", {})
    prep      = state.get("preparation_data", {})
    engine    = state.get("evaluation_results", {}).get("loan_engine", {})

    first_name     = (prep.get("nombre", "") or "").split()[0] or "amig@"
    motivo         = engine.get("motivo_rechazo", "ERR_DESCONOCIDO")
    application_id = session.get("application_id")

    MOTIVO_DESCRIPCION = {
        "ERR_EDAD":           "no cumples la edad mínima de 18 años",
        "ERR_RENTA":          "la renta declarada no alcanza el mínimo requerido ($500.000)",
        "ERR_ANTIGUEDAD":     "llevas menos de 6 meses en tu trabajo actual",
        "ERR_CAPACIDAD_PAGO": "la cuota mensual del crédito supera el 30% de tu renta",
        "ERR_SCORING":        "el puntaje de evaluación no alcanzó el mínimo requerido",
    }
    descripcion = MOTIVO_DESCRIPCION.get(motivo, "no se cumplieron los requisitos mínimos")

    context = f"""
CONTEXTO:
Usuario: {first_name}
Motivo del rechazo: {motivo}
Descripción human-friendly: {descripcion}

INSTRUCCIÓN: Comunica el rechazo con empatía, usando la descripción anterior en lenguaje natural.
"""

    flux_response = _flux_generator.invoke([
        SystemMessage(content=SYSTEM_PROMPT_REJECTED_POLICY),
        HumanMessage(content=context),
    ])
    clean_content = normalize_llm_response(flux_response.content)
    if not clean_content:
        clean_content = f"Lo sentimos, {first_name}. En esta oportunidad no podemos aprobar tu solicitud ({descripcion}). Te animamos a volver en el futuro."

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_REJECTED_POLICY",
            node_status="SUCCESS",
            engine_status="COMPLETED",
        )

    return {
        "messages": [AIMessage(content=clean_content)],
        "session":  {**session, "current_node": "LOAN_REJECTED_POLICY"},
        "flow_result": {
            "status_code":  "REJECTED",
            "close_reason": motivo,
            "product_name": "Crédito de Consumo",
            "closed_at":    __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        },
        "offer_data": {
            **state.get("offer_data", {}),
            "loan": {
                **state.get("offer_data", {}).get("loan", {}),
                "display_data": {"reason": motivo},
            },
        },
    }
```

---

### 6.5 Nodo `loan_otp_validation_node`

```python
def loan_otp_validation_node(state: FluxState) -> dict:
    """
    Nodo LOAN_OTP_VALIDATION: moderador determinista de la autenticación OTP.

    ID LangGraph : loan_otp_validation
    current_node : LOAN_OTP_VALIDATION

    ARQUITECTURA:
      - Solo Llamada B (moderación conversacional).
      - NUNCA extrae el código OTP del chat.
      - La validación la realiza el backend al recibir el payload del frontend.
      - El resultado (otp_user_input, otp_attempts, security_blocked)
        llega ya procesado en auth_control antes de que el grafo se re-ejecute.

    ESTADOS:
      1. INIT    : otp_generated vacío → generar, enviar, emitir mensaje de espera.
      2. FALLO   : otp_user_input presente pero distinto a otp_generated → mensaje de error.
      3. ÉXITO   : otp_user_input == otp_generated → avance silencioso (edge redirige).
      4. CHAT    : usuario escribió algo → respuesta empática recordando el campo UI.
    """
    from app.modules.security import generate_otp, send_otp_email
    from langchain_core.messages import SystemMessage

    session        = state.get("session", {})
    auth           = state.get("auth_control", {})
    prep           = state.get("preparation_data", {})
    messages       = state.get("messages", [])

    first_name     = (prep.get("nombre", "") or "").split()[0] or "amig@"
    mail           = prep.get("mail", "")
    otp_generated  = auth.get("otp_generated", "")
    otp_user_input = auth.get("otp_user_input", "")
    otp_attempts   = auth.get("otp_attempts", 0)
    security_blocked = auth.get("security_blocked", False)
    application_id = session.get("application_id")

    # Guardrail: estado terminal ya gestionado por la edge
    if security_blocked:
        return {"session": {**session, "current_node": "LOAN_OTP_VALIDATION"}}

    # ── ESTADO 3: ÉXITO — Avance silencioso ──────────────────────
    otp_verified = bool(otp_user_input) and otp_user_input == otp_generated
    if otp_verified:
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="LOAN_OTP_VALIDATION",
                node_status="SUCCESS",
                engine_status="NOT_APPLICABLE",
            )
        return {"session": {**session, "current_node": "LOAN_OTP_VALIDATION"}}

    # ── ESTADO 1: INIT — Primera ejecución ──────────────────────
    updated_auth = dict(auth)
    if not otp_generated:
        new_otp     = generate_otp()
        send_otp_email(mail, new_otp)
        updated_auth.update({
            "otp_generated": new_otp,
            "otp_attempts":  0,
        })
        otp_estado = "ENVIADO"
    else:
        # ── ESTADO 2: FALLO — Código incorrecto ─────────────────
        otp_estado = "FALLO" if otp_user_input else "ESPERA"

    # ── ESTADO 4: CHAT — Usuario escribió algo ──────────────────
    last_user_msg = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )
    intencion_otp = "DUDA" if last_user_msg.strip() and otp_generado_ok := bool(otp_generated) else "ESPERA"

    remaining = max(0, 3 - updated_auth.get("otp_attempts", 0))

    context = f"""
CONTEXTO PARA TU RESPUESTA:
Usuario: {first_name}
Estado OTP: {otp_estado}
Intentos fallidos: {updated_auth.get('otp_attempts', 0)}
Intentos restantes: {remaining}
Correo destino: {mail}
Último mensaje del usuario en el chat: "{last_user_msg}"

INSTRUCCIÓN: Genera la respuesta del moderador según el estado.
"""

    flux_response = _flux_generator.invoke([
        SystemMessage(content=SYSTEM_PROMPT_OTP_MODERATOR),
        HumanMessage(content=context),
    ])
    clean_content = normalize_llm_response(flux_response.content)
    if not clean_content:
        clean_content = f"Ingresa el código de 6 dígitos que enviamos a {mail} en el campo de la pantalla, {first_name}."

    return {
        "messages":    [AIMessage(content=clean_content)],
        "auth_control": updated_auth,
        "session":     {**session, "current_node": "LOAN_OTP_VALIDATION"},
    }
```

---

### 6.6 Nodo `loan_formalization_node`

```python
def loan_formalization_node(state: FluxState) -> dict:
    """
    Nodo LOAN_FORMALIZATION: generación de contrato PDF y espera de firma digital.

    ID LangGraph : loan_formalization
    current_node : LOAN_FORMALIZATION

    ARQUITECTURA:
      - Solo Llamada B (moderación y explicación del contrato).
      - NUNCA interpreta texto del chat como firma legal.
      - Genera el PDF con pdf_factory en la primera ejecución.
      - El frontend escribe contract_status = "SIGNED_AND_STAMPED" al recibir
        el payload del botón "Acepto Contrato".
      - La edge route_after_loan_formalization detecta ese status y avanza.
    """
    from app.modules.pdf_factory import generate_loan_contract
    from datetime import datetime, timezone
    from langchain_core.messages import SystemMessage

    session  = state.get("session", {})
    prep     = state.get("preparation_data", {})
    engine   = state.get("evaluation_results", {}).get("loan_engine", {})
    offer    = state.get("offer_data", {}).get("loan", {})
    messages = state.get("messages", [])

    first_name     = (prep.get("nombre", "") or "").split()[0] or "amig@"
    application_id = session.get("application_id")
    contract_path  = offer.get("file_contrato_path")

    output_offer = dict(state.get("offer_data", {}))
    output_loan  = dict(offer)

    # ── PRIMERA EJECUCIÓN: Generar el contrato ──────────────────
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
            "timestamp_acceptance": offer.get("timestamp_acceptance",
                                              datetime.now(timezone.utc).isoformat()),
        }
        file_path, sha256_hash = generate_loan_contract(contract_data)
        output_loan["file_contrato_path"] = file_path
        output_loan["hash_sha256"]        = sha256_hash

        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="LOAN_FORMALIZATION",
                node_status="SUCCESS",
                engine_status="NOT_APPLICABLE",
                document_status="GENERATED",
            )

    output_offer["loan"] = output_loan

    # ── Llamada B: Explicación del contrato ─────────────────────
    last_user_msg = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )

    context = f"""
CONTEXTO PARA TU RESPUESTA:
Usuario: {first_name}
Estado del contrato: {"Recién generado, esperando firma." if not contract_path else "Generado. Esperando firma del usuario."}
Último mensaje del usuario: "{last_user_msg}"

Datos clave para responder dudas:
  - Monto  : ${engine.get('monto_aprobado', 0):,} CLP
  - Plazo  : {engine.get('plazo_aprobado', 0)} cuotas
  - Cuota  : ${engine.get('cuota_mensual', 0):,} CLP
  - CAE    : {round(engine.get('cae', 0) * 100, 2)}%

INSTRUCCIÓN:
{"Explica que el contrato está listo y guía al usuario hacia el botón 'Acepto Contrato'." if not contract_path else "El usuario puede tener dudas. Respóndelas y recuérdale el botón de firma."}
"""

    flux_response = _flux_generator.invoke([
        SystemMessage(content=SYSTEM_PROMPT_FORMALIZATION),
        HumanMessage(content=context),
    ])
    clean_content = normalize_llm_response(flux_response.content)
    if not clean_content:
        clean_content = f"Tu contrato está listo, {first_name}. Revísalo en pantalla y usa el botón 'Acepto Contrato' cuando estés de acuerdo."

    return {
        "messages":  [AIMessage(content=clean_content)],
        "offer_data": output_offer,
        "session":   {**session, "current_node": "LOAN_FORMALIZATION"},
    }
```

---

### 6.7 Nodo `loan_completed_node`

```python
def loan_completed_node(state: FluxState) -> dict:
    """
    Nodo LOAN_COMPLETED: cierre exitoso del flujo de crédito.

    ID LangGraph : loan_completed
    current_node : LOAN_COMPLETED
    Terminal     : sí → END
    """
    from datetime import datetime, timezone
    from langchain_core.messages import SystemMessage

    session  = state.get("session", {})
    prep     = state.get("preparation_data", {})
    engine   = state.get("evaluation_results", {}).get("loan_engine", {})
    offer    = state.get("offer_data", {}).get("loan", {})

    first_name     = (prep.get("nombre", "") or "").split()[0] or "amig@"
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
        SystemMessage(content=SYSTEM_PROMPT_COMPLETED),
        HumanMessage(content=context),
    ])
    clean_content = normalize_llm_response(flux_response.content)
    if not clean_content:
        clean_content = f"¡Felicitaciones, {first_name}! Tu crédito está aprobado y formalizado. Recibirás el contrato en {mail}. ¡Fue un placer!"

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_COMPLETED",
            node_status="SUCCESS",
            engine_status="NOT_APPLICABLE",
            document_status="GENERATED",
        )

    return {
        "messages": [AIMessage(content=clean_content)],
        "session":  {**session, "current_node": "LOAN_COMPLETED"},
        "flow_result": {
            "status_code":  "SUCCESS",
            "close_reason": None,
            "product_name": "Crédito de Consumo",
            "closed_at":    datetime.now(timezone.utc).isoformat(),
        },
        "offer_data": {
            **state.get("offer_data", {}),
            "loan": {
                **offer,
                "display_data": {
                    "download_url":  offer.get("file_contrato_path"),
                    "main_detail":   f"Monto: ${engine.get('monto_aprobado', 0):,}",
                    "security_hash": offer.get("hash_sha256"),
                    "reason":        None,
                },
            },
        },
    }
```

---

### 6.8 Nodos terminales de excepción

```python
def loan_security_block_node(state: FluxState) -> dict:
    """
    Nodo LOAN_SECURITY_BLOCK: cierre por bloqueo OTP.
    Terminal → END.
    """
    from datetime import datetime, timezone
    from langchain_core.messages import SystemMessage

    session = state.get("session", {})
    prep    = state.get("preparation_data", {})
    auth    = state.get("auth_control", {})

    first_name     = (prep.get("nombre", "") or "").split()[0] or "amig@"
    block_ts       = datetime.now(timezone.utc).isoformat()
    application_id = session.get("application_id")

    context = f"""
CONTEXTO:
Usuario: {first_name}
Intentos OTP fallidos: {auth.get('otp_attempts', 3)}
Bloqueo activo: 24 horas
"""

    flux_response = _flux_generator.invoke([
        SystemMessage(content=SYSTEM_PROMPT_SECURITY_BLOCK),
        HumanMessage(content=context),
    ])
    clean_content = normalize_llm_response(flux_response.content)
    if not clean_content:
        clean_content = f"Por tu seguridad, {first_name}, hemos bloqueado temporalmente tu solicitud. Podrás intentarlo de nuevo en 24 horas."

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_SECURITY_BLOCK",
            node_status="FAILED",
            engine_status="NOT_APPLICABLE",
        )

    return {
        "messages": [AIMessage(content=clean_content)],
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


def loan_closed_by_user_node(state: FluxState) -> dict:
    """
    Nodo LOAN_CLOSED_BY_USER: cierre voluntario del usuario.
    Terminal → END.

    Captura el momento de cierre y el nodo anterior para analytics.
    """
    from datetime import datetime, timezone
    from langchain_core.messages import SystemMessage

    session = state.get("session", {})
    prep    = state.get("preparation_data", {})
    engine  = state.get("evaluation_results", {}).get("loan_engine", {})

    first_name     = (prep.get("nombre", "") or "").split()[0] or "amig@"
    application_id = session.get("application_id")
    close_ts       = datetime.now(timezone.utc).isoformat()

    context = f"""
CONTEXTO:
Usuario: {first_name}
Decisión: Rechazó voluntariamente la oferta de crédito.
Último estado alcanzado: {session.get('current_node', 'LOAN_PRE_APPROVED')}
"""

    flux_response = _flux_generator.invoke([
        SystemMessage(content=SYSTEM_PROMPT_CLOSED_BY_USER),
        HumanMessage(content=context),
    ])
    clean_content = normalize_llm_response(flux_response.content)
    if not clean_content:
        clean_content = f"Entendido, {first_name}. Cuando quieras retomar, estaré aquí. ¡Hasta pronto!"

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_CLOSED_BY_USER",
            node_status="SUCCESS",
            engine_status="NOT_APPLICABLE",
        )

    return {
        "messages": [AIMessage(content=clean_content)],
        "session":  {**session, "current_node": "LOAN_CLOSED_BY_USER"},
        "flow_result": {
            "status_code":  "CLOSED_BY_USER",
            "close_reason": "USER_REJECTED_OFFER",
            "product_name": "Crédito de Consumo",
            "closed_at":    close_ts,
        },
        "offer_data": {
            **state.get("offer_data", {}),
            "loan": {
                **state.get("offer_data", {}).get("loan", {}),
                "display_data": {
                    "main_detail": f"Monto ofertado: ${engine.get('monto_aprobado', 0):,}",
                    "reason":      "USER_REJECTED_OFFER",
                },
            },
        },
    }


def loan_service_error_node(state: FluxState) -> dict:
    """
    Nodo LOAN_SERVICE_ERROR: stub de error de servicio externo.

    ID LangGraph : loan_service_error
    current_node : LOAN_SERVICE_ERROR
    Terminal     : sí → END

    STUB Fase 2: Devuelve un mensaje hardcodeado.
    Fase 3: Implementar con SERVICE_ERROR_HANDLER transversal
    (persistencia del estado en financial_applications para retoma).
    """
    from datetime import datetime, timezone

    session        = state.get("session", {})
    application_id = session.get("application_id")

    msg = (
        "Nodo LOAN_SERVICE_ERROR no construido aún. "
        "Finalizando flujo por constancia. "
        "Disculpa el inconveniente; tus datos están guardados y podrás retomar en breve."
    )

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_SERVICE_ERROR",
            node_status="FAILED",
            engine_status="FAILED",
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session":  {**session, "current_node": "LOAN_SERVICE_ERROR"},
        "flow_result": {
            "status_code":  "SERVICE_ERROR",
            "close_reason": "EXTERNAL_SERVICE_FAILURE",
            "product_name": "Crédito de Consumo",
            "closed_at":    datetime.now(timezone.utc).isoformat(),
        },
    }
```

---

## VII. CÓDIGO — PASO 4: `workflow.py` (completo actualizado)

```python
"""
app/graph/workflow.py
─────────────────────────────────────────────────────────────
VERSIÓN: 2.1 — Flujo de crédito completo. Invariante de motor cerrado.

CAMBIOS vs v2.0:
  - Importados y registrados: loan_pre_approved_node, loan_otp_validation_node,
    loan_formalization_node, loan_completed_node, loan_rejected_policy_node,
    loan_security_block_node, loan_closed_by_user_node, loan_service_error_node.
  - Arista loan_risk_engine → END eliminada.
  - Arista condicional loan_risk_engine → route_after_loan_risk_engine implementada.
  - Aristas condicionales para pre_approved, otp_validation, formalization.
  - Nodos terminales (completed, rejected, security_block, closed_by_user,
    service_error) conectados a END.

NOMENCLATURA (Regla de Oro de este archivo):
  ┌──────────────────────────────┬──────────────────────────────────────┐
  │ ID LangGraph (snake)         │ Valor current_node (UPPER)           │
  ├──────────────────────────────┼──────────────────────────────────────┤
  │ welcome                      │ WELCOME_NODE                         │
  │ intent_router                │ INTENT_ROUTER                        │
  │ loan_init                    │ LOAN_INIT                            │
  │ loan_collecting_profile      │ LOAN_COLLECTING_PROFILE              │
  │ loan_collecting_simulation   │ LOAN_COLLECTING_SIMULATION           │
  │ loan_risk_engine             │ LOAN_RISK_ENGINE                     │
  │ loan_pre_approved            │ LOAN_PRE_APPROVED                    │
  │ loan_otp_validation          │ LOAN_OTP_VALIDATION                  │
  │ loan_formalization           │ LOAN_FORMALIZATION                   │
  │ loan_completed               │ LOAN_COMPLETED          [terminal]   │
  │ loan_rejected_policy         │ LOAN_REJECTED_POLICY    [terminal]   │
  │ loan_security_block          │ LOAN_SECURITY_BLOCK     [terminal]   │
  │ loan_closed_by_user          │ LOAN_CLOSED_BY_USER     [terminal]   │
  │ loan_service_error           │ LOAN_SERVICE_ERROR      [terminal]   │
  │ account_init                 │ ACCOUNT_INIT                         │
  │ account_collecting_profile   │ ACCOUNT_COLLECTING_PROFILE           │
  │ account_evaluation_engine    │ ACCOUNT_EVALUATION_ENGINE            │
  │ dap_init                     │ DAP_INIT                             │
  │ dap_collect_data             │ DAP_COLLECT_DATA                     │
  │ dap_investment_engine        │ DAP_INVESTMENT_ENGINE                │
  │ general_response             │ GENERAL_RESPONSE                     │
  └──────────────────────────────┴──────────────────────────────────────┘
"""

from langgraph.graph import StateGraph, END

from app.graph.state import FluxState
from app.graph.nodes.common import welcome_node, intent_router_node, general_response_node
from app.graph.nodes.credit import (
    loan_init_node,
    loan_collecting_profile_node,
    loan_collecting_sim_node,
    loan_risk_engine_node,
    loan_pre_approved_node,          # NUEVO
    loan_otp_validation_node,        # NUEVO
    loan_formalization_node,         # NUEVO
    loan_completed_node,             # NUEVO
    loan_rejected_policy_node,       # NUEVO
    loan_security_block_node,        # NUEVO
    loan_closed_by_user_node,        # NUEVO
    loan_service_error_node,         # NUEVO (stub)
)
from app.graph.nodes.account import (
    account_init_node,
    account_collecting_profile_node,
    account_evaluation_engine_node,
)
from app.graph.nodes.deposit import (
    dap_init_node,
    dap_collect_data_node,
    dap_investment_engine_node,
)
from app.graph.edges import (
    route_after_welcome,
    route_after_intent,
    route_after_loan_collecting_profile,
    route_after_loan_collecting_sim,
    route_after_account_collecting_profile,
    route_after_loan_risk_engine,       # NUEVO
    route_after_loan_pre_approved,      # NUEVO
    route_after_loan_otp_validation,    # NUEVO
    route_after_loan_formalization,     # NUEVO
)
from app.infra.checkpointer import get_checkpointer


def build_graph() -> StateGraph:
    graph = StateGraph(FluxState)

    # ── Nodos comunes ─────────────────────────────────────────────
    graph.add_node("welcome",          welcome_node)
    graph.add_node("intent_router",    intent_router_node)
    graph.add_node("general_response", general_response_node)

    # ── Nodos de Crédito de Consumo ───────────────────────────────
    graph.add_node("loan_init",                  loan_init_node)
    graph.add_node("loan_collecting_profile",     loan_collecting_profile_node)
    graph.add_node("loan_collecting_simulation",  loan_collecting_sim_node)
    graph.add_node("loan_risk_engine",            loan_risk_engine_node)
    graph.add_node("loan_pre_approved",           loan_pre_approved_node)
    graph.add_node("loan_otp_validation",         loan_otp_validation_node)
    graph.add_node("loan_formalization",          loan_formalization_node)
    graph.add_node("loan_completed",              loan_completed_node)
    graph.add_node("loan_rejected_policy",        loan_rejected_policy_node)
    graph.add_node("loan_security_block",         loan_security_block_node)
    graph.add_node("loan_closed_by_user",         loan_closed_by_user_node)
    graph.add_node("loan_service_error",          loan_service_error_node)

    # ── Nodos de Cuenta Corriente ──────────────────────────────────
    graph.add_node("account_init",               account_init_node)
    graph.add_node("account_collecting_profile", account_collecting_profile_node)
    graph.add_node("account_evaluation_engine",  account_evaluation_engine_node)

    # ── Nodos de Depósito a Plazo ──────────────────────────────────
    graph.add_node("dap_init",              dap_init_node)
    graph.add_node("dap_collect_data",      dap_collect_data_node)
    graph.add_node("dap_investment_engine", dap_investment_engine_node)

    # ── Punto de Entrada ───────────────────────────────────────────
    graph.set_entry_point("welcome")

    # ── Aristas de Navegación Principal ───────────────────────────
    graph.add_conditional_edges(
        "welcome",
        route_after_welcome,
        {
            "intent_router":               "intent_router",
            "loan_init":                   "loan_init",
            "account_init":                "account_init",
            "dap_init":                    "dap_init",
            "loan_collecting_profile":     "loan_collecting_profile",
            "loan_collecting_simulation":  "loan_collecting_simulation",
            "loan_risk_engine":            "loan_risk_engine",
            "loan_pre_approved":           "loan_pre_approved",
            "loan_otp_validation":         "loan_otp_validation",
            "loan_formalization":          "loan_formalization",
            "account_collecting_profile":  "account_collecting_profile",
            "dap_collect_data":            "dap_collect_data",
        }
    )
    graph.add_conditional_edges(
        "intent_router",
        route_after_intent,
        {
            "loan_init":        "loan_init",
            "account_init":     "account_init",
            "dap_init":         "dap_init",
            "general_response": "general_response",
        }
    )

    # ── Flujo de Crédito ───────────────────────────────────────────
    # Recolección
    graph.add_edge("loan_init", "loan_collecting_profile")
    graph.add_conditional_edges(
        "loan_collecting_profile",
        route_after_loan_collecting_profile,
        {
            "loan_collecting_simulation": "loan_collecting_simulation",
            END: END,
        }
    )
    graph.add_conditional_edges(
        "loan_collecting_simulation",
        route_after_loan_collecting_sim,
        {
            "loan_risk_engine": "loan_risk_engine",
            END: END,
        }
    )

    # Motor → Oferta o Rechazo [INVARIANTE: nunca END]
    graph.add_conditional_edges(
        "loan_risk_engine",
        route_after_loan_risk_engine,
        {
            "loan_pre_approved":   "loan_pre_approved",
            "loan_rejected_policy": "loan_rejected_policy",
            "loan_service_error":  "loan_service_error",
        }
    )

    # Pre-aprobado → OTP o Cierre voluntario
    graph.add_conditional_edges(
        "loan_pre_approved",
        route_after_loan_pre_approved,
        {
            "loan_otp_validation": "loan_otp_validation",
            "loan_closed_by_user": "loan_closed_by_user",
            "loan_pre_approved":   "loan_pre_approved",
        }
    )

    # OTP → Formalización o Bloqueo
    graph.add_conditional_edges(
        "loan_otp_validation",
        route_after_loan_otp_validation,
        {
            "loan_formalization":  "loan_formalization",
            "loan_security_block": "loan_security_block",
            "loan_otp_validation": "loan_otp_validation",
        }
    )

    # Formalización → Completado o Error
    graph.add_conditional_edges(
        "loan_formalization",
        route_after_loan_formalization,
        {
            "loan_completed":      "loan_completed",
            "loan_service_error":  "loan_service_error",
            "loan_formalization":  "loan_formalization",
        }
    )

    # Terminales de Crédito → END
    graph.add_edge("loan_completed",       END)
    graph.add_edge("loan_rejected_policy", END)
    graph.add_edge("loan_security_block",  END)
    graph.add_edge("loan_closed_by_user",  END)
    graph.add_edge("loan_service_error",   END)

    # ── Flujo de Cuenta Corriente ──────────────────────────────────
    graph.add_edge("account_init", "account_collecting_profile")
    graph.add_conditional_edges(
        "account_collecting_profile",
        route_after_account_collecting_profile,
        {
            "account_evaluation_engine": "account_evaluation_engine",
            END: END,
        }
    )
    graph.add_edge("account_evaluation_engine", END)

    # ── Flujo de Depósito a Plazo ──────────────────────────────────
    graph.add_edge("dap_init",              "dap_collect_data")
    graph.add_edge("dap_collect_data",      "dap_investment_engine")
    graph.add_edge("dap_investment_engine", END)

    # ── General ───────────────────────────────────────────────────
    graph.add_edge("general_response", END)

    return graph


def get_compiled_graph():
    graph       = build_graph()
    checkpointer = get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


_compiled_graph = None

def get_active_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = get_compiled_graph()
    return _compiled_graph
```

---

## VIII. STUBS TRANSVERSALES (`modules/security.py` y `modules/pdf_factory.py`)

Si no existen, crear con el mínimo funcional:

```python
# app/modules/security.py — STUB Fase 2
def generate_otp() -> str:
    """STUB: Retorna "123456". Fase 3: usar secrets.randbelow."""
    return "123456"

def send_otp_email(mail: str, otp: str) -> bool:
    """STUB: Simula envío exitoso."""
    print(f"[STUB] OTP {otp} 'enviado' a {mail}")
    return True


# app/modules/pdf_factory.py — STUB Fase 2
import hashlib

def generate_loan_contract(data: dict) -> tuple[str, str]:
    """STUB: Retorna path y hash ficticios. Fase 3: implementar con ReportLab."""
    mock_path = f"/contracts/loan_{data.get('rut', '00000000-0')}_STUB.pdf"
    mock_hash = hashlib.sha256(data.get("rut", "").encode()).hexdigest()
    print(f"[STUB] Contrato 'generado': {mock_path} | Hash: {mock_hash[:8]}...")
    return mock_path, mock_hash
```

---

## IX. PRUEBAS DE VALIDACIÓN

### 9.1 Tests unitarios de edges

```python
# tests/unit/test_edges_post_motor.py

from app.graph.edges import (
    route_after_loan_risk_engine,
    route_after_loan_pre_approved,
    route_after_loan_otp_validation,
    route_after_loan_formalization,
)


def test_risk_engine_pre_approved():
    state = {"evaluation_results": {"loan_engine": {"status_proceso": "PRE_APPROVED"}}}
    assert route_after_loan_risk_engine(state) == "loan_pre_approved"

def test_risk_engine_rejected():
    state = {"evaluation_results": {"loan_engine": {"status_proceso": "REJECTED"}}}
    assert route_after_loan_risk_engine(state) == "loan_rejected_policy"

def test_risk_engine_error_goes_to_service_error():
    state = {"evaluation_results": {"loan_engine": {"status_proceso": "ERROR"}}}
    assert route_after_loan_risk_engine(state) == "loan_service_error"

def test_risk_engine_never_returns_end():
    """INVARIANTE: La función nunca retorna END."""
    from langgraph.graph import END
    for status in ["PRE_APPROVED", "REJECTED", "ERROR", "UNKNOWN", ""]:
        state = {"evaluation_results": {"loan_engine": {"status_proceso": status}}}
        result = route_after_loan_risk_engine(state)
        assert result != END, f"status='{status}' retornó END, violando el invariante"

def test_pre_approved_loop_when_no_status():
    state = {"offer_data": {"loan": {}}}
    assert route_after_loan_pre_approved(state) == "loan_pre_approved"

def test_pre_approved_accepted():
    state = {"offer_data": {"loan": {"pre_approval_status": "ACCEPTED"}}}
    assert route_after_loan_pre_approved(state) == "loan_otp_validation"

def test_pre_approved_rejected():
    state = {"offer_data": {"loan": {"pre_approval_status": "REJECTED"}}}
    assert route_after_loan_pre_approved(state) == "loan_closed_by_user"

def test_otp_verified():
    state = {"auth_control": {"otp_generated": "123456", "otp_user_input": "123456"}}
    assert route_after_loan_otp_validation(state) == "loan_formalization"

def test_otp_wrong_code_loops():
    state = {"auth_control": {"otp_generated": "123456", "otp_user_input": "999999"}}
    assert route_after_loan_otp_validation(state) == "loan_otp_validation"

def test_otp_security_blocked():
    state = {"auth_control": {"otp_generated": "123456", "otp_user_input": "999",
                               "security_blocked": True}}
    assert route_after_loan_otp_validation(state) == "loan_security_block"

def test_otp_no_input_loops():
    state = {"auth_control": {"otp_generated": "123456", "otp_user_input": ""}}
    assert route_after_loan_otp_validation(state) == "loan_otp_validation"

def test_formalization_signed():
    state = {"offer_data": {"loan": {"contract_status": "SIGNED_AND_STAMPED"}}}
    assert route_after_loan_formalization(state) == "loan_completed"

def test_formalization_failed():
    state = {"offer_data": {"loan": {"contract_status": "GENERATION_FAILED"}}}
    assert route_after_loan_formalization(state) == "loan_service_error"

def test_formalization_pending_loops():
    state = {"offer_data": {"loan": {}}}
    assert route_after_loan_formalization(state) == "loan_formalization"
```

### 9.2 Tests unitarios de nodos (mocks)

```python
# tests/unit/test_credit_post_motor_nodes.py

from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

BASE_SESSION = {"current_node": "LOAN_RISK_ENGINE", "application_id": None,
                "progress": {}, "just_completed_step": None}
BASE_PREP    = {"nombre": "Ana Torres", "mail": "ana@test.cl",
                "rut": "12.345.678-9", "edad": 30}
BASE_ENGINE  = {
    "status_proceso": "PRE_APPROVED", "monto_aprobado": 5_000_000,
    "plazo_aprobado": 24, "cuota_mensual": 250_000,
    "tasa_interes_mensual": 0.02, "cae": 0.268,
    "ctc": 6_000_000, "total_intereses": 1_000_000, "nivel_riesgo": "MEDIO",
    "motivo_rechazo": None,
}


@patch("app.graph.nodes.credit._flux_generator")
def test_pre_approved_genera_mensaje_y_display_data(mock_gen):
    from app.graph.nodes.credit import loan_pre_approved_node
    mock_gen.invoke.return_value = MagicMock(content="¡Felicitaciones Ana!")
    state = {
        "session": BASE_SESSION, "preparation_data": BASE_PREP,
        "evaluation_results": {"loan_engine": BASE_ENGINE},
        "offer_data": {"loan": {}}, "messages": [],
    }
    result = loan_pre_approved_node(state)
    assert "messages" in result and len(result["messages"]) > 0
    assert result["offer_data"]["loan"]["display_data"]["monto_aprobado"] == 5_000_000
    assert "pre_approval_status" not in result["offer_data"]["loan"]
    assert result["session"]["just_completed_step"] is None   # Flag limpiada


@patch("app.graph.nodes.credit._flux_generator")
def test_rejected_policy_incluye_flow_result(mock_gen):
    from app.graph.nodes.credit import loan_rejected_policy_node
    mock_gen.invoke.return_value = MagicMock(content="Lo sentimos.")
    state = {
        "session": BASE_SESSION, "preparation_data": BASE_PREP,
        "evaluation_results": {"loan_engine": {**BASE_ENGINE, "motivo_rechazo": "ERR_RENTA"}},
        "offer_data": {}, "messages": [],
    }
    result = loan_rejected_policy_node(state)
    assert result["flow_result"]["status_code"] == "REJECTED"
    assert result["flow_result"]["close_reason"] == "ERR_RENTA"


@patch("app.graph.nodes.credit.send_otp_email")
@patch("app.graph.nodes.credit.generate_otp")
@patch("app.graph.nodes.credit._flux_generator")
def test_otp_init_genera_y_envia(mock_gen, mock_otp, mock_email):
    from app.graph.nodes.credit import loan_otp_validation_node
    mock_otp.return_value = "123456"
    mock_email.return_value = True
    mock_gen.invoke.return_value = MagicMock(content="Código enviado.")
    state = {
        "session": BASE_SESSION, "preparation_data": BASE_PREP,
        "auth_control": {}, "messages": [],
    }
    result = loan_otp_validation_node(state)
    mock_otp.assert_called_once()
    mock_email.assert_called_once_with("ana@test.cl", "123456")
    assert result["auth_control"]["otp_generated"] == "123456"


@patch("app.graph.nodes.credit._flux_generator")
def test_otp_exitoso_avance_silencioso(mock_gen):
    from app.graph.nodes.credit import loan_otp_validation_node
    state = {
        "session": BASE_SESSION, "preparation_data": BASE_PREP,
        "auth_control": {"otp_generated": "123456", "otp_user_input": "123456"},
        "messages": [],
    }
    result = loan_otp_validation_node(state)
    mock_gen.invoke.assert_not_called()
    assert "messages" not in result or len(result.get("messages", [])) == 0


def test_otp_nunca_extrae_codigo_del_chat():
    """El nodo NUNCA valida el OTP desde el chat."""
    from app.graph.nodes.credit import loan_otp_validation_node
    with patch("app.graph.nodes.credit._flux_generator") as mock_gen, \
         patch("app.graph.nodes.credit.generate_otp", return_value="123456"), \
         patch("app.graph.nodes.credit.send_otp_email", return_value=True):
        mock_gen.invoke.return_value = MagicMock(content="Ingresa el código.")
        state = {
            "session": BASE_SESSION, "preparation_data": BASE_PREP,
            "auth_control": {"otp_generated": "123456"},
            "messages": [HumanMessage(content="123456")],  # Código en el chat
        }
        result = loan_otp_validation_node(state)
        # otp_user_input no debe derivarse del chat
        assert result.get("auth_control", {}).get("otp_user_input") is None


@patch("app.graph.nodes.credit.generate_loan_contract")
@patch("app.graph.nodes.credit._flux_generator")
def test_formalization_genera_contrato_primera_vez(mock_gen, mock_pdf):
    from app.graph.nodes.credit import loan_formalization_node
    mock_pdf.return_value = ("/contracts/test.pdf", "abc123")
    mock_gen.invoke.return_value = MagicMock(content="Contrato listo.")
    state = {
        "session": BASE_SESSION, "preparation_data": BASE_PREP,
        "evaluation_results": {"loan_engine": BASE_ENGINE},
        "offer_data": {"loan": {}}, "messages": [],
    }
    result = loan_formalization_node(state)
    mock_pdf.assert_called_once()
    assert result["offer_data"]["loan"]["file_contrato_path"] == "/contracts/test.pdf"


@patch("app.graph.nodes.credit.generate_loan_contract")
@patch("app.graph.nodes.credit._flux_generator")
def test_formalization_no_acepta_texto_como_firma(mock_gen, mock_pdf):
    from app.graph.nodes.credit import loan_formalization_node
    mock_pdf.return_value = ("/contracts/test.pdf", "abc123")
    mock_gen.invoke.return_value = MagicMock(content="Perfecto, revisa el contrato.")
    state = {
        "session": BASE_SESSION, "preparation_data": BASE_PREP,
        "evaluation_results": {"loan_engine": BASE_ENGINE},
        "offer_data": {"loan": {"file_contrato_path": "/existing.pdf"}},
        "messages": [HumanMessage(content="Sí, acepto todo")],
    }
    result = loan_formalization_node(state)
    assert result.get("offer_data", {}).get("loan", {}).get("contract_status") is None


@patch("app.graph.nodes.credit._flux_generator")
def test_completed_escribe_flow_result_success(mock_gen):
    from app.graph.nodes.credit import loan_completed_node
    mock_gen.invoke.return_value = MagicMock(content="¡Felicitaciones!")
    state = {
        "session": BASE_SESSION, "preparation_data": BASE_PREP,
        "evaluation_results": {"loan_engine": BASE_ENGINE},
        "offer_data": {"loan": {"file_contrato_path": "/c.pdf", "hash_sha256": "x"}},
        "messages": [],
    }
    result = loan_completed_node(state)
    assert result["flow_result"]["status_code"] == "SUCCESS"
    assert result["offer_data"]["loan"]["display_data"]["download_url"] == "/c.pdf"


@patch("app.graph.nodes.credit._flux_generator")
def test_security_block_setea_timestamp_y_blocked(mock_gen):
    from app.graph.nodes.credit import loan_security_block_node
    mock_gen.invoke.return_value = MagicMock(content="Bloqueado por seguridad.")
    state = {
        "session": BASE_SESSION, "preparation_data": BASE_PREP,
        "auth_control": {"otp_attempts": 3}, "messages": [],
    }
    result = loan_security_block_node(state)
    assert result["auth_control"]["security_blocked"] is True
    assert result["auth_control"]["block_timestamp"] is not None
    assert result["flow_result"]["status_code"] == "SECURITY_BLOCKED"


def test_service_error_hardcoded_message():
    from app.graph.nodes.credit import loan_service_error_node
    state = {
        "session": BASE_SESSION, "preparation_data": BASE_PREP,
        "offer_data": {}, "messages": [],
    }
    result = loan_service_error_node(state)
    assert "messages" in result and len(result["messages"]) > 0
    assert "no construido" in result["messages"][0].content.lower() or \
           "error" in result["messages"][0].content.lower()
```

---

## X. CHECKLIST DE CIERRE DE FASE 2

```
CÓDIGO COMPLETADO
[ ] constants.py    — CompletedStep.LOAN_RISK_EVALUATED agregado
[ ] edges.py        — _RESUME_MAP, _SUCCESS_MAP, _VALID_DESTINATION_NODES extendidos
[ ] edges.py        — 4 nuevas funciones de edge agregadas al final del archivo
[ ] credit.py       — loan_risk_engine_node actualizado con escritura dual
[ ] credit.py       — 8 nuevos nodos implementados (pre_approved, rejected_policy,
                       otp_validation, formalization, completed, security_block,
                       closed_by_user, service_error)
[ ] credit.py       — 7 nuevos prompts SYSTEM_PROMPT_* definidos
[ ] workflow.py     — 8 nuevos nodos registrados
[ ] workflow.py     — Aristas del flujo de crédito completas y sin END silencioso
[ ] modules/security.py   — Stub funcional (generate_otp, send_otp_email)
[ ] modules/pdf_factory.py — Stub funcional (generate_loan_contract)

INVARIANTE DE MOTOR
[ ] route_after_loan_risk_engine NUNCA retorna END
[ ] test_risk_engine_never_returns_end pasa con todos los status posibles
[ ] loan_pre_approved_node genera AIMessage en TODA ejecución
[ ] loan_rejected_policy_node genera AIMessage
[ ] Todo ciclo de ejecución termina con al menos un AIMessage

INTERACCIÓN DETERMINISTA
[ ] loan_otp_validation_node nunca lee otp del chat (test confirmado)
[ ] loan_formalization_node nunca setea contract_status desde el chat (test confirmado)
[ ] loan_pre_approved_node nunca setea pre_approval_status desde el chat

TESTS PASANDO
[ ] pytest tests/unit/test_edges_post_motor.py          — 12/12 PASS
[ ] pytest tests/unit/test_credit_post_motor_nodes.py   — 11/11 PASS
[ ] pytest tests/unit/test_edges_credit.py              (fix-routes) — sin regresión
[ ] pytest tests/unit/test_credit_nodes_v22.py          (fix-routes) — sin regresión

STUBS PENDIENTES PARA FASE 3
[ ] modules/security.py   → generate_otp() real con secrets.randbelow
[ ] modules/pdf_factory.py → generate_loan_contract() real con ReportLab
[ ] loan_service_error_node → SERVICE_ERROR_HANDLER transversal
[ ] KNOWLEDGE_BASE_RAG nodo transversal (credito-datos.md §V.A)
[ ] SECURITY_WATCHDOG nodo transversal (credito-datos.md §V.C)
```

---

## XI. TABLA DE SEMÁFOROS ACTUALIZADA

| Nodo (UPPER_CASE)               | `node_status` | `engine_status`  | `document_status` |
|---------------------------------|---------------|------------------|-------------------|
| `LOAN_INIT`                     | `SUCCESS`     | `PENDING`        | —                 |
| `LOAN_COLLECTING_PROFILE`       | `SUCCESS`     | `PENDING`        | —                 |
| `LOAN_COLLECTING_SIMULATION`    | `SUCCESS`     | `PENDING`        | —                 |
| `LOAN_RISK_ENGINE` (aprobado)   | `SUCCESS`     | `SUCCESS`        | —                 |
| `LOAN_RISK_ENGINE` (error)      | `SUCCESS`     | `FAILED`         | —                 |
| `LOAN_PRE_APPROVED`             | `SUCCESS`     | `NOT_APPLICABLE` | —                 |
| `LOAN_OTP_VALIDATION` (éxito)   | `SUCCESS`     | `NOT_APPLICABLE` | —                 |
| `LOAN_FORMALIZATION`            | `SUCCESS`     | `NOT_APPLICABLE` | `GENERATED`       |
| `LOAN_COMPLETED`                | `SUCCESS`     | `NOT_APPLICABLE` | `GENERATED`       |
| `LOAN_REJECTED_POLICY`          | `SUCCESS`     | `COMPLETED`      | —                 |
| `LOAN_SECURITY_BLOCK`           | `FAILED`      | `NOT_APPLICABLE` | —                 |
| `LOAN_CLOSED_BY_USER`           | `SUCCESS`     | `NOT_APPLICABLE` | —                 |
| `LOAN_SERVICE_ERROR`            | `FAILED`      | `FAILED`         | —                 |

---

*Documento generado para Flux — Fase 2, Plan v5.0*  
*Reemplaza: `fase2.md` v4.0 (Pasos 3–7) + referencias a stubs en `fix-routes.md`*
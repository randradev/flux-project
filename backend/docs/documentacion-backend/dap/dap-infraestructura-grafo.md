# Plan de Implementación Quirúrgica — Producto DAP (Depósito a Plazo)

> **Principio rector:** DAP es un calco simétrico de ACCOUNT.
> La única diferencia de nomenclatura es que donde ACCOUNT usa `_COLLECTING_PROFILE`
> y `_EVALUATION_ENGINE`, DAP usa `_COLLECTING_DATA` y `_INVESTMENT_ENGINE`.
> Esa asimetría de nombres ya está soportada en los archivos existentes
> (los nodos `dap_collect_data` y `dap_investment_engine` ya están registrados).

---

## Diagnóstico del Estado Actual

Inventario exacto de lo que falta vs. lo que ya existe para DAP:

| Elemento | Estado actual |
|---|---|
| `CompletedStep.DAP_DATA` | ✅ Existe (equivale a `ACCOUNT_PROFILE`) |
| `CompletedStep.DAP_INVESTMENT_SUCCESS` / `DAP_INVESTMENT_REJECTED` | ❌ Faltan |
| `CompletedStep.DAP_PRE_APPROVED` | ❌ Falta |
| `CompletedStep.DAP_OTP_SUCCESS` | ❌ Falta |
| `CompletedStep.DAP_FORMALIZATION_SUCCESS` | ❌ Falta |
| `CompletedStep.DAP_SECURITY_BLOCK` / `DAP_CLOSED_BY_USER` | ❌ Faltan |
| `DapProgress` en `state.py` (solo tiene `data_completed`) | ⚠️ Incompleta — faltan 5 campos |
| `_RESUME_MAP` (`DAP_PRE_APPROVED`, `DAP_OTP_VALIDATION`) | ❌ Faltan 2 entradas |
| `_VALID_DESTINATION_NODES` (nodos finales DAP) | ❌ Faltan 7 nodos |
| `_SUCCESS_MAP["DAP"]` (solo tiene `DAP_DATA`) | ⚠️ Incompleto — faltan 7 transiciones |
| `_get_completed_steps_for_product` rama DAP | ⚠️ Incompleta — solo `data_completed` |
| Funciones `route_after_dap_*` | ❌ Faltan 4 funciones |
| Nodos DAP registrados en `workflow.py` (pre_approved, otp, etc.) | ❌ Faltan 7 nodos |
| Aristas DAP en `workflow.py` (`dap_collect_data → dap_investment_engine` es fija, debe ser condicional) | ❌ 2 aristas incorrectas + faltan todas las del flujo completo |
| Importaciones de nodos DAP en `workflow.py` | ❌ Faltan 7 importaciones |

---

## Tabla de Equivalencias ACCOUNT → DAP

Esta tabla es la referencia central. Cada línea define una sustitución exacta de prefijo/nombre.

| Concepto | ACCOUNT | DAP |
|---|---|---|
| Nodo de recolección (snake) | `account_collecting_profile` | `dap_collect_data` |
| Nodo de recolección (UPPER) | `ACCOUNT_COLLECTING_PROFILE` | `DAP_COLLECTING_DATA` |
| Nodo del motor (snake) | `account_evaluation_engine` | `dap_investment_engine` |
| Nodo del motor (UPPER) | `ACCOUNT_EVALUATION_ENGINE` | `DAP_INVESTMENT_ENGINE` |
| CompletedStep recolección | `ACCOUNT_PROFILE` | `DAP_DATA` ✅ ya existe |
| CompletedStep motor aprobó | `ACCOUNT_EVALUATION_SUCCESS` | `DAP_INVESTMENT_SUCCESS` |
| CompletedStep motor rechazó | `ACCOUNT_EVALUATION_REJECTED` | `DAP_INVESTMENT_REJECTED` |
| CompletedStep usuario aceptó | `ACCOUNT_PRE_APPROVED` | `DAP_PRE_APPROVED` |
| CompletedStep OTP OK | `ACCOUNT_OTP_SUCCESS` | `DAP_OTP_SUCCESS` |
| CompletedStep contrato sellado | `ACCOUNT_FORMALIZATION_SUCCESS` | `DAP_FORMALIZATION_SUCCESS` |
| CompletedStep 3 intentos OTP | `ACCOUNT_SECURITY_BLOCK` | `DAP_SECURITY_BLOCK` |
| CompletedStep usuario rechazó | `ACCOUNT_CLOSED_BY_USER` | `DAP_CLOSED_BY_USER` |
| Progress campo motor | `evaluation_engine_completed` | `investment_engine_completed` |
| Progress campo pre-aprobación | `pre_approval_accepted` | `pre_approval_accepted` |
| Progress campo cierre usuario | `closed_by_user` | `closed_by_user` |
| Progress campo OTP | `otp_validated` | `otp_validated` |
| Progress campo contrato | `contract_signed` | `contract_signed` |
| `evaluation_results` sub-clave | `account_engine` | `dap_engine` |

---

## Archivo 1 de 4: `constants.py`

### Qué cambiar

Añadir 7 constantes nuevas al bloque de DAP dentro de `CompletedStep`.
La constante `DAP_DATA` ya existe; el resto se agrega inmediatamente debajo.

### Código a modificar

**Localiza:**
```python
    # DAP
    DAP_DATA        = "DAP_DATA"
```

**Reemplaza por:**
```python
    # DAP
    DAP_DATA        = "DAP_DATA"

    # ── Evaluación y Oferta — DAP (NUEVOS) ────────────────────
    DAP_INVESTMENT_SUCCESS  = "DAP_INVESTMENT_SUCCESS"   # Motor calculó y aprobó
    DAP_INVESTMENT_REJECTED = "DAP_INVESTMENT_REJECTED"  # Motor calculó y rechazó

    # ── Formalización — DAP (NUEVOS) ─────────────────────────
    DAP_PRE_APPROVED          = "DAP_PRE_APPROVED"         # Usuario aceptó
    DAP_OTP_SUCCESS           = "DAP_OTP_SUCCESS"          # OTP validado
    DAP_FORMALIZATION_SUCCESS = "DAP_FORMALIZATION_SUCCESS" # Contrato sellado

    # ── Excepciones — DAP (NUEVOS) ────────────────────────────
    DAP_SECURITY_BLOCK  = "DAP_SECURITY_BLOCK"   # 3 intentos OTP fallidos
    DAP_CLOSED_BY_USER  = "DAP_CLOSED_BY_USER"   # Usuario rechazó la oferta
```

> **Nota de precisión:** El prefijo del motor es `INVESTMENT` (no `EVALUATION`) porque el nodo
> se llama `DAP_INVESTMENT_ENGINE`. Cualquier nodo que setee `just_completed_step` para el motor
> DAP **debe usar exactamente** `DAP_INVESTMENT_SUCCESS` o `DAP_INVESTMENT_REJECTED`.

---

## Archivo 2 de 4: `state.py`

### Qué cambiar

`DapProgress` solo tiene `data_completed`. Necesita los 5 campos restantes que espeja
`AccountProgress`, usando los mismos nombres de campo (la clave de progreso es agnóstica al
producto; el sub-cajón `dap` la aísla del de `account`).

### Código a modificar

**Localiza:**
```python
class DapProgress(TypedDict, total=False):
    """Registro histórico de completitud del flujo de depósito a plazo."""
    data_completed: bool
```

**Reemplaza por:**
```python
class DapProgress(TypedDict, total=False):
    """Registro histórico de completitud del flujo de depósito a plazo."""
    data_completed:              bool   # True cuando dap_params tiene todos los campos
    investment_engine_completed: bool   # True cuando el motor de inversión ya se ejecutó
    pre_approval_accepted:       bool   # True cuando el usuario acepta la tarjeta de transparencia
    closed_by_user:              bool   # True cuando el usuario rechaza la oferta
    otp_validated:               bool   # True cuando el OTP es verificado exitosamente
    contract_signed:             bool   # True cuando el contrato fue firmado digitalmente
```

> **Consistencia con `_get_completed_steps_for_product`:** El campo del motor se llama
> `investment_engine_completed` (no `evaluation_engine_completed`) para reflejar que el
> nodo se llama `DAP_INVESTMENT_ENGINE`. Los demás campos comparten nombre con ACCOUNT
> porque son conceptos idénticos aislados cada uno en su propio sub-cajón de `progress`.

---

## Archivo 3 de 4: `edges.py`

Se hacen **5 cambios quirúrgicos**. Ninguno toca el código existente de LOAN ni de ACCOUNT.

---

### Cambio 3.1 — `_RESUME_MAP`: añadir nodos DAP que esperan input del usuario

Los nodos que esperan respuesta del usuario entre turnos deben estar en este mapa para que
`route_after_welcome` los reanude correctamente (P2).

**Localiza:**
```python
    # Depósito a Plazo
    "DAP_INIT":                    "dap_init",
    "DAP_COLLECT_DATA":            "dap_collect_data",
```

**Reemplaza por:**
```python
    # Depósito a Plazo
    "DAP_INIT":                    "dap_init",
    "DAP_COLLECTING_DATA":         "dap_collect_data",
    # Depósito a Plazo — Evaluación y Oferta
    "DAP_PRE_APPROVED":            "dap_pre_approved",
    "DAP_OTP_VALIDATION":          "dap_otp_validation",
    # NOTA: DAP_INVESTMENT_ENGINE y DAP_FORMALIZATION son nodos de servicio automáticos.
    # No tienen reanudación por turno: si el proceso se interrumpe en ellos,
    # la reanudación ocurre vía _SUCCESS_MAP desde el paso previo.
```

> **Corrección de nomenclatura incluida:** La clave existente `"DAP_COLLECT_DATA"` no coincide
> con el valor `current_node` en UPPER_CASE que los nodos escribirían (`"DAP_COLLECTING_DATA"`
> según el Mermaid). Se corrige aquí para mantener coherencia. El valor snake_case
> `"dap_collect_data"` queda igual porque es el ID de LangGraph ya registrado en el grafo.

---

### Cambio 3.2 — `_VALID_DESTINATION_NODES`: registrar nodos DAP completos

**Localiza:**
```python
    # DAP
    "dap_init",
    "dap_collect_data",
    "dap_investment_engine",
```

**Reemplaza por:**
```python
    # DAP
    "dap_init",
    "dap_collect_data",
    "dap_investment_engine",
    "dap_pre_approved",
    "dap_otp_validation",
    "dap_formalization",
    "dap_completed",
    "dap_rejected_policy",
    "dap_security_block",
    "dap_closed_by_user",
```

---

### Cambio 3.3 — `_SUCCESS_MAP["DAP"]`: flujo completo

**Localiza:**
```python
    "DAP": {
        CompletedStep.DAP_DATA: "dap_investment_engine",
    },
```

**Reemplaza por:**
```python
    "DAP": {
        CompletedStep.DAP_DATA:                  "dap_investment_engine",
        CompletedStep.DAP_INVESTMENT_SUCCESS:    "dap_pre_approved",
        CompletedStep.DAP_PRE_APPROVED:          "dap_otp_validation",
        CompletedStep.DAP_OTP_SUCCESS:           "dap_formalization",
        CompletedStep.DAP_FORMALIZATION_SUCCESS: "dap_completed",

        CompletedStep.DAP_INVESTMENT_REJECTED:   "dap_rejected_policy",
        CompletedStep.DAP_CLOSED_BY_USER:        "dap_closed_by_user",
        CompletedStep.DAP_SECURITY_BLOCK:        "dap_security_block",
    },
```

---

### Cambio 3.4 — `_get_completed_steps_for_product`: rama DAP completa

**Localiza:**
```python
    elif product == "DAP":
        if product_progress.get("data_completed"):
            completed.append(CompletedStep.DAP_DATA)
    return completed
```

**Reemplaza por:**
```python
    elif product == "DAP":
        # A. Recolección
        if product_progress.get("data_completed"):
            completed.append(CompletedStep.DAP_DATA)

        # B. Evaluación
        if product_progress.get("investment_engine_completed"):
            engine_status = state.get("evaluation_results", {}).get("dap_engine", {}).get("status_proceso")
            if engine_status == "PRE_APPROVED":
                completed.append(CompletedStep.DAP_INVESTMENT_SUCCESS)
            else:
                completed.append(CompletedStep.DAP_INVESTMENT_REJECTED)

        # C. Oferta y OTP
        if product_progress.get("pre_approval_accepted"):
            completed.append(CompletedStep.DAP_PRE_APPROVED)
        elif product_progress.get("closed_by_user"):
            completed.append(CompletedStep.DAP_CLOSED_BY_USER)

        if product_progress.get("otp_validated"):
            completed.append(CompletedStep.DAP_OTP_SUCCESS)
        elif state.get("auth_control", {}).get("security_blocked"):
            completed.append(CompletedStep.DAP_SECURITY_BLOCK)

        # D. Formalización (Final del flujo)
        if product_progress.get("contract_signed"):
            completed.append(CompletedStep.DAP_FORMALIZATION_SUCCESS)

    return completed
```

---

### Cambio 3.5 — Añadir las 4 funciones de ruteo de DAP

Ubícate al **final del archivo**, después de `route_after_account_formalization`,
y añade el siguiente bloque completo:

```python
# ──────────────────────────────────────────────────────────────────────────────────────
# DECISIONES DE ARISTAS NODOS DE DEPÓSITO A PLAZO
# ──────────────────────────────────────────────────────────────────────────────────────

def route_after_dap_collecting_data(state: FluxState) -> str:
    """
    Decisión de arista post-dap_collect_data.

    Si los datos de inversión se completaron (just_completed_step = DAP_DATA),
    salta directamente al motor de inversión en el mismo turno.
    Si no, va a END para esperar el siguiente mensaje del usuario.

    NOTA: No se usa progress aquí deliberadamente; just_completed_step es
    la señal más fresca y específica del turno actual.
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.DAP_DATA:
        return "dap_investment_engine"
    return END


def route_after_dap_investment_engine(state: FluxState) -> str:
    """
    Decisión de arista post-dap_investment_engine.

    El motor de inversión es un nodo de servicio automático: siempre completa
    su trabajo en el mismo turno y emite exactamente uno de dos CompletedStep:
      - DAP_INVESTMENT_SUCCESS  → dap_pre_approved
      - DAP_INVESTMENT_REJECTED → dap_rejected_policy

    NOTA: Este edge NO tiene rama END porque dap_investment_engine nunca
    espera input del usuario. Si just_completed_step es None o inesperado,
    se redirige a dap_rejected_policy como fallback seguro (evita loop).
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.DAP_INVESTMENT_SUCCESS:
        return "dap_pre_approved"
    if just_completed == CompletedStep.DAP_INVESTMENT_REJECTED:
        return "dap_rejected_policy"

    # Fallback defensivo: si el motor no emitió señal, redirigir a rechazo
    _routing_logger.warning(
        f"route_after_dap_investment_engine: just_completed_step='{just_completed}' "
        "inesperado. Redirigiendo a 'dap_rejected_policy' como fallback."
    )
    return "dap_rejected_policy"


def route_after_dap_pre_approved(state: FluxState) -> str:
    """
    Decisión de arista post-dap_pre_approved.

    Este nodo espera la decisión del usuario (ACCEPTED / REJECTED).
    La señal viaja en just_completed_step:
      - DAP_PRE_APPROVED    → dap_otp_validation   (usuario aceptó)
      - DAP_CLOSED_BY_USER  → dap_closed_by_user   (usuario rechazó)
      - None                → END                   (primer turno: espera respuesta)

    REGLA: Si el nodo acaba de generar la tarjeta de transparencia y aún
    no hay respuesta del usuario, just_completed_step será None → END.
    En el siguiente turno, el nodo vuelve a ejecutarse, lee la respuesta
    y emite el CompletedStep correspondiente.
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.DAP_PRE_APPROVED:
        return "dap_otp_validation"
    if just_completed == CompletedStep.DAP_CLOSED_BY_USER:
        return "dap_closed_by_user"

    return END  # Esperar respuesta del usuario


def route_after_dap_otp_validation(state: FluxState) -> str:
    """
    Decisión de arista post-dap_otp_validation.

    El nodo OTP espera que el usuario ingrese el código.
    La señal viaja en just_completed_step:
      - DAP_OTP_SUCCESS    → dap_formalization    (código correcto)
      - DAP_SECURITY_BLOCK → dap_security_block   (3 intentos fallidos)
      - None               → END                  (código incorrecto, reintento)

    DISEÑO DE RETENCIÓN: Cuando el código es incorrecto pero hay intentos
    disponibles, el nodo actualiza el contador en auth_control y retorna
    sin setear just_completed_step → este edge retorna END → el grafo espera
    otro turno → el nodo OTP vuelve a ejecutarse en el siguiente mensaje.
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.DAP_OTP_SUCCESS:
        return "dap_formalization"
    if just_completed == CompletedStep.DAP_SECURITY_BLOCK:
        return "dap_security_block"

    return END  # Código incorrecto: esperar reintento del usuario


def route_after_dap_formalization(state: FluxState) -> str:
    """
    Decisión de arista post-dap_formalization.
    Solo permite el avance al éxito si el contrato se selló y subió correctamente.
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.DAP_FORMALIZATION_SUCCESS:
        return "dap_completed"

    return END  # Si falló (None), el flujo se detiene por seguridad.
```

---

## Archivo 4 de 4: `workflow.py`

Se hacen **4 cambios quirúrgicos** sobre el archivo existente.

---

### Cambio 4.1 — Importar los nuevos nodos de DAP

**Localiza:**
```python
from app.graph.nodes.deposit import dap_init_node, dap_collect_data_node, dap_investment_engine_node
```

**Reemplaza por:**
```python
from app.graph.nodes.deposit import (
    dap_init_node,
    dap_collect_data_node,
    dap_investment_engine_node,
    dap_pre_approved_node,
    dap_otp_validation_node,
    dap_formalization_node,
    dap_completed_node,
    dap_rejected_policy_node,
    dap_security_block_node,
    dap_closed_by_user_node,
)
```

---

### Cambio 4.2 — Importar las nuevas funciones de ruteo de DAP

**Localiza:**
```python
    # Cuenta Corriente
    route_after_account_collecting_profile,
    route_after_account_evaluation_engine,
    route_after_account_pre_approved,
    route_after_account_otp_validation,
    route_after_account_formalization,
```

**Reemplaza por:**
```python
    # Cuenta Corriente
    route_after_account_collecting_profile,
    route_after_account_evaluation_engine,
    route_after_account_pre_approved,
    route_after_account_otp_validation,
    route_after_account_formalization,
    # Depósito a Plazo
    route_after_dap_collecting_data,
    route_after_dap_investment_engine,
    route_after_dap_pre_approved,
    route_after_dap_otp_validation,
    route_after_dap_formalization,
```

---

### Cambio 4.3 — Registrar los nuevos nodos DAP en `build_graph()`

**Localiza:**
```python
    # ── Depósito a Plazo ─────────────────────────────────────────────
    graph.add_node("dap_init",                   dap_init_node)
    graph.add_node("dap_collect_data",           dap_collect_data_node) # placeholder
    graph.add_node("dap_investment_engine",      dap_investment_engine_node)
```

**Reemplaza por:**
```python
    # ── Depósito a Plazo ─────────────────────────────────────────────
    # Recolección
    graph.add_node("dap_init",                   dap_init_node)
    graph.add_node("dap_collect_data",           dap_collect_data_node)
    # Evaluación y Oferta
    graph.add_node("dap_investment_engine",      dap_investment_engine_node)
    graph.add_node("dap_pre_approved",           dap_pre_approved_node)
    # Formalización y Cierre
    graph.add_node("dap_otp_validation",         dap_otp_validation_node)
    graph.add_node("dap_formalization",          dap_formalization_node)
    graph.add_node("dap_completed",              dap_completed_node)
    # Excepciones
    graph.add_node("dap_rejected_policy",        dap_rejected_policy_node)
    graph.add_node("dap_security_block",         dap_security_block_node)
    graph.add_node("dap_closed_by_user",         dap_closed_by_user_node)
```

---

### Cambio 4.4 — Actualizar el mapa del `add_conditional_edges("welcome", ...)`

Añadir las entradas faltantes de DAP al dict existente.

**Localiza** la sección `# Reanudación de recolección` del dict y añade la entrada DAP faltante:
```python
            "dap_collect_data":            "dap_collect_data",
```
*(Esta entrada ya existe; verificar que sigue presente.)*

**A continuación**, en la sección de **reanudación de oferta/OTP**, añade justo debajo de las entradas de ACCOUNT:
```python
            # Reanudación de oferta/OTP — DAP
            "dap_pre_approved":            "dap_pre_approved",
            "dap_otp_validation":          "dap_otp_validation",
```

**Y en la sección de saltos por éxito**, añade justo debajo de `"dap_investment_engine"`:
```python
            # Saltos por éxito — DAP (desde _SUCCESS_MAP vía P1)
            "dap_formalization":           "dap_formalization",
            "dap_completed":               "dap_completed",
            "dap_rejected_policy":         "dap_rejected_policy",
            "dap_security_block":          "dap_security_block",
            "dap_closed_by_user":          "dap_closed_by_user",
```

**El bloque `add_conditional_edges("welcome", ...)` completo queda así:**
```python
    graph.add_conditional_edges(
        "welcome",
        route_after_welcome,
        {
            # Clasificación
            "intent_router":               "intent_router",
            # Intención directa
            "loan_init":                   "loan_init",
            "account_init":                "account_init",
            "dap_init":                    "dap_init",
            # Reanudación de recolección
            "loan_collecting_profile":     "loan_collecting_profile",
            "loan_collecting_simulation":  "loan_collecting_simulation",
            "account_collecting_profile":  "account_collecting_profile",
            "dap_collect_data":            "dap_collect_data",
            # Reanudación de oferta/OTP — LOAN
            "loan_pre_approved":           "loan_pre_approved",
            "loan_otp_validation":         "loan_otp_validation",
            # Reanudación de oferta/OTP — ACCOUNT
            "account_pre_approved":        "account_pre_approved",
            "account_otp_validation":      "account_otp_validation",
            # Reanudación de oferta/OTP — DAP
            "dap_pre_approved":            "dap_pre_approved",
            "dap_otp_validation":          "dap_otp_validation",
            # Saltos por éxito — LOAN (desde _SUCCESS_MAP vía P1)
            "loan_risk_engine":            "loan_risk_engine",
            "loan_formalization":          "loan_formalization",
            "loan_completed":              "loan_completed",
            "loan_rejected_policy":        "loan_rejected_policy",
            "loan_security_block":         "loan_security_block",
            "loan_closed_by_user":         "loan_closed_by_user",
            # Saltos por éxito — ACCOUNT (desde _SUCCESS_MAP vía P1)
            "account_evaluation_engine":   "account_evaluation_engine",
            "account_formalization":       "account_formalization",
            "account_completed":           "account_completed",
            "account_rejected_policy":     "account_rejected_policy",
            "account_security_block":      "account_security_block",
            "account_closed_by_user":      "account_closed_by_user",
            # Saltos por éxito — DAP (desde _SUCCESS_MAP vía P1)
            "dap_investment_engine":       "dap_investment_engine",
            "dap_formalization":           "dap_formalization",
            "dap_completed":               "dap_completed",
            "dap_rejected_policy":         "dap_rejected_policy",
            "dap_security_block":          "dap_security_block",
            "dap_closed_by_user":          "dap_closed_by_user",
            # General
            "general_response":            "general_response",
        }
    )
```

---

### Cambio 4.5 — Reemplazar la sección de RUTAS DE DEPÓSITO A PLAZO completa

Esta es la corrección más crítica del archivo: las 3 aristas fijas actuales de DAP
(`dap_init → dap_collect_data`, `dap_collect_data → dap_investment_engine`,
`dap_investment_engine → END`) deben convertirse en el flujo condicional completo.

**Localiza:**
```python
    # ──────────────────────────────────────────────────────────────────────────────────────
    # RUTAS DE DEPÓSITO A PLAZO
    # ──────────────────────────────────────────────────────────────────────────────────────
    # DAP: dap_collect_data ya tiene edge fijo a dap_investment_engine
    # (DAP no tiene paso de perfil separado, el salto ocurre diferente)
    # graph.add_edge("dap_collect_data", "dap_investment_engine") — mantener
    graph.add_edge("dap_init",                   "dap_collect_data")
    graph.add_edge("dap_collect_data",           "dap_investment_engine")
    graph.add_edge("dap_investment_engine",      END)
    # General
    graph.add_edge("general_response",          END)
```

**Reemplaza por:**
```python
    # ──────────────────────────────────────────────────────────────────────────────────────
    # RUTAS DE DEPÓSITO A PLAZO
    # ──────────────────────────────────────────────────────────────────────────────────────
    # dap_init → dap_collect_data (NO va a END)
    # Razón: dap_init es un nodo de bienvenida automático que no espera input.
    # Transiciona directamente al primer nodo de recolección en el mismo turno.
    graph.add_edge("dap_init", "dap_collect_data")

    # Recolección de datos (con salto condicional al completarse)
    graph.add_conditional_edges(
        "dap_collect_data",
        route_after_dap_collecting_data,
        {
            "dap_investment_engine": "dap_investment_engine",
            END: END,
        }
    )

    # Motor de inversión (bifurcación: aprobado / rechazado)
    graph.add_conditional_edges(
        "dap_investment_engine",
        route_after_dap_investment_engine,
        {
            "dap_pre_approved":    "dap_pre_approved",
            "dap_rejected_policy": "dap_rejected_policy",
        }
    )

    # Oferta (bifurcación: aceptada / rechazada por usuario)
    graph.add_conditional_edges(
        "dap_pre_approved",
        route_after_dap_pre_approved,
        {
            "dap_otp_validation":  "dap_otp_validation",
            "dap_closed_by_user":  "dap_closed_by_user",
            END: END,  # Espera turno del usuario
        }
    )

    # Validación OTP (bifurcación: éxito / bloqueo de seguridad)
    graph.add_conditional_edges(
        "dap_otp_validation",
        route_after_dap_otp_validation,
        {
            "dap_formalization":   "dap_formalization",
            "dap_security_block":  "dap_security_block",
            END: END,  # Espera turno del usuario (código incorrecto, reintento)
        }
    )

    # Formalización → Completado (bifurcación condicional)
    graph.add_conditional_edges(
        "dap_formalization",
        route_after_dap_formalization,
        {
            "dap_completed": "dap_completed",
            END: END,
        }
    )

    # Nodos terminales → END
    graph.add_edge("dap_completed",       END)
    graph.add_edge("dap_rejected_policy", END)
    graph.add_edge("dap_security_block",  END)
    graph.add_edge("dap_closed_by_user",  END)

    # General
    graph.add_edge("general_response", END)
```

---

### Cambio 4.6 — Actualizar la tabla de nomenclatura (header del `build_graph`)

Añadir las filas faltantes a la tabla del docstring:

```
│ dap_pre_approved             │ DAP_PRE_APPROVED                 │
│ dap_otp_validation           │ DAP_OTP_VALIDATION               │
│ dap_formalization            │ DAP_FORMALIZATION                │
│ dap_completed                │ DAP_COMPLETED                    │
│ dap_rejected_policy          │ DAP_REJECTED_POLICY              │
│ dap_security_block           │ DAP_SECURITY_BLOCK               │
│ dap_closed_by_user           │ DAP_CLOSED_BY_USER               │
```

---

## Checklist de Verificación Post-Implementación

**constants.py**
- [ ] `CompletedStep.DAP_INVESTMENT_SUCCESS` definido como `"DAP_INVESTMENT_SUCCESS"`
- [ ] `CompletedStep.DAP_INVESTMENT_REJECTED` definido como `"DAP_INVESTMENT_REJECTED"`
- [ ] `CompletedStep.DAP_PRE_APPROVED` definido como `"DAP_PRE_APPROVED"`
- [ ] `CompletedStep.DAP_OTP_SUCCESS` definido como `"DAP_OTP_SUCCESS"`
- [ ] `CompletedStep.DAP_FORMALIZATION_SUCCESS` definido como `"DAP_FORMALIZATION_SUCCESS"`
- [ ] `CompletedStep.DAP_SECURITY_BLOCK` definido como `"DAP_SECURITY_BLOCK"`
- [ ] `CompletedStep.DAP_CLOSED_BY_USER` definido como `"DAP_CLOSED_BY_USER"`

**state.py**
- [ ] `DapProgress` tiene los 6 campos: `data_completed`, `investment_engine_completed`, `pre_approval_accepted`, `closed_by_user`, `otp_validated`, `contract_signed`

**edges.py**
- [ ] `_RESUME_MAP` incluye `"DAP_COLLECTING_DATA"` (corregido desde `"DAP_COLLECT_DATA"`), `"DAP_PRE_APPROVED"` y `"DAP_OTP_VALIDATION"`
- [ ] `_VALID_DESTINATION_NODES` incluye los 7 nodos nuevos de DAP
- [ ] `_SUCCESS_MAP["DAP"]` tiene 8 entradas (1 existente + 7 nuevas)
- [ ] `_get_completed_steps_for_product` rama DAP cubre los 6 campos de `DapProgress`
- [ ] Las 5 funciones `route_after_dap_*` están definidas y exportables

**workflow.py**
- [ ] 7 nodos nuevos de DAP importados desde `app.graph.nodes.deposit`
- [ ] 5 funciones nuevas importadas desde `app.graph.edges`
- [ ] 7 nodos nuevos registrados con `graph.add_node(...)`
- [ ] `dap_collect_data` tiene `add_conditional_edges` (NO `add_edge(..., dap_investment_engine)`)
- [ ] `dap_investment_engine` tiene `add_conditional_edges` (NO `add_edge(..., END)`)
- [ ] Los 4 nodos terminales DAP tienen `add_edge(..., END)`
- [ ] El dict del `add_conditional_edges("welcome", ...)` incluye los 7 nuevos destinos DAP

---

## Resumen del Flujo DAP Resultante

```
dap_init
    │ (edge fijo)
    ▼
dap_collect_data ──(loop END)──► [espera usuario]
    │ DAP_DATA
    ▼
dap_investment_engine
    ├── DAP_INVESTMENT_SUCCESS ──► dap_pre_approved ──(loop END)──► [espera usuario]
    │                                  ├── DAP_PRE_APPROVED ──► dap_otp_validation ──(loop END)──► [espera usuario]
    │                                  │                             ├── DAP_OTP_SUCCESS ──► dap_formalization ──► dap_completed ──► END
    │                                  │                             └── DAP_SECURITY_BLOCK ──► dap_security_block ──► END
    │                                  └── DAP_CLOSED_BY_USER ──► dap_closed_by_user ──► END
    └── DAP_INVESTMENT_REJECTED ──► dap_rejected_policy ──► END
```
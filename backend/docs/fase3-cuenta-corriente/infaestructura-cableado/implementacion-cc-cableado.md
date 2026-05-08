# Plan de Implementación Quirúrgica — Producto ACCOUNT (Cuenta Corriente)

> **Principio rector:** Todo lo que existe para `LOAN` debe existir para `ACCOUNT`.
> La única excepción estructural es la ausencia del nodo `collecting_simulation` en ACCOUNT,
> que salta directamente de `ACCOUNT_COLLECTING_PROFILE` a `ACCOUNT_EVALUATION_ENGINE`.

---

## Diagnóstico del Estado Actual

Antes de tocar ningún archivo, este es el inventario exacto de lo que falta vs. lo que ya existe:

| Elemento | Estado actual |
|---|---|
| `CompletedStep.ACCOUNT_PROFILE` | ✅ Existe |
| `CompletedStep.ACCOUNT_EVALUATION_*` / `ACCOUNT_PRE_APPROVED` / etc. | ❌ Faltan 7 constantes |
| `AccountProgress` en `state.py` (solo tiene `profile_completed`) | ⚠️ Incompleta — faltan 5 campos |
| `_RESUME_MAP` (ACCOUNT_PRE_APPROVED, ACCOUNT_OTP_VALIDATION) | ❌ Faltan 2 entradas |
| `_VALID_DESTINATION_NODES` (nodos finales ACCOUNT) | ❌ Faltan 7 nodos |
| `_SUCCESS_MAP["ACCOUNT"]` (solo tiene `ACCOUNT_PROFILE`) | ⚠️ Incompleto — faltan 7 transiciones |
| `_get_completed_steps_for_product` rama ACCOUNT | ⚠️ Incompleta — solo `profile_completed` |
| Funciones `route_after_account_*` (motor, oferta, OTP, formalización) | ❌ Faltan 4 funciones |
| Nodos ACCOUNT registrados en `workflow.py` (pre_approved, otp, etc.) | ❌ Faltan 6 nodos |
| Aristas ACCOUNT en `workflow.py` (account_init → END en lugar de → collecting) | ❌ 1 arista incorrecta + faltan todas las del flujo completo |

---

## Archivo 1 de 4: `constants.py`

### Qué cambiar

Añadir 7 constantes nuevas dentro de `CompletedStep`. El bloque `ACCOUNT_PROFILE` ya existe; el resto va justo debajo.

### Código a insertar

Localiza el bloque actual:
```python
class CompletedStep:
    # ── Recolección (ya existentes) ───────────────────────────
    LOAN_PROFILE    = "LOAN_PROFILE"
    LOAN_SIMULATION = "LOAN_SIMULATION"
    ACCOUNT_PROFILE = "ACCOUNT_PROFILE"   # ← ya existe
    DAP_DATA        = "DAP_DATA"
```

**Reemplaza ese bloque completo por:**

```python
class CompletedStep:
    """
    Valores válidos para session["just_completed_step"].
    Flag volátil: vive exactamente un turno.
    Se setea al completar un paso; se limpia en el return del nodo generador.
    """
    # ── Recolección ───────────────────────────────────────────
    LOAN_PROFILE    = "LOAN_PROFILE"
    LOAN_SIMULATION = "LOAN_SIMULATION"
    ACCOUNT_PROFILE = "ACCOUNT_PROFILE"
    DAP_DATA        = "DAP_DATA"

    # ── Evaluación y Oferta — LOAN ────────────────────────────
    LOAN_RISK_SUCCESS  = "LOAN_RISK_SUCCESS"
    LOAN_RISK_REJECTED = "LOAN_RISK_REJECTED"

    # ── Formalización — LOAN ──────────────────────────────────
    LOAN_PRE_APPROVED          = "LOAN_PRE_APPROVED"
    LOAN_OTP_SUCCESS           = "LOAN_OTP_SUCCESS"
    LOAN_FORMALIZATION_SUCCESS = "LOAN_FORMALIZATION_SUCCESS"

    # ── Excepciones — LOAN ────────────────────────────────────
    LOAN_SECURITY_BLOCK  = "LOAN_SECURITY_BLOCK"
    LOAN_CLOSED_BY_USER  = "LOAN_CLOSED_BY_USER"

    # ── Evaluación y Oferta — ACCOUNT (NUEVOS) ────────────────
    ACCOUNT_EVALUATION_SUCCESS  = "ACCOUNT_EVALUATION_SUCCESS"   # Motor aprobó
    ACCOUNT_EVALUATION_REJECTED = "ACCOUNT_EVALUATION_REJECTED"  # Motor rechazó

    # ── Formalización — ACCOUNT (NUEVOS) ─────────────────────
    ACCOUNT_PRE_APPROVED          = "ACCOUNT_PRE_APPROVED"         # Usuario aceptó
    ACCOUNT_OTP_SUCCESS           = "ACCOUNT_OTP_SUCCESS"          # OTP validado
    ACCOUNT_FORMALIZATION_SUCCESS = "ACCOUNT_FORMALIZATION_SUCCESS" # Contrato sellado

    # ── Excepciones — ACCOUNT (NUEVOS) ────────────────────────
    ACCOUNT_SECURITY_BLOCK  = "ACCOUNT_SECURITY_BLOCK"   # 3 intentos OTP fallidos
    ACCOUNT_CLOSED_BY_USER  = "ACCOUNT_CLOSED_BY_USER"   # Usuario rechazó la oferta
```

> **Nota de precisión:** Los nombres `ACCOUNT_EVALUATION_SUCCESS` y `ACCOUNT_EVALUATION_REJECTED`
> reflejan que el nodo del motor se llama `ACCOUNT_EVALUATION_ENGINE` (no `RISK_ENGINE`).
> Cualquier nodo que setee `just_completed_step` **debe usar exactamente estos strings**.

---

## Archivo 2 de 4: `state.py`

### Qué cambiar

`AccountProgress` solo tiene `profile_completed`. Necesita los 5 campos restantes que espeja
`LoanProgress` (menos `simulation_completed`, que no aplica para ACCOUNT).

### Código a modificar

**Reemplaza el bloque actual:**
```python
class AccountProgress(TypedDict, total=False):
    """Registro histórico de completitud del flujo de cuenta corriente."""
    profile_completed: bool
```

**Por:**
```python
class AccountProgress(TypedDict, total=False):
    """Registro histórico de completitud del flujo de cuenta corriente."""
    profile_completed:          bool   # True cuando account_profile tiene todos los campos
    evaluation_engine_completed: bool  # True cuando el motor de evaluación ya se ejecutó
    pre_approval_accepted:      bool   # True cuando el usuario acepta la tarjeta de transparencia
    closed_by_user:             bool   # True cuando el usuario rechaza la oferta
    otp_validated:              bool   # True cuando el OTP es verificado exitosamente
    contract_signed:            bool   # True cuando el contrato fue firmado digitalmente
```

> **Consistencia con `_get_completed_steps_for_product`:** Las claves definidas aquí
> (`evaluation_engine_completed`, `pre_approval_accepted`, etc.) son exactamente las que
> `edges.py` consulta vía `product_progress.get(...)`. Cualquier discrepancia entre
> esta definición y la lectura en edges produce un `None` silencioso que rompe el ruteo.

---

## Archivo 3 de 4: `edges.py`

Este es el archivo más extenso de modificar. Se hacen **5 cambios quirúrgicos**, ninguno toca el código existente de LOAN.

---

### Cambio 3.1 — `_RESUME_MAP`: añadir nodos que esperan input del usuario

Los nodos que esperan respuesta del usuario entre turnos deben estar en este mapa para que
`route_after_welcome` los reanude correctamente (P2).

**Localiza:**
```python
    # Cuenta Corriente
    "ACCOUNT_INIT":                "account_init",
    "ACCOUNT_COLLECTING_PROFILE":  "account_collecting_profile",
```

**Reemplaza por:**
```python
    # Cuenta Corriente
    "ACCOUNT_INIT":                "account_init",
    "ACCOUNT_COLLECTING_PROFILE":  "account_collecting_profile",
    "ACCOUNT_PRE_APPROVED":        "account_pre_approved",
    "ACCOUNT_OTP_VALIDATION":      "account_otp_validation",
    # NOTA: ACCOUNT_EVALUATION_ENGINE y ACCOUNT_FORMALIZATION son nodos de servicio automáticos.
    # No tienen reanudación por turno: si el proceso se interrumpe en ellos,
    # la reanudación ocurre vía _SUCCESS_MAP desde el paso previo.
```

---

### Cambio 3.2 — `_VALID_DESTINATION_NODES`: registrar nodos ACCOUNT completos

**Localiza:**
```python
    # Cuenta Corriente
    "account_init",
    "account_collecting_profile",
    "account_evaluation_engine",
```

**Reemplaza por:**
```python
    # Cuenta Corriente
    "account_init",
    "account_collecting_profile",
    "account_evaluation_engine",
    "account_pre_approved",
    "account_otp_validation",
    "account_formalization",
    "account_completed",
    "account_rejected_policy",
    "account_security_block",
    "account_closed_by_user",
```

---

### Cambio 3.3 — `_SUCCESS_MAP["ACCOUNT"]`: flujo completo

**Localiza:**
```python
    "ACCOUNT": {
        CompletedStep.ACCOUNT_PROFILE: "account_evaluation_engine",
    },
```

**Reemplaza por:**
```python
    "ACCOUNT": {
        CompletedStep.ACCOUNT_PROFILE:               "account_evaluation_engine",
        CompletedStep.ACCOUNT_EVALUATION_SUCCESS:    "account_pre_approved",
        CompletedStep.ACCOUNT_PRE_APPROVED:          "account_otp_validation",
        CompletedStep.ACCOUNT_OTP_SUCCESS:           "account_formalization",
        CompletedStep.ACCOUNT_FORMALIZATION_SUCCESS: "account_completed",

        CompletedStep.ACCOUNT_EVALUATION_REJECTED:   "account_rejected_policy",
        CompletedStep.ACCOUNT_CLOSED_BY_USER:        "account_closed_by_user",
        CompletedStep.ACCOUNT_SECURITY_BLOCK:        "account_security_block",
    },
```

---

### Cambio 3.4 — `_get_completed_steps_for_product`: rama ACCOUNT completa

**Localiza:**
```python
    elif product == "ACCOUNT":
        if product_progress.get("profile_completed"):
            completed.append(CompletedStep.ACCOUNT_PROFILE)
    elif product == "DAP":
```

**Reemplaza por:**
```python
    elif product == "ACCOUNT":
        # A. Recolección
        if product_progress.get("profile_completed"):
            completed.append(CompletedStep.ACCOUNT_PROFILE)

        # B. Evaluación
        if product_progress.get("evaluation_engine_completed"):
            engine_status = state.get("evaluation_results", {}).get("account_engine", {}).get("status_proceso")
            if engine_status == "PRE_APPROVED":
                completed.append(CompletedStep.ACCOUNT_EVALUATION_SUCCESS)
            else:
                completed.append(CompletedStep.ACCOUNT_EVALUATION_REJECTED)

        # C. Oferta y OTP
        if product_progress.get("pre_approval_accepted"):
            completed.append(CompletedStep.ACCOUNT_PRE_APPROVED)
        elif product_progress.get("closed_by_user"):
            completed.append(CompletedStep.ACCOUNT_CLOSED_BY_USER)

        if product_progress.get("otp_validated"):
            completed.append(CompletedStep.ACCOUNT_OTP_SUCCESS)
        elif state.get("auth_control", {}).get("security_blocked"):
            completed.append(CompletedStep.ACCOUNT_SECURITY_BLOCK)

        # D. Formalización (Final del flujo)
        if product_progress.get("contract_signed"):
            completed.append(CompletedStep.ACCOUNT_FORMALIZATION_SUCCESS)

    elif product == "DAP":
```

---

### Cambio 3.5 — Añadir las 4 funciones de ruteo de ACCOUNT

Ubícate al final del archivo, **después de `route_after_account_collecting_profile`**,
y añade el siguiente bloque completo:

```python
def route_after_account_evaluation_engine(state: FluxState) -> str:
    """
    Decisión de arista post-account_evaluation_engine.

    El motor de evaluación es un nodo de servicio automático: siempre completa
    su trabajo en el mismo turno y emite exactamente uno de dos CompletedStep:
      - ACCOUNT_EVALUATION_SUCCESS  → account_pre_approved
      - ACCOUNT_EVALUATION_REJECTED → account_rejected_policy

    NOTA: Este edge NO tiene rama END porque account_evaluation_engine nunca
    espera input del usuario. Si just_completed_step es None o inesperado,
    se redirige a account_rejected_policy como fallback seguro (evita loop).
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.ACCOUNT_EVALUATION_SUCCESS:
        return "account_pre_approved"
    if just_completed == CompletedStep.ACCOUNT_EVALUATION_REJECTED:
        return "account_rejected_policy"

    # Fallback defensivo: si el motor no emitió señal, redirigir a rechazo
    _routing_logger.warning(
        f"route_after_account_evaluation_engine: just_completed_step='{just_completed}' "
        "inesperado. Redirigiendo a 'account_rejected_policy' como fallback."
    )
    return "account_rejected_policy"


def route_after_account_pre_approved(state: FluxState) -> str:
    """
    Decisión de arista post-account_pre_approved.

    Este nodo espera la decisión del usuario (ACCEPTED / REJECTED).
    La señal viaja en just_completed_step:
      - ACCOUNT_PRE_APPROVED    → account_otp_validation  (usuario aceptó)
      - ACCOUNT_CLOSED_BY_USER  → account_closed_by_user  (usuario rechazó)
      - None                    → END                      (primer turno: espera respuesta)

    REGLA: Si el nodo acaba de generar la tarjeta de transparencia y aún
    no hay respuesta del usuario, just_completed_step será None → END.
    En el siguiente turno, el nodo vuelve a ejecutarse, lee la respuesta
    y emite el CompletedStep correspondiente.
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.ACCOUNT_PRE_APPROVED:
        return "account_otp_validation"
    if just_completed == CompletedStep.ACCOUNT_CLOSED_BY_USER:
        return "account_closed_by_user"

    return END  # Esperar respuesta del usuario


def route_after_account_otp_validation(state: FluxState) -> str:
    """
    Decisión de arista post-account_otp_validation.

    El nodo OTP espera que el usuario ingrese el código.
    La señal viaja en just_completed_step:
      - ACCOUNT_OTP_SUCCESS    → account_formalization    (código correcto)
      - ACCOUNT_SECURITY_BLOCK → account_security_block   (3 intentos fallidos)
      - None                   → END                      (código incorrecto, reintento)

    DISEÑO DE RETENCIÓN: Cuando el código es incorrecto pero hay intentos
    disponibles, el nodo actualiza el contador en auth_control y retorna
    sin setear just_completed_step → este edge retorna END → el grafo espera
    otro turno → el nodo OTP vuelve a ejecutarse en el siguiente mensaje.
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.ACCOUNT_OTP_SUCCESS:
        return "account_formalization"
    if just_completed == CompletedStep.ACCOUNT_SECURITY_BLOCK:
        return "account_security_block"

    return END  # Código incorrecto: esperar reintento del usuario


def route_after_account_formalization(state: FluxState) -> str:
    """
    Decisión de arista post-account_formalization.
    Solo permite el avance al éxito si el contrato se selló y subió correctamente.
    """
    session        = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.ACCOUNT_FORMALIZATION_SUCCESS:
        return "account_completed"

    return END  # Si falló (None), el flujo se detiene por seguridad.
```

---

## Archivo 4 de 4: `workflow.py`

Se hacen **4 cambios quirúrgicos** sobre el archivo existente.

---

### Cambio 4.1 — Importar los nuevos nodos de ACCOUNT

**Localiza:**
```python
from app.graph.nodes.account import account_init_node, account_collecting_profile_node, account_evaluation_engine_node
```

**Reemplaza por:**
```python
from app.graph.nodes.account import (
    account_init_node,
    account_collecting_profile_node,
    account_evaluation_engine_node,
    account_pre_approved_node,
    account_otp_validation_node,
    account_formalization_node,
    account_completed_node,
    account_rejected_policy_node,
    account_security_block_node,
    account_closed_by_user_node,
)
```

---

### Cambio 4.2 — Importar las nuevas funciones de ruteo de ACCOUNT

**Localiza:**
```python
    # Cuenta Corriente
    route_after_account_collecting_profile,
```

**Reemplaza por:**
```python
    # Cuenta Corriente
    route_after_account_collecting_profile,
    route_after_account_evaluation_engine,
    route_after_account_pre_approved,
    route_after_account_otp_validation,
    route_after_account_formalization,
```

---

### Cambio 4.3 — Registrar los nuevos nodos en `build_graph()`

**Localiza:**
```python
    # ── Cuenta Corriente ─────────────────────────────────────────────
    graph.add_node("account_init",               account_init_node)
    graph.add_node("account_collecting_profile", account_collecting_profile_node) # placeholder
    graph.add_node("account_evaluation_engine",  account_evaluation_engine_node)
```

**Reemplaza por:**
```python
    # ── Cuenta Corriente ─────────────────────────────────────────────
    # Recolección
    graph.add_node("account_init",               account_init_node)
    graph.add_node("account_collecting_profile", account_collecting_profile_node)
    # Evaluación y Oferta
    graph.add_node("account_evaluation_engine",  account_evaluation_engine_node)
    graph.add_node("account_pre_approved",       account_pre_approved_node)
    # Formalización y Cierre
    graph.add_node("account_otp_validation",     account_otp_validation_node)
    graph.add_node("account_formalization",      account_formalization_node)
    graph.add_node("account_completed",          account_completed_node)
    # Excepciones
    graph.add_node("account_rejected_policy",    account_rejected_policy_node)
    graph.add_node("account_security_block",     account_security_block_node)
    graph.add_node("account_closed_by_user",     account_closed_by_user_node)
```

---

### Cambio 4.4 — Actualizar el mapa de aristas condicionales del nodo `welcome`

Los nuevos nodos ACCOUNT deben ser destinos válidos para `route_after_welcome` (P1 y P2).

**Localiza el bloque de `add_conditional_edges("welcome", ...)` y añade las entradas faltantes:**

Dentro del dict del `add_conditional_edges`, **bajo la sección de reanudación de ACCOUNT**, añade:
```python
            # Reanudación de oferta/OTP — ACCOUNT
            "account_pre_approved":        "account_pre_approved",
            "account_otp_validation":      "account_otp_validation",
```

Y **bajo la sección de saltos por éxito**, añade:
```python
            # Saltos por éxito — ACCOUNT (desde _SUCCESS_MAP vía P1)
            "account_formalization":       "account_formalization",
            "account_completed":           "account_completed",
            "account_rejected_policy":     "account_rejected_policy",
            "account_security_block":      "account_security_block",
            "account_closed_by_user":      "account_closed_by_user",
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
            # Saltos por éxito — DAP
            "dap_investment_engine":       "dap_investment_engine",
            # General
            "general_response":            "general_response",
        }
    )
```

---

### Cambio 4.5 — Reemplazar la sección de RUTAS DE CUENTA CORRIENTE completa

**Localiza:**
```python
    # ──────────────────────────────────────────────────────────────────────────────────────
    # RUTAS DE CUENTA CORRIENTE
    # ──────────────────────────────────────────────────────────────────────────────────────
    graph.add_edge("account_init", END)
    
    graph.add_conditional_edges(
        "account_collecting_profile",
        route_after_account_collecting_profile,
        {
            "account_evaluation_engine": "account_evaluation_engine",
            END: END,
        }
    )

    graph.add_edge("account_evaluation_engine", END)
```

**Reemplaza por:**
```python
    # ──────────────────────────────────────────────────────────────────────────────────────
    # RUTAS DE CUENTA CORRIENTE
    # ──────────────────────────────────────────────────────────────────────────────────────
    # account_init → account_collecting_profile (NO va a END)
    # Razón: account_init es un nodo de bienvenida automático que no espera input.
    # Transiciona directamente al primer nodo de recolección en el mismo turno.
    graph.add_edge("account_init", "account_collecting_profile")

    # Recolección de perfil (con salto condicional al completarse)
    graph.add_conditional_edges(
        "account_collecting_profile",
        route_after_account_collecting_profile,
        {
            "account_evaluation_engine": "account_evaluation_engine",
            END: END,
        }
    )

    # Motor de evaluación (bifurcación: aprobado / rechazado)
    graph.add_conditional_edges(
        "account_evaluation_engine",
        route_after_account_evaluation_engine,
        {
            "account_pre_approved":    "account_pre_approved",
            "account_rejected_policy": "account_rejected_policy",
        }
    )

    # Oferta (bifurcación: aceptada / rechazada por usuario)
    graph.add_conditional_edges(
        "account_pre_approved",
        route_after_account_pre_approved,
        {
            "account_otp_validation":  "account_otp_validation",
            "account_closed_by_user":  "account_closed_by_user",
            END: END,  # Espera turno del usuario
        }
    )

    # Validación OTP (bifurcación: éxito / bloqueo de seguridad)
    graph.add_conditional_edges(
        "account_otp_validation",
        route_after_account_otp_validation,
        {
            "account_formalization":   "account_formalization",
            "account_security_block":  "account_security_block",
            END: END,  # Espera turno del usuario (código incorrecto, reintento)
        }
    )

    # Formalización → Completado (bifurcación condicional)
    graph.add_conditional_edges(
        "account_formalization",
        route_after_account_formalization,
        {
            "account_completed": "account_completed",
            END: END,
        }
    )

    # Nodos terminales → END
    graph.add_edge("account_completed",      END)
    graph.add_edge("account_rejected_policy", END)
    graph.add_edge("account_security_block",  END)
    graph.add_edge("account_closed_by_user",  END)
```

---

### Cambio 4.6 — Actualizar la tabla de nomenclatura (header del `build_graph`)

Añadir las filas faltantes a la tabla del docstring de `build_graph`:

```
│ account_pre_approved         │ ACCOUNT_PRE_APPROVED             │
│ account_otp_validation       │ ACCOUNT_OTP_VALIDATION           │
│ account_formalization        │ ACCOUNT_FORMALIZATION            │
│ account_completed            │ ACCOUNT_COMPLETED                │
│ account_rejected_policy      │ ACCOUNT_REJECTED_POLICY          │
│ account_security_block       │ ACCOUNT_SECURITY_BLOCK           │
│ account_closed_by_user       │ ACCOUNT_CLOSED_BY_USER           │
```

---

## Checklist de Verificación Post-Implementación

Una vez aplicados todos los cambios, valida cada punto antes de hacer deploy:

**constants.py**
- [ ] `CompletedStep.ACCOUNT_EVALUATION_SUCCESS` definido como `"ACCOUNT_EVALUATION_SUCCESS"`
- [ ] `CompletedStep.ACCOUNT_EVALUATION_REJECTED` definido como `"ACCOUNT_EVALUATION_REJECTED"`
- [ ] `CompletedStep.ACCOUNT_PRE_APPROVED` definido como `"ACCOUNT_PRE_APPROVED"`
- [ ] `CompletedStep.ACCOUNT_OTP_SUCCESS` definido como `"ACCOUNT_OTP_SUCCESS"`
- [ ] `CompletedStep.ACCOUNT_FORMALIZATION_SUCCESS` definido como `"ACCOUNT_FORMALIZATION_SUCCESS"`
- [ ] `CompletedStep.ACCOUNT_SECURITY_BLOCK` definido como `"ACCOUNT_SECURITY_BLOCK"`
- [ ] `CompletedStep.ACCOUNT_CLOSED_BY_USER` definido como `"ACCOUNT_CLOSED_BY_USER"`

**state.py**
- [ ] `AccountProgress` tiene los 6 campos: `profile_completed`, `evaluation_engine_completed`, `pre_approval_accepted`, `closed_by_user`, `otp_validated`, `contract_signed`

**edges.py**
- [ ] `_RESUME_MAP` incluye `"ACCOUNT_PRE_APPROVED"` y `"ACCOUNT_OTP_VALIDATION"`
- [ ] `_VALID_DESTINATION_NODES` incluye los 7 nodos nuevos de ACCOUNT
- [ ] `_SUCCESS_MAP["ACCOUNT"]` tiene 8 entradas (1 existente + 7 nuevas)
- [ ] `_get_completed_steps_for_product` rama ACCOUNT cubre los 6 campos de `AccountProgress`
- [ ] Las 4 funciones `route_after_account_*` nuevas están definidas y exportables

**workflow.py**
- [ ] 7 nodos nuevos de ACCOUNT importados desde `app.graph.nodes.account`
- [ ] 4 funciones nuevas importadas desde `app.graph.edges`
- [ ] 7 nodos nuevos registrados con `graph.add_node(...)`
- [ ] `account_init` apunta a `"account_collecting_profile"` (NO a `END`)
- [ ] `account_evaluation_engine` tiene `add_conditional_edges` (NO `add_edge(..., END)`)
- [ ] Los 4 nodos terminales ACCOUNT tienen `add_edge(..., END)`
- [ ] El dict del `add_conditional_edges("welcome", ...)` incluye los 7 nuevos destinos ACCOUNT

---

## Resumen del Flujo ACCOUNT Resultante

```
account_init
    │ (edge fijo)
    ▼
account_collecting_profile ──(loop END)──► [espera usuario]
    │ ACCOUNT_PROFILE
    ▼
account_evaluation_engine
    ├── ACCOUNT_EVALUATION_SUCCESS ──► account_pre_approved ──(loop END)──► [espera usuario]
    │                                       ├── ACCOUNT_PRE_APPROVED ──► account_otp_validation ──(loop END)──► [espera usuario]
    │                                       │                                  ├── ACCOUNT_OTP_SUCCESS ──► account_formalization ──► account_completed ──► END
    │                                       │                                  └── ACCOUNT_SECURITY_BLOCK ──► account_security_block ──► END
    │                                       └── ACCOUNT_CLOSED_BY_USER ──► account_closed_by_user ──► END
    └── ACCOUNT_EVALUATION_REJECTED ──► account_rejected_policy ──► END
```
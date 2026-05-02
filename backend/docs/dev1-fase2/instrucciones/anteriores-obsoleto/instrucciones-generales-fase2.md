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
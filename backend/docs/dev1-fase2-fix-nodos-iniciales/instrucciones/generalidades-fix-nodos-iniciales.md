# Plan de Implementación: Resolución del "Bucle de Amnesia" y Estabilización de la Fase 2

**Proyecto:** FLUX — Asistente Financiero  
**Versión objetivo:** 2.1  
**Archivos afectados:** `edges.py`, `common.py`, `credit.py`, `workflow.py` + nuevo `common_schemas.py`  
**Archivos inmutables:** `state.py`, `loan_schemas.py`

---

## I. Análisis y Evaluación de la Propuesta

### 1.1 Hallazgos del Análisis de Código

Antes de describir los cambios, se documentan los resultados del análisis de los archivos fuente, incluyendo desviaciones respecto al informe original.

#### Requerimiento 1 — Welcome Silencioso ✅ Aprobado (con precisión)

El `welcome_node` actual siempre emite un `AIMessage`, sobreescribiendo `current_node` a `"WELCOME_NODE"` en cada invocación. La lógica de `is_resumed` ya existe pero **sólo cambia el texto del saludo, no lo elimina**. El informe está en lo correcto: el nodo debe operar en modo silencioso cuando ya hay intención o historial activo.

**Condición de silencio propuesta (refinada):** el nodo no emitirá mensaje cuando se cumpla **cualquiera** de:
- `session.product_intent` es distinto de `None`, o
- `len(messages) > 0` (hay historial — sesión reanudada).

> **Nota de precisión:** el informe señala "si hay intención o historial", lo cual es correcto. La primera condición cubre el caso de clic de botón en sesión nueva; la segunda cubre la reanudación.

#### Requerimiento 2 — Eliminación del Saludo Hardcodeado en `loan_init_node` ✅ Aprobado

El string fijo confirmado en `credit.py` línea 181:
```
"¡Perfecto, {first_name}! Vamos a revisar tu solicitud de Crédito de Consumo..."
```
El nodo ya tiene `_flux_generator` instanciado y `SYSTEM_PROMPT_GENERATION_PROFILE` definido. Se puede reutilizar el mismo generador, con un prompt de bienvenida distinto (`SYSTEM_PROMPT_INIT_LOAN`) para no contaminar el flujo de recolección.

#### Requerimiento 3 — Blindar `edges.py` con jerarquía `current_node` ✅ Aprobado

La función `route_after_welcome` actual sólo evalúa `product_intent`. La Prioridad 1 (Reanudación basada en `current_node`) está **completamente ausente**. Esto es la causa raíz del bucle.

**Mapa de reanudación requerido** (inferido de `workflow.py` y `state.py`):
| `current_node` | Destino de reanudación |
|---|---|
| `LOAN_INIT` | `loan_init` |
| `LOAN_COLLECTING_PROFILE` | `loan_collecting_profile` |
| `LOAN_COLLECTING_SIMULATION` | `loan_collecting_simulation` |
| `ACCOUNT_INIT` | `account_init` |
| `ACCOUNT_COLLECTING_PROFILE` | `account_collecting_profile` |
| `DAP_INIT` | `dap_init` |
| `DAP_COLLECT_DATA` | `dap_collect_data` |

#### Requerimiento 4 — `common_schemas.py` ✅ Aprobado con modificación metodológica

El informe sugiere usar `LLM.with_structured_output()` para el `intent_router_node`, igual que los nodos de crédito. Sin embargo, el `intent_router_node` actual ya funciona con clasificación de texto plano y validación de categorías, lo cual es robusto para 4 categorías simples. La mejora con Pydantic agrega:
- Documentación del contrato de extracción.
- Validación en tiempo de parseo.
- Campo `confianza` para logging (opcional pero útil).
- Uniformidad metodológica con `loan_schemas.py`.

Se aprueba el cambio; el schema será `IntentExtractionSchema`.

#### Requerimiento 5 — Script Simulador ✅ Aprobado, con arquitectura expandida

El informe describe el simulador conceptualmente. Este plan lo convierte en código concreto.

---

### 1.2 Hallazgos Propios (Críticos — Sección VII)

> ⚠️ Se detectaron 2 brechas críticas no cubiertas en el informe original que deben resolverse en este mismo sprint. Ver **Sección VII**.

---

## VII. Hallazgos Propios — Brechas Críticas

> Estas brechas no están cubiertas en el informe original y bloquearían la implementación si no se resuelven en paralelo.

### 🔴 Hallazgo 1 (Crítico): `loan_collecting_profile_node` no está registrado en `workflow.py`

**Evidencia:** `credit.py` tiene implementado `loan_collecting_profile_node` (y presumiblemente `loan_collecting_simulation_node`), pero `workflow.py` sólo registra `loan_init` y `loan_risk_engine`, con un edge directo entre ellos:

```python
# workflow.py actual — INCORRECTO
graph.add_edge("loan_init", "loan_risk_engine")  # Salta toda la recolección
```

Esto significa que actualmente **el flujo de crédito nunca recolecta datos**: va de `loan_init` directamente al motor de riesgo, que necesita `collecting_data` para funcionar.

**Acción requerida:** Registrar todos los nodos del flujo de crédito y reconectar las aristas. La topología correcta es:

```
loan_init
    ↓
loan_collecting_profile  ←─ (reanudación desde aquí en turnos siguientes)
    ↓ (cuando profile está completo — avance silencioso)
loan_collecting_simulation
    ↓ (cuando sim está completo — avance silencioso)
loan_risk_engine
    ↓
END
```

**Cambios en `workflow.py`:**

```python
# Importar los nodos que faltan
from app.graph.nodes.credit import (
    loan_init_node,
    loan_collecting_profile_node,     # AGREGAR
    loan_collecting_simulation_node,   # AGREGAR (si existe)
    loan_risk_engine_node,
)

# Registrar nodos que faltan
graph.add_node("loan_collecting_profile",    loan_collecting_profile_node)
graph.add_node("loan_collecting_simulation", loan_collecting_simulation_node)

# Reconectar aristas (reemplazar la línea incorrecta)
# ELIMINAR: graph.add_edge("loan_init", "loan_risk_engine")
# AGREGAR:
graph.add_edge("loan_init",                  "loan_collecting_profile")
graph.add_edge("loan_collecting_profile",    "loan_collecting_simulation")
graph.add_edge("loan_collecting_simulation", "loan_risk_engine")
graph.add_edge("loan_risk_engine",           END)
```

**Nota:** Si `loan_collecting_profile` puede avanzar silenciosamente (sin mensaje del usuario), LangGraph lo manejará dentro del mismo `invoke()`. No se necesita un edge condicional para esto; el nodo simplemente retorna sin `messages` y el grafo continúa.

---

### 🟡 Hallazgo 2 (Importante): `update_application_semaphores` con `"BYPASSED"` puede fallar

**Evidencia:** El `Paso 2` propone usar `node_status="BYPASSED"` en el modo silencioso del `welcome_node`. Si el enum en Supabase no tiene este valor, generará un error.

**Acción:** Usar `"SUCCESS"` para el semáforo de welcome en modo silencioso, o agregar `"BYPASSED"` al enum en la migración de DB correspondiente. Se recomienda la primera opción para no bloquear el sprint.

```python
# Alternativa segura en welcome_node modo silencioso:
if application_id:
    update_application_semaphores(
        application_id,
        current_node_id="WELCOME_NODE",
        node_status="SUCCESS",   # No "BYPASSED" hasta validar el enum
        engine_status="PENDING"
    )
```

---

## VIII. Orden de Implementación Recomendado

| # | Paso | Archivo(s) | Dependencias |
|---|---|---|---|
| 1 | Crear `common_schemas.py` | Nuevo archivo | Ninguna |
| 2 | Blindar `edges.py` | `edges.py` | Paso 1 (mapa de reanudación) |
| 3 | Registrar nodos en `workflow.py` | `workflow.py` | Paso 2 (mapa de edges) |
| 4 | `welcome_node` silencioso | `common.py` | Paso 2 |
| 5 | `intent_router_node` estructurado | `common.py` | Paso 1 |
| 6 | `loan_init_node` Llamada Tipo B | `credit.py` | Pasos 4 y 5 |
| 7 | Script Simulador | `scripts/` | Pasos 2–6 |
| 8 | Tests unitarios por paso | `tests/` | Cada paso |

---

## IX. Checklist de Validación Final

Antes de considerar el sprint completo, ejecutar:

```bash
# 1. Todos los tests unitarios
pytest tests/unit/ -v

# 2. Tests de integración del simulador
pytest tests/integration/test_simulator_scenarios.py -v

# 3. Escenario de Happy Path en consola (validación visual)
python scripts/simulate_conversation.py --scenario happy_path_loan

# 4. Escenario de reanudación (el más crítico)
python scripts/simulate_conversation.py --scenario resume_mid_loan
```

**Criterios de aceptación:**

- [ ] `route_after_welcome` devuelve `loan_collecting_profile` cuando `current_node=LOAN_COLLECTING_PROFILE`.
- [ ] `welcome_node` no emite mensaje cuando `product_intent="LOAN"`.
- [ ] `welcome_node` no emite mensaje cuando `len(messages) > 0`.
- [ ] `loan_init_node` llama al LLM y no usa el string fijo.
- [ ] `loan_init_node` deja `current_node="LOAN_COLLECTING_PROFILE"` al retornar.
- [ ] El simulador no reporta violaciones en el escenario `resume_mid_loan`.
- [ ] `loan_collecting_profile_node` está registrado en `workflow.py`.
- [ ] `IntentExtractionSchema` normaliza intenciones inválidas a `GENERAL`.
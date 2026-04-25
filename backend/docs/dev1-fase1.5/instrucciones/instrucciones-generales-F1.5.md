# Plan de Migración: FluxState → Arquitectura de Namespaces
**Proyecto:** FLUX — Chatbot Financiero  
**Fase:** Transición Fase 1 → Fase 2  
**Objetivo:** Refactorizar `state.py` desde diccionarios genéricos (`collected_data`, `control_flags`) hacia TypedDicts anidados por namespace, garantizando escalabilidad multi-producto y cero colisión de datos.

---

## Índice

1. [Paso 1 — Nuevo `state.py`](#paso-1)
2. [Paso 2 — Refactor de `common.py`](#paso-2)
3. [Paso 3 — Patrón de Reset en Nodos INIT](#paso-3)
4. [Paso 4 — Mapeo de Motores a `evaluation_results`](#paso-4)
5. [Paso 5 — Verificación de `edges.py`](#paso-5)

---

## Resumen Ejecutivo de la Migración

| Paso | Archivo Principal | Cambio | Riesgo |
|------|------------------|--------|--------|
| 1 | `state.py` | Reescritura completa (v1→v2) | 🔴 Alto — es la fuente de verdad |
| 2 | `common.py` | Agregar escritura de `preparation_data` + `_calculate_age` | 🟡 Medio |
| 3 | `credit.py`, `account.py`, `deposit.py` | Agregar reset de namespace en INIT | 🟢 Bajo |
| 4 | `credit.py`, `deposit.py` | Stubs de motores con patrón de escritura correcto | 🟢 Bajo |
| 5 | `edges.py`, `workflow.py` | Sin cambios (verificación) | 🟢 Ninguno |

### Invariantes que Deben Mantenerse en Todo Momento

1. `messages` con reducer `add_messages` — intocable.
2. `session["product_intent"]` — GPS del grafo, solo escrito por `intent_router_node`.
3. Checkpointer de Supabase — solo cambia `state.py`, LangGraph maneja el resto automáticamente.
4. Un producto nunca escribe en el namespace de otro.
5. `preparation_data` es de solo lectura para todos los nodos excepto `welcome_node`.

### Secuencia de Ejecución Recomendada

```
Paso 1 → pytest test_state_v2.py ✓
Paso 2 → pytest test_welcome_node_v2.py ✓
Paso 3 → pytest test_init_nodes_v2.py ✓
Paso 4 → pytest test_engines_v2.py ✓
Paso 5 → pytest test_integration_v2.py ✓
         → smoke test manual con el servidor levantado
```
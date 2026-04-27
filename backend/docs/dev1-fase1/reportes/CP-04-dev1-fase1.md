# CHECKPOINT 04 — Core del Grafo LangGraph
## Fase 1 — Dev 1

### Estado del Paso: 🟡 En Progreso (4.1 Validado)

### Reporte de Sub-pasos:

#### Sub-paso 4.1 — Definir el StateSchema en `app/graph/state.py`
- **Estado:** ✅ Completado
- **Acciones:**
    - [x] Validar importaciones y sintaxis.
    - [x] Verificar cumplimiento de Regla de Oro #1 (State como única fuente de verdad).
    - [x] Confirmar campos requeridos (`messages`, `user_data`, `session`, `collected_data`, `control_flags`).
- **Resultado:** Código validado. El esquema cumple con la estructura `TypedDict` necesaria para LangGraph y respeta la jerarquía de datos definida en el plan.

#### Sub-paso 4.2 — Implementar `WELCOME_NODE` e `INTENT_ROUTER_NODE`
- **Estado:** ✅ Completado
- **Acciones:**
    - [x] Validar lógica de bienvenida (nueva vs reanudada).
    - [x] Validar prompt de clasificación de intenciones.
    - [x] Verificar actualización de GPS (`current_node`) en DB.
- **Resultado:** Implementados en `nodes/common.py`. La lógica de saludo diferencia correctamente sesiones reanudadas. El clasificador de intenciones usa `get_chat_model()` y valida contra el set de categorías permitido. Se integra correctamente la actualización del nodo en Supabase.

#### Sub-paso 4.3 — Implementar `app/graph/edges.py`
- **Estado:** ✅ Completado
- **Acciones:**
    - [x] Validar ruteo condicional post-bienvenida.
    - [x] Validar ruteo condicional post-router.
- **Resultado:** Implementadas funciones `route_after_welcome` y `route_after_intent`. El ruteo condicional permite el "fast-track" a nodos de producto si la intención ya está persistida en el estado, optimizando la experiencia en sesiones reanudadas.

#### Sub-paso 4.4 — Crear stubs de nodos de producto
- **Estado:** ✅ Completado
- **Acciones:**
    - [x] Validar stubs en `credit.py`, `account.py`, `deposit.py`.
    - [x] Validar `general_response_node` en `common.py`.
- **Resultado:** Archivos de producto creados con stubs funcionales que confirman la intención detectada. El nodo `general_response_node` ha sido ubicado correctamente al final de `common.py`, proporcionando una salida elegante para intenciones no específicas.

#### Sub-paso 4.5 — Compilar el Grafo en `app/graph/workflow.py`
- **Estado:** ✅ Completado
- **Acciones:**
    - [x] Validar construcción del `StateGraph`.
    - [x] Validar integración del checkpointer de Supabase.
    - [x] Confirmar exportación de `compiled_graph` (vía `get_active_graph`).
- **Resultado:** Grafo definido y compilado exitosamente. Se aplicó **Lazy Initialization** para evitar errores de `AsyncConnectionPool` en tiempo de importación, permitiendo tests síncronos de la estructura del grafo.

---

### 📌 Registro de Elementos Provisionales (Stubs)
Se deja constancia de los elementos creados en este paso que actúan como placeholders y deberán ser desarrollados o expandidos en fases posteriores:

| Elemento | Archivo | Nodo en Grafo | Estado | Fase de Desarrollo |
|----------|---------|---------------|--------|-------------------|
| `loan_init_node` | `nodes/credit.py` | `loan_init` | Stub | **Fase 2** (Implementación Completa) |
| `account_init_node` | `nodes/account.py` | `account_init` | Stub | **Fase 3** |
| `dap_init_node` | `nodes/deposit.py` | `dap_init` | Stub | **Fase 3** |
| `general_response_node`| `nodes/common.py` | `general_response`| Funcional | Base para expansión de FAQs |
| `route_after_welcome` | `edges.py` | N/A | Lógica Base | Expandible con nuevos productos |
| `AsyncPostgresSaver` | `infra/checkpointer.py` | N/A | Pendiente de test | Validar compatibilidad con flujo sync |

---

---

### 🧠 Decisiones Técnicas y Resolución de Conflictos

#### 1. Implementación de Lazy Initialization en `workflow.py`
Se refactorizó la exposición del grafo mediante `get_active_graph()` para evitar el error `RuntimeError: AsyncConnectionPool open with no running loop` durante el tiempo de importación.

#### 2. Manejo Robust de Respuestas Gemini (`common.py`)
Se detectó que `ChatVertexAI` devolvía contenido en formato `list` en lugar de `str`. Se implementó un extractor robusto que normaliza la respuesta del LLM antes de la clasificación de intenciones.

#### 3. Compatibilidad con Windows y PgBouncer (`checkpointer.py` y `tests`)
- **Event Loop:** Se configuró `WindowsSelectorEventLoopPolicy` en los tests para permitir operaciones asíncronas con `psycopg`.
- **PgBouncer (Supabase):** Se desactivaron los *Prepared Statements* mediante `prepare_threshold: None` y el parámetro de sesión `options="-c prepare_threshold=0"`, resolviendo el error `DuplicatePreparedStatement` crítico para la persistencia del estado.

---

### ✅ REPORTE DE CHECKPOINT 4 (Final)
*Paso 4 completado tras validación exhaustiva de infraestructura y orquestación.*

| Prueba | Nombre | Resultado | Interpretación |
|--------|--------|-----------|----------------|
| 4.A | Validación del StateSchema y Grafo | ✅ PASSED | Estructura y compilación verificadas. |
| 4.B | Clasificación de Intenciones | ✅ PASSED | Gemini clasifica LOAN, ACCOUNT, DAP y GENERAL. |
| 4.C | Persistencia del Estado | ✅ PASSED | Estado guardado y recuperado en Supabase. |

**Estado General:** 🟢 **PASO 4 COMPLETADO**

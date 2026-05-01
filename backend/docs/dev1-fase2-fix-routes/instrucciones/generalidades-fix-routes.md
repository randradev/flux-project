# Plan de Implementación: Ruteo Consciente de Progreso
**Proyecto:** FLUX — Asistente Financiero  
**Versión objetivo:** 2.2  
**Archivos afectados:** `state.py`, `credit.py`, `edges.py`, `workflow.py`, `common.py`  
**Problema raíz:** `loan_collecting_profile` retorna sin mensajes al completarse, el grafo termina en `END`, y el siguiente turno reanuda en el mismo nodo → bucle infinito de recolección.

---

## I. Validación Técnica de Viabilidad

### 1.1 Diagnóstico del Bucle Infinito

El ciclo se reproduce así con el código actual:

```
Turno N (usuario completa perfil):
  welcome (silencioso)
  → route_after_welcome: current_node="LOAN_COLLECTING_PROFILE" → P1 → loan_collecting_profile
  → loan_collecting_profile: profile completo → sets profile_just_completed=True, sin mensajes
  → Edge: loan_collecting_profile → END  ← aquí nace el problema
  → State persiste: current_node="LOAN_COLLECTING_PROFILE", profile_just_completed=True

Turno N+1 (usuario escribe cualquier cosa):
  welcome (silencioso)
  → route_after_welcome: current_node="LOAN_COLLECTING_PROFILE" → P1 → loan_collecting_profile
  → loan_collecting_profile: profile sigue completo → sin mensajes → END
  → ∞ (bucle)
```

La causa raíz es que `current_node` no avanza cuando el nodo hace "avance silencioso", porque termina en `END` en vez de avanzar al nodo siguiente. La solución tiene dos capas complementarias que el requerimiento describe correctamente:

- **Capa intra-turno (Fase 4):** arista condicional que, cuando el perfil se completa, salta a `loan_collecting_simulation` en el **mismo** turno, actualizando `current_node` antes de terminar.
- **Capa inter-turno de seguridad (Fase 3):** `_SUCCESS_MAP` en `route_after_welcome` que, si de algún modo el estado quedó con `progress.loan.profile_completed = True` y `current_node` todavía apunta al nodo de perfil, salta al siguiente nodo en vez de repetirlo.

### 1.2 Viabilidad por Fase

| Fase | Viabilidad | Observaciones |
|---|---|---|
| 1 — Esquema de State | ✅ Viable | `state.py` admite extensión de `SessionData` sin romper sesiones existentes si se usan `total=False`. |
| 2 — Refactorización de flags | ✅ Viable | `profile_just_completed` está en pocos puntos; la migración es quirúrgica. |
| 3 — `_SUCCESS_MAP` + P0/P1 | ✅ Viable | Se integra sobre `_RESUME_MAP` existente como capa superior. |
| 4 — Aristas condicionales intra-turno | ✅ Viable sin restricciones | LangGraph actualiza el state entre nodos dentro del mismo `invoke()`. Las funciones de edge leen el state post-nodo. La preocupación de "silencio de grafo" al saltar a `loan_risk_engine` queda eliminada por el invariante: el motor siempre enruta a un nodo generador de respuesta. |

### 1.3 ~~Hallazgo Crítico: Lectura de `just_completed_step` en Salto Intra-turno~~ → Resuelto por Invariante de Motor

~~Cuando `loan_collecting_profile` salta a `loan_collecting_simulation` en el mismo turno, el nodo de simulación **no tiene un mensaje nuevo del usuario** para su propia Llamada A.~~

**Este apartado queda resuelto por la siguiente decisión de arquitectura:**

> **Invariante de Motor:** `loan_risk_engine` (y cualquier nodo lógico futuro) **nunca apunta a `END`**. Su salida está mapeada obligatoriamente a nodos generadores de respuesta: `loan_pre_approved`, `loan_rejected_policy`, o `loan_service_error`. Esto garantiza que todo ciclo de ejecución termina con al menos un `AIMessage` en `state["messages"]`, eliminando el riesgo de "silencio de grafo" en cualquier escenario de salto intra-turno.

La regla de diseño sobre **omitir la Llamada A en salto intra-turno** se mantiene intacta y sigue siendo necesaria (el mensaje del usuario ya fue procesado por el nodo anterior), pero ya no es una precaución de seguridad ante posibles silencios: es simplemente eficiencia de procesamiento.

### 1.4 Orden de Limpieza de `just_completed_step`

La flag debe sobrevivir exactamente hasta que el generador (Llamada B) la consuma. El punto de limpieza correcto es **dentro del mismo `return` dict del nodo que invoca la Llamada B**. Así:

```
loan_collecting_profile retorna: just_completed_step = "LOAN_PROFILE"
  ↓ (salto intra-turno)
loan_collecting_sim_node lee: just_completed_step == "LOAN_PROFILE" → omite Llamada A
loan_collecting_sim_node invoca Llamada B con contexto de celebración
loan_collecting_sim_node retorna: just_completed_step = None  ← limpieza en el mismo return
```

Si la simulación también se completa en el mismo turno (el usuario dio monto y plazo junto con el último dato del perfil), la misma lógica aplica en cascada: `loan_collecting_sim_node` setea `just_completed_step = "LOAN_SIMULATION"`, y el salto intra-turno continúa hacia `loan_risk_engine`. Gracias al **invariante de motor** (§1.3), `loan_risk_engine` siempre enruta a `loan_pre_approved` o `loan_rejected_policy`, garantizando que la cascada completa termina con un mensaje visible para el usuario sin excepciones.

---

## VII. Orden de Implementación y Dependencias

| # | Paso | Archivos | Depende de |
|---|---|---|---|
| 1 | Crear `constants.py` | Nuevo | — |
| 2 | Actualizar `state.py` | `state.py` | Paso 1 |
| 3 | Actualizar `_build_sim_generation_context` en `credit.py` | `credit.py` | Pasos 1, 2 |
| 4 | Actualizar `loan_collecting_profile_node` | `credit.py` | Pasos 1, 2, 3 |
| 5 | Actualizar `loan_collecting_sim_node` | `credit.py` | Paso 4 |
| 6 | Actualizar `common.py` (init progress) | `common.py` | Paso 2 |
| 7 | Agregar `_SUCCESS_MAP` y helpers a `edges.py` | `edges.py` | Pasos 1, 2 |
| 8 | Refactorizar `route_after_welcome` en `edges.py` | `edges.py` | Paso 7 |
| 9 | Agregar funciones de edge intra-turno a `edges.py` | `edges.py` | Paso 1 |
| 10 | Actualizar `workflow.py` con edges condicionales | `workflow.py` | Pasos 8, 9 |
| 11 | Suite de tests unitarios | `tests/unit/` | Cada paso |
| 12 | Test de integración intra-turno | `tests/integration/` | Todos los anteriores |

---

## VIII. Checklist de Aceptación Final

```bash
# Todos los tests
pytest tests/unit/ tests/integration/ -v

# Escenario crítico en consola
python scripts/simulate_conversation.py --scenario happy_path_loan
```

- [ ] `loan_collecting_profile` escribe `just_completed_step = "LOAN_PROFILE"` y `progress.loan.profile_completed = True` al completarse.
- [ ] `loan_collecting_sim_node` omite la Llamada A cuando `just_completed_step == "LOAN_PROFILE"`.
- [ ] `loan_collecting_sim_node` retorna `just_completed_step = None` tras invocar Llamada B.
- [ ] `route_after_loan_collecting_profile` retorna `"loan_collecting_simulation"` cuando `just_completed_step == "LOAN_PROFILE"`.
- [ ] `route_after_loan_collecting_sim` retorna `"loan_risk_engine"` cuando `just_completed_step == "LOAN_SIMULATION"` (habilitado sin restricciones por el invariante de motor).
- [ ] **[INVARIANTE]** `loan_risk_engine` nunca tiene edge a `END`. Su arista condicional solo puede resolver a `loan_pre_approved` o `loan_rejected_policy`.
- [ ] **[INVARIANTE]** `loan_pre_approved` y `loan_rejected_policy` generan al menos un `AIMessage` antes de retornar. Todo ciclo de ejecución termina con un mensaje visible.
- [ ] El turno donde se completa el perfil genera exactamente **un mensaje** de Flux (celebración + pregunta de monto), no cero ni dos.
- [ ] El turno siguiente (usuario da el monto) no incluye instrucción de celebración de perfil en el contexto de Llamada B.
- [ ] `route_after_welcome` con `progress.loan.profile_completed = True` y `current_node = "LOAN_COLLECTING_PROFILE"` devuelve `"loan_collecting_simulation"` (P1 activo como red de seguridad).
- [ ] `route_after_welcome` con `product_intent = "ACCOUNT"` estando en flujo `LOAN_*` devuelve `"account_init"` (P0 activo).
- [ ] No hay referencias a `profile_just_completed` en ningún archivo.
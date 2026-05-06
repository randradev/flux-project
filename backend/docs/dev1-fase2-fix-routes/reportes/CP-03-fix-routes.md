# Reporte de Checkpoint: CP-03-fix-routes

**Fase:** 3 — `_SUCCESS_MAP` y Jerarquía de Prioridades en `edges.py`  
**Estado:** COMPLETADO  
**Fecha:** 2026-05-01  

---

## 1. Hitos Logrados
- **Import de Constantes:** Se corrigió el `NameError` importando `CompletedStep` desde `app.graph.constants`.
- **Implementación de _SUCCESS_MAP:** Se definió el mapa de éxito para todos los productos (Loan, Account, Dap), proporcionando la capa de seguridad inter-turno.
- **Nueva Jerarquía de Ruteo (P0-P4):**
  - **P0 (Cambio de Producto):** Detecta si el usuario quiere cambiar de producto a mitad de camino.
  - **P1 (Salto por Éxito):** Reasigna la navegación si el paso actual ya está completo en el historial.
  - **P2 (Reanudación):** Comportamiento estándar de vuelta al nodo activo.
  - **P3 (Intención Directa):** Manejo de clics de botones.
  - **P4 (Sin Señales):** Clasificación vía LLM.
- **Fallback de Seguridad:** Se implementó un ruteo de recuperación hacia `intent_router` en caso de detectar un nodo destino inválido en el mapa de éxito.

## 2. Resultados de Testing
Se ejecutó la suite `tests/unit/test_edges_v22.py` (9 tests) cubriendo todos los niveles de prioridad:
- **P0 - Cambio de producto:** ✅ PASSED.
- **P1 - Salto por éxito (Perfil completo):** ✅ PASSED.
- **P1 - Salto por éxito (Simulación completa):** ✅ PASSED.
- **P1 - Fallback de seguridad (Nodo inválido):** ✅ PASSED.
- **P2 - Reanudación estándar:** ✅ PASSED.
- **P3 - Intención directa:** ✅ PASSED.
- **P4 - Clasificación general:** ✅ PASSED.

## 3. Hallazgos y Observaciones (Auditoría)
- **Consistencia de Nombres:** Se verificó que los IDs de nodo en `_SUCCESS_MAP` y `_RESUME_MAP` coincidan con la nomenclatura snake_case requerida por LangGraph.
- **Seguridad Inter-turno:** La lógica P1 actúa como un "cortafuegos" efectivo: si el usuario recarga la página o el grafo renace tras un error de red, el sistema detectará el progreso guardado y lo llevará al paso siguiente automáticamente.

## 4. Estado de los Invariantes
- **Invariante de Motor:** Fortalecido. La seguridad inter-turno garantiza que el grafo nunca se quede atascado en un nodo cuya tarea ya fue completada.
- **Regla de Prioridad:** El orden P0-P4 es lógico y prioriza la intención explícita del usuario sobre el estado guardado.

## 5. Pendientes para Fase 4
- Implementación de aristas condicionales en `workflow.py`.
- Integración final del intra-turno (Phase 2) con el inter-turno (Phase 3).

---
*Firma: Antigravity — QA & Architecture Oversight*

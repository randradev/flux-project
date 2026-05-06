# Reporte de Checkpoint: CP-02-fix-routes

**Fase:** 2 — Refactorización de Nodos y Helpers en `credit.py`  
**Estado:** COMPLETADO  
**Fecha:** 2026-05-01  

---

## 1. Hitos Logrados
- **Escritura Dual en Perfil:** `loan_collecting_profile_node` implementa correctamente la persistencia en `progress` y la señal volátil en `just_completed_step`.
- **Lógica de Salto en Simulación:** `loan_collecting_sim_node` detecta saltos intra-turno y omite la Llamada A (extractor) para evitar sobre-procesamiento.
- **Limpieza de Flags:** Se verificó que `just_completed_step` se limpia correctamente en los retornos de los nodos tras ser consumida.
- **Eliminación de Legado:** Se eliminaron todas las referencias funcionales a `profile_just_completed`.

## 2. Resultados de Testing
Se creó y ejecutó la suite `tests/unit/test_credit_nodes_v22.py` (5 tests):
- **Test 2.A (Dual Flag Profile):** ✅ PASSED.
- **Test 2.B (Skip Extractor on Jump):** ✅ PASSED.
- **Test 2.C (Clean Flag post-Gen):** ✅ PASSED.
- **Test 2.D (Dual Flag Sim Completion):** ✅ PASSED.
- **Test 2.E (Incomplete Profile handling):** ✅ PASSED.

## 3. Hallazgos y Observaciones (Auditoría)

### ✅ SOLUCIONADO: Construcción de Contexto Restaurada
Se corrigió la función `_build_sim_generation_context` restaurando los bloques de datos (`known_lines`, `new_lines`, `missing_labels`). El LLM ahora recibe el contexto completo para generar respuestas precisas.

## 4. Estado de los Invariantes
- **Invariante de Motor:** El ruteo intra-turno es ahora consciente del estado gracias a `just_completed_step`.
- **Regla de Consumo:** La flag volátil se limpia adecuadamente, garantizando que no se procesen saltos fantasmas en turnos posteriores.

## 5. Pendientes para Fase 3
- Definición de `_SUCCESS_MAP` en `edges.py`.
- Lógica de ruteo inter-turno basada en `progress`.

---
*Firma: Antigravity — QA & Architecture Oversight*

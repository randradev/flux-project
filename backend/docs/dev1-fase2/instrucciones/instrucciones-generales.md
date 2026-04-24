# PLAN DE IMPLEMENTACIÓN — FASE 2: EL PRIMER VUELO
## Dev 1 (AI Orchestrator) · Crédito de Consumo
### Proyecto FLUX · Backend LangGraph

---

> **Documento de Referencia de Ejecución para Agente Antigravity**
>
> **Regla de Oro de Operación:** El agente debe respetar estrictamente cada punto de pausa (`⛔ DETENCIÓN OBLIGATORIA`), solicitar confirmación explícita del desarrollador antes de continuar, y nunca realizar cambios fuera del scope del sub-paso activo. Ante cualquier ambigüedad técnica no contemplada en este plan, el agente debe **reportar y preguntar**, nunca asumir ni proceder.

---

## ÍNDICE DE PASOS

| Paso | Nombre | Archivos Principales |
|------|--------|---------------------|
| 1 | Motor de Riesgo Financiero | `app/modules/credit_eng.py` |
| 2 | Capa de Persistencia para Crédito | `app/infra/supabase.py` |
| 3 | Nodos de Recolección de Datos | `app/graph/nodes/credit.py` |
| 4 | Nodo Motor de Riesgo (Servicio) | `app/graph/nodes/credit.py` |
| 5 | Nodos de Oferta y Validación OTP | `app/graph/nodes/credit.py` |
| 6 | Nodos de Cierre y Manejo de Errores | `app/graph/nodes/credit.py` |
| 7 | Integración del Grafo | `app/graph/edges.py`, `app/graph/workflow.py` |

---

## CONVENCIONES DEL PLAN

### Nomenclatura de Archivos de Checkpoint
Cada paso crea y actualiza su propio archivo:
```
/backend/tests/fase2-dev1/CP-01-dev1-fase2.md   ← Paso 1
/backend/tests/fase2-dev1/CP-02-dev1-fase2.md   ← Paso 2
...
/backend/tests/fase2-dev1/CP-07-dev1-fase2.md   ← Paso 7
```

### Protocolo de Sub-paso
Al completar cada sub-paso, el agente debe:
1. Agregar al `CP-0X-dev1-fase2.md` activo un reporte del sub-paso completado.
2. Declarar explícitamente cualquier decisión técnica adoptada.
3. Emitir la frase literal: **"Sub-paso X.Y completado. Solicito confirmación para continuar con Sub-paso X.Z."**

### Verificación de Nomenclatura (Mandato Universal)
En **cada** sub-paso, antes de escribir o modificar cualquier código, el agente debe verificar y documentar en el CP:
- Nombres de funciones: `snake_case`, describen acción + sujeto (ej. `calculate_credit_score`, no `calc_score` ni `creditScore`).
- Nombres de nodos en el State: deben coincidir exactamente con los definidos en `credito-datos.md` (ej. `LOAN_INIT`, `LOAN_RISK_ENGINE`).
- Claves de `collected_data`: deben coincidir con los nombres del modelo de datos (ej. `renta`, `antiguedad_laboral`, `monto_solicitado`).
- Campos del State: jamás se crean nuevas claves en `FluxState` sin aprobación; toda escritura va a `collected_data` (dict libre) o `control_flags` (dict libre).
- Nombres de tablas y columnas de Supabase: deben coincidir exactamente con `modelo-datos.md`.

### Restricciones Técnicas Absolutas
1. **`with_structured_output` es obligatorio** en todos los nodos de recolección LLM (Collecting Profile, Collecting Simulation). No se acepta parseo manual de strings.
2. **`financial_applications` debe actualizarse** en cada nodo de servicio (LOAN_INIT, LOAN_RISK_ENGINE, LOAN_FORMALIZATION, LOAN_COMPLETED, y todos los nodos de error). Mínimo obligatorio: `current_node_id` + `node_status`.
3. **Los eventos SSE `node_transition` deben preservarse**: cada nodo debe actualizar `session["current_node"]` en el State para que el generador de streaming los emita automáticamente.
4. **`state.py` es sagrado**: el agente no puede modificar `FluxState`, `UserData` ni `SessionData`. Toda información nueva del flujo de crédito va en `collected_data` (TypedDict libre).
5. **Rama de Git**: todos los commits de esta fase van en la rama `feat/fase2-dev1/credito-consumo`.

---

## CIERRE DE LA FASE 2 — Dev 1

Al completar todos los pasos, el agente debe:

1. **Consolidar todos los CPs** en un resumen ejecutivo en el archivo `tests/fase2-dev1/RESUMEN-FASE2-DEV1.md`.

2. **Lista de Mocks Activos** (pendientes de reemplazo por Dev 3):
   - `_mock_generate_otp()` y `_mock_send_otp_email()` en `nodes/credit.py`.
   - `_mock_generate_pdf()` en `nodes/credit.py`.

3. **Contratos de Interfaz a comunicar:**
   - Al **Dev 2 (FE):** Protocolo de mensajes `TRANSPARENCY_CARD`, `OTP_INPUT_WIDGET`, `COMPLETION_CARD` y el protocolo `OFFER_ACCEPTED`/`OFFER_REJECTED`.
   - Al **Dev 3 (Secure):** Protocolo de hashing SHA-256 para OTP (usando `hashlib`), contrato de llamada a `pdf_factory.generate_loan_contract()`.

4. **Pull Request a `main`:** El PR debe pasar el checklist:
   - [ ] El servidor FastAPI levanta sin errores.
   - [ ] Los 7 Checkpoints tienen todos sus tests en verde.
   - [ ] Todos los nodos actualizan `session["current_node"]`.
   - [ ] Todos los nodos de servicio actualizan `financial_applications`.
   - [ ] No hay strings hardcodeados que debieran ser FKs a catálogos.
   - [ ] `state.py` no fue modificado.

5. Commit final: `chore: cerrar fase2 dev1 - flujo completo crédito de consumo`

⛔ **DETENCIÓN FINAL.** Presentar al desarrollador el resumen de la Fase 2 y solicitar revisión del PR antes del merge a `main`.

---

*Documento generado para uso exclusivo del agente Antigravity bajo supervisión del Dev 1 (Human). Versión: 1.0 · FLUX Phase 2.*
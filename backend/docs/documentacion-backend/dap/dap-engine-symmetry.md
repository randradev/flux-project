# Informe de Requerimientos de Simetría: Motor de Inversión DAP

Este documento define las especificaciones técnicas para la implementación del motor de inversión del producto **Depósito a Plazo (DAP)**, asegurando la simetría arquitectónica con el motor de evaluación de `ACCOUNT` (`account_eng.py`) y su nodo integrador.

## 1. Arquitectura del Módulo (`modules/dap_eng.py`)

El motor debe ser una **función pura** encapsulada en una clase, sin dependencias directas del `State` de LangGraph.

### Estructura de la Clase `DapEngine`
- **Constructor (`__init__`)**: Debe recibir `preparation_data: dict` y `dap_params: dict`.
- **Atributos de Instancia**: Debe inicializar atributos (ej: `monto_final`, `ganancia_neta`, `tasa_aplicada`) con valores por defecto para que sean accesibles desde el bloque `except` del nodo en caso de rechazo tardío.
- **Método `run()`**: Orquestador que ejecuta la evaluación y puebla los atributos de la instancia.
- **Método `evaluate()` (estático)**: Contiene la lógica core. Debe retornar un diccionario compatible con `DapEngineResult`.

### Manejo de Excepciones (Simetría de Dominio)
Debe implementar las mismas clases de excepción que `ACCOUNT`:
1. **`PolicyRejectionError(Exception)`**: Se lanza cuando el usuario no cumple reglas de negocio (ej: monto menor al mínimo, plazo fuera de rango). Debe transportar un `motivo` (ej: `ERR_MONTO_MINIMO`).
2. **`EngineCalculationError(Exception)`**: Se lanza ante fallos técnicos o datos faltantes críticos que la recolección no filtró.

---

## 2. Requerimientos del Nodo (`dap_investment_engine_node`)

El nodo actúa como un adaptador/wrapper del motor. Debe seguir el patrón exacto de `account_evaluation_engine_node`.

### Flujo de Operación
1. **Extracción**: Obtener `preparation_data`, `dap_params` y el namespace de resultados `investment_results`.
2. **Invocación Protegida**:
   - Ejecutar `engine.run()` dentro de un bloque `try-except`.
   - **Catch `PolicyRejectionError`**: Capturar el motivo y formatear un `engine_result` con `status_proceso: "REJECTED"`.
   - **Catch `Exception`**: Capturar errores inesperados, loguear con prefijo `[ERROR-ENGINE]` y retornar `status_proceso: "ERROR"`.
3. **Semáforos de Supabase**:
   - Actualizar mediante `update_application_semaphores`.
   - `engine_status` debe ser `"SUCCESS"` siempre que no sea un error técnico (`ERROR`).
4. **Persistencia de Progreso**:
   - Si el resultado es satisfactorio, marcar `investment_engine_completed: True` en el objeto de progreso de la sesión (`session["progress"]["dap"]`).
5. **Flags de Salida**:
   - Usar `just_completed_step` para comunicar el resultado a `edges.py`.
   - Éxito: `CompletedStep.DAP_INVESTMENT_SUCCESS`.
   - Rechazo/Error: `CompletedStep.DAP_INVESTMENT_REJECTED`.

---

## 3. Checklist de Simetría (Puntos Críticos)

| Elemento | Requerimiento de Simetría |
| :--- | :--- |
| **Input Mapping** | `preparation_data` (EDAD) + `dap_params` (MONTO/PLAZO/MONEDA). |
| **Output Storage** | Los resultados deben guardarse en `state["evaluation_results"]["dap_engine"]`. |
| **Status Process** | Debe usar obligatoriamente los literales `"PRE_APPROVED"`, `"REJECTED"` o `"ERROR"`. |
| **Atomicidad** | Un único `return` al final del nodo (excepto en los catches que interrumpen el flujo). |
| **Logging** | Mantener el prefijo de debug: `[DEBUG-DAP-ENGINE]`. |

## 4. Diferencias Aceptables (Específicas de DAP)
- **Lógica de Cálculo**: Mientras `ACCOUNT` asigna categorías y líneas de crédito, `DAP` calculará rentabilidades basadas en el monto y el plazo.
- **Campos de Resultado**: El diccionario de salida contendrá campos como `tasa_anual`, `tasa_periodo`, `monto_final` y `fecha_vencimiento_estimada`, en lugar de categorías de tarjeta.

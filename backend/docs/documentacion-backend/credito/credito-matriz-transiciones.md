### Matriz de Transiciones: Crédito de Consumo

| Estado Origen | Estado Destino (Éxito) | Llave de Paso (Condición) | Estado Destino (Fallo/Desvío) | Motivo del Desvío/Fallo |
| :--- | :--- | :--- | :--- | :--- |
| **`LOAN_INIT`** | `LOAN_COLLECTING_PROFILE` | Datos recuperados de DB exitosamente. | `SERVICE_ERROR` | Error de conexión con la Base de Datos. |
| **`LOAN_COLLECTING_PROFILE`** | `LOAN_COLLECTING_SIMULATION` | Renta, Antigüedad y Estudios capturados. | *(Se mantiene)* | Datos incompletos en el chat. |
| **`LOAN_COLLECTING_SIMULATION`** | `LOAN_RISK_ENGINE` | Monto y Plazo capturados. | *(Se mantiene)* | Datos de simulación incompletos. |
| **`LOAN_RISK_ENGINE`** | `LOAN_PRE_APPROVED` | `status_proceso: PRE_APPROVED` (Capacidad de pago y Scoring OK). | `LOAN_REJECTED_POLICY` | `status_proceso: REJECTED_POLICY` (ERR_EDAD, ERR_RENTA, ERR_ANTIGUEDAD, ERR_SCORING, ERR_CAPACIDAD_PAGO). |
| **`LOAN_RISK_ENGINE`** | `LOAN_PRE_APPROVED` | N/A | `SERVICE_ERROR` | `status_proceso: ERROR_TECHNICAL` (Fallo matemático o de conexión). |
| **`LOAN_PRE_APPROVED`** | `LOAN_OTP_VALIDATION` | Evento: `ACCEPTED` (Clic en botón "Aceptar"). | `LOAN_CLOSED_BY_USER` | Evento: `REJECTED` (Clic en botón "Rechazar"). |
| **`LOAN_OTP_VALIDATION`** | `LOAN_FORMALIZATION` | `otp_status: VERIFIED`. | `LOAN_SECURITY_BLOCK` | `otp_status: BLOCKED` (3 intentos fallidos). |
| **`LOAN_OTP_VALIDATION`** | `LOAN_FORMALIZATION` | N/A | *(Se mantiene)* | `otp_status: FAILED` (Código erróneo, intentos < 3). |
| **`LOAN_FORMALIZATION`** | `LOAN_COMPLETED` | `contract_status: SIGNED_AND_STAMPED`. | `SERVICE_ERROR` | `contract_status: GENERATION_FAILED` (Error en ReportLab/Hash). |
| **`LOAN_REJECTED_POLICY`** | `END` | Mensaje de rechazo enviado según `motivo_rechazo`. | N/A | Fin de flujo por política de riesgo. |
| **`LOAN_SECURITY_BLOCK`** | `END` | Registro de `block_timestamp` y aviso de seguridad. | N/A | Fin de flujo por sospecha de fraude. |
| **`LOAN_CLOSED_BY_USER`** | `END` | Registro de analítica (`monto_aprobado`, `cuota_mensual`) y despedida. | N/A | Fin de flujo por decisión del cliente. |
| **`LOAN_COMPLETED`** | `END` | Entrega de PDF y visualización de `hash_sha256`. | N/A | Fin de flujo exitoso. |
# Contrato de Interfaz Frontend | Fase 2 Dev 2

Este contrato describe los datos que el frontend puede consumir para renderizar el flujo de Credito de Consumo sin calcular reglas financieras en React.

## Eventos SSE soportados

El frontend mantiene compatibilidad con fase 1:

- `message`
- `node_transition`
- `done`
- `error`

Para fase 2, `node_transition` puede traer campos adicionales. Tambien se aceptan eventos equivalentes mientras incluyan alguno de los campos de estado descritos abajo.

```json
{
  "type": "node_transition",
  "node": "LOAN_PRE_APPROVED",
  "product_intent": "LOAN",
  "application_id": "uuid",
  "node_status": "SUCCESS",
  "engine_status": "COMPLETED",
  "document_status": "PENDING",
  "evaluation_results": {
    "loan_engine": {
      "status_proceso": "PRE_APPROVED",
      "monto_aprobado": 5000000,
      "plazo_aprobado": 24,
      "tasa_interes_mensual": 0.012,
      "cuota_mensual": 235000,
      "cae": 0.153946,
      "ctc": 5640000,
      "total_intereses": 640000
    }
  }
}
```

## Nodos de credito esperados

- `LOAN_INIT`
- `LOAN_COLLECTING_PROFILE`
- `LOAN_COLLECTING_SIMULATION`
- `LOAN_RISK_ENGINE`
- `LOAN_PRE_APPROVED`
- `LOAN_OTP_VALIDATION`
- `LOAN_FORMALIZATION`
- `LOAN_COMPLETED`
- `LOAN_REJECTED_POLICY`
- `LOAN_SECURITY_BLOCK`
- `LOAN_CLOSED_BY_USER`

## Acciones enviadas desde la UI

Mientras no exista un endpoint dedicado de acciones, los widgets envian mensajes controlados por `/api/v1/chat`:

- Aceptar oferta: `ACEPTAR_OFERTA_CREDITO`
- Rechazar oferta: `RECHAZAR_OFERTA_CREDITO`
- OTP: el codigo numerico de 6 digitos como mensaje del usuario.

## Campos opcionales consumidos

El frontend puede leer estos campos si llegan por SSE:

- `application_id`
- `node_status`
- `engine_status`
- `document_status`
- `evaluation_results.loan_engine`
- `risk_results`
- `offer_data.loan`
- `auth_control`
- `flow_result`

Los nombres camelCase equivalentes tambien son tolerados por la capa de adaptacion del frontend.

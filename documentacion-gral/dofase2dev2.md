# dofase2dev2

Documento de contexto e instrucciones para trabajar en `fase2-dev2` sobre la branch activa `feat/fase2-dev2`.

## 1. Fuentes revisadas

Se revisaron los 6 archivos base de `documentacion-gral`:

- `flux.md`
- `arquitectura.md`
- `arquitectura-diagrama.md`
- `branding.md`
- `modelo-datos.md`
- `plan-implementacion.md`

Tambien se reviso el frontend actual en `frontend/src` para contrastarlo contra el alcance de `fase1/dev2`.

## 2. Contexto de la app FLUX

FLUX es una app de banca digital conversacional para Chile. Su objetivo es reemplazar formularios financieros tradicionales por una experiencia guiada por chat, donde un asistente ayuda al usuario desde la intencion inicial hasta la evaluacion, oferta, validacion y formalizacion legal de productos financieros.

La app no debe comportarse como un chat generico. El centro del sistema es un grafo de estados persistente: cada nodo representa un hito de negocio y el frontend funciona como el GPS visual de ese avance.

Productos MVP:

- Credito de Consumo: scoring, riesgo, tasa, cuota, CAE, OTP y contrato.
- Cuenta Corriente: apertura segmentada por renta, estudios y antiguedad.
- DAP: simulacion de inversion por monto, moneda y plazo.

Capas principales:

- Frontend React: pinta el estado, conversa por chat y renderiza widgets interactivos.
- Backend FastAPI: expone endpoints REST/SSE, valida JWT y conecta la UI con LangGraph.
- LangGraph + Gemini/Vertex AI: clasifica intenciones, extrae entidades y decide transiciones.
- Modulos de negocio: motores de credito, cuenta, DAP, seguridad y documentos.
- Supabase: Auth, Postgres, historial, solicitudes, checkpoints y Storage.

Regla clave para Dev 2: el frontend no inventa estados ni condiciones de negocio. Lee el estado que emite el backend o que persiste `financial_applications`, y desde eso mueve el Progress Monitor, widgets y cierres.

## 3. Fases y responsabilidades de los 3 devs

## Fase 1: Cimientos y Modularizacion

Objetivo: que el sistema lata y que el frontend quede ordenado.

Dev 1 - AI / Backend:

- Montar FastAPI, entorno, settings y endpoints base.
- Integrar Supabase, Auth JWT, historial y persistencia de conversaciones.
- Configurar Vertex AI/Gemini.
- Crear StateSchema, nodos base, router de intencion, welcome node y workflow inicial.
- Exponer `/chat` con streaming y `/history` para recuperar conversaciones.

Dev 2 - Frontend / UX:

- Separar el frontend en `components`, `hooks`, `services` y estado global.
- Eliminar mockdata como fuente principal.
- Crear `services/api.js` y leer streaming SSE con `fetch` + reader.
- Implementar Login/Signup con Supabase Auth.
- Proteger rutas del chat.
- Conectar Sidebar de historial a `/history`.
- Enviar JWT en cada request.
- Mostrar visualmente en que nodo va el grafo.
- Agregar opcion de borrar conversaciones previas cuando exista soporte real.

Dev 3 - Trust / Fulfillment:

- Crear bases de OTP.
- Preparar generacion de PDF con ReportLab.
- Preparar hashing SHA-256.
- Integrar Supabase Storage.
- Dejar modulos de seguridad/documentos listos para ser llamados por Dev 1.

## Fase 2: Primer Vuelo - Credito de Consumo

Objetivo: completar el primer flujo de producto punta a punta.

Dev 1 - AI / Backend:

- Implementar nodos de credito: `LOAN_INIT`, `LOAN_COLLECTING_PROFILE`, `LOAN_COLLECTING_SIMULATION`, `LOAN_RISK_ENGINE`, `LOAN_PRE_APPROVED`, `LOAN_OTP_VALIDATION`, `LOAN_FORMALIZATION`, `LOAN_COMPLETED`.
- Agregar nodos de excepcion: `LOAN_REJECTED_POLICY`, `LOAN_SECURITY_BLOCK`, `LOAN_CLOSED_BY_USER`.
- Usar extraccion estructurada para renta, antiguedad, estudios, monto y plazo.
- Ejecutar motor de riesgo y persistir resultados.
- Configurar aristas condicionales para avanzar, repreguntar o cerrar.

Dev 2 - Frontend / UX:

- Adaptar el Flux Progress Monitor al flujo de credito.
- Mapear IDs backend a etiquetas de usuario.
- Marcar pasos como completados, activos o pendientes segun `current_node/current_step`.
- Crear la Tarjeta de Transparencia para `LOAN_PRE_APPROVED`.
- Renderizar monto aprobado, tasa, cuota y CAE desde resultados reales del backend.
- Agregar acciones "Aceptar Oferta" y "Rechazar/Cerrar".
- Crear widget OTP de 6 digitos con estados de error y bloqueo.
- Mostrar cierres para `LOAN_REJECTED_POLICY` y `LOAN_SECURITY_BLOCK`.

Dev 3 - Trust / Fulfillment:

- Persistir OTP hasheado en Supabase.
- Manejar TTL, reintentos y envio simulado/API.
- Automatizar generacion de contrato cuando OTP este verificado.
- Mapear datos finales a PDF.
- Persistir hash y Storage path.
- Probar que nunca se genera PDF sin OTP verificado.

## Fase 3: Expansion y Blindaje

Objetivo: reutilizar lo anterior para Cuenta/DAP y pulir el MVP completo.

Dev 1 - AI / Backend:

- Implementar ramas definitivas de Cuenta Corriente y DAP.
- Integrar productos en el grafo maestro.
- Agregar nodos transversales: RAG, ambiguedad, global end y service error handler.
- Centralizar manejo de errores tecnicos.

Dev 2 - Frontend / UX:

- Implementar visor de contratos PDF.
- Mostrar sello de integridad con hash SHA-256.
- Agregar transiciones, skeletons y estados de carga especificos.
- Completar dashboard de historial y perfil.
- Mostrar exito final con estados visuales profesionales.

Dev 3 - Trust / Fulfillment:

- Implementar Security Watchdog.
- Bloquear usuario/solicitud tras intentos fallidos.
- Endurecer PDF y Storage privado con URLs firmadas.
- Optimizar latencia de PDF y hash.

## 4. Auditoria del frontend actual contra fase1/dev2

Veredicto general: cumple la mayor parte del alcance de `fase1/dev2`, con una brecha clara en borrado real de conversaciones y algunas oportunidades de endurecimiento antes de fase 2.

Cumplido:

- Arquitectura modular: existen `frontend/src/components`, `hooks`, `services`, `context` y `constants`.
- Estado global: `AuthContext` y `FluxContext` centralizan sesion, historial, conversacion activa, errores y envio.
- Pantalla de registro: `RegisterPage.jsx` existe y usa Supabase Auth.
- Login Supabase: `AuthContext.jsx` usa `supabase.auth.signInWithPassword`, `signUp`, `signOut` y recupera sesion.
- JWT en requests: `services/api.js` agrega `Authorization: Bearer <accessToken>`.
- Servicio API: `services/api.js` encapsula `/api/v1/chat`, `/api/v1/history` y `/api/v1/history/{conversationId}`.
- Streaming SSE: `streamChat()` usa `response.body.getReader()`, `TextDecoder`, buffer SSE y callbacks por evento.
- Historial real: `FluxContext` llama `fetchConversationHistory()` y `fetchConversationMessages()`.
- Progress Monitor fase 1: `ProcessPanel.jsx` mapea `WELCOME_NODE`, `INTENT_ROUTER` y nodos stub/resultados a estados visuales.
- Mockdata principal removida: no se ve `INITIAL_CHATS` ni `PRODUCTS` en `src`; la app consume historial/backend.

Parcial o pendiente:

- Borrado de conversaciones: `Sidebar.jsx` muestra un boton deshabilitado y texto indicando que queda pendiente hasta que el backend exponga endpoint. Por lo tanto, no cumple completamente la tarea "Agregar opcion de borrar conversaciones previas" si se exige funcionalidad real.
- Contrato de fase 2: el frontend actual solo entiende eventos `message`, `node_transition`, `done` y `error`. Para widgets de credito necesitara aceptar payloads de oferta, OTP, status de solicitud o consultar un endpoint de aplicacion.
- Nombres de estado: fase 1 actual usa `currentNode`; la documentacion habla de `current_step/current_node_id`. Para fase 2 conviene normalizar un adaptador que soporte ambos.

## 5. Instrucciones para ejecutar fase2-dev2

Branch esperada:

```bash
git branch --show-current
```

Debe responder:

```bash
feat/fase2-dev2
```

Instalar y levantar frontend:

```bash
cd frontend
npm install
npm run dev
```

URL esperada:

```bash
http://127.0.0.1:5173
```

Compilar antes de cerrar cambios:

```bash
cd frontend
npm run build
```

Variables requeridas en `frontend/.env.local`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=<url_supabase>
VITE_SUPABASE_ANON_KEY=<anon_key_supabase>
VITE_AUTH_REDIRECT_TO=http://127.0.0.1:5173
```

Backend requerido para probar integracion:

```bash
cd backend
python main.py
```

La API debe exponer:

- `POST /api/v1/chat`
- `GET /api/v1/history`
- `GET /api/v1/history/{conversation_id}`

## 6. Plan recomendado para Dev 2 en fase 2

Paso 1 - Extender constantes de flujo:

- Reemplazar `PHASE_ONE_STEPS` como unica fuente por un mapa `PRODUCT_STEPS`.
- Agregar `PRODUCT_STEPS.LOAN` con:
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

Paso 2 - Adaptar estado global:

- En `FluxContext.jsx`, guardar no solo `currentNode`, sino tambien:
  - `applicationId`
  - `nodeStatus`
  - `engineStatus`
  - `documentStatus`
  - `riskResults` o `evaluationResults.loan_engine`
  - `offerData.loan`
  - `authControl`
  - `flowResult`
- Mantener compatibilidad con el contrato fase 1, donde solo llega `node_transition`.

Paso 3 - Crear widgets:

- Crear `frontend/src/components/widgets/LoanOfferCard.jsx`.
- Crear `frontend/src/components/widgets/OtpInput.jsx`.
- Crear `frontend/src/components/widgets/FlowClosure.jsx`.
- Renderizarlos desde el panel de chat o un area de componentes dinamicos cuando el nodo actual lo exija.

Paso 4 - Tarjeta de Transparencia:

- Activar cuando `currentNode === "LOAN_PRE_APPROVED"`.
- Leer datos desde `evaluation_results.loan_engine`, `risk_results` u `offer_data.loan`, segun el contrato que entregue Dev 1.
- Mostrar:
  - monto aprobado
  - plazo aprobado
  - tasa mensual
  - cuota mensual
  - CAE
  - CTC / total intereses si viene disponible
- No calcular valores financieros en el frontend.

Paso 5 - Acciones de oferta:

- Encapsular acciones en helpers, por ejemplo:
  - `sendLoanOfferAccepted()`
  - `sendLoanOfferRejected()`
  - `sendOtpCode(code)`
- Mientras no exista endpoint dedicado, enviar mensajes controlados al chat como accion de usuario.
- No hardcodear strings repartidos en componentes; mantenerlos en una sola capa.

Paso 6 - OTP:

- Activar cuando `currentNode === "LOAN_OTP_VALIDATION"`.
- Input de 6 digitos, solo numeros.
- Deshabilitar submit si el codigo no tiene 6 digitos.
- Mostrar intentos restantes o error si el backend lo informa.
- Si llega `LOAN_SECURITY_BLOCK`, bloquear input y mostrar cierre de seguridad.

Paso 7 - Excepciones y cierres:

- `LOAN_REJECTED_POLICY`: mostrar rechazo explicativo y motivo si viene en `flowResult`.
- `LOAN_SECURITY_BLOCK`: mostrar bloqueo por seguridad.
- `LOAN_CLOSED_BY_USER`: mostrar cierre voluntario.
- `LOAN_COMPLETED`: preparar el cierre para fase 3, aunque el PDF completo pueda quedar como stub.

Paso 8 - Verificacion:

- Ejecutar `npm run build`.
- Probar login real con Supabase.
- Probar historial.
- Probar stream fase 1 para asegurar no romper compatibilidad.
- Probar un stream fase 2 mockeado o real con nodos `LOAN_*`.
- Verificar responsive desktop/mobile del Progress Monitor y widgets.

## 7. Contrato minimo que Dev 2 necesita de Dev 1

Para que fase 2 sea robusta, el frontend necesita que el stream o un endpoint de detalle entregue alguno de estos formatos:

Opcion A - SSE extendido:

```json
{
  "type": "node_transition",
  "node": "LOAN_PRE_APPROVED",
  "product_intent": "LOAN",
  "application_id": "uuid",
  "node_status": "SUCCESS",
  "engine_status": "COMPLETED",
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

Opcion B - Endpoint de aplicacion:

```bash
GET /api/v1/applications/{application_id}
```

Debe retornar `current_node_id`, `node_status`, `engine_status`, `document_status`, estado de negocio y resultados del producto.

Sin uno de estos dos contratos, Dev 2 puede construir la UI, pero no podra poblarla con datos reales de oferta ni OTP.

## 8. Guardrails para esta branch

- No modificar `backend/app/graph/state.py` desde Dev 2 sin aprobacion de Dev 1.
- No calcular scoring, tasas, CAE ni cuotas en React.
- No usar mockdata como fuente final; solo fixtures temporales para desarrollar widgets.
- Mantener compatibilidad con fase 1: login, historial y SSE basico deben seguir funcionando.
- Documentar cualquier payload nuevo en `frontend/documentacion-frontend/contratos`.
- Antes de commit: `npm run build`.

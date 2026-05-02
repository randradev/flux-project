# Resumen real y objetivo del proyecto flux-project-main

Fecha de revision: 2026-04-27  
Proposito de este archivo: entregar contexto preciso a otra IA para interpretar el backend actual de `flux-project-main` y evaluar un frontend ubicado en otra carpeta.

Nota importante: este resumen fue construido desde el codigo y archivos reales del repositorio. No usa como fuente el archivo `intermain.md`.

---

## 1. Descripcion general

`flux-project-main` es un monorepo para FLUX, una aplicacion de banca digital conversacional. El proyecto busca que un usuario pueda iniciar conversaciones sobre productos financieros y que un backend con FastAPI, LangGraph, Supabase y Vertex AI clasifique la intencion y orqueste flujos por producto.

Estado real actual: el backend implementa la base de Fase 1. Tiene API FastAPI, autenticacion con JWT de Supabase, creacion/reanudacion de conversaciones, streaming SSE, persistencia de mensajes y un grafo LangGraph minimo. Los flujos reales de credito, cuenta corriente y deposito a plazo aun no estan implementados: existen como stubs de entrada.

El frontend incluido en este repositorio es una maqueta funcional local en React. No consume todavia el backend real, no usa Supabase Auth SDK y no procesa SSE. Para evaluar un frontend externo, el contrato que importa es el backend descrito en este documento, no la implementacion mock del frontend local.

---

## 2. Estructura principal del repositorio

```text
flux-project-main/
  README.md
  intermain.md                    # resumen anterior; no usar como fuente tecnica
  intermain2.md                   # este resumen
  backend/
    main.py                       # app FastAPI, CORS, routers, /health
    requirements.txt              # dependencias Python
    app/
      config.py                   # settings desde .env
      api/
        deps.py                   # autenticacion Bearer JWT Supabase
        v1/
          chat.py                 # POST /api/v1/chat con StreamingResponse SSE
          docs.py                 # GET /api/v1/history y /history/{conversation_id}
      graph/
        state.py                  # FluxState TypedDict
        workflow.py               # construccion y compilacion LangGraph
        edges.py                  # rutas condicionales
        nodes/
          common.py               # welcome, intent_router, general_response
          credit.py               # loan_entry_node stub
          account.py              # account_entry_node stub
          deposit.py              # deposit_entry_node stub
      infra/
        supabase.py               # clientes Supabase y helpers DB
        gemini_client.py          # wrapper Vertex AI / Gemini
        embeddings.py             # stub RAG, retorna lista vacia
        checkpointer.py           # AsyncPostgresSaver
        threading.py              # thread_id = conversation_id
      modules/
        credit_eng.py             # vacio
        account_eng.py            # vacio
        eco_service.py            # vacio
        security.py               # vacio
        pdf_factory.py            # vacio
    migrations/                   # SQL de modelo de datos y seed
    docs/                         # documentacion backend, instrucciones y reportes
    tests/fase1-dev1/             # tests de Fase 1
  frontend/
    package.json                  # React/Vite solamente
    src/main.jsx                  # UI mock con estado local
    src/styles.css
    documentacion-frontend/
      contratos/contrato-interfaz-fase1.md
  documentacion-gral/
    arquitectura.md
    modelo-datos.md
    plan-implementacion.md
    branding.md
    flux.md
```

---

## 3. Stack real declarado

Backend:
- Python 3.10+
- FastAPI 0.115.0
- Uvicorn 0.30.6
- pydantic-settings 2.4.0
- LangGraph 0.2.39
- langchain-core 0.3.15
- langchain-google-vertexai 2.0.4
- google-cloud-aiplatform 1.70.0
- Supabase 2.7.4
- langgraph-checkpoint-postgres 2.0.2
- psycopg 3.2.1
- reportlab 4.2.2, declarado pero sin modulo implementado
- pandas 2.2.3
- pytest, pytest-asyncio, httpx

Frontend local:
- React 19
- React DOM 19
- Vite 7
- @vitejs/plugin-react
- No aparece `@supabase/supabase-js`.
- No aparece Axios.
- No hay implementacion real de consumo del backend.

---

## 4. Configuracion requerida del backend

`backend/app/config.py` carga variables desde `.env` en la carpeta `backend`.

Variables requeridas:

```text
GOOGLE_CLOUD_PROJECT_ID
GOOGLE_CLOUD_LOCATION
GOOGLE_APPLICATION_CREDENTIALS
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
DATABASE_URL
```

Valores por defecto:

```text
GOOGLE_CLOUD_LOCATION=us-central1
DEBUG=false
APP_NAME=FLUX-Backend
APP_VERSION=0.1.0
```

Si falta una variable requerida, el backend falla al importar `settings`.

---

## 5. Backend FastAPI real

Archivo principal: `backend/main.py`.

La app:
- Crea una instancia `FastAPI`.
- Configura CORS para:
  - `http://localhost:3000`
  - `http://localhost:5173`
- Registra routers:
  - `chat.router` con prefijo `/api/v1`
  - `docs.router` con prefijo `/api/v1`
- Expone `GET /health`.
- En Windows ajusta el event loop a `WindowsSelectorEventLoopPolicy`.

Endpoint de salud:

```http
GET /health
```

Respuesta:

```json
{
  "status": "alive",
  "service": "FLUX-Backend",
  "version": "0.1.0",
  "engine": "LangGraph + VertexAI",
  "debug_mode": false
}
```

Observacion: `main.py` define `app`, pero no contiene un bloque `uvicorn.run(...)`. Para levantarlo normalmente se debe usar algo como `uvicorn main:app --reload` desde `backend`, salvo que exista otro script externo.

---

## 6. Autenticacion y perfil de usuario

Archivo: `backend/app/api/deps.py`.

Todos los endpoints de chat e historial requieren header:

```http
Authorization: Bearer <jwt_supabase>
```

Flujo real:
1. `get_current_user()` usa `HTTPBearer`.
2. Valida el token llamando a `supabase_admin.auth.get_user(token)`.
3. Extrae `user.id` y `user.email` desde Supabase Auth.
4. `get_verified_user()` busca un perfil de negocio por email en tabla `users`.
5. Si no existe perfil en `users`, responde 403.
6. Si el estado del usuario es `BLOCKED_SECURITY`, responde 403.
7. Si pasa, retorna el perfil completo desde DB.

Punto critico para frontend:
- No basta con iniciar sesion en Supabase Auth: el email autenticado debe existir tambien en la tabla `users`.
- El backend espera JWT real en cada request protegida.

---

## 7. Endpoints reales de API

### 7.1 Chat principal con streaming

```http
POST /api/v1/chat
Authorization: Bearer <jwt_supabase>
Content-Type: application/json
```

Body:

```json
{
  "message": "Hola, quiero un credito",
  "conversation_id": null
}
```

`conversation_id`:
- `null` o ausente: crea una nueva conversacion en Supabase.
- UUID existente: intenta reanudar esa conversacion.
- Si el UUID no pertenece al usuario autenticado, responde 403.

Respuesta:
- `StreamingResponse`
- `media_type`: `text/event-stream`
- Headers:
  - `Cache-Control: no-cache`
  - `X-Accel-Buffering: no`
  - `X-Conversation-Id: <uuid>`

El cuerpo llega como eventos SSE con formato:

```text
data: {"type":"message","content":"...","node":"welcome"}

data: {"type":"node_transition","node":"WELCOME_NODE","product_intent":null}

data: {"type":"done","conversation_id":"..."}
```

Tipos reales de evento:

| type | Significado | Campos |
|---|---|---|
| `message` | Texto producido por un nodo del grafo | `content`, `node` |
| `node_transition` | Estado actual declarado por el nodo en `session.current_node` | `node`, `product_intent` |
| `done` | Fin del stream de la vuelta conversacional | `conversation_id` |
| `error` | Error capturado dentro del generador SSE | `detail` |

Diferencia importante:
- En eventos `message`, el campo `node` usa el nombre interno del nodo LangGraph: `welcome`, `intent_router`, `loan_entry`, `account_entry`, `dap_entry`, `general_response`.
- En eventos `node_transition`, el campo `node` usa el valor escrito en `session.current_node`: `WELCOME_NODE`, `INTENT_ROUTER`, `LOAN_ENTRY_STUB`, `ACCOUNT_ENTRY_STUB`, `DAP_ENTRY_STUB`, `GENERAL_RESPONSE`.

Persistencia real:
- Antes de ejecutar el grafo, guarda el mensaje del usuario en tabla `messages`.
- Al terminar, concatena todos los mensajes AI emitidos y guarda una sola respuesta `assistant`.
- El `node_at_time` del mensaje assistant queda como el ultimo nodo LangGraph ejecutado.

Limitacion real:
- `update_conversation_node()` se llama dentro de `welcome_node`, pero los demas nodos no actualizan explicitamente `conversations.current_node` en DB. El frontend debe confiar principalmente en los eventos SSE si necesita progreso en vivo.
- Actualmente no se actualiza `conversations.product_type_id` despues de clasificar intencion.

### 7.2 Historial de conversaciones

```http
GET /api/v1/history
Authorization: Bearer <jwt_supabase>
```

Respuesta real:

```json
{
  "conversations": [
    {
      "id": "...",
      "product_type_id": 1,
      "current_node": "WELCOME_NODE",
      "is_active": true,
      "created_at": "...",
      "updated_at": "...",
      "product_types": {
        "name": "Credito de Consumo"
      }
    }
  ]
}
```

Detalles:
- Filtra por `user_id` del usuario autenticado.
- Ordena por `updated_at DESC`.
- Limita a 20 conversaciones.
- No incluye preview del ultimo mensaje en la query actual, aunque algunos comentarios lo sugieren.

### 7.3 Mensajes de una conversacion

```http
GET /api/v1/history/{conversation_id}
Authorization: Bearer <jwt_supabase>
```

Comportamiento:
- Verifica que la conversacion pertenezca al usuario autenticado.
- Si no pertenece o no existe, responde 404.
- Retorna mensajes cronologicos desde tabla `messages`.

Respuesta:

```json
{
  "conversation_id": "...",
  "messages": [
    {
      "id": 1,
      "conversation_id": "...",
      "role": "user",
      "content": "Hola",
      "extracted_data": null,
      "node_at_time": null,
      "created_at": "..."
    }
  ]
}
```

### 7.4 Endpoints que NO existen actualmente

No existe implementacion real de:
- `GET /api/v1/docs/{doc_id}`
- descarga de PDF
- verificacion de hash documental
- endpoints OTP
- endpoints especificos de credito/cuenta/DAP
- login/signup propio del backend

---

## 8. LangGraph: estado y flujo real

### 8.1 Estado global

Archivo: `backend/app/graph/state.py`.

TypedDict raiz: `FluxState`.

Campos:

```python
messages: Annotated[list, add_messages]
user_data: UserData
session: SessionData
collected_data: dict
control_flags: dict
```

`user_data` esperado:

```text
user_id
full_name
email
rut
birth_date
user_status
user_category
```

`session` esperado:

```text
conversation_id
application_id
product_intent
current_node
previous_node
is_transversal_active
```

`control_flags` usado en estado inicial:

```json
{
  "security_blocked": false,
  "service_error": false,
  "otp_attempts": 0,
  "error_detail": null
}
```

### 8.2 Grafo compilado

Archivo: `backend/app/graph/workflow.py`.

Nodos registrados:
- `welcome`
- `intent_router`
- `loan_entry`
- `account_entry`
- `dap_entry`
- `general_response`

Entrada:
- `welcome`

Rutas:
- Despues de `welcome`: `route_after_welcome`.
- Despues de `intent_router`: `route_after_intent`.
- `loan_entry`, `account_entry`, `dap_entry` y `general_response` terminan en `END`.

Checkpointer:
- `get_compiled_graph()` compila con `get_checkpointer()`.
- `get_active_graph()` usa lazy singleton.
- `backend/app/infra/checkpointer.py` usa `AsyncPostgresSaver` con `DATABASE_URL`.
- El pool usa `prepare_threshold: None` y option `-c prepare_threshold=0` por compatibilidad con PgBouncer.

### 8.3 Nodos reales

`welcome_node`:
- Genera saludo inicial o saludo de reanudacion si existe `previous_node`.
- Usa `user_data.full_name` para saludar.
- Actualiza `conversations.current_node` a `WELCOME_NODE`.
- Retorna `AIMessage` y `session.current_node = "WELCOME_NODE"`.

`intent_router_node`:
- Busca el ultimo mensaje humano.
- Llama a Gemini mediante `get_chat_model()`.
- Clasifica en una de: `LOAN`, `ACCOUNT`, `DAP`, `GENERAL`.
- Si la respuesta no coincide exactamente, usa `GENERAL`.
- Retorna `session.product_intent` y `session.current_node = "INTENT_ROUTER"`.
- No genera mensaje visible al usuario.

`general_response_node`:
- Genera respuesta textual con lista de productos disponibles.
- Retorna `session.current_node = "GENERAL_RESPONSE"`.

`loan_entry_node`:
- Stub Fase 1.
- Confirma que el usuario quiere Credito de Consumo.
- Retorna `session.current_node = "LOAN_ENTRY_STUB"`.
- No calcula riesgo, no crea solicitud financiera, no pide datos.

`account_entry_node`:
- Stub Fase 1.
- Confirma Cuenta Corriente.
- Retorna `session.current_node = "ACCOUNT_ENTRY_STUB"`.

`deposit_entry_node`:
- Stub Fase 1.
- Confirma Deposito a Plazo.
- Retorna `session.current_node = "DAP_ENTRY_STUB"`.

### 8.4 Flujo esperado por mensaje

Para mensaje nuevo como "quiero un credito":

1. API valida JWT.
2. API crea conversacion si no hay `conversation_id`.
3. API guarda mensaje del usuario.
4. Estado inicial entra al grafo en `welcome`.
5. `welcome` emite saludo y `node_transition` a `WELCOME_NODE`.
6. `intent_router` clasifica intencion con Gemini.
7. Edge envia a `loan_entry`.
8. `loan_entry` emite mensaje stub y `node_transition` a `LOAN_ENTRY_STUB`.
9. API guarda respuesta assistant concatenada.
10. API emite `done` con `conversation_id`.

---

## 9. Vertex AI / Gemini

Archivo: `backend/app/infra/gemini_client.py`.

Credenciales:
- Setea `GOOGLE_APPLICATION_CREDENTIALS` desde settings.
- Setea `GOOGLE_CLOUD_PROJECT`.
- Usa Application Default Credentials, no API key.

Modelos:
- Chat y extraccion: `gemini-3-flash-preview`.
- Embeddings: `text-embedding-004`.

Funciones:
- `get_chat_model()` retorna `ChatVertexAI` con:
  - `model_name="gemini-3-flash-preview"`
  - `api_endpoint="aiplatform.googleapis.com"`
  - `temperature=0.3`
  - `max_output_tokens=2048`
- `get_structured_model(schema)` retorna modelo con `with_structured_output(schema)` y temperatura 0.1.
- `get_embeddings_model()` retorna `VertexAIEmbeddings`.

Observacion:
- Hay una incongruencia menor en comentarios: un comentario menciona `gemini-2.0-flash`, pero el codigo real usa `gemini-3-flash-preview`.

---

## 10. Supabase e infraestructura

Archivo: `backend/app/infra/supabase.py`.

Clientes:
- `supabase_client`: creado con `SUPABASE_SERVICE_ROLE_KEY`.
- `supabase_admin`: creado tambien con `SUPABASE_SERVICE_ROLE_KEY`.

Aunque existe `SUPABASE_ANON_KEY` en settings, el cliente estandar actual no la usa.

Helpers implementados:
- `get_user_by_email(email)`
- `get_user_by_id(user_id)`
- `create_conversation(user_id, product_type_code=None)`
- `save_message(conversation_id, role, content, node_at_time=None, extracted_data=None)`
- `get_conversation_messages(conversation_id)`
- `update_conversation_node(conversation_id, current_node, state_snapshot=None)`

`backend/app/infra/threading.py`:
- `get_or_create_thread(user_id, conversation_id=None)`
- Si no hay `conversation_id`, crea conversacion.
- Si hay `conversation_id`, valida propiedad por `id` y `user_id`.
- `get_langgraph_config(thread_id)` retorna:

```json
{
  "configurable": {
    "thread_id": "<conversation_id>"
  }
}
```

Regla real:
- En FLUX, `thread_id` de LangGraph equivale al UUID de `conversations.id`.

`backend/app/infra/embeddings.py`:
- `similarity_search(query, top_k=3)` existe como stub.
- Actualmente retorna `[]`.
- No hay RAG real implementado.

---

## 11. Modelo de datos real por migraciones

Las migraciones estan en `backend/migrations/`.

### 11.1 Catalogos

Archivo: `001_catalogs.sql`.

Tablas:
- `user_statuses`
- `user_categories`
- `product_types`
- `application_statuses`
- `education_levels`
- `risk_levels`
- `rejection_reason_codes`
- `currencies`
- `dap_terms`
- `document_types`
- `economic_indicators`

Seed principal en `000_seed.sql`:
- user statuses: `ACTIVE`, `BLOCKED_SECURITY`, `PROSPECT`
- user categories: `START`, `MEDIUM`, `ADVANCE`
- product types: `LOAN`, `ACCOUNT`, `DAP`
- application statuses: `IN_PROGRESS`, `PRE_APPROVED`, `REJECTED`, `COMPLETED`, `CLOSED_BY_USER`
- education levels: `POSTGRADO`, `UNIVERSITARIO`, `TECNICO`, `MEDIA`
- risk levels: `BAJO`, `MEDIO`, `ALTO`
- currencies: `CLP`, `UF`, `USD`
- dap terms: 7, 14, 30, 180, 360 dias
- document types: `CONTRATO_CREDITO`, `CONTRATO_CUENTA`, `CONTRATO_DAP`
- economic indicators: `UF`, `USD`, `IPC`

### 11.2 Identidad

Archivo: `002_identity.sql`.

Tabla `users`:
- `id`
- `rut`
- `full_name`
- `email`
- `phone`
- `birth_date`
- `status_id`
- `category_id`
- `created_at`
- `updated_at`

El perfil de negocio se vincula con Supabase Auth por email.

### 11.3 Conversaciones y mensajes

Archivo: `003_conversations.sql`.

Tabla `conversations`:
- `id`
- `user_id`
- `product_type_id`
- `current_node`
- `state_snapshot`
- `is_active`
- `metadata`
- `created_at`
- `updated_at`

Tabla `messages`:
- `id`
- `conversation_id`
- `role`: `user`, `assistant` o `system`
- `content`
- `extracted_data`
- `node_at_time`
- `created_at`

### 11.4 Solicitudes financieras

Archivo: `004_applications.sql`.

Tabla `financial_applications`:
- `id`
- `user_id`
- `product_type_id`
- `conversation_id`
- `status_id`
- `current_node_id`
- `node_status`
- `engine_status`
- `document_status`
- `metadata`
- `created_at`
- `updated_at`

Actualmente el codigo de Fase 1 no crea ni usa activamente `financial_applications`.

### 11.5 Detalles por producto

Archivo: `005_product_details.sql`.

Tablas:
- `loan_details`
- `account_details`
- `dap_details`

Estas tablas estan definidas, pero los modulos/nodos que deberian poblarlas no estan implementados.

### 11.6 Seguridad, documentos e indicadores

Archivo: `006_security_docs.sql`.

Tablas:
- `security_otp`
- `documents`
- `economic_history`

Estas tablas estan definidas, pero no hay endpoints ni modulos funcionales para OTP, PDF o consulta de indicadores.

---

## 12. Modulos de negocio

Carpeta: `backend/app/modules/`.

Estado real:
- `credit_eng.py`: archivo vacio.
- `account_eng.py`: archivo vacio.
- `eco_service.py`: archivo vacio.
- `security.py`: archivo vacio.
- `pdf_factory.py`: archivo vacio.
- `__init__.py`: archivo vacio.

Implicacion para frontend:
- No hay calculo real de scoring.
- No hay simulacion real de credito.
- No hay segmentacion real de cuenta.
- No hay calculo real de DAP.
- No hay OTP real.
- No hay PDF real.
- No hay hash documental real.
- No hay widgets dinamicos disparados desde backend.

---

## 13. Frontend incluido en este repo

Carpeta: `frontend/`.

Estado real:
- Es una aplicacion React/Vite.
- Implementa login visual local, sin Supabase real.
- Usa `useState`, `useMemo`, `useRef`.
- Tiene datos iniciales mock en `INITIAL_CHATS`.
- Tiene productos mock en `PRODUCTS`.
- Tiene una funcion local `inferProduct(text)` para detectar credito/cuenta/DAP por palabras.
- `handleSend(text)` agrega mensajes y avanza pasos localmente.
- No llama a `fetch()`.
- No usa `EventSource`.
- No parsea SSE.
- No usa `Authorization: Bearer`.
- No persiste `conversation_id` real del backend.
- No llama `/api/v1/history`.

Por tanto, si se evalua un frontend externo, se debe verificar contra el backend real y no contra este frontend local.

---

## 14. Contrato que debe cumplir un frontend externo

Un frontend compatible con el estado actual del backend debe:

1. Obtener un JWT valido de Supabase Auth.
2. Enviar `Authorization: Bearer <jwt>` en cada llamada.
3. Enviar mensajes a:

```http
POST /api/v1/chat
```

con body:

```json
{
  "message": "texto del usuario",
  "conversation_id": null
}
```

4. Leer `X-Conversation-Id` desde headers o `conversation_id` desde evento `done`.
5. Persistir ese `conversation_id` en estado frontend para continuar el hilo.
6. Consumir `text/event-stream`.
7. Parsear lineas `data: {...}`.
8. Manejar eventos:
   - `message`: agregar `content` al chat.
   - `node_transition`: actualizar indicador visual de progreso.
   - `done`: cerrar estado de loading.
   - `error`: mostrar error tecnico.
9. Consultar historial con:

```http
GET /api/v1/history
GET /api/v1/history/{conversation_id}
```

10. Reconstruir conversaciones usando `messages[].role` y `messages[].content`.

Consideraciones importantes:
- El stream puede traer mas de un evento `message` por request.
- El texto assistant final se guarda como una sola respuesta concatenada en DB.
- Los flujos de producto terminan en stubs; el frontend no debe esperar payloads de oferta, OTP, amortizacion o PDF.
- Para `POST` con streaming, no basta con `EventSource` nativo porque `EventSource` no soporta POST con body y headers personalizados de forma estandar. Conviene usar `fetch()` y leer `response.body` como stream.

---

## 15. Estados/nodos utiles para UI

Valores posibles en evento `node_transition.node` hoy:

```text
WELCOME_NODE
INTENT_ROUTER
GENERAL_RESPONSE
LOAN_ENTRY_STUB
ACCOUNT_ENTRY_STUB
DAP_ENTRY_STUB
```

Valores posibles en evento `node_transition.product_intent`:

```text
null
LOAN
ACCOUNT
DAP
GENERAL
```

Valores posibles en evento `message.node` hoy:

```text
welcome
loan_entry
account_entry
dap_entry
general_response
```

Nota: `intent_router` normalmente no emite `message`, porque solo clasifica y no retorna `AIMessage`.

---

## 16. Lo implementado vs lo pendiente

Implementado:
- API FastAPI base.
- CORS para localhost 3000 y 5173.
- `GET /health`.
- JWT Bearer contra Supabase Auth.
- Verificacion de perfil en tabla `users`.
- Creacion/reanudacion segura de conversaciones.
- Persistencia de mensajes.
- Endpoints de historial.
- LangGraph minimo.
- Clasificacion de intencion con Gemini.
- Streaming SSE.
- Checkpointer Postgres de LangGraph.
- Modelo SQL amplio para fases posteriores.

Stub o mock:
- `loan_entry_node`, `account_entry_node`, `deposit_entry_node`.
- `embeddings.similarity_search()`.
- Frontend local completo.

Pendiente/no implementado:
- Flujo real de credito.
- Flujo real de cuenta corriente.
- Flujo real de DAP.
- Extraccion conversacional de datos estructurados.
- Motores financieros.
- OTP.
- PDF.
- Hash documental.
- Descarga de documentos.
- RAG real.
- Manejo transversal de errores del grafo.
- Seguridad tipo watchdog.
- Integracion real del frontend local con backend.

---

## 17. Criterios recomendados para evaluar un frontend externo

La otra IA deberia revisar si el frontend externo:

- Usa Supabase Auth o algun mecanismo capaz de obtener JWT Supabase real.
- Envia `Authorization: Bearer`.
- Soporta POST streaming con `fetch` + `ReadableStream`.
- Parsear SSE correctamente aunque los chunks lleguen partidos.
- Persiste `conversation_id`.
- Usa `X-Conversation-Id` y/o evento `done`.
- Implementa historial con `/api/v1/history`.
- Implementa detalle con `/api/v1/history/{conversation_id}`.
- Distingue `message.node` de `node_transition.node`.
- Maneja nodos actuales de Fase 1, incluidos los `*_STUB`.
- No asume que ya existen endpoints de PDF, OTP, scoring, ofertas o documentos.
- No asume que el backend devuelve widgets dinamicos.
- Muestra estados de carga/error para eventos `error`.
- Tolera que `product_type_id` o `product_types` puedan ser null en conversaciones nuevas.
- Tolera que `current_node` en historial pueda no reflejar el ultimo nodo real del stream.

---

## 18. Resumen ejecutivo final

`flux-project-main` contiene un backend Fase 1 funcional para conversacion bancaria basica: autentica por Supabase, crea conversaciones, ejecuta un grafo LangGraph, clasifica intenciones con Gemini y emite eventos SSE al frontend. A nivel de producto financiero, todavia no implementa logica real: credito, cuenta corriente y DAP existen solo como stubs conversacionales.

El frontend incluido en este repositorio no es una referencia de integracion backend: es una maqueta local con datos simulados. El frontend externo que se evalue debe ser juzgado principalmente por su compatibilidad con los endpoints reales, autenticacion JWT, consumo SSE por POST, persistencia de `conversation_id` y manejo honesto de que los flujos avanzados aun no existen.

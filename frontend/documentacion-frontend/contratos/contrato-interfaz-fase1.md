# Contrato de Interfaz Backend-Frontend | FASE 1
## Proyecto FLUX · AI Orchestrator & UI

Este documento define el protocolo de comunicación entre el orquestador (LangGraph/FastAPI) y la interfaz de usuario (React/Frontend) para la **FASE 1**, detallando los eventos de streaming, la recuperación de historial y la persistencia de chats.

---

### 1. Endpoints de Comunicación

Todos los endpoints requieren un token JWT válido en el header de `Authorization`.

#### A. Chat Principal (Streaming)
- **URL**: `/api/v1/chat`
- **Método**: `POST`
- **Body**:
  ```json
  {
    "message": "Hola, quiero información",
    "conversation_id": "UUID-opcional"
  }
  ```
  *Si `conversation_id` es null, se crea una nueva conversación. Si se provee un UUID, se reanuda el hilo previo.*

#### B. Historial de Conversaciones
- **URL**: `/api/v1/history`
- **Método**: `GET`
- **Respuesta**: Lista de hilos de conversación del usuario (id, título, fecha).

#### C. Detalle de Conversación
- **URL**: `/api/v1/history/{conversation_id}`
- **Método**: `GET`
- **Respuesta**: Lista cronológica de mensajes (role, content, timestamp) para el hilo solicitado.

---

### 2. Protocolo de Streaming (SSE)

El endpoint `/chat` responde con un `text/event-stream`. Cada evento es un objeto JSON enviado en el campo `data`.

#### Tipos de Eventos (Event Types):
| Evento | Función | Payload de ejemplo |
|--------|---------|---------|
| `message` | Fragmento de texto generado por el asistente (incremental). | `{"type": "message", "content": "Hola", "node": "welcome"}` |
| `node_transition` | Notifica el cambio de estado interno del grafo (GPS). | `{"type": "node_transition", "node": "intent_router", "product_intent": "LOAN"}` |
| `done` | Señal de que la respuesta ha finalizado. | `{"type": "done", "conversation_id": "UUID"}` |
| `error` | Notificación de fallo técnico. | `{"type": "error", "detail": "Descripción del error"}` |

---

### 3. Estados del Grafo en Fase 1 (GPS)

El frontend debe monitorear el evento `node_transition` para conocer la ubicación del usuario en el flujo:

1.  **`welcome`**: El sistema está saludando o recuperando el contexto de una sesión previa.
2.  **`intent_router`**: El orquestador está analizando el mensaje para clasificar la intención (Crédito, Cuenta, DAP o General).
3.  **`general_response`**: El sistema está respondiendo a una consulta que no es un flujo de producto financiero.
4.  **`loan_init` / `account_init` / `dap_init`**: El usuario ha entrado al "punto de partida" de un producto (Stubs de Fase 1).

---

### 4. Persistencia y Sincronía

- **Conversaciones**: Cada hilo de chat se guarda en la tabla `conversations`.
- **Mensajes**: Cada interacción (User/Assistant) se persiste automáticamente en la tabla `messages` vinculada al `conversation_id`.
- **Sincronía**: El `conversation_id` devuelto en el header `X-Conversation-Id` o en el evento `done` es el que debe persistirse en el estado del Frontend para mantener la continuidad del hilo.

---
> [!IMPORTANT]
> En esta Fase 1, la interacción es puramente textual (incremental). No se incluyen widgets dinámicos ni lógica de motores financieros, los cuales serán introducidos en la Fase 2.

---

*NOTA PARA DEV BACKEND/AI: Este es el estado actual de la comunicación Backend-Frontend. Para la Fase 2 se debe evolucionar este contrato. Se debe determinar cómo extender los eventos SSE para incluir los nuevos nodos de crédito y los payloads JSON que gatillarán los widgets (Tarjeta de Transparencia, OTP, etc.) que el Dev 2 (Frontend)debe construir.*
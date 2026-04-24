# Reporte de Consolidación — Fase 1 (Dev 1)
## Proyecto FLUX · AI Orchestrator & Backend Infrastructure

Este documento resume la infraestructura técnica y lógica implementada en la Fase 1, diseñada para servir como base estable para la **Fase 2 (Flujos de Crédito)**.

---

### 1. Arquitectura Base: FastAPI + LangGraph + Supabase

El sistema opera como una tríada sincronizada:
- **FastAPI**: Capa de entrada que gestiona la concurrencia asíncrona, validación de esquemas (Pydantic) e inyección de dependencias para seguridad.
- **LangGraph**: Orquestador de estados que transforma el chat en un flujo determinista. Utiliza un `StateGraph` para manejar la memoria de corto y largo plazo.
- **Supabase**: Backend-as-a-Service que provee la persistencia del grafo (PostgreSQL), gestión de identidad (Auth) y almacenamiento de registros de auditoría (Messages/Conversations).

---

### 2. Lógica de Persistencia (Checkpointer)

La persistencia permite que FLUX "recuerde" exactamente en qué punto del flujo quedó un usuario, incluso si cierra la pestaña o cambia de dispositivo.

- **Configuración de PostgresSaver**: 
  Se utiliza `AsyncPostgresSaver` (en `app/infra/checkpointer.py`) conectado a la base de datos PostgreSQL de Supabase. Para garantizar compatibilidad con **PgBouncer**, se configuró el `AsyncConnectionPool` con `prepare_threshold: None` y parámetros de sesión `options="-c prepare_threshold=0"`. Esto evita errores de *Prepared Statements* duplicados en entornos de pool de conexiones.
- **Estado del Grafo**: 
  Todo el `FluxState` (mensajes, datos recolectados, banderas de control) se serializa y guarda en tablas de sistema (`checkpoints`) gestionadas automáticamente por LangGraph.
- **Uso del `thread_id`**: 
  El `thread_id` es la llave primaria de la persistencia. En FLUX, este ID coincide exactamente con el UUID de la tabla `conversations`. El backend asegura que un usuario solo pueda cargar un `thread_id` que le pertenezca mediante una validación forzada en la capa de `app/infra/threading.py`.

---

### 3. Tubería de Seguridad (Auth + RLS)

Se ha implementado una arquitectura de "Privilegio Mínimo" para proteger la integridad financiera:

- **Autenticación JWT**: Cada request a `/chat` o `/history` debe incluir un token de Supabase Auth. El backend valida este token, extrae el `user_id` y verifica el estado del usuario en la tabla `users` (Filtro de Seguridad).
- **Backend Privilegiado (`supabase_admin`)**: El servidor utiliza el `service_role_key` para instanciar un cliente con privilegios de administrador. Esto permite que el backend escriba estados y mensajes sin estar restringido por las políticas de RLS, actuando como una entidad de confianza.
- **Políticas RLS en Supabase**: En la base de datos, se han configurado políticas de **Row Level Security** (RLS) estrictas:
  - `auth.uid() = user_id`: Los usuarios solo pueden consultar sus propias conversaciones y mensajes.
  - `WITH CHECK`: Garantiza que los usuarios no puedan insertar registros con un `user_id` ajeno.

---

### 4. Estructura de Endpoints y Streaming

El endpoint principal es `POST /api/v1/chat`, el cual utiliza **Server-Sent Events (SSE)** para una experiencia fluida.

- **Funcionamiento del Stream**: 
  El generador `stream_graph_response` consume el stream asíncrono del grafo (`astream`). Emite eventos JSON en tiempo real.
- **Eventos de Mensaje (`type: message`)**: Fragmentos de texto generados por los nodos del LLM.
- **Eventos de Transición (`type: node_transition`)**: 
  Este es un componente crítico para el Frontend. Cada vez que el grafo se mueve de un nodo a otro (ej: de `WELCOME` a `INTENT_ROUTER`), el sistema emite un evento con el nombre del nodo actual (`current_node`) y la intención detectada (`product_intent`). 
  *Propósito:* Funciona como un **GPS de Proceso**, permitiendo que la UI muestre indicadores de progreso o cambie la interfaz visual dinámicamente antes de que el mensaje termine de llegar.

---

### 5. Elementos Clave para Fase 2 (Contexto AI)

Para la implementación de los nodos de Crédito en la Fase 2, Claude debe considerar:

- **Lazy Initialization del Grafo**: El grafo se compila bajo demanda mediante `get_active_graph()` en `app/graph/workflow.py` para evitar problemas con el event loop en tiempo de importación.
- **Patrón de Nodos**: Los nodos están separados en `nodes/common.py` (transversales) y archivos por producto (`nodes/credit.py`).
- **Motores de Cálculo**: El motor de riesgo y amortización reside en `app/modules/credit_eng.py`, separado del flujo del grafo para facilitar el testing unitario de fórmulas financieras.
- **Dual-Init Gemini**: El cliente en `app/infra/gemini_client.py` está configurado para inicializar tanto el modelo de chat como el de embeddings de forma centralizada.
- **Manejo de Windows**: La aplicación incluye un parche de `WindowsSelectorEventLoopPolicy` en `main.py` para asegurar que el desarrollo local en Windows sea 100% compatible con la persistencia asíncrona de Postgres.

---
*Este reporte consolida el estado actual y asegura la trazabilidad técnica para la expansión de capacidades de IA.*

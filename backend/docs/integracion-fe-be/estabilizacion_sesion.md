# Estabilización de Sesión y Persistencia (Frontend ↔ Backend)

## 1. El Problema: "Amnesia Conversacional"
Se detectó una regresión crítica donde el asistente Flux perdía el contexto de la conversación (Product Intent y State) en el segundo turno del mensaje, redirigiendo erróneamente al usuario al menú general (`intent_router`).

### Síntomas:
1. Turno 1 (Botón de Inicio): Funcionaba correctamente, Flux pedía la renta.
2. Turno 2 (Ingreso de Datos): Flux respondía con el menú general ("¡Hola! Puedo asistirte con Crédito, Cuenta Corriente...").
3. Logs del Backend: Mostraban `ID=None` e `INTENT=None` en el segundo mensaje.

---

## 2. Diagnóstico de Causas Raíz

### A. Lado Frontend (FluxContext.jsx)
1. **Reset Agresivo de Selección:** Un `useEffect` reseteaba el `selectedConversationId` a `DRAFT_ID` si el ID actual no se encontraba en la lista de conversaciones (causado por la latencia del polling del servidor).
2. **Desincronización de ID:** Al recibir el ID real desde el Backend, el Frontend actualizaba el estado de selección pero no mutaba el ID del objeto en la lista `conversations`, causando que el siguiente mensaje se enviara con el ID del draft (`null`).

### B. Lado Backend (chat.py)
1. **Falta de Rehidratación:** El API confiaba exclusivamente en el checkpointer de LangGraph. Si este fallaba (errores 520 de Supabase), el Grafo arrancaba sin estado inicial.
2. **Inconsistencia de Case-Sensitivity:** Se guardaba el `current_node` en minúsculas (ID técnico), pero el ruteador (`edges.py`) esperaba MAYÚSCULAS (ID semántico), rompiendo el mapa de reanudación (`_RESUME_MAP`).

---

## 3. Soluciones Implementadas

### Fase 1: Blindaje en Frontend (FluxContext.jsx)
- **Protección de Selección:** Se modificó el `useEffect` de selección para que no toque el ID si ya hay uno válido activo, evitando el reset durante el polling.
- **Promoción Inmediata de ID:** Al recibir el evento `done`, el sistema ahora busca el `DRAFT_ID` en la lista local y le asigna el ID real del Backend instantáneamente.
- **Payload Seguro:** Se implementó la lógica de `effectiveId` en `sendMessage` para asegurar que el `conversation_id` enviado sea el correcto.

### Fase 2: Rehidratación Robusta en Backend (chat.py)
- **Hidratación desde DB:** Antes de invocar al Grafo, el API ahora consulta la tabla `conversations` de Supabase. Si existe un `state_snapshot`, lo inyecta directamente en el `initial_state`.
- **Sincronización Centralizada:** Se movió la lógica de guardado al final del stream de respuesta, asegurando que tanto el producto como el estado completo se persistan en un solo bloque.
- **Normalización de Nodos:** Se forzó el guardado de `current_node` en MAYÚSCULAS para garantizar compatibilidad con los ruteadores de `edges.py`.

---

## 4. Flujo de Trabajo Resultante (Punto de Verdad)

1. **Turno 1:** Se crea el chat -> El Backend retorna UUID -> El Frontend lo ancla localmente.
2. **Persistencia:** El Backend guarda el snapshot del Grafo en la columna `state_snapshot`.
3. **Turno 2:** El Frontend envía el UUID -> El Backend carga el snapshot -> El Grafo recupera su posición exacta en el flujo de crédito.

> [!IMPORTANT]
> Esta arquitectura "híbrida" (Checkpointer + Snapshot Manual) garantiza que la conversación nunca se pierda, incluso ante inestabilidad de red o reinicios del servidor.

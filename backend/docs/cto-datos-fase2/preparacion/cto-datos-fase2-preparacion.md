# Análisis de Contrato de Datos - Fase 2: Interfaz Simétrica y Adaptativa

Este documento define el contrato de comunicación entre el Backend (LangGraph + FastAPI) y el Frontend para la Fase 2 del proyecto FLUX. El objetivo es lograr una interfaz que se adapte dinámicamente al producto activo (`LOAN`, `ACCOUNT`, `DAP`) basándose en eventos estructurados.

## 1. Arquitectura de Comunicación (SSE)

El canal principal es el endpoint `/api/v1/chat`. Se expande el esquema de eventos Server-Sent Events (SSE) para incluir metadatos de UI.

### Tipos de Eventos y Payloads

| Tipo de Evento | Propósito | Estructura del Payload (JSON) |
| :--- | :--- | :--- |
| `message` | Texto incremental del asistente | `{ "type": "message", "content": "Hola...", "node": "..." }` |
| `node_transition` | Actualización de estado y progreso | `{ "type": "node_transition", "node": "LOAN_COLLECTING_PROFILE", "friendly_label": "Perfil Laboral", "product": "LOAN", "progress_percent": 33 }` |
| `collection_status` | Estado de captura de datos | `{ "type": "collection_status", "fields": [{ "name": "renta", "label": "Renta Líquida", "status": "captured", "value": 1500000 }, { "name": "antiguedad", "label": "Antigüedad", "status": "pending" }] }` |
| `ui_component` | Gatilla componentes visuales complejos | `{ "type": "ui_component", "component": "TRANSPARENCY_CARD", "data": { ... } }` |

---

## 2. Mapeo de Nodos a Componentes UI

El Frontend debe reaccionar al campo `node` y `product_intent` del flujo para renderizar el componente adecuado.

### A. Nodos de Recolección (Simetría de Producto)
La UI debe consultar el namespace `collecting_data` y `ProgressData` del estado.

*   **Lógica:** Si el nodo contiene `COLLECTING`, la UI muestra un panel lateral o superior con los campos requeridos.
*   **Campos por Producto (Ejemplo):**
    *   `LOAN`: `renta`, `antiguedad_laboral`, `nivel_estudios`, `monto_solicitado`, `plazo_solicitado`.
    *   `ACCOUNT`: `renta`, `antiguedad_laboral`, `nivel_estudios`.
    *   `DAP`: `monto`, `moneda`, `plazo`.

### B. Nodo Pre-Approved (Tarjeta de Transparencia)
*   **Gatillo:** Transición a nodo con sufijo `PRE_APPROVED`.
*   **Componente:** `TransparencyCard`.
*   **Datos:** Consume el namespace `transparency_data`.
*   **Acciones:** Botones "Aceptar" y "Rechazar" envían mensajes de texto al chat (ej: "Acepto la oferta") para gatillar la transición en el grafo.

### C. Nodo OTP (Seguridad)
*   **Gatillo:** Transición a nodo `OTP_VALIDATION`.
*   **Componente:** `OtpInputCard`.
*   **Datos:** `auth_control.otp_attempts`.
*   **Acción:** El input manda el código al backend. El backend responde con un nuevo evento SSE indicando éxito o error.

### D. Nodo de Cierre (Visor de PDF)
*   **Gatillo:** Transición a nodo con sufijo `COMPLETED`.
*   **Componente:** `PdfSuccessViewer`.
*   **Datos:** `offer_data[producto].display_data`.
    *   `download_url`: Link directo al PDF.
    *   `main_detail`: Resumen final (ej: "Crédito por $5.000.000").
    *   `security_hash`: Hash SHA-256 para validación de integridad.

---

## 3. Reflexión Técnica sobre Simetría

Para que el Frontend sea 100% adaptativo, el Backend debe proveer un "Diccionario de Etiquetas" (Friendly Labels) y una lista de "Campos por Paso".

### Propuesta de Enriquecimiento en `chat.py`

En lugar de que el FE tenga "quemados" los nombres de los nodos, el evento `node_transition` inyectará metadatos descriptivos:

```python
# Ejemplo de lo que el API debería emitir en Fase 2
{
    "type": "node_transition",
    "node": "LOAN_COLLECTING_SIMULATION",
    "friendly_label": "Simulación de Crédito",
    "product": "LOAN",
    "ui_hints": {
        "show_chat": True,
        "show_sidebar": True,
        "focus_fields": ["monto_solicitado", "plazo_solicitado"]
    }
}
```

---

## 4. Análisis de Cambios Requeridos

1.  **En `state.py`**: El estado ya está preparado con namespaces segmentados (`loan`, `account`, `dap`). Es robusto.
2.  **En `chat.py`**: Es el punto de mayor cambio. Se debe crear un extractor que mapee el `FluxState` actual a los eventos SSE mencionados arriba.
3.  **Nodos Silenciosos**: Los motores de riesgo/evaluación y formalización no emiten `ui_component`. El FE debe mostrar un "Estado de Carga" (Loading) genérico mientras espera el siguiente evento SSE de tipo `message` o `ui_component`.

## 5. Próximos Pasos Recomendados

1.  **Definir Diccionario de Etiquetas**: Crear una constante en el backend que asocie `LOAN_COLLECTING_PROFILE` -> "Información Personal".
2.  **Implementar el `SSE_Broker`**: Una función en el API que transforme el diccionario de salida de LangGraph en los eventos SSE tipados.
3.  **Endpoint de Descarga**: Formalizar `GET /api/v1/docs/download/{id}`.

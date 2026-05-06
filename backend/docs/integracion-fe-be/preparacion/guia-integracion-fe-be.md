# Contrato de Datos y Guía de Integración Frontend - Backend (Master Doc para IA)

## 0. Resumen Ejecutivo y Regla de Oro
Este documento sirve como contexto maestro para la implementación de la integración entre el Backend (LangGraph) y el Frontend (React) en la Fase 2 del proyecto FLUX.

**REGLA DE ORO DE INTEGRACIÓN:** El estado definido en el Backend (`state.py`) y los requerimientos de negocio actuales **mandan** sobre cualquier lógica o campo que exista actualmente en el Frontend. Si el Frontend espera un campo `loan_engine` pero el Backend entrega `evaluation_results.loan_engine`, el Frontend debe adaptarse o el API debe normalizar hacia la estructura del Backend.

---

## 1. Visión de la Integración: Interfaz Simétrica y Adaptativa
El objetivo es que el Frontend sea un "cascarón inteligente" que reaccione dinámicamente al producto activo (`LOAN`, `ACCOUNT`, `DAP`). La UI no debe "conocer" las reglas de negocio, sino renderizar el estado que el Backend le dicte a través de los namespaces de `FluxState`.

### 1.1. Simetría de Flujos por Producto
Aunque los datos varían, el ciclo de vida es constante para los tres productos:

*   **Crédito de Consumo (`LOAN`):** 
    *   Recolección: 2 fases (Perfil + Simulación).
    *   Motor: `LOAN_RISK_ENGINE` (Evaluación de riesgo y scoring).
*   **Cuenta Corriente (`ACCOUNT`):** 
    *   Recolección: 1 fase (Perfil).
    *   Motor: `ACCOUNT_EVALUATION_ENGINE` (Evaluación comercial).
*   **Depósito a Plazo (`DAP`):** 
    *   Recolección: 1 fase (Parámetros de inversión).
    *   Motor: `DAP_INVESTMENT_ENGINE` (Cálculo de tasas y retorno).

### 1.2. Comportamiento Específico por Tipo de Nodo

#### A. Nodos de Recolección (COLLECTING)
El Frontend debe usar el namespace `collecting_data` y `ProgressData` para mostrar:
*   **Campos Requeridos:** Lista de campos según el producto (Renta, Antigüedad, Monto, Plazo, etc.).
*   **Estado de Captura:** Visualización tipo "Checklist" donde los campos presentes en el estado se marcan como capturados y los `null` como pendientes.
*   **Lenguaje Humano:** Mapear IDs técnicos a etiquetas (ej: `renta` -> "Renta Líquida Mensual").

#### B. Nodos de Servicio/Motor (ENGINE / FORMALIZATION)
Estos nodos son "Cajas Negras" para el usuario.
*   **Estado UI:** El Frontend detecta la transición a estos nodos y debe mostrar un **Spinner de Procesamiento** o un estado de "Calculando oferta personalizada..." o "Generando documentos...".
*   **Silencio:** No se muestran widgets de interacción; el usuario solo espera el siguiente evento SSE.

#### C. Nodo de Oferta (PRE_APPROVED)
Al llegar a este hito, se gatilla la **Tarjeta de Transparencia**.
*   **Datos:** Consume el namespace `transparency_data` del producto activo.
*   **Interacción:** Debe presentar dos botones claros:
    *   **Aceptar:** Envía el mensaje "ACEPTAR_OFERTA_CREDITO" (o equivalente por producto) al chat.
    *   **Rechazar:** Envía "RECHAZAR_OFERTA_CREDITO" al chat.

#### D. Nodo de Seguridad (OTP_VALIDATION)
Se gatilla la **Card de Validación de Identidad**.
*   **Datos:** Muestra el número de intentos restantes desde `auth_control.otp_attempts`.
*   **Interacción:** Un input de 6 dígitos que, al completarse o presionar enviar, manda el código como un mensaje de texto plano al backend para su validación en el grafo.

#### E. Nodo de Cierre (COMPLETED / REJECTED)
Se gatilla la **Pantalla de Cierre**.
*   **Éxito:** Muestra el componente `FlowClosure` con:
    *   Visor de PDF (usando `download_url`).
    *   Botón de descarga.
    *   Hash SHA-256 de integridad visible para el usuario.
*   **Rechazo:** Muestra la razón del rechazo de forma empática (`offer_data.display_data.reason`).

---

## 2. Especificación Técnica del Contrato (SSE)

El flujo de comunicación es unidireccional (Backend -> Frontend) mediante Server-Sent Events. Cada "chunk" de datos debe ser un JSON válido enviado bajo el prefijo `data: `.

### 2.1. Tipos de Eventos y Esquemas JSON

#### A. Mensaje de Texto (`type: "message"`)
Se envía cada vez que el asistente genera contenido incremental o final.
```json
{
  "type": "message",
  "content": "He calculado tu oferta...",
  "node": "LOAN_RISK_ENGINE"
}
```

#### B. Transición y Estado (`type: "node_transition"`)
Es el evento más importante para la UI. Gatilla el cambio de widgets y actualiza el monitor de progreso. **Importante:** Los namespaces de estado deben ir en la raíz del objeto.
```json
{
  "type": "node_transition",
  "node": "LOAN_PRE_APPROVED",
  "product_intent": "LOAN",
  "friendly_label": "Oferta Pre-Aprobada",
  "application_id": "uuid-solicitud",
  "node_status": "SUCCESS",
  "transparency_data": {
    "loan": {
      "monto_aprobado": "$5.000.000",
      "cuota_mensual": "$235.000",
      "cae": "15.4%"
    }
  }
}
```

#### C. Fin de Stream (`type: "done"`)
Indica al Frontend que el proceso ha terminado y debe cerrar la conexión.
```json
{
  "type": "done",
  "conversation_id": "uuid-conversacion"
}
```

#### D. Error de Proceso (`type: "error"`)
Informa fallos técnicos o de negocio durante la ejecución del grafo.
```json
{
  "type": "error",
  "detail": "No pudimos conectar con el motor de riesgo. Intenta más tarde."
}
```

---

## 3. Mapeo de Componentes Frontend

La integración se basa en un despacho dinámico dentro de `CreditWidgets.jsx`, el cual evalúa el `currentNode` y renderiza el componente adecuado.

### 3.1. Matriz de Componentes y Estado

| Nodo Backend (Sufijo) | Componente UI | Namespace de Estado Consumido | Callbacks / Acciones |
| :--- | :--- | :--- | :--- |
| `COLLECTING_PROFILE` | `ProcessPanel` | `state.collecting_data[product]` | Visualización de campos capturados. |
| `COLLECTING_SIM` | `ProcessPanel` | `state.collecting_data[product]` | Visualización de montos y plazos. |
| `PRE_APPROVED` | `LoanOfferCard` | `state.transparency_data[product]` | `onAcceptOffer`, `onRejectOffer` |
| `OTP_VALIDATION` | `OtpInput` | `state.auth_control` | `onSubmitOtp` |
| `COMPLETED` | `FlowClosure` | `state.offer_data[product].display_data` | `download_url`, `security_hash` |
| `REJECTED_POLICY` | `FlowClosure` | `state.offer_data[product].display_data` | Muestra `reason` de rechazo. |

### 3.2. Lógica de Despacho (Dispatch Logic)
Para garantizar la simetría, el Frontend debe seguir estas reglas:

1.  **Visibilidad Global:** El componente `ProcessPanel` siempre está visible en el lateral, reflejando el `friendly_label` y el `progress_percent` recibido en el evento `node_transition`.
2.  **Inyección en el Chat:** Los widgets (`LoanOfferCard`, `OtpInput`, `FlowClosure`) se inyectan al final del flujo de mensajes en `ChatPanel.jsx` a través del orquestador `CreditWidgets.jsx`.
3.  **Estado de Deshabilitación:** Mientras el flag `sending` sea `true` (streaming activo), los widgets deben mostrar un estado *disabled* o *loading* para evitar envíos duplicados.
4.  **Normalización de Props:** Independientemente del producto (`LOAN`, `ACCOUNT`, `DAP`), los componentes de UI deben recibir una interfaz de datos normalizada (ej: el `LoanOfferCard` debe poder renderizar una oferta de Cuenta Corriente si los campos mapean correctamente).

---

## 4. Fuentes de Verdad para la IA de Implementación

Para ejecutar este plan con éxito, la IA de implementación debe consultar obligatoriamente este set de archivos:

### 4.1. Backend (Estructura y Datos)
1.  **`backend/app/graph/state.py`**: El esquema maestro de namespaces.
2.  **`backend/app/graph/workflow.py`**: El mapa de conexiones y nombres de nodos.
3.  **`backend/app/api/v1/chat.py`**: El punto de inyección para el nuevo Broker de SSE.

### 4.2. Frontend (Integración y UI)
1.  **`frontend/src/context/FluxContext.jsx`**: Lógica de procesamiento de eventos SSE y actualización del estado global de React.
2.  **`frontend/src/constants/flux.js`**: Diccionario de normalización de IDs de nodos y etiquetas de UI.
3.  **`frontend/src/components/widgets/CreditWidgets.jsx`**: El orquestador que decide qué widget mostrar en el chat.
4.  **`frontend/src/components/widgets/LoanOfferCard.jsx`**: Estructura de props requerida por la Tarjeta de Transparencia.

---

## 5. Próximos Pasos Técnicos

1.  **Desarrollo del Broker de SSE:** Modificar `backend/app/api/v1/chat.py` para extraer los namespaces (`transparency_data`, `offer_data`, `auth_control`) del `FluxState` y emitirlos como eventos SSE tipados.
2.  **Evaluación de Adaptación FE:** Analizar y ejecutar cambios menores en los componentes de la carpeta `frontend/src/components/widgets/` para asegurar que las propiedades recibidas desde el nuevo Broker se mapeen correctamente a la interfaz, manteniendo la simetría de productos.
3.  **Sincronización de Diccionarios:** Asegurar que cualquier nuevo nodo o estado definido en el Backend tenga su contraparte correspondiente en `frontend/src/constants/flux.js`.

---

## 6. Escalabilidad y Futuros Productos (Mandato de Abstracción)

Es imperativo que la IA de implementación considere lo siguiente para la arquitectura de la solución:

1.  **Estado de los Productos:** Actualmente, solo el producto de **Crédito de Consumo (`LOAN`)** está implementado al 100% en el backend. Los productos de **Cuenta Corriente (`ACCOUNT`)** y **Depósito a Plazo (`DAP`)** se encuentran en fase de definición y no poseen lógica de motor o formalización activa.
2.  **Requerimiento de Abstracción:** La integración (el Broker de SSE y el procesamiento en `FluxContext.jsx`) debe realizarse con un nivel de abstracción tal que la incorporación de `ACCOUNT` y `DAP` en el futuro requiera cambios **nulos o mínimos**.
3.  **Patrón de Implementación:** Se debe evitar el código específico para "Loan" en las capas de transporte de datos. Se debe preferir el uso del parámetro `product_intent` y el acceso dinámico a los namespaces del estado (ej: `state.evaluation_results[product_intent]`) para que el sistema sea agnóstico al producto que viaja por el flujo.

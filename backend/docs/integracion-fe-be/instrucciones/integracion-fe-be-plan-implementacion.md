# Plan de Implementación: Integración Simétrica y Adaptativa FLUX — Fase 2

**Versión:** 1.0  
**Fecha:** Mayo 2026  
**Autor:** Staff Software Engineer  
**Contexto:** Integración Backend (LangGraph/FastAPI) ↔ Frontend (React) para el sistema FLUX.

---

## Índice

1. [Diagnóstico de Brechas](#1-diagnóstico-de-brechas)
2. [Fase 1: El Puente de Datos — SSE Broker en `chat.py`](#fase-1-el-puente-de-datos--sse-broker-en-chatpy)
3. [Fase 2: El Sistema Nervioso — `FluxContext.jsx`](#fase-2-el-sistema-nervioso--fluxcontextjsx)
4. [Fase 3: Orquestación de Widgets — `CreditWidgets.jsx` y `LoanOfferCard.jsx`](#fase-3-orquestación-de-widgets--creditwidgetsjsx-y-loanoffercardsjsx)
5. [Fase 4: Cierre y Seguridad — `FlowClosure` y manejo de errores](#fase-4-cierre-y-seguridad--flowclosure-y-manejo-de-errores)
6. [Riesgos de Integración](#6-riesgos-de-integración)
7. [Checklist de Entrega](#7-checklist-de-entrega)

---

## 1. Diagnóstico de Brechas

Antes de ejecutar, hay que entender con precisión qué existe y qué falta. El análisis de los archivos entregados revela **cuatro brechas estructurales**:

### Brecha 1 — `chat.py`: El Broker SSE es incompleto
El generador `stream_graph_response` solo emite dos tipos de eventos:
- `message` (contenido del asistente)
- `node_transition` con `node` y `product_intent` (sin namespaces de estado)

**Lo que falta:** Los namespaces `transparency_data`, `collecting_data`, `offer_data`, `auth_control`, `flow_result` y los campos `application_id`, `friendly_label`, `node_status`, `progress_percent` nunca se emiten.

El estado completo de `FluxState` está disponible en el output de cada nodo (`node_output`), pero el código actual solo extrae `messages` y `session`.

### Brecha 2 — `FluxContext.jsx`: No consume los nuevos namespaces
`updateConversationFromPayload` maneja `evaluationResults`, `offerData` y `authControl`, pero no tiene soporte para:
- `transparencyData` (el namespace correcto para `LoanOfferCard`)
- `collectingData` (para el `ProcessPanel`)
- `friendly_label` y `progress_percent` (para el monitor de progreso)
- `nodeStatus` como `SUCCESS/PROCESSING/ERROR`

Además, `createRuntimeState()` no incluye `transparencyData` ni `collectingData`, por lo que esos campos son `undefined` en la conversación.

### Brecha 3 — `LoanOfferCard.jsx`: Lee de la fuente equivocada
`readLoanResult` busca datos en `riskResults`, `evaluationResults.loan_engine` o `offerData.loan`. Según el contrato de la guía y `state.py`, la fuente correcta para la Tarjeta de Transparencia es `transparency_data[product]` — un namespace separado con valores ya formateados como strings.

### Brecha 4 — `CreditWidgets.jsx`: No es product-agnostic
El guard `if (!currentNode?.startsWith('LOAN_'))` rompe el Mandato de Abstracción. Un flujo de `ACCOUNT` o `DAP` nunca renderizaría ningún widget. La lógica de despacho debe basarse en el sufijo del nodo (`_PRE_APPROVED`, `_OTP_VALIDATION`, `_COMPLETED`), no en el prefijo del producto.

---

## Fase 1: El Puente de Datos — SSE Broker en `chat.py`

### Objetivo Técnico
Modificar `stream_graph_response` en `backend/app/api/v1/chat.py` para que los eventos `node_transition` incluyan todos los namespaces relevantes del `FluxState`, de forma dinámica y agnóstica al producto activo.

---

### Paso 1.1 — Diseñar el extractor dinámico de namespaces

**Problema:** El objeto `node_output` de LangGraph contiene los campos del estado que el nodo **modificó** en ese turno. El broker debe extraer los namespaces relevantes solo cuando estén presentes.

**Implementación:** Crear una función `build_node_transition_payload` en `chat.py` que construya el JSON de forma declarativa. Los namespaces deben ser seleccionados por nombre de key, sin lógica condicional por producto.

```python
# backend/app/api/v1/chat.py — Nueva función auxiliar

# Namespaces del FluxState que el Frontend necesita consumir.
# Para agregar soporte a un nuevo namespace, solo añadir su key aquí.
_STATE_NAMESPACES = [
    "transparency_data",
    "collecting_data",
    "evaluation_results",
    "offer_data",
    "auth_control",
    "flow_result",
]

def build_node_transition_payload(
    node_name: str,
    node_output: dict,
) -> dict | None:
    """
    Construye el payload de un evento node_transition a partir del output
    de un nodo de LangGraph.

    Retorna None si no hay datos de sesión relevantes para emitir.
    Solo incluye en el payload los namespaces que el nodo realmente modificó
    (i.e., que están presentes como keys en node_output con valor no None).
    """
    session = node_output.get("session", {})
    current_node = session.get("current_node")

    if not current_node:
        return None

    payload = {
        "type": "node_transition",
        "node": current_node,
        "node_status": "SUCCESS",  # Extendible: ERROR, PROCESSING
        "product_intent": session.get("product_intent"),
        "application_id": session.get("application_id"),
        "friendly_label": None,    # Ver Paso 1.2
        "progress_percent": None,  # Ver Paso 1.2
    }

    # Inyección dinámica de namespaces: solo los que el nodo escribió
    for namespace_key in _STATE_NAMESPACES:
        value = node_output.get(namespace_key)
        if value is not None:
            payload[namespace_key] = value

    return payload
```

**Criterio de aceptación:** La función nunca hardcodea `loan`, `account` ni `dap`. Opera sobre los datos que LangGraph entrega, sin conocer el producto activo.

---

### Paso 1.2 — Integrar `friendly_label` y `progress_percent` desde `flux.js`

El `friendly_label` no existe en `state.py`; es metadata de presentación que vive en el Frontend (`flux.js → NODE_DETAILS`). Sin embargo, el Backend debe emitirlo para que el `ProcessPanel` funcione sin que el Frontend "conozca" la lógica de negocio.

**Solución:** Crear un diccionario de etiquetas en el Backend que espeje a `flux.js`. Este diccionario es el único lugar donde se puede agregar un nuevo nodo y su etiqueta.

```python
# backend/app/api/v1/chat.py

# Espejo del NODE_DETAILS de flux.js. Fuente de verdad para etiquetas en el stream.
_NODE_LABELS: dict[str, dict] = {
    "WELCOME_NODE":               {"label": "Recepcion",          "progress": 0},
    "INTENT_ROUTER":              {"label": "Clasificacion",       "progress": 5},
    "GENERAL_RESPONSE":           {"label": "Respuesta general",   "progress": 100},
    "LOAN_INIT":                  {"label": "Inicio credito",      "progress": 10},
    "LOAN_COLLECTING_PROFILE":    {"label": "Perfil financiero",   "progress": 20},
    "LOAN_COLLECTING_SIMULATION": {"label": "Simulacion",          "progress": 35},
    "LOAN_RISK_ENGINE":           {"label": "Motor de riesgo",     "progress": 55},
    "LOAN_PRE_APPROVED":          {"label": "Oferta transparente", "progress": 65},
    "LOAN_OTP_VALIDATION":        {"label": "Validacion OTP",      "progress": 80},
    "LOAN_FORMALIZATION":         {"label": "Formalizacion",       "progress": 90},
    "LOAN_COMPLETED":             {"label": "Credito completado",  "progress": 100},
    "LOAN_REJECTED_POLICY":       {"label": "Solicitud rechazada", "progress": 100},
    "LOAN_SECURITY_BLOCK":        {"label": "Bloqueo seguridad",   "progress": 100},
    "LOAN_CLOSED_BY_USER":        {"label": "Cierre voluntario",   "progress": 100},
    # Agregar ACCOUNT_* y DAP_* cuando sus flujos estén listos
}

def enrich_payload_with_labels(payload: dict) -> dict:
    """Agrega friendly_label y progress_percent al payload usando _NODE_LABELS."""
    node = payload.get("node", "")
    meta = _NODE_LABELS.get(node, {})
    payload["friendly_label"] = meta.get("label", node)
    payload["progress_percent"] = meta.get("progress", None)
    return payload
```

Actualizar `build_node_transition_payload` para llamar `enrich_payload_with_labels` antes de retornar.

---

### Paso 1.3 — Reemplazar la lógica de emisión en `stream_graph_response`

Sustituir el bloque `if session_update.get("current_node"):` del generador actual por la nueva función:

```python
# backend/app/api/v1/chat.py — Bloque de streaming actualizado (dentro del for)

async for event in compiled_graph.astream(initial_state, config=config):
    for node_name, node_output in event.items():
        last_node = node_name

        # 1. Emitir mensajes del asistente (sin cambios)
        messages = node_output.get("messages", [])
        for msg in messages:
            if hasattr(msg, "type") and msg.type == "ai":
                content = msg.content
                full_assistant_response += content
                sse_data = json.dumps({
                    "type": "message",
                    "content": content,
                    "node": node_name,
                })
                yield f"data: {sse_data}\n\n"

        # 2. Emitir transición de nodo con namespaces completos
        transition_payload = build_node_transition_payload(node_name, node_output)
        if transition_payload:
            transition_payload = enrich_payload_with_labels(transition_payload)
            yield f"data: {json.dumps(transition_payload)}\n\n"
```

**Resultado:** Un evento `node_transition` ahora puede verse así:

```json
{
  "type": "node_transition",
  "node": "LOAN_PRE_APPROVED",
  "node_status": "SUCCESS",
  "product_intent": "LOAN",
  "application_id": "uuid-solicitud",
  "friendly_label": "Oferta transparente",
  "progress_percent": 65,
  "transparency_data": {
    "loan": {
      "monto_aprobado": "$5.000.000",
      "cuota_mensual": "$235.000",
      "plazo_aprobado": "36 meses",
      "tasa_interes_mensual": "1,50%",
      "cae": "18,20%",
      "ctc": "$8.460.000",
      "total_intereses": "$3.460.000",
      "nivel_riesgo": "Medio"
    }
  }
}
```

---

### Paso 1.4 — Nodos tipo ENGINE: emitir estado `PROCESSING`

Los nodos `LOAN_RISK_ENGINE`, `ACCOUNT_EVALUATION_ENGINE` y `DAP_INVESTMENT_ENGINE` son "cajas negras". El Frontend debe mostrar un spinner mientras estos corren. Para ello, hay que emitir un evento `node_transition` con `node_status: "PROCESSING"` **antes** de que el nodo termine, y `"SUCCESS"` cuando entregue su output.

El patrón de LangGraph con `astream` solo entrega el output cuando el nodo termina. La solución correcta es emitir el `PROCESSING` desde el output del nodo anterior:

```python
# Lista de nodos cuya entrada debe pre-anunciar un estado PROCESSING
_ENGINE_NODES = {
    "LOAN_RISK_ENGINE",
    "ACCOUNT_EVALUATION_ENGINE",
    "DAP_INVESTMENT_ENGINE",
    "LOAN_FORMALIZATION",
}

# Dentro del bucle, al recibir session.current_node:
if transition_payload and transition_payload.get("node") in _ENGINE_NODES:
    processing_event = {
        "type": "node_transition",
        "node": transition_payload["node"],
        "node_status": "PROCESSING",
        "product_intent": transition_payload.get("product_intent"),
        "friendly_label": transition_payload.get("friendly_label"),
        "progress_percent": transition_payload.get("progress_percent"),
    }
    yield f"data: {json.dumps(processing_event)}\n\n"
    # El evento SUCCESS con los namespaces se emite al finalizar el nodo (lógica anterior)
```

> **Nota de diseño:** Esta es una solución pragmática. Si en el futuro se requiere streaming real mid-nodo (por ejemplo, para logs del motor), se puede implementar un `RunnableGenerator` en LangGraph que emita events parciales.

---

### Pruebas — Fase 1

#### Pruebas Automatizadas (pytest + httpx)

```python
# tests/api/test_sse_broker.py

import pytest, json
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_node_transition_includes_transparency_data(mock_graph_with_pre_approved):
    """
    Dado un grafo mockeado que llega a LOAN_PRE_APPROVED con transparency_data,
    el broker debe emitir un evento node_transition que incluya transparency_data.loan.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/chat",
            json={"message": "quiero un credito"},
            headers={"Authorization": "Bearer test-token"})
        
        events = parse_sse_stream(response.text)
        transitions = [e for e in events if e.get("type") == "node_transition"]
        pre_approved = next((e for e in transitions if e.get("node") == "LOAN_PRE_APPROVED"), None)
        
        assert pre_approved is not None
        assert "transparency_data" in pre_approved
        assert "loan" in pre_approved["transparency_data"]
        assert pre_approved["transparency_data"]["loan"]["monto_aprobado"] is not None

@pytest.mark.asyncio
async def test_engine_node_emits_processing_then_success(mock_graph_with_risk_engine):
    """
    Para LOAN_RISK_ENGINE, el broker debe emitir PROCESSING antes del SUCCESS.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/chat",
            json={"message": "continuar"},
            headers={"Authorization": "Bearer test-token"})
        
        events = parse_sse_stream(response.text)
        risk_events = [e for e in events
                       if e.get("type") == "node_transition"
                       and e.get("node") == "LOAN_RISK_ENGINE"]
        
        statuses = [e["node_status"] for e in risk_events]
        assert "PROCESSING" in statuses
        assert statuses.index("PROCESSING") < statuses.index("SUCCESS")

@pytest.mark.asyncio
async def test_no_product_hardcoding_in_payload_keys():
    """
    Las keys de primer nivel en node_transition no deben contener 'loan', 
    'account' o 'dap' — ese detalle vive DENTRO de los namespaces.
    """
    from app.api.v1.chat import build_node_transition_payload
    
    mock_output = {
        "session": {"current_node": "LOAN_PRE_APPROVED", "product_intent": "LOAN"},
        "transparency_data": {"loan": {"monto_aprobado": "$5.000.000"}},
    }
    payload = build_node_transition_payload("loan_pre_approved", mock_output)
    
    product_keys = [k for k in payload.keys() if k in ("loan", "account", "dap")]
    assert product_keys == [], f"Keys de producto encontradas en raíz: {product_keys}"
```

#### Prueba Manual (curl / Postman)

```bash
# 1. Obtener token JWT de la sesión activa
TOKEN="Bearer eyJ..."

# 2. Abrir stream en terminal
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: $TOKEN" \
  -d '{"message": "quiero solicitar un credito de consumo"}'

# 3. Qué validar en la respuesta:
#    a) Cada chunk comienza con "data: {"
#    b) Los eventos type:"node_transition" incluyen "friendly_label"
#    c) Al llegar a LOAN_PRE_APPROVED, el payload incluye "transparency_data"
#    d) Al llegar a LOAN_RISK_ENGINE, aparece node_status:"PROCESSING" seguido de "SUCCESS"
#    e) El último evento es type:"done" con conversation_id

# 4. Validar que no hay datos de un producto en la raíz del JSON:
#    CORRECTO: {"type":"node_transition","node":"LOAN_PRE_APPROVED","transparency_data":{"loan":{...}}}
#    INCORRECTO: {"type":"node_transition","loan_data":{...}}
```

---

## Fase 2: El Sistema Nervioso — `FluxContext.jsx`

### Objetivo Técnico
Extender `FluxContext.jsx` para que el estado de conversación refleje los nuevos namespaces emitidos por el Broker SSE, manteniendo compatibilidad con el código existente y sin romper la lógica de `riskResults` / `evaluationResults` que ya funciona.

---

### Paso 2.1 — Ampliar `createRuntimeState` con los nuevos namespaces

```jsx
// frontend/src/context/FluxContext.jsx

function createRuntimeState() {
  return {
    applicationId: null,
    nodeStatus: null,         // "PROCESSING" | "SUCCESS" | "ERROR"
    engineStatus: null,
    documentStatus: null,
    friendlyLabel: null,      // NUEVO: etiqueta legible del nodo actual
    progressPercent: null,    // NUEVO: porcentaje de progreso (0-100)
    evaluationResults: {},
    riskResults: null,
    transparencyData: {},     // NUEVO: namespace transparency_data del backend
    collectingData: {},       // NUEVO: namespace collecting_data del backend
    offerData: {},
    authControl: {},
    flowResult: null
  };
}
```

**Por qué es seguro:** `createRuntimeState` se usa en `createDraftConversation` y como base de `mapHistoryItem`. Agregar campos nuevos con valor `null` o `{}` no rompe ninguna renderización existente.

---

### Paso 2.2 — Agregar lectores de nuevos namespaces

Agregar funciones de lectura puras al estilo del resto del archivo:

```jsx
// frontend/src/context/FluxContext.jsx — Nuevas funciones de lectura

function readTransparencyData(payload) {
  // El backend emite transparency_data como namespace de primer nivel
  return payload.transparency_data ?? payload.transparencyData ?? null;
}

function readCollectingData(payload) {
  return payload.collecting_data ?? payload.collectingData ?? null;
}

function readFriendlyLabel(payload) {
  return payload.friendly_label ?? payload.friendlyLabel ?? null;
}

function readProgressPercent(payload) {
  const val = payload.progress_percent ?? payload.progressPercent ?? null;
  return val !== null ? Number(val) : null;
}

function readNodeStatus(payload) {
  return payload.node_status ?? payload.nodeStatus ?? null;
}
```

---

### Paso 2.3 — Actualizar `updateConversationFromPayload`

Dentro del `updater`, agregar las lecturas de los nuevos namespaces. Los campos existentes no se tocan:

```jsx
// frontend/src/context/FluxContext.jsx — Dentro de updateConversationFromPayload

function updateConversationFromPayload(conversationId, payload) {
  const updater = (conversation) => {
    // ── Lecturas existentes (sin cambios) ──
    const application = readApplicationPayload(payload);
    const nextNode = readNodeFromPayload(payload);
    const nextProductIntent = /* ... (código existente sin cambios) */;
    const nextEvaluationResults = readEvaluationResults(payload);
    const mergedEvaluationResults = mergeObjectPayload(conversation.evaluationResults, nextEvaluationResults);
    const nextOfferData = readOfferData(payload);
    const nextAuthControl = payload.auth_control ?? payload.authControl ?? null;
    const nextFlowResult = payload.flow_result ?? payload.flowResult ?? null;
    const productTitle = nextProductIntent ? getProductLabel(nextProductIntent) : conversation.title;

    // ── Nuevas lecturas (Fase 2) ──
    const nextTransparencyData = readTransparencyData(payload);
    const nextCollectingData = readCollectingData(payload);
    const nextFriendlyLabel = readFriendlyLabel(payload);
    const nextProgressPercent = readProgressPercent(payload);
    const nextNodeStatus = readNodeStatus(payload);

    return {
      ...conversation,
      // ── Campos existentes sin cambios ──
      applicationId: payload.application_id ?? payload.applicationId ?? application.id ?? conversation.applicationId,
      currentNode: nextNode ?? conversation.currentNode,
      nodeStatus: nextNodeStatus ?? conversation.nodeStatus,      // Actualizado: usa el nuevo lector
      engineStatus: /* ... (código existente) */,
      documentStatus: /* ... (código existente) */,
      evaluationResults: mergedEvaluationResults,
      riskResults: readLoanRiskResults(payload, nextEvaluationResults, conversation.riskResults),
      offerData: mergeObjectPayload(conversation.offerData, nextOfferData),
      authControl: mergeObjectPayload(conversation.authControl, nextAuthControl),
      flowResult: nextFlowResult ?? conversation.flowResult,
      productIntent: nextProductIntent,
      title: conversation.productName || productTitle,
      nodeSource: 'stream',
      updatedAt: new Date().toISOString(),

      // ── Nuevos campos (Fase 2) ──
      transparencyData: mergeObjectPayload(conversation.transparencyData, nextTransparencyData),
      collectingData: mergeObjectPayload(conversation.collectingData, nextCollectingData),
      friendlyLabel: nextFriendlyLabel ?? conversation.friendlyLabel,
      progressPercent: nextProgressPercent ?? conversation.progressPercent,
    };
  };
  // ... (resto del código existente sin cambios)
}
```

---

### Paso 2.4 — Actualizar `hasStatePayload` para los nuevos namespaces

```jsx
// frontend/src/context/FluxContext.jsx

function hasStatePayload(payload) {
  return Boolean(
    readNodeFromPayload(payload) ||
    payload.application_id || payload.applicationId ||
    payload.node_status || payload.nodeStatus ||
    payload.engine_status || payload.engineStatus ||
    payload.document_status || payload.documentStatus ||
    payload.evaluation_results || payload.evaluationResults ||
    payload.risk_results || payload.riskResults ||
    payload.offer_data || payload.offerData ||
    payload.auth_control || payload.authControl ||
    payload.flow_result || payload.flowResult ||
    // NUEVOS:
    payload.transparency_data || payload.transparencyData ||
    payload.collecting_data || payload.collectingData
  );
}
```

---

### Paso 2.5 — Gestión del estado PROCESSING (silencio de widgets)

El `nodeStatus: "PROCESSING"` ya se guarda en la conversación desde el Paso 2.3. Lo que hay que hacer es **exponerlo en el contexto** para que los componentes puedan reaccionar:

```jsx
// frontend/src/context/FluxContext.jsx — Dentro de FluxProvider

// El flag "sending" ya existe y cubre el streaming de mensajes.
// "isEngineRunning" cubre el estado PROCESSING de nodos ENGINE.
const isEngineRunning = selectedConversation?.nodeStatus === 'PROCESSING';

const value = {
  // ... (campos existentes sin cambios)
  isEngineRunning,  // NUEVO: true cuando un nodo ENGINE está corriendo
};
```

---

### Pruebas — Fase 2

#### Pruebas Automatizadas (Jest + React Testing Library)

```jsx
// frontend/src/__tests__/FluxContext.test.jsx

import { renderHook, act } from '@testing-library/react';
import { FluxProvider, FluxContext } from '../context/FluxContext';

describe('updateConversationFromPayload', () => {
  test('persiste transparencyData.loan en la conversación activa', async () => {
    // Simular la recepción de un evento node_transition con transparency_data
    const payload = {
      type: 'node_transition',
      node: 'LOAN_PRE_APPROVED',
      product_intent: 'LOAN',
      transparency_data: {
        loan: { monto_aprobado: '$5.000.000', cuota_mensual: '$235.000' }
      }
    };
    
    // ... setup del hook con conversación activa ...
    
    act(() => { updateConversationFromPayload(conversationId, payload); });
    
    expect(result.current.selectedConversation.transparencyData?.loan?.monto_aprobado)
      .toBe('$5.000.000');
  });

  test('friendlyLabel y progressPercent se actualizan desde el evento', async () => {
    const payload = {
      type: 'node_transition',
      node: 'LOAN_COLLECTING_PROFILE',
      friendly_label: 'Perfil financiero',
      progress_percent: 20,
    };
    
    // ...
    
    expect(result.current.selectedConversation.friendlyLabel).toBe('Perfil financiero');
    expect(result.current.selectedConversation.progressPercent).toBe(20);
  });

  test('nodeStatus PROCESSING activa isEngineRunning en el contexto', async () => {
    const payload = {
      type: 'node_transition',
      node: 'LOAN_RISK_ENGINE',
      node_status: 'PROCESSING',
    };
    
    // ...
    
    expect(result.current.isEngineRunning).toBe(true);
  });

  test('mergeObjectPayload es aditivo: no borra transparency_data de nodos anteriores', async () => {
    // Primer evento: llega transparency_data.loan
    // Segundo evento (nodo distinto): llega auth_control
    // Resultado: transparencyData sigue teniendo .loan
    // ...
  });
});
```

#### Prueba Manual (React DevTools)

```
1. Abrir la app en Chrome con React DevTools instalado.
2. Iniciar una conversación nueva y enviar "quiero un crédito de 3 millones".
3. Abrir React DevTools → Components → buscar "FluxProvider".
4. En el panel de props/state, expandir "selectedConversation".
5. Validar en tiempo real mientras el stream llega:
   a) "currentNode" cambia: LOAN_INIT → LOAN_COLLECTING_PROFILE → ...
   b) "friendlyLabel" se actualiza con cada node_transition.
   c) "progressPercent" aumenta progresivamente.
   d) Cuando llega LOAN_RISK_ENGINE: "nodeStatus" = "PROCESSING".
   e) Cuando llega LOAN_PRE_APPROVED: "transparencyData.loan" tiene datos.
   f) "nodeStatus" vuelve a "SUCCESS" después del ENGINE.
```

---

## Fase 3: Orquestación de Widgets — `CreditWidgets.jsx` y `LoanOfferCard.jsx`

### Objetivo Técnico
Hacer que el orquestador de widgets sea agnóstico al producto y que `LoanOfferCard` consuma la fuente de datos correcta (`transparencyData[product]`). Actualizar `flux.js` para completar la sincronización de diccionarios.

---

### Paso 3.1 — Refactorizar `CreditWidgets.jsx` con dispatch por sufijo de nodo

**El problema actual:** `if (!currentNode?.startsWith('LOAN_'))` impide que funcione con `ACCOUNT_PRE_APPROVED` o `DAP_PRE_APPROVED`.

**Solución:** Despachar por sufijo del nodo, no por prefijo del producto.

```jsx
// frontend/src/components/widgets/CreditWidgets.jsx — Versión Fase 2

import React from 'react';
import LoanOfferCard from './LoanOfferCard';
import OtpInput from './OtpInput';
import FlowClosure from './FlowClosure';

// Sufijos de nodo que determinan qué widget renderizar.
// Para agregar soporte a un nuevo producto, solo añadir sus nodos
// a estas constantes si tienen un comportamiento DIFERENTE.
// Si comparten sufijo (ej: ACCOUNT_PRE_APPROVED), ya funcionan sin cambios.
const CLOSURE_SUFFIXES = new Set([
  'REJECTED_POLICY',
  'SECURITY_BLOCK',
  'CLOSED_BY_USER',
  'COMPLETED',
]);

function getNodeSuffix(nodeId) {
  if (!nodeId) return null;
  // Extrae el sufijo: "LOAN_PRE_APPROVED" → "PRE_APPROVED"
  const parts = nodeId.split('_');
  // El prefijo del producto es siempre una sola palabra (LOAN, ACCOUNT, DAP)
  return parts.slice(1).join('_') || null;
}

export default function CreditWidgets({
  conversation,
  disabled,
  onAcceptOffer,
  onRejectOffer,
  onSubmitOtp
}) {
  const currentNode = conversation?.currentNode;
  const suffix = getNodeSuffix(currentNode);

  if (!suffix) return null;

  // Guard: solo renderizar widgets para nodos de producto conocido
  const product = conversation?.productIntent;
  const isProductNode = ['LOAN', 'ACCOUNT', 'DAP'].includes(product) && currentNode?.includes('_');

  if (!isProductNode) return null;

  return (
    <div className="dynamic-widgets">
      {suffix === 'PRE_APPROVED' && (
        <LoanOfferCard
          conversation={conversation}
          disabled={disabled}
          onAccept={onAcceptOffer}
          onReject={onRejectOffer}
        />
      )}

      {suffix === 'OTP_VALIDATION' && (
        <OtpInput
          authControl={conversation?.authControl}
          disabled={disabled}
          onSubmit={onSubmitOtp}
        />
      )}

      {CLOSURE_SUFFIXES.has(suffix) && (
        <FlowClosure conversation={conversation} />
      )}
    </div>
  );
}
```

**Resultado:** `ACCOUNT_PRE_APPROVED` → renderiza `LoanOfferCard` (que pasará a llamarse `OfferCard` en una refactorización futura). `DAP_COMPLETED` → renderiza `FlowClosure`. Cero cambios estructurales para los productos futuros.

---

### Paso 3.2 — Actualizar `LoanOfferCard.jsx` para consumir `transparencyData`

**Problema actual:** `readLoanResult` tiene una cadena de fallbacks que mezcla `riskResults`, `evaluationResults.loan_engine` y `offerData.loan`. Según el contrato de la guía, la fuente correcta y ya formateada es `transparency_data[product]`.

```jsx
// frontend/src/components/widgets/LoanOfferCard.jsx — Versión Fase 2

// Renombrar a OfferTransparencyCard.jsx en el futuro para generalidad.
// Por ahora, mantener el nombre para no romper imports existentes.

/**
 * Lee los datos de transparencia del producto activo.
 * Prioridad 1: transparency_data[product] (fuente correcta según contrato v2)
 * Prioridad 2 (fallback): riskResults o evaluationResults (compatibilidad v1)
 */
function readOfferDetails(conversation) {
  const product = (conversation?.productIntent ?? 'loan').toLowerCase();
  
  // Fuente primaria: transparency_data[product_intent]
  const fromTransparency = conversation?.transparencyData?.[product] ?? null;
  if (fromTransparency && Object.keys(fromTransparency).length > 0) {
    return { source: 'transparency', data: fromTransparency };
  }

  // Fallback de compatibilidad (Fase 1 sin broker actualizado)
  const legacyData =
    conversation?.riskResults ??
    conversation?.evaluationResults?.loan_engine ??
    conversation?.evaluationResults?.loanEngine ??
    conversation?.offerData?.loan ??
    {};
  
  return { source: 'legacy', data: legacyData };
}

export default function LoanOfferCard({ conversation, disabled, onAccept, onReject }) {
  const { source, data: result } = readOfferDetails(conversation);

  // Los campos de transparency_data ya vienen formateados como strings desde el backend.
  // Los campos legacy pueden ser números y necesitan formato.
  const isFormatted = source === 'transparency';

  const fmt = (value) => value ?? 'Pendiente';
  const fmtClp = (value) => isFormatted ? fmt(value) : formatClp(value);
  const fmtPct = (value) => isFormatted ? fmt(value) : formatPercent(value);

  const hasOfferData = Object.keys(result).length > 0;

  const details = [
    ['Monto aprobado',  fmtClp(result.monto_aprobado ?? result.montoAprobado)],
    ['Plazo',           result.plazo_aprobado ?? result.plazoAprobado
                          ? `${result.plazo_aprobado ?? result.plazoAprobado}` : 'Pendiente'],
    ['Tasa mensual',    fmtPct(result.tasa_interes_mensual ?? result.tasaInteresMensual)],
    ['Cuota mensual',   fmtClp(result.cuota_mensual ?? result.cuotaMensual)],
    ['CAE',             fmtPct(result.cae)],
    ['Costo total',     fmtClp(result.ctc)],
    ['Intereses',       fmtClp(result.total_intereses ?? result.totalIntereses)],
  ];

  // ... (JSX sin cambios respecto a la versión actual)
}
```

**Importante:** El fallback a `riskResults` garantiza que si el backend todavía no emite `transparency_data` (durante el desarrollo), la card sigue funcionando.

---

### Paso 3.3 — Actualizar `flux.js` para sincronizar nodos de ACCOUNT y DAP

El `NODE_DETAILS` de `flux.js` no tiene entradas para los nodos de `ACCOUNT` y `DAP` que ya existen en `workflow.py`. Hay que agregar sus entradas para que `getNodeMeta` no retorne "Nodo no mapeado":

```javascript
// frontend/src/constants/flux.js — Agregar al NODE_DETAILS existente

// ── Cuenta Corriente ─────────────────────────────────────────
ACCOUNT_INIT: {
  label: 'Inicio cuenta',
  description: 'FLUX abre la solicitud de Cuenta Corriente.'
},
ACCOUNT_COLLECTING_PROFILE: {
  label: 'Perfil financiero',
  description: 'Se recopila renta y antigüedad laboral.'
},
ACCOUNT_EVALUATION_ENGINE: {
  label: 'Evaluacion comercial',
  description: 'El backend evalua la apertura de cuenta.'
},

// ── Deposito a Plazo ─────────────────────────────────────────
DAP_INIT: {
  label: 'Inicio DAP',
  description: 'FLUX abre la solicitud de Depósito a Plazo.'
},
DAP_COLLECT_DATA: {
  label: 'Parametros de inversion',
  description: 'Se define monto, moneda y plazo.'
},
DAP_INVESTMENT_ENGINE: {
  label: 'Motor de inversion',
  description: 'El backend calcula tasa y retorno estimado.'
},
```

Actualizar también `NODE_ALIASES` para mapear los snake_case de LangGraph:

```javascript
// Agregar al NODE_ALIASES:
account_init: 'ACCOUNT_INIT',
account_collecting_profile: 'ACCOUNT_COLLECTING_PROFILE',
account_evaluation_engine: 'ACCOUNT_EVALUATION_ENGINE',
dap_init: 'DAP_INIT',
dap_collect_data: 'DAP_COLLECT_DATA',
dap_investment_engine: 'DAP_INVESTMENT_ENGINE',
```

---

### Paso 3.4 — Exponer `ProcessPanel` con los nuevos campos del contexto

El `ProcessPanel` debe consumir `friendlyLabel` y `progressPercent` directamente del contexto. El componente receptor (sea `ChatPanel.jsx` o el layout principal) debe usar:

```jsx
// Ejemplo de uso en ChatPanel.jsx o el layout principal

const { selectedConversation, isEngineRunning } = useContext(FluxContext);

<ProcessPanel
  label={selectedConversation?.friendlyLabel ?? 'Iniciando...'}
  progress={selectedConversation?.progressPercent ?? 0}
  isLoading={isEngineRunning}  // Muestra spinner cuando hay ENGINE en curso
  product={selectedConversation?.productIntent}
/>
```

---

### Pruebas — Fase 3

#### Pruebas Automatizadas

```jsx
// frontend/src/__tests__/CreditWidgets.test.jsx

describe('CreditWidgets — dispatch por sufijo', () => {
  test('renderiza LoanOfferCard para LOAN_PRE_APPROVED', () => {
    const conv = { currentNode: 'LOAN_PRE_APPROVED', productIntent: 'LOAN', transparencyData: {} };
    render(<CreditWidgets conversation={conv} />);
    expect(screen.getByLabelText('Tarjeta de transparencia')).toBeInTheDocument();
  });

  test('renderiza LoanOfferCard para ACCOUNT_PRE_APPROVED (simetría)', () => {
    const conv = { currentNode: 'ACCOUNT_PRE_APPROVED', productIntent: 'ACCOUNT', transparencyData: {} };
    render(<CreditWidgets conversation={conv} />);
    expect(screen.getByLabelText('Tarjeta de transparencia')).toBeInTheDocument();
  });

  test('NO renderiza nada para nodos ENGINE (silencio)', () => {
    const conv = { currentNode: 'LOAN_RISK_ENGINE', productIntent: 'LOAN' };
    const { container } = render(<CreditWidgets conversation={conv} />);
    expect(container.firstChild).toBeEmptyDOMElement();
  });

  test('renderiza FlowClosure para cualquier sufijo terminal', () => {
    ['LOAN_COMPLETED', 'ACCOUNT_COMPLETED', 'LOAN_REJECTED_POLICY'].forEach(node => {
      const product = node.split('_')[0];
      const conv = { currentNode: node, productIntent: product };
      const { container } = render(<CreditWidgets conversation={conv} />);
      expect(container.querySelector('.flow-closure')).not.toBeNull();
    });
  });
});

// frontend/src/__tests__/LoanOfferCard.test.jsx

test('prioriza transparency_data sobre riskResults', () => {
  const conv = {
    productIntent: 'LOAN',
    transparencyData: { loan: { monto_aprobado: '$5.000.000', cuota_mensual: '$235.000' } },
    riskResults: { monto_aprobado: 4000000 },  // Valor diferente en legacy
  };
  render(<LoanOfferCard conversation={conv} />);
  expect(screen.getByText('$5.000.000')).toBeInTheDocument();  // Fuente primaria
  expect(screen.queryByText('$4.000.000')).not.toBeInTheDocument();  // Legacy ignorado
});
```

#### Prueba Manual (Navegador)

```
Escenario: Flujo completo de Crédito de Consumo

1. Iniciar conversación nueva.
2. Escribir "Quiero un crédito de 3 millones a 24 meses".
3. Verificar en la barra lateral (ProcessPanel):
   a) El label cambia: "Inicio crédito" → "Perfil financiero" → "Simulación".
   b) La barra de progreso avanza visualmente con cada nodo.
4. Al llegar a LOAN_RISK_ENGINE:
   a) Confirmar que el ProcessPanel muestra un spinner o estado "Calculando...".
   b) Confirmar que NO aparece ningún widget de interacción en el chat.
5. Al llegar a LOAN_PRE_APPROVED:
   a) Confirmar que aparece la LoanOfferCard con datos reales del backend.
   b) Abrir DevTools → Network → buscar el último chunk SSE y verificar que
      el JSON tiene "transparency_data.loan.monto_aprobado" con valor string.
   c) Los botones "Aceptar" y "Rechazar" están habilitados (sending=false).
6. Hacer clic en "Aceptar Oferta":
   a) El widget se deshabilita inmediatamente (sending=true).
   b) El mensaje "ACEPTAR_OFERTA_CREDITO" aparece en el chat.
   c) El flujo avanza al nodo OTP_VALIDATION.
7. Al llegar a LOAN_OTP_VALIDATION:
   a) Aparece el widget OtpInput con el número de intentos restantes.
   b) Ingresar un código de 6 dígitos y presionar enviar.
   c) El código se envía como mensaje de texto plano.
```

---

## Fase 4: Cierre y Seguridad — `FlowClosure` y manejo de errores

### Objetivo Técnico
Conectar `FlowClosure` con los datos de `offer_data[product].display_data` del backend, implementar la validación del hash SHA-256, y asegurar un manejo elegante de errores y desconexiones del `EventSource`.

---

### Paso 4.1 — Definir la interfaz de props de `FlowClosure`

`FlowClosure` debe leer de `offer_data[product].display_data` (vía `offerData` en la conversación) y de `flow_result` (vía `flowResult`):

```jsx
// frontend/src/components/widgets/FlowClosure.jsx — Interfaz esperada

/**
 * Lee los datos de cierre del producto activo.
 * 
 * Backend emite: offer_data[product].display_data
 * FluxContext guarda como: conversation.offerData[product].display_data
 * flow_result → conversation.flowResult
 */
function readClosureData(conversation) {
  const product = (conversation?.productIntent ?? 'loan').toLowerCase();
  const offerProduct = conversation?.offerData?.[product] ?? {};

  return {
    // Datos de éxito (COMPLETED)
    downloadUrl: offerProduct.display_data?.download_url ?? offerProduct.file_contrato_path ?? null,
    securityHash: offerProduct.display_data?.security_hash ?? offerProduct.hash_sha256 ?? null,
    contractStatus: offerProduct.contract_status ?? null,
    
    // Datos de rechazo
    rejectionReason: offerProduct.display_data?.reason ?? null,
    
    // Estado de cierre
    statusCode: conversation?.flowResult?.status_code ?? null,
    closedAt: conversation?.flowResult?.closed_at ?? null,
  };
}

export default function FlowClosure({ conversation }) {
  const { downloadUrl, securityHash, rejectionReason, statusCode } = readClosureData(conversation);
  const isSuccess = statusCode === 'SUCCESS' || conversation?.currentNode?.endsWith('COMPLETED');

  return (
    <section className="flow-closure" aria-label="Cierre del proceso">
      {isSuccess ? (
        <SuccessView
          downloadUrl={downloadUrl}
          securityHash={securityHash}
        />
      ) : (
        <RejectionView
          reason={rejectionReason}
          statusCode={statusCode}
        />
      )}
    </section>
  );
}
```

---

### Paso 4.2 — Implementar validación SHA-256 en el Frontend

El hash SHA-256 se muestra al usuario para que pueda verificar la integridad del contrato. El Frontend también puede validarlo en el momento de descarga:

```jsx
// Dentro de SuccessView

async function verifyDocumentIntegrity(downloadUrl, expectedHash) {
  try {
    const response = await fetch(downloadUrl);
    const buffer = await response.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const actualHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    return actualHash === expectedHash?.toLowerCase();
  } catch {
    return null; // No se pudo verificar (error de red)
  }
}

// En el componente, exponer el hash para el usuario y verificar al descargar:
<p className="security-hash" aria-label="Hash de integridad SHA-256">
  SHA-256: <code>{securityHash}</code>
</p>
<button
  onClick={async () => {
    const isValid = await verifyDocumentIntegrity(downloadUrl, securityHash);
    if (isValid === false) {
      alert('Advertencia: El documento no coincide con el hash de integridad.');
    }
    window.open(downloadUrl, '_blank');
  }}
>
  Descargar Contrato
</button>
```

---

### Paso 4.3 — Manejo de desconexiones y errores del EventSource

El servicio `streamChat` en `api.js` debe implementar reconexión con backoff y limpieza de recursos. Esta es una tarea de `frontend/src/services/api.js` pero se especifica aquí por completitud:

```javascript
// frontend/src/services/api.js — Mejoras recomendadas para streamChat

export async function streamChat({ accessToken, message, conversationId, onOpen, onEvent }) {
  return new Promise((resolve, reject) => {
    let eventSource;
    
    // Timeout de seguridad: si no llega "done" en 5 minutos, cerrar
    const timeoutId = setTimeout(() => {
      eventSource?.close();
      reject(new Error('Stream timeout: el backend no respondió en el tiempo esperado.'));
    }, 5 * 60 * 1000);

    // Registrar el EventSource en un AbortController (para cancelación manual)
    // ...

    eventSource.onerror = (err) => {
      clearTimeout(timeoutId);
      eventSource.close();
      // No rechazar si ya se recibió "done" — el error puede ser el cierre normal del stream
      if (!streamCompleted) {
        reject(new Error('La conexión con el servidor se interrumpió inesperadamente.'));
      }
    };

    eventSource.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        onEvent(payload);
        if (payload.type === 'done') {
          streamCompleted = true;
          clearTimeout(timeoutId);
          eventSource.close();
          resolve();
        }
        if (payload.type === 'error') {
          clearTimeout(timeoutId);
          eventSource.close();
          resolve(); // No rechazar — el error se maneja en FluxContext via onEvent
        }
      } catch (parseError) {
        console.error('SSE parse error:', parseError, e.data);
      }
    };
  });
}
```

---

### Paso 4.4 — Manejo de errores de negocio en `FluxContext.jsx`

El evento `type: "error"` del backend ya se maneja en `sendMessage`. Solo hay que asegurar que el widget correcto se muestre cuando `nodeStatus === 'ERROR'`:

```jsx
// En CreditWidgets.jsx — agregar guard de error
if (conversation?.nodeStatus === 'ERROR') {
  return (
    <div className="widget-error" role="alert">
      <p>Hubo un problema procesando tu solicitud. Por favor, inténtalo de nuevo.</p>
    </div>
  );
}
```

---

### Pruebas — Fase 4

#### Pruebas Automatizadas

```javascript
// tests/api/test_sse_error_handling.py

@pytest.mark.asyncio
async def test_error_event_on_graph_exception(mock_graph_that_raises):
    """El broker emite type:'error' cuando el grafo lanza una excepción."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/v1/chat", ...)
        events = parse_sse_stream(response.text)
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1
        assert "detail" in error_events[0]

@pytest.mark.asyncio
async def test_done_event_always_sent_after_error():
    """Incluso con error, el stream debe terminar con type:'done' o type:'error' — nunca colgado."""
    # Verificar que el generador siempre termina limpiamente
    pass
```

```jsx
// frontend/src/__tests__/FlowClosure.test.jsx

test('muestra SHA-256 visible al usuario en modo SUCCESS', () => {
  const conv = {
    currentNode: 'LOAN_COMPLETED',
    productIntent: 'LOAN',
    offerData: {
      loan: {
        hash_sha256: 'abc123',
        file_contrato_path: 'https://example.com/contrato.pdf',
        contract_status: 'SIGNED_AND_STAMPED'
      }
    },
    flowResult: { status_code: 'SUCCESS' }
  };
  render(<FlowClosure conversation={conv} />);
  expect(screen.getByText(/abc123/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Descargar/i })).toBeEnabled();
});

test('muestra razón de rechazo en modo REJECTED', () => {
  const conv = {
    currentNode: 'LOAN_REJECTED_POLICY',
    productIntent: 'LOAN',
    offerData: {
      loan: { display_data: { reason: 'No cumple política de antigüedad mínima.' } }
    },
    flowResult: { status_code: 'REJECTED' }
  };
  render(<FlowClosure conversation={conv} />);
  expect(screen.getByText(/política de antigüedad/i)).toBeInTheDocument();
});
```

#### Prueba Manual

```
Escenario: Manejo de error de red

1. Iniciar un flujo de crédito hasta llegar a LOAN_COLLECTING_PROFILE.
2. En Chrome DevTools → Network → seleccionar la request del stream SSE.
3. Hacer clic derecho → "Block request URL".
4. Enviar el siguiente mensaje de chat.
5. Verificar que:
   a) Aparece un mensaje de error legible en la UI (no un spinner infinito).
   b) El campo de input de mensaje vuelve a estar habilitado (sending=false).
   c) No hay errores en la consola de JavaScript no capturados.
   d) Desbloquear la URL y enviar un nuevo mensaje: la conversación reanuda
      correctamente sin duplicar el estado.
```

---

## 6. Riesgos de Integración

### Riesgo 1 — Mismatch de campos entre `state.py` y el broker 🔴 Alto

**Descripción:** `node_output` en LangGraph contiene solo los campos que **el nodo modificó** en ese turno, no el estado completo. Si `LOAN_RISK_ENGINE` no escribe `transparency_data` (porque ese namespace lo escribe `LOAN_PRE_APPROVED`), el broker no lo emitirá para el nodo del motor. El Frontend recibiría el `node_transition` de `LOAN_RISK_ENGINE` sin `transparency_data` — lo cual es correcto — pero el desarrollador puede confundirlo con un bug.

**Mitigación:** Documentar en el código del broker que la ausencia de un namespace en un evento es intencional (el nodo no lo modificó). Agregar un test que valide qué namespaces emite cada nodo específico. Considerar que el broker use `compiled_graph.aget_state(config)` para leer el estado completo del checkpointer en nodos terminales.

---

### Riesgo 2 — Estado inicial desincronizado al reanudar conversaciones 🟡 Medio

**Descripción:** Al reanudar una conversación existente (`conversation_id` no nulo), el `initial_state` en `chat.py` sobreescribe los namespaces con dicts vacíos (`"collecting_data": {}`, `"evaluation_results": {}`). Si LangGraph usa el checkpointer de Supabase, el estado previo debería restaurarse desde ahí. Pero si la restauración falla silenciosamente, el Frontend vería un estado corrupto.

**Mitigación:** En `chat.py`, para conversaciones reanudadas, el `initial_state` solo debe incluir `messages` y `user_data`. Los namespaces deben omitirse para que LangGraph los restaure del checkpointer. Agregar un test de integración que verifique la restauración.

```python
# chat.py — estado inicial simplificado para conversaciones reanudadas
if request.conversation_id:
    initial_state = {
        "messages": [HumanMessage(content=user_message)],
        "user_data": { ... }  # Solo datos necesarios para el turno
        # Sin collecting_data, evaluation_results, etc.
    }
```

---

### Riesgo 3 — Race condition entre `promoteDraftConversation` y `updateConversationFromPayload` 🟡 Medio

**Descripción:** En `FluxContext.jsx`, `promoteDraftConversation` se llama en `onOpen` (cuando se recibe el header `X-Conversation-Id`). Pero los primeros eventos SSE pueden llegar antes de que React procese el cambio de estado de draft a conversación real, causando que `updateConversationFromPayload` aplique al `DRAFT_ID` en lugar del ID real.

**Mitigación:** La lógica actual usa `activeConversationId` como variable mutable de closure, lo cual es la solución correcta. Sin embargo, hay que verificar que `promoteDraftConversation` actualiza `activeConversationId` antes del primer `onEvent`. Agregar un test que simule un stream veloz.

---

### Riesgo 4 — `FluxState` v2.0 vs el `initial_state` actual de `chat.py` 🔴 Alto

**Descripción:** El `initial_state` construido en `stream_graph_response` usa las keys de la v1.0 (`"collected_data"`, `"control_flags"`), que ya no existen en `FluxState` v2.0. Esto puede causar que LangGraph ignore o rechace esos campos, o que los nodos de destino fallen al intentar leer namespaces que no existen.

**Mitigación:** Actualizar el `initial_state` inmediatamente para alinearlo con `FluxState` v2.0:

```python
# chat.py — initial_state actualizado para FluxState v2.0
initial_state = {
    "messages": [HumanMessage(content=user_message)],
    "user_data": { ... },
    "session": {
        "conversation_id": thread_id,
        "current_node": "START",
        "product_intent": None,
        "is_transversal_active": False,
        "progress": {},
    },
    # Namespaces v2.0: inicializar vacíos para que LangGraph los restaure
    "collecting_data": {},
    "evaluation_results": {},
    "offer_data": {},
    "auth_control": {
        "security_blocked": False,
        "service_error": False,
        "otp_attempts": 0,
    },
    "transparency_data": {},
    "flow_result": None,
}
# ELIMINAR: "collected_data" y "control_flags" (v1.0)
```

---

### Riesgo 5 — `LoanOfferCard` muestra datos vacíos si el producto no tiene transparency_data 🟡 Medio

**Descripción:** Si `ACCOUNT_PRE_APPROVED` llega sin `transparency_data.account` (porque ese producto aún no tiene motor financiero), `LoanOfferCard` mostrará "Pendiente" en todos los campos sin dar contexto al usuario.

**Mitigación:** En `CreditWidgets.jsx`, agregar un guard adicional:
```jsx
{suffix === 'PRE_APPROVED' && (
  conversation?.transparencyData?.[product?.toLowerCase()] ? (
    <LoanOfferCard ... />
  ) : (
    <ProcessingIndicator label="Preparando oferta..." />
  )
)}
```

---

### Riesgo 6 — Doble emisión de `node_transition` para nodos que se concatenan en el mismo turno 🟢 Bajo

**Descripción:** En `workflow.py`, `loan_init` tiene un edge fijo hacia `loan_collecting_profile` (sin END intermedio). Esto significa que en un mismo turno de `astream`, LangGraph puede emitir dos nodos: `loan_init` y `loan_collecting_profile`. El Frontend recibirá dos eventos `node_transition` consecutivos, y el `ProcessPanel` hará un "salto" visual.

**Mitigación:** Aceptable por ahora. El estado final es correcto. Si se quiere suavizar la experiencia, agregar un debounce de 300ms en `ProcessPanel` antes de actualizar el label visible.

---

## 7. Checklist de Entrega

### Backend (`backend/app/api/v1/chat.py`)
- [ ] Función `build_node_transition_payload` implementada y testeada
- [ ] Función `enrich_payload_with_labels` con `_NODE_LABELS` completo
- [ ] Lista `_ENGINE_NODES` y emisión de evento `PROCESSING`
- [ ] `initial_state` actualizado a `FluxState` v2.0 (sin `collected_data` ni `control_flags`)
- [ ] Tests: `test_sse_broker.py` con los 3 casos descritos

### Frontend — `FluxContext.jsx`
- [ ] `createRuntimeState` con `transparencyData`, `collectingData`, `friendlyLabel`, `progressPercent`
- [ ] Funciones `readTransparencyData`, `readCollectingData`, `readFriendlyLabel`, `readProgressPercent`
- [ ] `updateConversationFromPayload` actualizado
- [ ] `hasStatePayload` actualizado
- [ ] `isEngineRunning` exportado desde el contexto
- [ ] Tests: `FluxContext.test.jsx` con los 4 casos descritos

### Frontend — `CreditWidgets.jsx`
- [ ] Guard por sufijo de nodo (`getNodeSuffix`)
- [ ] Eliminado el guard `startsWith('LOAN_')`
- [ ] Guard de error para `nodeStatus === 'ERROR'`
- [ ] Tests: `CreditWidgets.test.jsx` con los 4 casos (incluyendo ACCOUNT)

### Frontend — `LoanOfferCard.jsx`
- [ ] `readOfferDetails` con prioridad `transparencyData[product]`
- [ ] Fallback de compatibilidad hacia `riskResults`
- [ ] Formateo condicional según fuente (`isFormatted`)
- [ ] Tests: `LoanOfferCard.test.jsx`

### Frontend — `flux.js`
- [ ] `NODE_DETAILS` con entradas para todos los nodos de `workflow.py`
- [ ] `NODE_ALIASES` actualizado con nodos de ACCOUNT y DAP
- [ ] Sincronía verificada con la tabla de nodos de `workflow.py`

### Frontend — `FlowClosure.jsx`
- [ ] `readClosureData` con acceso dinámico por `productIntent`
- [ ] Validación SHA-256 en descarga
- [ ] Tests: `FlowClosure.test.jsx`

### Frontend — `services/api.js`
- [ ] Timeout de seguridad en `streamChat`
- [ ] Cierre limpio del `EventSource` en error y en `done`

---

*Este documento es la fuente de verdad para la Fase 2 de integración FLUX. Cualquier desviación del contrato definido aquí debe ser aprobada por el equipo y reflejada en una nueva versión del documento.*
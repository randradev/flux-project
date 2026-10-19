import React, { createContext, useEffect, useState } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import {
  fetchConversationHistory,
  fetchConversationMessages,
  hasApiConfig,
  streamChat,
  apiBaseUrl,
  deleteConversation
} from '../services/api';
import { getProductFromNode, getProductLabel, normalizeNodeId, getNodeMeta } from '../constants/flux';

export const DRAFT_ID = '__draft__';

export const FluxContext = createContext(null);

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

function createDraftConversation() {
  return {
    id: DRAFT_ID,
    isDraft: true,
    title: 'Nueva conversacion',
    productName: '',
    productIntent: null,
    currentNode: null,
    nodeSource: 'local',
    messages: [],
    detailLoaded: true,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...createRuntimeState()
  };
}

function formatConversationTitle(item) {
  const productIntent = item.product_types?.code || item.productIntent;
  const currentNode = item.current_node_id || item.current_node || item.currentNode;
  
  // Nombres cortos de batalla para el historial
  const shortLabels = {
    LOAN: 'Crédito',
    ACCOUNT: 'Cuenta',
    DAP: 'Inversión',
    GENERAL: 'Flux'
  };

  const productLabel = shortLabels[productIntent] || 'Flux';
  const nodeMeta = getNodeMeta(currentNode);
  const stage = nodeMeta.label; // Ej: "Simulación"

  // Si es general, algo muy breve
  if (!productIntent || productIntent === 'GENERAL') {
    const date = new Date(item.updated_at || item.created_at || Date.now());
    return `Flux: ${date.toLocaleDateString('es-CL', { day: 'numeric', month: 'short' })}`;
  }

  // Formato ultra-corto: "Crédito · Simulación"
  return stage ? `${productLabel} · ${stage}` : productLabel;
}

function mapHistoryItem(item) {
  // 1. Normalizamos los datos de navegación
  const currentNode = normalizeNodeId(item.current_node_id ?? item.current_node ?? item.currentStep ?? null);
  const productIntent = getProductFromNode(currentNode, item.product_types?.code ?? null);
  
  // 2. Extraemos el Snapshot (la "foto" de la sesión que manda el backend)
  const snapshot = item.state_snapshot || {};
  // 3. Creamos el objeto con los datos ya hidratados
  const mapped = {
    id: item.id,
    isDraft: false,
    productIntent,
    currentNode,
    productName: item.product_types?.name || '',
    messages: [],
    detailLoaded: false,
    createdAt: item.created_at,
    updatedAt: item.updated_at || item.created_at,
    
    // --- AQUÍ ESTÁ EL TRUCO: Hidratamos los datos desde el snapshot ---
    transparencyData: snapshot.transparency_data || {},
    collectingData: snapshot.collecting_data || {},
    evaluationResults: snapshot.evaluation_results || {},
    offerData: snapshot.offer_data || {},
    authControl: snapshot.auth_control || {},
    flowResult: snapshot.flow_result || null
  };
  // 4. Generamos el título con los datos ya puestos
  mapped.title = formatConversationTitle(mapped);
  return mapped;
}

function mapMessage(item) {
  return {
    id: String(item.id ?? crypto.randomUUID()),
    role: item.role,
    content: item.content,
    nodeAtTime: item.node_at_time ?? null,
    createdAt: item.created_at ?? new Date().toISOString()
  };
}

function appendMessageToConversation(conversations, conversationId, message) {
  return conversations.map((conversation) => {
    if (conversation.id !== conversationId) {
      return conversation;
    }

    return {
      ...conversation,
      messages: [...conversation.messages, message],
      detailLoaded: true,
      updatedAt: new Date().toISOString()
    };
  });
}

function readApplicationPayload(payload) {
  return payload.application ?? payload.financial_application ?? payload.financialApplication ?? {};
}

function readNodeFromPayload(payload) {
  const application = readApplicationPayload(payload);
  return normalizeNodeId(
    payload.current_node_id ??
      payload.currentNodeId ??
      payload.current_node ??
      payload.currentNode ??
      payload.current_step ??
      payload.currentStep ??
      payload.node ??
      application.current_node_id ??
      application.currentNodeId ??
      application.current_node ??
      application.currentNode ??
      null
  );
}

// 1. Añadir este ayudante cerca de los otros (ej: después de readOfferData)
function readTransparencyData(payload) {
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

function readEvaluationResults(payload) {
  const direct = payload.evaluation_results ?? payload.evaluationResults ?? null;

  if (direct) {
    return direct;
  }

  const loanEngine =
    payload.loan_engine ??
    payload.loanEngine ??
    payload.risk_results ??
    payload.riskResults ??
    payload.risk_result ??
    payload.riskResult ??
    null;

  return loanEngine ? { loan_engine: loanEngine } : null;
}

function readLoanRiskResults(payload, evaluationResults, currentRiskResults) {
  return (
    payload.risk_results ??
    payload.riskResults ??
    payload.loan_engine ??
    payload.loanEngine ??
    evaluationResults?.loan_engine ??
    evaluationResults?.loanEngine ??
    currentRiskResults
  );
}

function readOfferData(payload) {
  const direct = payload.offer_data ?? payload.offerData ?? null;
  const loanOffer = payload.loan_offer ?? payload.loanOffer ?? payload.offer ?? null;

  if (direct) {
    return direct;
  }

  return loanOffer ? { loan: loanOffer } : null;
}

function mergeObjectPayload(current, next) {
  if (!next || typeof next !== 'object') {
    return current;
  }

  return {
    ...(current ?? {}),
    ...next
  };
}

function hasStatePayload(payload) {
  return Boolean(
    readNodeFromPayload(payload) ||
      payload.application_id ||
      payload.applicationId ||
      payload.node_status ||
      payload.nodeStatus ||
      payload.engine_status ||
      payload.engineStatus ||
      payload.document_status ||
      payload.documentStatus ||
      payload.evaluation_results ||
      payload.evaluationResults ||
      payload.risk_results ||
      payload.riskResults ||
      payload.offer_data ||
      payload.offerData ||
      payload.auth_control ||
      payload.authControl ||
      payload.flow_result ||
      payload.flowResult ||
      // NUEVOS:
      payload.transparency_data || payload.transparencyData ||
      payload.collecting_data || payload.collectingData
  );
}

export function FluxProvider({ accessToken, children }) {
  const [conversations, setConversations] = useState([]);
  const [draftConversation, setDraftConversation] = useState(createDraftConversation());
  const [selectedConversationId, setSelectedConversationId] = useState(DRAFT_ID);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [appError, setAppError] = useState('');

  useEffect(() => {
    if (!accessToken || !hasApiConfig) {
      return;
    }

    refreshHistory();
  }, [accessToken]);

/*   // ── AUTO-SELECCIÓN INICIAL ──
  // Solo queremos auto-seleccionar la primera conversación al CARGAR la app, 
  // no cada vez que el usuario elige "Nueva Conversación".
  const hasAutoSelected = React.useRef(false); // Necesitas importar useRef o usar React.useRef
  useEffect(() => {
    // Si ya auto-seleccionamos una vez, o si el usuario ya eligió algo, no hacemos nada.
    if (hasAutoSelected.current || conversations.length === 0) return;
    // Solo al inicio, si estamos en el estado inicial, cargamos la última conversación
    if (selectedConversationId === DRAFT_ID) {
      setSelectedConversationId(conversations[0].id);
      hasAutoSelected.current = true;
    }
  }, [conversations]); */

  function mergeHistory(nextItems) {
    setConversations((current) => {
      const existingById = new Map(current.map((item) => [item.id, item]));
      const merged = nextItems.map((item) => {
        const existing = existingById.get(item.id);
        const shouldKeepLiveNode =
          existing?.nodeSource === 'stream' &&
          existing.currentNode &&
          existing.currentNode !== item.currentNode;

        const snapshot = item.state_snapshot || {};

        return {
          ...item,
          messages: existing?.messages ?? [],
          detailLoaded: existing?.detailLoaded ?? false,
          // Preservamos el estado capturado para que no desaparezca al refrescar la lista
          // Priorizamos el estado 'existing' (en memoria) sobre el 'snapshot' (base de datos)
          collectingData: existing?.collectingData ?? snapshot.collecting_data ?? {},
          evaluationResults: existing?.evaluationResults ?? snapshot.evaluation_results ?? {},
          offerData: existing?.offerData ?? snapshot.offer_data ?? {},
          transparencyData: existing?.transparencyData ?? snapshot.transparency_data ?? {},
          applicationId: existing?.applicationId ?? snapshot.session?.application_id ?? null,
          productIntent: existing?.productIntent ?? snapshot.session?.product_intent ?? item.productIntent,
          currentNode: shouldKeepLiveNode ? existing.currentNode : (snapshot.session?.current_node || item.currentNode),
          nodeSource: shouldKeepLiveNode ? 'stream' : item.nodeSource
        };
      });

      // --- ESTO ES LO NUEVO: Preservar el DRAFT si existe ---
      const draft = existingById.get(DRAFT_ID);
      if (draft && !merged.find(m => m.id === DRAFT_ID)) {
        merged.push(draft);
      }

      const missingSelected =
        selectedConversationId &&
        selectedConversationId !== DRAFT_ID &&
        // current.find((item) => item.id === selectedConversationId) &&
        !merged.find((item) => item.id === selectedConversationId);

      if (missingSelected) {
        const existing = current.find((item) => item.id === selectedConversationId);
        if (existing) {
          merged.unshift(existing);
        }
      }
      
      const localOnly = current.filter(c => 
        c.id !== DRAFT_ID && !merged.find(m => m.id === c.id)
      );
      
      return [...localOnly, ...merged]; // <--- Combinamos ambas
    });
  }

  async function refreshHistory() {
    if (!accessToken || !hasApiConfig) {
      return;
    }

    setLoadingHistory(true);
    setAppError('');

    try {
      const historyItems = await fetchConversationHistory(accessToken);
      mergeHistory(historyItems.map(mapHistoryItem));
    } catch (error) {
      setAppError(error.message);
    } finally {
      setLoadingHistory(false);
    }
  }

  async function loadConversation(conversationId) {
    if (!conversationId || conversationId === DRAFT_ID) {
      return;
    }

    const target = conversations.find((item) => item.id === conversationId);

    if (target?.detailLoaded) {
      return;
    }

    setLoadingMessages(true);
    setAppError('');

    try {
      const payload = await fetchConversationMessages(accessToken, conversationId);
      const snapshot = payload.state_snapshot || {};

      setConversations((current) =>
        current.map((item) => {
          if (item.id !== conversationId) {
            return item;
          }

          return {
            ...item,
            messages: (payload.messages || []).map(mapMessage),
            detailLoaded: true,
            // Hidratación desde el snapshot del servidor
            transparencyData: snapshot.transparency_data || snapshot.transparencyData || item.transparencyData,
            collectingData: snapshot.collecting_data || snapshot.collectingData || item.collectingData,
            evaluationResults: snapshot.evaluation_results || snapshot.evaluationResults || item.evaluationResults,
            offerData: snapshot.offer_data || snapshot.offerData || item.offerData,
            authControl: snapshot.auth_control || snapshot.authControl || item.authControl,
            flowResult: snapshot.flow_result || snapshot.flowResult || item.flowResult
          };
        })
      );
    } catch (error) {
      setAppError(error.message);
    } finally {
      setLoadingMessages(false);
    }
  }

  async function selectConversation(conversationId) {
    setSelectedConversationId(conversationId);
    if (conversationId !== DRAFT_ID) {
      await loadConversation(conversationId);
    }
  }

  function startDraftConversation() {
    setDraftConversation(createDraftConversation());
    setSelectedConversationId(DRAFT_ID);
    setAppError('');
  }

  function promoteDraftConversation(conversationId, initialMessages = []) {
    // Marcamos que ya hubo una selección (la nuestra), para que el useEffect no interfiera
    hasAutoSelected.current = true; 
    setConversations((current) => {
      if (current.find(c => c.id === conversationId)) return current;
      return [
        {
          ...draftConversation,
          id: conversationId,
          isDraft: false,
          nodeSource: 'stream',
          messages: initialMessages
        },
        ...current
      ];
    });
    setSelectedConversationId(conversationId);
  }

  function updateConversationFromPayload(conversationId, payload) {
    const updater = (conversation) => {
      const application = readApplicationPayload(payload);
      const nextNode = readNodeFromPayload(payload);
      const nextProductIntent =
        payload.product_intent ??
        payload.productIntent ??
        application.product_intent ??
        application.productIntent ??
        getProductFromNode(nextNode, conversation.productIntent);
      const nextEvaluationResults = readEvaluationResults(payload);
      const mergedEvaluationResults = mergeObjectPayload(
        conversation.evaluationResults,
        nextEvaluationResults
      );
      const nextOfferData = readOfferData(payload);
      const nextAuthControl = payload.auth_control ?? payload.authControl ?? null;
      const nextFlowResult = payload.flow_result ?? payload.flowResult ?? null;
      const productTitle = nextProductIntent ? getProductLabel(nextProductIntent) : conversation.title;

      // ── Nuevas lecturas (Fase 2) ──
      const nextTransparencyData = mergeObjectPayload(conversation.transparencyData, readTransparencyData(payload));
      const nextCollectingData = readCollectingData(payload);
      const nextFriendlyLabel = readFriendlyLabel(payload);
      const nextProgressPercent = readProgressPercent(payload);
      const nextNodeStatus = readNodeStatus(payload);

      return {
        ...conversation,
        applicationId:
          payload.application_id ??
          payload.applicationId ??
          application.id ??
          application.application_id ??
          conversation.applicationId,
        currentNode: nextNode ?? conversation.currentNode,
        nodeStatus:
          payload.node_status ??
          payload.nodeStatus ??
          application.node_status ??
          application.nodeStatus ??
          conversation.nodeStatus,
        engineStatus:
          payload.engine_status ??
          payload.engineStatus ??
          application.engine_status ??
          application.engineStatus ??
          conversation.engineStatus,
        documentStatus:
          payload.document_status ??
          payload.documentStatus ??
          application.document_status ??
          application.documentStatus ??
          conversation.documentStatus,
        evaluationResults: mergedEvaluationResults,
        riskResults: readLoanRiskResults(payload, nextEvaluationResults, conversation.riskResults),
        offerData: mergeObjectPayload(conversation.offerData, nextOfferData),
        authControl: mergeObjectPayload(conversation.authControl, nextAuthControl),
        flowResult: nextFlowResult ?? conversation.flowResult,
        productIntent: nextProductIntent,
        title: formatConversationTitle({ ...conversation, currentNode: nextNode }),
        nodeSource: 'stream',
        updatedAt: new Date().toISOString(),
        // ── Nuevos campos (Fase 2) ──
        transparencyData: mergeObjectPayload(conversation.transparencyData, nextTransparencyData),
        collectingData: mergeObjectPayload(conversation.collectingData, nextCollectingData),
        friendlyLabel: nextFriendlyLabel ?? conversation.friendlyLabel,
        progressPercent: nextProgressPercent ?? conversation.progressPercent,
      };
    };

    if (conversationId === DRAFT_ID) {
      setDraftConversation((current) => updater(current));
      return;
    }

    setConversations((current) =>
      current.map((conversation) => (conversation.id === conversationId ? updater(conversation) : conversation))
    );
  }

  function appendLocalMessage(conversationId, message) {
    if (conversationId === DRAFT_ID) {
      setDraftConversation((current) => ({
        ...current,
        messages: [...current.messages, message],
        detailLoaded: true,
        updatedAt: new Date().toISOString()
      }));
      return;
    }

    setConversations((current) => appendMessageToConversation(current, conversationId, message));
  }

  function handleStreamEvent(event, targetId) {
    if (event.type === 'message') {
      appendLocalMessage(targetId, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: event.content ?? '',
        createdAt: new Date().toISOString(),
        nodeAtTime: normalizeNodeId(event.node) ?? null
      });
    }

    if (event.type === 'node_transition' || hasStatePayload(event)) {
      updateConversationFromPayload(targetId, event);
    }

    if (event.type === 'done') {
      console.log("Proceso completado para:", event.conversation_id);
      setSelectedConversationId(event.conversation_id);
      setConversations(prev => prev.map(c => 
        c.id === DRAFT_ID ? { ...c, id: event.conversation_id } : c
      ));
      setSending(false);
    }

    if (event.type === 'error') {
      setAppError(event.detail || 'Error en el stream.');
      setSending(false);
    }
  }


  async function sendMessage(text, productIntent = null, forcedConversationId = undefined) {
  const cleanText = text.trim();
  if (!cleanText || !accessToken || sending) {
    return;
  }
  setSending(true);
  setAppError('');
  // 2. Lógica de ID Robusta: si mandamos null, forzamos una conversación nueva
  const baseId = forcedConversationId !== undefined ? forcedConversationId : selectedConversationId;
  const effectiveId = (baseId && baseId !== DRAFT_ID) ? baseId : null;
  
  let activeConversationId = effectiveId || DRAFT_ID;

  const userMessage = {
    id: crypto.randomUUID(),
    role: 'user',
    content: cleanText,
    createdAt: new Date().toISOString(),
    nodeAtTime: null
  };

  appendLocalMessage(activeConversationId, userMessage);

    try {
      await streamChat({
        accessToken,
        message: cleanText,
        conversationId: effectiveId,
        productIntent: productIntent,
        onOpen: ({ conversationId }) => {
          /* if (activeConversationId === DRAFT_ID && conversationId) {
            activeConversationId = conversationId;
            promoteDraftConversation(conversationId);
          } */
        },
        onEvent: (event) => {
          if (event.type === 'message') {
            const targetConversationId = activeConversationId || DRAFT_ID;

            appendLocalMessage(targetConversationId, {
              id: crypto.randomUUID(),
              role: 'assistant',
              content: event.content ?? '',
              createdAt: new Date().toISOString(),
              nodeAtTime: normalizeNodeId(event.node) ?? null
            });
          }

          if (event.type === 'node_transition' || hasStatePayload(event)) {
            const targetConversationId = activeConversationId || DRAFT_ID;
            updateConversationFromPayload(targetConversationId, event);
          }

          if (event.type === 'done') {
            console.log("Finalizando stream para:", event.conversation_id);
            
            setConversations(prev => prev.map(c => 
              c.id === DRAFT_ID ? { ...c, id: event.conversation_id, isDraft: false } : c
            ));
            
            setSelectedConversationId(event.conversation_id);
            setSending(false);
            // El "truco" para la demo: darle 500ms antes de refrescar la lista lateral
            setTimeout(() => {
              refreshHistory();
            }, 500);
          }

          if (event.type === 'error') {
            setAppError(event.detail || 'El backend reporto un error durante el stream.');
          }
        }
      });

      // await refreshHistory();
    } catch (error) {
      setAppError(error.message);
      appendLocalMessage(activeConversationId, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `No fue posible completar el envio: ${error.message}`,
        createdAt: new Date().toISOString(),
        nodeAtTime: null
      });
    } finally {
      setSending(false);
    }
  }

  async function sendAction(action) {
    
    console.log("Intentando ejecutar acción:", action, "en conversación:", selectedConversationId);
    
    if (!selectedConversationId || selectedConversationId === DRAFT_ID) {
        console.warn("Acción abortada: ID no válido o es DRAFT");
        return;
    }

    setSending(true);
    setAppError('');

    try {
      await fetchEventSource(`${apiBaseUrl}/api/v1/action`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({
          conversation_id: selectedConversationId,
          action: action
        }),
        onmessage: (msg) => {
          const event = JSON.parse(msg.data);
          // ¡Aquí usamos el helper!
          handleStreamEvent(event, selectedConversationId);
        },
        onerror: (err) => {
          setAppError('Error al ejecutar la acción.');
          setSending(false);
        }
      });
      
      await refreshHistory();
    } catch (error) {
      setAppError(error.message);
    } finally {
      setSending(false);
    }
  }



  function sendLoanOfferAccepted() {
    // Al usar sendMessage, el mensaje aparecerá en el chat y se usará el API normal
    return sendMessage("Acepto la oferta de crédito");
  }
  function sendLoanOfferRejected() {
    return sendMessage("Rechazo la oferta");
  }


  function sendOtpCode(code) {
    return sendMessage(String(code ?? '').trim());
  }

  const selectedConversation =
    selectedConversationId === DRAFT_ID
      ? draftConversation
      : conversations.find((item) => item.id === selectedConversationId) ?? draftConversation;

  const isEngineRunning = selectedConversation?.nodeStatus === 'PROCESSING';
  
  async function deleteChat(conversationId) {
    try {
      // Pasamos el accessToken que ya tenemos en el scope del contexto
      await deleteConversation(accessToken, conversationId);
      
      if (selectedConversationId === conversationId) {
        startDraftConversation();
      }
      
      setConversations(prev => prev.filter(c => c.id !== conversationId));
    } catch (error) {
      console.error("Error borrando chat:", error);
      setAppError("No se pudo eliminar la conversación");
    }
  }

  const value = {
    apiBaseUrl,
    appError,
    clearAppError: () => setAppError(''),
    conversations,
    DRAFT_ID,
    hasApiConfig,
    loadingHistory,
    loadingMessages,
    refreshHistory,
    selectedConversation,
    selectedConversationId,
    onAcceptLoanOffer: sendLoanOfferAccepted, 
    onRejectLoanOffer: sendLoanOfferRejected,
    selectConversation,
    sendLoanOfferAccepted,
    sendLoanOfferRejected,
    sendMessage,
    sendOtpCode,
    sending,
    startDraftConversation,
    deleteChat,
    isEngineRunning,  // NUEVO: true cuando un nodo ENGINE está corriendo
  };

  return <FluxContext.Provider value={value}>{children}</FluxContext.Provider>;
}

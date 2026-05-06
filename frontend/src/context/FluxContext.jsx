import React, { createContext, useEffect, useState } from 'react';
import {
  fetchConversationHistory,
  fetchConversationMessages,
  hasApiConfig,
  streamChat,
  apiBaseUrl
} from '../services/api';
import { getProductFromNode, getProductLabel, normalizeNodeId } from '../constants/flux';

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
  const productName = item.product_types?.name ?? '';

  if (productName) {
    return productName;
  }

  const date = new Date(item.updated_at || item.created_at || Date.now());

  return `Conversacion ${date.toLocaleDateString('es-CL')}`;
}

function mapHistoryItem(item) {
  const currentNode = normalizeNodeId(item.current_node_id ?? item.current_node ?? item.currentStep ?? null);
  const productIntent = getProductFromNode(currentNode, item.product_types?.code ?? null);

  return {
    id: item.id,
    isDraft: false,
    title: formatConversationTitle(item),
    productName: item.product_types?.name ?? '',
    productIntent,
    currentNode,
    nodeSource: 'history',
    isActive: item.is_active ?? true,
    messages: [],
    detailLoaded: false,
    createdAt: item.created_at ?? null,
    updatedAt: item.updated_at ?? item.created_at ?? null,
    ...createRuntimeState()
  };
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

  useEffect(() => {
    if (selectedConversationId) {
      return;
    }

    if (conversations.length) {
      setSelectedConversationId(conversations[0].id);
      return;
    }

    setSelectedConversationId(DRAFT_ID);
  }, [conversations, selectedConversationId]);

  function mergeHistory(nextItems) {
    setConversations((current) => {
      const existingById = new Map(current.map((item) => [item.id, item]));
      const merged = nextItems.map((item) => {
        const existing = existingById.get(item.id);
        const shouldKeepLiveNode =
          existing?.nodeSource === 'stream' &&
          existing.currentNode &&
          existing.currentNode !== item.currentNode;

        return {
          ...item,
          messages: existing?.messages ?? [],
          detailLoaded: existing?.detailLoaded ?? false,
          productIntent: existing?.productIntent ?? null,
          currentNode: shouldKeepLiveNode ? existing.currentNode : item.currentNode,
          nodeSource: shouldKeepLiveNode ? 'stream' : item.nodeSource
        };
      });

      const missingSelected =
        selectedConversationId &&
        selectedConversationId !== DRAFT_ID &&
        current.find((item) => item.id === selectedConversationId) &&
        !merged.find((item) => item.id === selectedConversationId);

      if (missingSelected) {
        const existing = current.find((item) => item.id === selectedConversationId);
        if (existing) {
          merged.unshift(existing);
        }
      }

      return merged;
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
      const messageItems = await fetchConversationMessages(accessToken, conversationId);
      setConversations((current) =>
        current.map((item) => {
          if (item.id !== conversationId) {
            return item;
          }

          return {
            ...item,
            messages: messageItems.map(mapMessage),
            detailLoaded: true
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

  function promoteDraftConversation(conversationId) {
    setConversations((current) => [
      {
        ...draftConversation,
        id: conversationId,
        isDraft: false,
        title: draftConversation.title || 'Conversacion FLUX',
        nodeSource: 'stream'
      },
      ...current
    ]);
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
      const nextTransparencyData = readTransparencyData(payload);
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

  async function sendMessage(text, productIntent = null) {
    const cleanText = text.trim();

    if (!cleanText || !accessToken || sending) {
      return;
    }

    setSending(true);
    setAppError('');

    let activeConversationId = selectedConversationId || DRAFT_ID;

    appendLocalMessage(activeConversationId, {
      id: crypto.randomUUID(),
      role: 'user',
      content: cleanText,
      createdAt: new Date().toISOString(),
      nodeAtTime: null
    });

    try {
      await streamChat({
        accessToken,
        message: cleanText,
        conversationId: activeConversationId === DRAFT_ID ? null : activeConversationId,
        productIntent: productIntent,
        onOpen: ({ conversationId }) => {
          if (activeConversationId === DRAFT_ID && conversationId) {
            activeConversationId = conversationId;
            promoteDraftConversation(conversationId);
          }
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

          if (event.type === 'done' && event.conversation_id) {
            activeConversationId = event.conversation_id;
            setSelectedConversationId(event.conversation_id);
          }

          if (event.type === 'error') {
            setAppError(event.detail || 'El backend reporto un error durante el stream.');
          }
        }
      });

      await refreshHistory();
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

  function sendLoanOfferAccepted() {
    return sendMessage('ACEPTAR_OFERTA_CREDITO');
  }

  function sendLoanOfferRejected() {
    return sendMessage('RECHAZAR_OFERTA_CREDITO');
  }

  function sendOtpCode(code) {
    return sendMessage(String(code ?? '').trim());
  }

  const selectedConversation =
    selectedConversationId === DRAFT_ID
      ? draftConversation
      : conversations.find((item) => item.id === selectedConversationId) ?? draftConversation;

  const isEngineRunning = selectedConversation?.nodeStatus === 'PROCESSING';

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
    selectConversation,
    sendLoanOfferAccepted,
    sendLoanOfferRejected,
    sendMessage,
    sendOtpCode,
    sending,
    startDraftConversation,
    isEngineRunning,  // NUEVO: true cuando un nodo ENGINE está corriendo
  };

  return <FluxContext.Provider value={value}>{children}</FluxContext.Provider>;
}

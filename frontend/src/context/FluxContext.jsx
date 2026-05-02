import React, { createContext, useEffect, useState } from 'react';
import {
  fetchConversationHistory,
  fetchConversationMessages,
  hasApiConfig,
  streamChat,
  apiBaseUrl
} from '../services/api';
import { getProductLabel } from '../constants/flux';

const DRAFT_ID = '__draft__';

export const FluxContext = createContext(null);

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
    updatedAt: new Date().toISOString()
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
  return {
    id: item.id,
    isDraft: false,
    title: formatConversationTitle(item),
    productName: item.product_types?.name ?? '',
    productIntent: null,
    currentNode: item.current_node ?? null,
    nodeSource: 'history',
    isActive: item.is_active ?? true,
    messages: [],
    detailLoaded: false,
    createdAt: item.created_at ?? null,
    updatedAt: item.updated_at ?? item.created_at ?? null
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

  function updateConversationNode(conversationId, payload) {
    const updater = (conversation) => ({
      ...conversation,
      currentNode: payload.node ?? conversation.currentNode,
      productIntent: payload.product_intent ?? conversation.productIntent,
      title: getProductLabel(payload.product_intent, conversation.productName || conversation.title),
      nodeSource: 'stream',
      updatedAt: new Date().toISOString()
    });

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

  async function sendMessage(text) {
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
              nodeAtTime: event.node ?? null
            });
          }

          if (event.type === 'node_transition') {
            const targetConversationId = activeConversationId || DRAFT_ID;
            updateConversationNode(targetConversationId, event);
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

  const selectedConversation =
    selectedConversationId === DRAFT_ID
      ? draftConversation
      : conversations.find((item) => item.id === selectedConversationId) ?? draftConversation;

  const value = {
    apiBaseUrl,
    appError,
    clearAppError: () => setAppError(''),
    conversations,
    hasApiConfig,
    loadingHistory,
    loadingMessages,
    refreshHistory,
    selectedConversation,
    selectedConversationId,
    selectConversation,
    sendMessage,
    sending,
    startDraftConversation
  };

  return <FluxContext.Provider value={value}>{children}</FluxContext.Provider>;
}

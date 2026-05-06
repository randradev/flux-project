const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

export const apiBaseUrl = rawApiBaseUrl.replace(/\/$/, '');
export const hasApiConfig = Boolean(apiBaseUrl);

class ApiError extends Error {
  constructor(message, status = 500) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function readJsonSafe(response) {
  const text = await response.text();

  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

async function authorizedFetch(path, accessToken, init = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${accessToken}`,
      ...(init.headers ?? {})
    }
  });

  if (!response.ok) {
    const payload = await readJsonSafe(response);
    const detail =
      payload?.detail ?? payload?.message ?? `La API respondio con estado ${response.status}.`;
    throw new ApiError(detail, response.status);
  }

  return response;
}

export async function fetchConversationHistory(accessToken) {
  const response = await authorizedFetch('/api/v1/history', accessToken);
  const payload = await response.json();
  return payload.conversations ?? [];
}

export async function fetchConversationMessages(accessToken, conversationId) {
  const response = await authorizedFetch(`/api/v1/history/${conversationId}`, accessToken);
  const payload = await response.json();
  return payload.messages ?? [];
}

function parseSseChunk(chunk) {
  const lines = chunk
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => line.startsWith('data:'));

  if (!lines.length) {
    return [];
  }

  const payload = lines.map((line) => line.slice(5).trimStart()).join('\n');

  try {
    return [JSON.parse(payload)];
  } catch {
    return [];
  }
}

export async function streamChat({
  accessToken,
  message,
  conversationId,
  productIntent, // <--- 1. Asegúrate que reciba el parámetro
  signal,
  onOpen,
  onEvent
}) {
  const response = await authorizedFetch('/api/v1/chat', accessToken, {
    method: 'POST',
    signal,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream'
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId ?? null,
      product_intent: productIntent, // <--- 2. Y que lo envíe al backend
    })
  });

  const headerConversationId = response.headers.get('X-Conversation-Id');

  onOpen?.({
    conversationId: headerConversationId
  });

  if (!response.body) {
    throw new ApiError('La respuesta del backend no incluyo stream SSE.', response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    const chunks = buffer.split(/\r?\n\r?\n/);
    buffer = chunks.pop() ?? '';

    for (const chunk of chunks) {
      const events = parseSseChunk(chunk);

      for (const event of events) {
        onEvent?.(event);
      }
    }

    if (done) {
      break;
    }
  }

  if (buffer.trim()) {
    const trailingEvents = parseSseChunk(buffer);

    for (const event of trailingEvents) {
      onEvent?.(event);
    }
  }
}

export { ApiError };

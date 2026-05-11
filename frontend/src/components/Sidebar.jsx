import React from 'react';
import Brand from './Brand';
import { getProductIcon } from '../constants/flux';

function formatTimestamp(value) {
  if (!value) {
    return 'Sin fecha';
  }

  const date = new Date(value);

  return new Intl.DateTimeFormat('es-CL', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
}

export default function Sidebar({
  conversations,
  loadingHistory,
  onNewConversation,
  onRefresh,
  onSelectConversation,
  selectedConversationId
}) {
  return (
    <aside className="left-panel">
      <div className="sidebar-head">
        <Brand />
      </div>

      <div className="sidebar-actions">
        <button className="primary-button flux-orange-btn" type="button" onClick={onNewConversation}>
          <span>Nueva conversación</span>
        </button>
      </div>

      <div className="panel-title-row">
        <span>Tu historial</span>
        <small>{conversations.length} conversaciones</small>
      </div>

      <div className="chat-history" aria-label="Historial de conversaciones">
        {selectedConversationId === '__draft__' && (
          <button
            className="history-card selected draft-card orange-theme"
            onClick={onNewConversation}
            type="button"
          >
            <span className="history-icon">🚀</span>
            <div className="history-info">
              <small>Justo ahora</small>
              <strong>Tu próximo paso</strong>
            </div>
          </button>
        )}

        {conversations.map((conversation) => (
          <button
            key={conversation.id}
            className={`history-card ${selectedConversationId === conversation.id ? 'selected' : ''}`}
            onClick={() => onSelectConversation(conversation.id)}
            type="button"
          >
            <span className="history-icon">
              {getProductIcon(conversation.productIntent, conversation.productName)}
            </span>
            <div className="history-info">
              <small>{formatTimestamp(conversation.updatedAt)}</small>
              <strong>{conversation.title}</strong>
            </div>
          </button>
        ))}
      </div>

      {/* <div className="sidebar-foot">
        <button className="secondary-button" type="button" disabled>
          Borrar conversacion
        </button>
      </div> */}
    </aside>
  );
}

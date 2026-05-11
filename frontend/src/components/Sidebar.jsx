import React, { useContext, useState } from 'react';
import { FluxContext } from '../context/FluxContext';
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
  selectedConversationId,

}) {

const [showConfirm, setShowConfirm] = useState(false);
const [idToDelete, setIdToDelete] = useState(null);

  const { deleteChat } = useContext(FluxContext);

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
        // 1. Envolvemos todo en un div con la clase history-item
        <div key={conversation.id} className="history-item"> 
          <button
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
          {/* 2. El botón de borrar ahora es hermano del principal, dentro del div */}
          <button 
            className="delete-chat-btn"
            onClick={(e) => {
              e.stopPropagation();
              setIdToDelete(conversation.id);
              setShowConfirm(true);
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
            </svg>
          </button>
        </div>
      ))}
      </div>

      {/* <div className="sidebar-foot">
        <button className="secondary-button" type="button" disabled>
          Borrar conversacion
        </button>
      </div> */}
    {showConfirm && (
  <div className="modal-overlay">
    <div className="modal-card">
      <div className="modal-icon-container">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
        </svg>
      </div>
      <h3 className="modal-title">¿Borrar chat?</h3>
      <p className="modal-text">Esta acción es permanente y no podrás recuperar los mensajes de esta conversación.</p>
      <div className="modal-actions">
        <button className="modal-btn modal-btn-cancel" onClick={() => setShowConfirm(false)}>
          Cancelar
        </button>
        <button className="modal-btn modal-btn-delete" onClick={() => {
          deleteChat(idToDelete);
          setShowConfirm(false);
        }}>
          Borrar ahora
        </button>
      </div>
    </div>
  </div>
)}
    </aside>
  );
}

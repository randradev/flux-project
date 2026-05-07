import React, { useEffect, useRef, useState } from 'react';
import Brand from './Brand';
import CreditWidgets from './widgets/CreditWidgets';
import WelcomeMessage from './WelcomeMessage';

function formatMessageTime(value) {
  if (!value) {
    return '';
  }

  return new Intl.DateTimeFormat('es-CL', {
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value));
}

export default function ChatPanel({
  apiBaseUrl,
  conversation,
  loadingMessages,
  onAcceptLoanOffer,
  onLogout,
  onRejectLoanOffer,
  onSendMessage,
  onSubmitOtp,
  sending,
  user
}) {
  const [message, setMessage] = useState('');
  const windowRef = useRef(null);

  useEffect(() => {
    if (!windowRef.current) {
      return;
    }

    windowRef.current.scrollTop = windowRef.current.scrollHeight;
  }, [conversation?.messages?.length, conversation?.currentNode, sending]);

  function handleProductSelect(intent, label) {
    onSendMessage(`Me interesa: ${label}`, intent);
  }


  function handleSubmit(event) {
    event.preventDefault();
    if (!message.trim()) {
      return;
    }

    onSendMessage(message);
    setMessage('');
  }

  return (
    <section className="chat-panel">
      <header className="chat-header">
        <div className="chat-brand">
          <Brand />
          <div>
            <strong>{user?.user_metadata?.full_name || user?.email || 'Sesion FLUX'}</strong>
            {/* <small>{apiBaseUrl}</small> */}
          </div>
        </div>

        <button className="secondary-button" type="button" onClick={onLogout}>
          Cerrar sesion
        </button>
      </header>

      <div className="chat-status-row">
        <span className="status-chip">{sending ? 'Streaming SSE activo' : 'Listo para enviar'}</span>
        <span className="status-chip muted">
          {conversation?.isDraft ? 'Draft local' : conversation?.id || 'Sin conversation_id'}
        </span>
        {conversation?.applicationId && (
          <span className="status-chip muted">{conversation.applicationId}</span>
        )}
      </div>

      <div ref={windowRef} className="chat-window" aria-live="polite">
        {!conversation?.messages?.length && (
          <WelcomeMessage onSelect={handleProductSelect} />
        )}
      

        {loadingMessages && (
          <section className="loading-inline">
            <p>Cargando mensajes persistidos...</p>
          </section>
        )}

        {conversation?.messages?.map((item) => (
          <article key={item.id} className={`message ${item.role}`}>
            <div className="message-bubble">
              <p>{item.content}</p>
              <small>
                {item.role} {item.nodeAtTime ? `- ${item.nodeAtTime}` : ''} {formatMessageTime(item.createdAt)}
              </small>
            </div>
          </article>
        ))}

        <CreditWidgets
          conversation={conversation}
          disabled={sending}
          onAcceptOffer={onAcceptLoanOffer}
          onRejectOffer={onRejectLoanOffer}
          onSubmitOtp={onSubmitOtp}
        />
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <input
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Escribe un mensaje para FLUX..."
          disabled={sending}
        />
        <button className="primary-button composer-button" type="submit" disabled={sending}>
          {sending ? 'Enviando...' : 'Enviar'}
        </button>
      </form>
    </section>
  );
}

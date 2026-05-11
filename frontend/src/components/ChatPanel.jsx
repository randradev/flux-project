import React, { useEffect, useRef, useState } from 'react';
import Brand from './Brand';
import CreditWidgets from './widgets/CreditWidgets';
import AccountWidgets from './widgets/AccountWidgets';
import DapWidgets from './widgets/DapWidgets';
import WelcomeMessage from './WelcomeMessage';
import FluxLoadingFeedback from './FluxLoagingFeedback';


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

  const lastAssistantIndex = [...(conversation?.messages || [])]
    .reverse()
    .findIndex(m => m.role === 'assistant');
  const actualLastAssistantIndex = lastAssistantIndex !== -1
    ? (conversation.messages.length - 1 - lastAssistantIndex)
    : -1;

  useEffect(() => {
    if (!windowRef.current) {
      return;
    }

    windowRef.current.scrollTop = windowRef.current.scrollHeight;
  }, [conversation?.messages?.length, conversation?.currentNode, sending]);

  // A. Forzar nueva conversación al elegir producto (Línea 44 aprox)
  function handleProductSelect(intent, label) {
    // Pasamos null como tercer argumento para forzar la creación de un nuevo hilo en el backend
    onSendMessage(intent, intent, null);
  }
  // B. Ocultar WelcomeMessage mientras carga la historia (Línea 87 aprox)
  // Esto evita que el usuario haga clic en un botón "fantasma" mientras se carga un chat viejo
  {!conversation?.messages?.length && !loadingMessages && (
    <WelcomeMessage onSelect={handleProductSelect} />
  )}


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

      <div ref={windowRef} className="chat-window" aria-live="polite">
        {!conversation?.messages?.length && !loadingMessages && (
          <WelcomeMessage onSelect={handleProductSelect} />
        )}

        {loadingMessages && (
          <div className="skeleton-container" aria-hidden="true">
            <div className="skeleton-bubble user" style={{ width: '40%' }} />
            <div className="skeleton-bubble assistant" />
            <div className="skeleton-bubble user" style={{ width: '70%' }} />
            <div className="skeleton-bubble assistant" style={{ width: '50%' }} />
          </div>
        )}

        
        {conversation?.messages?.map((item, index) => (
          <React.Fragment key={item.id}>
            <article className={`message ${item.role}`}>
              <div className="message-bubble">
                <p>{item.content}</p>
                <small>
                  {item.role === 'user' ? 'Tú' : 'Asistente Flux'} {' | '} {formatMessageTime(item.createdAt)}
                </small>
              </div>
            </article>
            {/* INSERTAMOS LOS WIDGETS AQUÍ: Justo después del último mensaje del asistente */}
            {index === actualLastAssistantIndex && (
              <div className="widgets-flow-container flux-widget-entry" style={{ margin: '1.5rem 0' }}>
                <CreditWidgets
                  conversation={conversation}
                  disabled={sending}
                  onAcceptOffer={onAcceptLoanOffer}
                  onRejectOffer={onRejectLoanOffer}
                />
                <AccountWidgets
                  conversation={conversation}
                  disabled={sending}
                />
                <DapWidgets
                  conversation={conversation}
                  disabled={sending}
                />
              </div>
            )}
          </React.Fragment>
        ))}

        {sending && conversation?.messages?.at(-1)?.role === 'user' && (
          <FluxLoadingFeedback />
        )}
      </div>

      {!!conversation?.messages?.length && (
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
      )}
    </section>
  );
}

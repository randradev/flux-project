import React from 'react';
import ChatPanel from './ChatPanel';
import ConfigNotice from './ConfigNotice';
import ProcessPanel from './ProcessPanel';
import Sidebar from './Sidebar';
import { useAuth } from '../hooks/useAuth';
import { useFlux } from '../hooks/useFlux';
import ProductSelectorModal from './ProductSelectorModal';

export default function Dashboard() {
  const { hasSupabaseConfig, signOut, user } = useAuth();
  const {
    apiBaseUrl,
    appError,
    clearAppError,
    conversations,
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
    DRAFT_ID,
    startDraftConversation
  } = useFlux();

  const missingConfigLines = [
    !hasSupabaseConfig && 'Falta configurar Supabase Auth.',
    !hasApiConfig && 'Falta configurar la URL base del backend.'
  ].filter(Boolean);

  const isNewConversation = 
    selectedConversationId === DRAFT_ID && 
    (!selectedConversation?.messages || selectedConversation.messages.length === 0);

  const handleProductSelect = (intent, label) => {
    // Enviamos el mensaje inicial con la intención oculta
    sendMessage(`Me interesa: ${label}`, intent);
  };


  return (
    <main className="app-shell">
      <Sidebar
        conversations={conversations}
        loadingHistory={loadingHistory}
        onNewConversation={startDraftConversation}
        onRefresh={refreshHistory}
        onSelectConversation={selectConversation}
        selectedConversationId={selectedConversationId}
      />

      <ProcessPanel conversation={selectedConversation} />

      <section className="workspace-panel">
        {!!missingConfigLines.length && (
          <ConfigNotice title="Configuracion pendiente" lines={missingConfigLines} />
        )}

        {appError && (
          <section className="config-notice error-notice">
            <strong>Error de integracion</strong>
            <p>{appError}</p>
            <button className="secondary-button inline-button" type="button" onClick={clearAppError}>
              Ocultar
            </button>
          </section>
        )}

        <ChatPanel
          apiBaseUrl={apiBaseUrl}
          conversation={selectedConversation}
          loadingMessages={loadingMessages}
          onAcceptLoanOffer={sendLoanOfferAccepted}
          onLogout={signOut}
          onRejectLoanOffer={sendLoanOfferRejected}
          onSendMessage={sendMessage}
          onSubmitOtp={sendOtpCode}
          sending={sending}
          user={user}
        />
        {isNewConversation && !sending && (
          <ProductSelectorModal onSelect={handleProductSelect} />
        )}
      </section>
      
    </main>
  );
}

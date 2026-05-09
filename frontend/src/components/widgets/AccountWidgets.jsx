import React from 'react';
import AccountOfferCard from './AccountOfferCard';
import FlowClosure from './FlowClosure';

// Definimos qué nodos de cuenta disparan la pantalla de cierre
const CLOSURE_NODES = new Set([
  'ACCOUNT_COMPLETED',
  'ACCOUNT_REJECTED_POLICY',
  'ACCOUNT_SECURITY_BLOCK',
  'ACCOUNT_CLOSED_BY_USER'
]);

export default function AccountWidgets({
  conversation,
  disabled,
  onAcceptOffer,
  onRejectOffer
}) {
  const currentNode = conversation?.currentNode;

  // Solo nos activamos si el nodo es de cuenta corriente
  if (!currentNode?.startsWith('ACCOUNT_')) {
    return null;
  }

  return (
    <div className="dynamic-widgets">
      {/* 1. Tarjeta de Oferta Transparente */}
      {currentNode === 'ACCOUNT_PRE_APPROVED' && (
        <AccountOfferCard conversation={conversation} disabled={disabled} />
      )}

      {/* 2. Pantalla de Cierre (Éxito, Rechazo, Bloqueo) */}
      {CLOSURE_NODES.has(currentNode) && (
        <FlowClosure conversation={conversation} />
      )}
    </div>
  );
}

import React from 'react';
import DapOfferCard from './DapOfferCard';
import FlowClosure from './FlowClosure';

// 1. Definimos qué nodos de DAP disparan la pantalla de cierre
const CLOSURE_NODES = new Set([
  'DAP_COMPLETED',
  'DAP_REJECTED_POLICY',
  'DAP_SECURITY_BLOCK',
  'DAP_CLOSED_BY_USER'
]);

export default function DapWidgets({
  conversation,
  disabled,
  onAcceptOffer,
  onRejectOffer
}) {
  const currentNode = conversation?.currentNode;

  // 2. Solo nos activamos si el nodo es de Depósito a Plazo
  if (!currentNode?.startsWith('DAP_')) {
    return null;
  }

  return (
    <div className="dynamic-widgets">
      {/* 3. Tarjeta de Oferta Transparente de Inversión */}
      {currentNode === 'DAP_PRE_APPROVED' && (
        <DapOfferCard 
          conversation={conversation} 
          disabled={disabled} 
          onAccept={onAcceptOffer}
          onReject={onRejectOffer}
        />
      )}

      {/* 4. Pantalla de Cierre (Éxito, Rechazo, Bloqueo) */}
      {CLOSURE_NODES.has(currentNode) && (
        <FlowClosure conversation={conversation} />
      )}
    </div>
  );
}
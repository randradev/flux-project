import React from 'react';
import LoanOfferCard from './LoanOfferCard';
import OtpInput from './OtpInput';
import FlowClosure from './FlowClosure';

const CLOSURE_NODES = new Set([
  'LOAN_REJECTED_POLICY',
  'LOAN_SECURITY_BLOCK',
  'LOAN_CLOSED_BY_USER',
  'LOAN_COMPLETED'
]);

export default function CreditWidgets({
  conversation,
  disabled,
  onAcceptOffer,
  onRejectOffer,
  onSubmitOtp
}) {
  const currentNode = conversation?.currentNode;

  if (!currentNode?.startsWith('LOAN_')) {
    return null;
  }

  return (
    <div className="dynamic-widgets">
      {currentNode === 'LOAN_PRE_APPROVED' && (
        <LoanOfferCard
          conversation={conversation}
          disabled={disabled}
          onAccept={onAcceptOffer}
          onReject={onRejectOffer}
        />
      )}

      {currentNode === 'LOAN_OTP_VALIDATION' && (
        <OtpInput
          authControl={conversation?.authControl}
          disabled={disabled}
          onSubmit={onSubmitOtp}
        />
      )}

      {CLOSURE_NODES.has(currentNode) && <FlowClosure conversation={conversation} />}
    </div>
  );
}

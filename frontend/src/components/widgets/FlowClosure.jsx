import React from 'react';
import { getNodeMeta } from '../../constants/flux';

const CLOSURE_COPY = {
  LOAN_REJECTED_POLICY: {
    tone: 'warning',
    title: 'Solicitud no aprobada',
    body: 'La evaluacion finalizo por una politica financiera.'
  },
  LOAN_SECURITY_BLOCK: {
    tone: 'danger',
    title: 'Solicitud bloqueada',
    body: 'Por seguridad, este flujo quedo bloqueado tras la validacion OTP.'
  },
  LOAN_CLOSED_BY_USER: {
    tone: 'neutral',
    title: 'Solicitud cerrada',
    body: 'Decidiste no continuar con esta oferta.'
  },
  LOAN_COMPLETED: {
    tone: 'success',
    title: 'Credito completado',
    body: 'La solicitud termino correctamente.'
  }
};

export default function FlowClosure({ conversation }) {
  const currentNode = conversation?.currentNode;
  const flowResult = conversation?.flowResult ?? {};
  const copy = CLOSURE_COPY[currentNode];

  if (!copy) {
    return null;
  }

  const nodeMeta = getNodeMeta(currentNode);

  return (
    <section className={`loan-widget closure-widget ${copy.tone}`} aria-label="Cierre del flujo">
      <div className="widget-head">
        <span className="status-label">{nodeMeta.label}</span>
        <strong>{copy.title}</strong>
        <p>{flowResult.reason ?? flowResult.close_reason ?? copy.body}</p>
      </div>

      <dl className="closure-grid">
        <div>
          <dt>Estado</dt>
          <dd>{flowResult.status_code ?? flowResult.statusCode ?? currentNode}</dd>
        </div>
        <div>
          <dt>Motivo</dt>
          <dd>{flowResult.close_reason ?? flowResult.closeReason ?? 'No informado'}</dd>
        </div>
        <div>
          <dt>Producto</dt>
          <dd>{flowResult.product_name ?? flowResult.productName ?? 'Credito de Consumo'}</dd>
        </div>
      </dl>
    </section>
  );
}

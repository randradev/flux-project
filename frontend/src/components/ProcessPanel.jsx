import React from 'react';
import {
  getFlowResultLabel,
  getNodeMeta,
  getPhaseStepIndex,
  getProductLabel,
  PHASE_ONE_STEPS
} from '../constants/flux';

export default function ProcessPanel({ conversation }) {
  const currentNode = conversation?.currentNode ?? null;
  const currentStepIndex = getPhaseStepIndex(currentNode);
  const nodeMeta = getNodeMeta(currentNode);
  const productLabel = getProductLabel(conversation?.productIntent, conversation?.productName);

  return (
    <aside className="process-panel">
      <div className="panel-block">
        <div className="panel-title-row">
          <span>Flux Progress Monitor</span>
          <small>Fase 1 Dev 2</small>
        </div>

        <ol className="milestones">
          {PHASE_ONE_STEPS.map((step, index) => {
            const state = index < currentStepIndex ? 'complete' : index === currentStepIndex ? 'active' : 'waiting';
            const description =
              step.id === 'FLOW_RESULT' && currentNode ? getFlowResultLabel(currentNode) : step.description;

            return (
              <li key={step.id} className={state}>
                <span className="milestone-dot" aria-hidden="true" />
                <span>
                  <strong>{step.label}</strong>
                  <small>{description}</small>
                </span>
              </li>
            );
          })}
        </ol>
      </div>

      <section className="status-stack">
        <article className="status-card">
          <span className="status-label">Nodo actual</span>
          <strong>{nodeMeta.label}</strong>
          <p>{nodeMeta.description}</p>
          <code>{currentNode || 'SIN_NODO'}</code>
        </article>

        <article className="status-card">
          <span className="status-label">Producto detectado</span>
          <strong>{productLabel}</strong>
          <p>
            En Fase 1 el backend solo llega a stubs. El frontend muestra el estado real sin
            inventar ofertas ni OTP.
          </p>
          <code>{conversation?.productIntent || 'GENERAL'}</code>
        </article>

        <article className="status-card">
          <span className="status-label">Conversacion activa</span>
          <strong>{conversation?.isDraft ? 'Pendiente de persistir' : 'Persistida en backend'}</strong>
          <p>El `conversation_id` real se asigna al primer POST exitoso del stream.</p>
          <code>{conversation?.isDraft ? 'draft' : conversation?.id}</code>
        </article>
      </section>
    </aside>
  );
}

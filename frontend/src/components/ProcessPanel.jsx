import React, { useState, useEffect } from 'react';
import {
  getFlowResultLabel,
  getMilestoneState,
  getNodeMeta,
  getProductLabel,
  getStepsForConversation,
  getFluxTip
} from '../constants/flux';


export default function ProcessPanel({ conversation }) {
  const currentNode = conversation?.currentNode ?? null;
  const nodeMeta = getNodeMeta(currentNode);
  const productLabel = getProductLabel(conversation?.productIntent, conversation?.productName);
  const steps = getStepsForConversation(conversation).filter(step => !step.hidden);
  /* Herramientas para Desarrollador: No renderizar 
    const phaseLabel =
    conversation?.productIntent === 'LOAN' || currentNode?.startsWith('LOAN_')
      ? 'Fase 2 Dev 2'
      : 'Fase 1 Dev 2'; */

  const [tipIndex, setTipIndex] = useState(0);

  useEffect(() => {
    // Quitamos [currentNode] de las dependencias para que el timer no se resetee
    const interval = setInterval(() => {
      setTipIndex(prev => prev + 1);
    }, 8000);
    
    return () => clearInterval(interval);
  }, [currentNode]); // Se reinicia el contador si cambiamos de etapa

  return (
    <aside className="process-panel">
      <div className="panel-block">
        <div className="panel-title-row">
          <span>En qué estamos...</span>
          {/*Herramientas para Desarrollador: No renderizar
          <small>{phaseLabel}</small> */}
        </div>

        {/* Solo renderizamos la lista de hitos si hay un producto detectado */}
          {conversation?.productIntent && conversation?.productIntent !== 'GENERAL' && (
            <ol className="milestones">
              {steps.map((step, index) => {
                const state = getMilestoneState(step.id, currentNode, index, steps);
                const description =
                  step.id === 'FLOW_RESULT' && currentNode ? getFlowResultLabel(currentNode) : '';
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
          )}
      </div>
      <div className="flux-tip-card">
        <div className="tip-header">
          <span className="tip-icon">💡</span>
          <strong>Flux Tip</strong>
        </div>
        <p className="tip-text" key={tipIndex}>
          {getFluxTip(conversation?.productIntent, currentNode, (conversation?.id?.length || 0) + tipIndex)}
        </p>
        {/* Barra de progreso de tiempo (Timer Bar) */}
        <div className="tip-timer-bar">
          <div className="tip-timer-fill" key={tipIndex} />
        </div>
      </div>

      {/* Herramientas para Desarrollador: No renderizar
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
          <p>El frontend refleja el estado recibido desde el backend y no calcula reglas de negocio.</p>
          <code>{conversation?.productIntent || 'GENERAL'}</code>
        </article>

        <article className="status-card">
          <span className="status-label">Semaforos</span>
          <strong>{conversation?.nodeStatus || 'Sin node_status'}</strong>
          <p>
            Motor: {conversation?.engineStatus || 'sin dato'} | Documento:{' '}
            {conversation?.documentStatus || 'sin dato'}
          </p>
          <code>{conversation?.applicationId || 'sin application_id'}</code>
        </article>

        <article className="status-card">
          <span className="status-label">Conversacion activa</span>
          <strong>{conversation?.isDraft ? 'Pendiente de persistir' : 'Persistida en backend'}</strong>
          <p>El `conversation_id` real se asigna al primer POST exitoso del stream.</p>
          <code>{conversation?.isDraft ? 'draft' : conversation?.id}</code>
        </article>
      </section> */}
    </aside>
  );
}

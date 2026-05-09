import React from 'react';

// 1. Formateadores (Simétricos a LoanOfferCard)
function formatClp(value) {
  if (value === null || value === undefined || value === '') return 'Pendiente';
  if (typeof value === 'string' && value.includes('$')) return value;
  return new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'CLP',
    maximumFractionDigits: 0
  }).format(Number(value));
}

// 2. Extractor de datos (Prioriza transparencia del backend)
function readAccountResult(conversation) {
  return (
    conversation?.transparencyData?.account ??
    conversation?.evaluationResults?.account_engine ??
    conversation?.offerData?.account ??
    {}
  );
}

export default function AccountOfferCard({ conversation, disabled, onAccept, onReject }) {
  const result = readAccountResult(conversation);
  
  // Mapeo simétrico de campos
  const details = [
    ['Plan sugerido', result.plan_nombre ?? result.final_category ?? 'Pendiente'],
    ['Línea de crédito', formatClp(result.cupo_linea ?? result.credit_line_amount)],
    ['Costo mensual', formatClp(result.costo_mensual ?? result.monthly_cost)],
    ['Beneficio Upgrade', result.beneficio_upgrade ?? (result.has_upgrade ? 'Sí' : 'No') ?? 'No']
  ];

  return (
    <section className="account-widget offer-widget" aria-label="Tarjeta de transparencia cuenta">
      <div className="widget-head">
        <strong>Plan Cuenta Corriente Flux</strong>
        <p>Hemos diseñado este plan basándonos en tu perfil. ¡Revisa los detalles y cuéntanos si te gusta!</p>
      </div>

      <dl className="offer-grid">
        {details.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      {/* Acciones comentadas para mantener simetría con el estado actual de LoanOfferCard */}
      {/* 
      <div className="widget-actions">
        <button className="primary-button" type="button" onClick={onAccept} disabled={disabled}>
          Contratar Cuenta
        </button>
        <button className="secondary-button danger-button" type="button" onClick={onReject} disabled={disabled}>
          No me interesa
        </button>
      </div> 
      */}
    </section>
  );
}

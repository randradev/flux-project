import React from 'react';

// 1. Actualizamos los formateadores para que acepten strings ya formateados
function formatClp(value) {
  if (value === null || value === undefined || value === '') return 'Pendiente';
  if (typeof value === 'string' && value.includes('$')) return value; // Ya viene formateado
  return new Intl.NumberFormat('es-CL', {
    style: 'currency',
    currency: 'CLP',
    maximumFractionDigits: 0
  }).format(Number(value));
}
function formatPercent(value) {
  if (value === null || value === undefined || value === '') return 'Pendiente';
  if (typeof value === 'string' && value.includes('%')) return value; // Ya viene formateado
  return new Intl.NumberFormat('es-CL', {
    style: 'percent',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(Number(value));
}
// 2. Actualizamos la lectura para priorizar transparencyData
function readLoanResult(conversation) {
  return (
    conversation?.transparencyData?.loan ??
    conversation?.riskResults ??
    conversation?.evaluationResults?.loan_engine ??
    conversation?.evaluationResults?.loanEngine ??
    conversation?.offerData?.loan ??
    {}
  );
}

export default function LoanOfferCard({ conversation, disabled, onAccept, onReject }) {
  const result = readLoanResult(conversation);
  const hasOfferData = Boolean(result.monto_aprobado || result.montoAprobado || result.cuota_mensual);

  const details = [
    ['Monto aprobado', formatClp(result.monto_aprobado ?? result.montoAprobado)],
    ['Plazo', result.plazo_aprobado ?? result.plazoAprobado ? `${result.plazo_aprobado ?? result.plazoAprobado} meses` : 'Pendiente'],
    ['Tasa mensual', formatPercent(result.tasa_interes_mensual ?? result.tasaInteresMensual)],
    ['Cuota mensual', formatClp(result.cuota_mensual ?? result.cuotaMensual)],
    ['CAE', formatPercent(result.cae)],
    ['Costo total', formatClp(result.ctc)],
    ['Intereses', formatClp(result.total_intereses ?? result.totalIntereses)]
  ];

  return (
    <section className="loan-widget offer-widget" aria-label="Tarjeta de transparencia">
      <div className="widget-head">
        <span className="status-label">Oferta pre-aprobada</span>
        <strong>Tarjeta de Transparencia</strong>
        <p>Condiciones recibidas desde el backend para tu Credito de Consumo.</p>
      </div>

      {!hasOfferData && (
        <p className="widget-hint">
          El nodo `LOAN_PRE_APPROVED` esta activo, pero aun no llego un payload de oferta.
        </p>
      )}

      <dl className="offer-grid">
        {details.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      <div className="widget-actions">
        <button className="primary-button" type="button" onClick={onAccept} disabled={disabled}>
          Aceptar Oferta
        </button>
        <button className="secondary-button danger-button" type="button" onClick={onReject} disabled={disabled}>
          Rechazar/Cerrar
        </button>
      </div>
    </section>
  );
}

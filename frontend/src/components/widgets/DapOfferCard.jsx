import React from 'react';

// 1. Formateadores dinámicos según Moneda
function formatMoney(value, currency = 'CLP') {
  if (value === null || value === undefined || value === '') return 'Pendiente';
  
  const options = {
    style: 'currency',
    currency: currency,
    maximumFractionDigits: currency === 'CLP' ? 0 : 2
  };

  return new Intl.NumberFormat('es-CL', options).format(Number(value));
}

function formatPercent(value) {
  if (!value) return '0%';
  return (value * 100).toFixed(2) + '%';
}

// 2. Extractor de datos (Namespace DAP)
function readDapResult(conversation) {
  return (
    conversation?.transparencyData?.dap ??
    conversation?.evaluationResults?.dap_engine ??
    conversation?.offerData?.dap ??
    {}
  );
}

export default function DapOfferCard({ conversation, disabled, onAccept, onReject }) {
  const result = readDapResult(conversation);
  const moneda = result.moneda ?? 'CLP';
  
  // Mapeo específico para Inversión
  const details = [
    ['Monto Invertido', formatMoney(result.monto, moneda)],
    ['Plazo', `${result.plazo ?? 0} días`],
    ['Tasa Mensual', formatPercent(result.monthly_rate_total)],
    ['Ganancia Estimada', formatMoney(result.estimated_gain, moneda)],
    ['Total a Recibir', formatMoney(result.total_return, moneda)]
  ];

  return (
    <section className="account-widget offer-widget" aria-label="Tarjeta de inversión DAP">
      <div className="widget-head">
        <strong>Tu Inversión Flux</strong>
        <p>Hemos calculado tu rentabilidad con la mejor tasa vigente. ¡Asegura tus ahorros hoy!</p>
      </div>

      <dl className="offer-grid">
        {details.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd className={label === 'Total a Recibir' ? 'highlight-value' : ''}>
                {value}
            </dd>
          </div>
        ))}
      </dl>

      {/* <div className="widget-actions">
        <button className="primary-button" type="button" onClick={onAccept} disabled={disabled}>
          Constituir Depósito
        </button>
        <button className="secondary-button danger-button" type="button" onClick={onReject} disabled={disabled}>
          No me interesa
        </button>
      </div> */}
    </section>
  );
}
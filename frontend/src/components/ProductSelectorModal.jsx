import React from 'react';

export default function ProductSelectorModal({ onSelect }) {
  const options = [
    { id: 'LOAN', label: 'Crédito de Consumo', icon: '💳', desc: 'Simula y solicita financiamiento inmediato.' },
    { id: 'ACCOUNT', label: 'Cuenta Corriente', icon: '🏦', desc: 'Abre tu cuenta 100% digital en minutos.' },
    { id: 'DAP', label: 'Depósito a Plazo', icon: '📈', desc: 'Haz crecer tus ahorros con tasa fija.' },
    { id: 'GENERAL', label: 'Consultas Generales', icon: '💬', desc: 'Dudas sobre productos, horarios o soporte.' },
  ];

  return (
    <div className="product-selector-overlay">
      <div className="product-selector-card">
        <h2>¿En qué te podemos ayudar hoy?</h2>
        <p>Selecciona una opción para comenzar tu flujo guiado por FLUX.</p>
        
        <div className="product-options-grid">
          {options.map((opt) => (
            <button 
              key={opt.id} 
              className="product-option-button"
              onClick={() => onSelect(opt.id, opt.label)}
            >
              <span className="option-icon">{opt.icon}</span>
              <div className="option-text">
                <span className="option-label">{opt.label}</span>
                <span className="option-desc">{opt.desc}</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

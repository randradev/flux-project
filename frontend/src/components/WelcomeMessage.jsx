import React from 'react';

export default function WelcomeMessage({ onSelect }) {
  const actions = [
    { id: 'LOAN', label: 'Pedir mi Crédito', icon: '💰', desc: 'Plata en tu cuenta en minutos.' },
    { id: 'ACCOUNT', label: 'Abrir Cuenta', icon: '🏦', desc: 'Sin comisiones, 100% digital.' },
    { id: 'DAP', label: 'Hacer crecer mi plata', icon: '📈', desc: 'Invierte fácil y seguro.' },
  ];

  return (
    <section className="welcome-view">
      <div className="welcome-content">
        <header className="welcome-header">
          <div className="brand-accent-line"></div>
          <h1>¡Hola! Soy Flux</h1>
          <p>Tu dinero, en lenguaje humano. Olvídate de la burocracia, <strong>estoy aquí para devolverte el control.</strong></p>
        </header>

        <div className="quick-actions-grid">
          {actions.map((action) => (
            <button
              key={action.id}
              className="quick-action-card"
              onClick={() => onSelect(action.id, action.label)}
            >
              <span className="action-icon">{action.icon}</span>
              <div className="action-info">
                <span className="action-label">{action.label}</span>
                <span className="action-desc">{action.desc}</span>
              </div>
              <span className="action-arrow">→</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}


import React, { useState, useEffect } from 'react';

const FLUX_PHRASES = [
  "Afilando el lápiz para tu oferta...",
  "Haciendo malabares con los números...",
  "Consultando con el oráculo de las finanzas...",
  "Buscando las lucas entre los sillones...",
  "Flux está pensando... no lo interrumpas que se marea.",
  "Calculando más rápido que calculadora de almacén...",
  "Revisando los bolsillos para ver qué sale...",
  "Hablando con los duendes del banco..."
];

export default function FluxLoadingFeedback() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setIndex((prev) => (prev + 1) % FLUX_PHRASES.length);
    }, 2800);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flux-loading-feedback">
      <div className="typing-indicator">
        <span></span><span></span><span></span>
      </div>
      <em>{FLUX_PHRASES[index]}</em>
    </div>
  );
}

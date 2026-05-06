import React, { useState } from 'react';

export default function OtpInput({ authControl = {}, disabled, onSubmit }) {
  const [code, setCode] = useState('');
  const attempts = Number(authControl.otp_attempts ?? authControl.otpAttempts ?? 0);
  const remainingAttempts = Math.max(0, 3 - attempts);
  const isBlocked = Boolean(authControl.security_blocked ?? authControl.securityBlocked);
  const isReady = code.length === 6 && !disabled && !isBlocked;

  function handleChange(event) {
    setCode(event.target.value.replace(/\D/g, '').slice(0, 6));
  }

  function handleSubmit(event) {
    event.preventDefault();

    if (!isReady) {
      return;
    }

    onSubmit(code);
    setCode('');
  }

  return (
    <section className="loan-widget otp-widget" aria-label="Validacion OTP">
      <div className="widget-head">
        <span className="status-label">Validacion de identidad</span>
        <strong>Codigo OTP</strong>
        <p>Ingresa el codigo de 6 digitos que FLUX envio por el canal configurado.</p>
      </div>

      <form className="otp-form" onSubmit={handleSubmit}>
        <input
          value={code}
          onChange={handleChange}
          inputMode="numeric"
          pattern="[0-9]*"
          placeholder="000000"
          aria-label="Codigo OTP de 6 digitos"
          disabled={disabled || isBlocked}
        />
        <button className="primary-button" type="submit" disabled={!isReady}>
          Validar
        </button>
      </form>

      <p className={`widget-hint ${isBlocked ? 'danger-text' : ''}`}>
        {isBlocked
          ? 'Solicitud bloqueada por seguridad.'
          : `Intentos disponibles: ${remainingAttempts}`}
      </p>
    </section>
  );
}

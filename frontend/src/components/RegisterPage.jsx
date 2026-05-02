import React, { useState } from 'react';
import Brand from './Brand';
import ConfigNotice from './ConfigNotice';
import { useAuth } from '../hooks/useAuth';
import { SUPABASE_CONFIG_MESSAGE } from '../services/supabase';

const INITIAL_FORM = {
  fullName: '',
  rut: '',
  email: '',
  phone: '',
  birthDate: '',
  password: ''
};

export default function RegisterPage({ onBack }) {
  const { hasSupabaseConfig, signUp } = useAuth();
  const [formData, setFormData] = useState(INITIAL_FORM);
  const [status, setStatus] = useState('form');
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  function updateField(field, value) {
    setFormData((current) => ({
      ...current,
      [field]: value
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setFormError('');

    try {
      const response = await signUp(formData);
      const needsConfirmation = !response.session;
      setStatus(needsConfirmation ? 'confirm-email' : 'done');
    } catch (error) {
      setFormError(error.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="screen-shell auth-screen">
      <header className="topbar">
        <span>FLUX frontend fase 1</span>
        <Brand compact />
      </header>

      <section className="auth-card register-card">
        <Brand />
        <div className="hero-copy">
          <span className="eyebrow">Registro con Supabase Auth</span>
          <h1>Crear acceso FLUX</h1>
          <p>
            Esta pantalla registra la cuenta en Supabase Auth. Para usar el backend, el mismo email
            debe existir tambien en la tabla <code>users</code> del proyecto FLUX.
          </p>
        </div>

        {!hasSupabaseConfig && (
          <ConfigNotice
            title="Configuracion pendiente"
            lines={[
              SUPABASE_CONFIG_MESSAGE,
              'Variables esperadas: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY.'
            ]}
          />
        )}

        {status === 'form' && (
          <form className="auth-form register-form" onSubmit={handleSubmit}>
            <label>
              Nombre completo
              <input
                value={formData.fullName}
                onChange={(event) => updateField('fullName', event.target.value)}
                placeholder="Nombre y apellido"
                required
              />
            </label>

            <label>
              RUT
              <input
                value={formData.rut}
                onChange={(event) => updateField('rut', event.target.value)}
                placeholder="12345678-9"
                required
              />
            </label>

            <label>
              Email
              <input
                value={formData.email}
                onChange={(event) => updateField('email', event.target.value)}
                type="email"
                placeholder="cliente@flux.cl"
                autoComplete="email"
                required
              />
            </label>

            <label>
              Telefono
              <input
                value={formData.phone}
                onChange={(event) => updateField('phone', event.target.value)}
                type="tel"
                placeholder="+56 9 1234 5678"
                autoComplete="tel"
                required
              />
            </label>

            <label>
              Fecha de nacimiento
              <input
                value={formData.birthDate}
                onChange={(event) => updateField('birthDate', event.target.value)}
                type="date"
                required
              />
            </label>

            <label>
              Password
              <input
                value={formData.password}
                onChange={(event) => updateField('password', event.target.value)}
                type="password"
                placeholder="Minimo 8 caracteres"
                autoComplete="new-password"
                minLength={8}
                required
              />
            </label>

            {formError && <p className="form-error">{formError}</p>}

            <div className="auth-actions">
              <button className="primary-button" type="submit" disabled={submitting || !hasSupabaseConfig}>
                {submitting ? 'Creando...' : 'Crear cuenta'}
              </button>
              <button className="secondary-button" type="button" onClick={onBack}>
                Volver al login
              </button>
            </div>
          </form>
        )}

        {status === 'confirm-email' && (
          <section className="status-card">
            <h2>Confirma tu correo</h2>
            <p>
              Supabase creo la cuenta y envio la confirmacion por email. Cuando la actives, vuelve
              al login para abrir sesion.
            </p>
            <button className="secondary-button" type="button" onClick={onBack}>
              Ir al login
            </button>
          </section>
        )}

        {status === 'done' && (
          <section className="status-card">
            <h2>Cuenta creada</h2>
            <p>Tu acceso quedo habilitado. Si el perfil existe en la tabla users, ya puedes usar FLUX.</p>
            <button className="secondary-button" type="button" onClick={onBack}>
              Ir al login
            </button>
          </section>
        )}
      </section>
    </main>
  );
}

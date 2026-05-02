import React, { useState } from 'react';
import Brand from './Brand';
import ConfigNotice from './ConfigNotice';
import { useAuth } from '../hooks/useAuth';
import { SUPABASE_CONFIG_MESSAGE } from '../services/supabase';

export default function LoginPage({ onRegister }) {
  const { authError, clearAuthError, hasSupabaseConfig, signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setFormError('');
    clearAuthError();

    try {
      await signIn({ email, password });
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

      <section className="auth-card">
        <Brand />
        <div className="hero-copy">
          <span className="eyebrow">Banca digital conversacional</span>
          <h1>Login real con Supabase</h1>
          <p>
            Esta version deja la maqueta atras: autentica usuarios y prepara el dashboard para
            consumir historial y streaming SSE del backend FLUX.
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

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            Email
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="cliente@flux.cl"
              type="email"
              autoComplete="email"
              required
            />
          </label>

          <label>
            Password
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Tu password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>

          {(formError || authError) && <p className="form-error">{formError || authError}</p>}

          <button className="primary-button" type="submit" disabled={submitting || !hasSupabaseConfig}>
            {submitting ? 'Ingresando...' : 'Acceder'}
          </button>
        </form>

        <div className="auth-footer">
          <p>El backend FLUX espera un JWT de Supabase valido en cada request.</p>
          <button className="secondary-button" type="button" onClick={onRegister}>
            Crear cuenta
          </button>
        </div>
      </section>
    </main>
  );
}

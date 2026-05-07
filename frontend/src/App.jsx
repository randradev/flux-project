import React from 'react';
import Dashboard from './components/Dashboard';
import LoginPage from './components/LoginPage';
import RegisterPage from './components/RegisterPage';
import { FluxProvider } from './context/FluxContext';
import { useAuth } from './hooks/useAuth';
import './styles.css';

export default function App() {
  const { accessToken, isAuthenticated, loading, screen, setScreen } = useAuth();

  if (loading) {
    return (
      <main className="screen-shell loading-screen">
        <section className="status-card">
          <h1>Conectando FLUX</h1>
          <p>Estamos recuperando tu sesion y la configuracion del frontend.</p>
        </section>
      </main>
    );
  }

  if (!isAuthenticated && screen === 'register') {
    return <RegisterPage onBack={() => setScreen('login')} />;
  }

  if (!isAuthenticated) {
    return <LoginPage onRegister={() => setScreen('register')} />;
  }

  return (
    <FluxProvider accessToken={accessToken}>
      <Dashboard />
    </FluxProvider>
  );
}

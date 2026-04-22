import React, { useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const PRODUCTS = {
  credito: {
    label: 'Credito Consumo',
    accent: '#314cff',
    icon: '💳',
    historyTitle: 'CREDITO CONSUMO',
    intro:
      'Hola. Soy el asistente de FLUX. Veo que estas interesado en un Credito de Consumo. Para comenzar la simulacion, necesito confirmar algunos datos personales. Podrias indicarme tu RUT?',
    milestones: [
      {
        title: 'Datos Personales',
        fields: [
          ['Full Name', 'Juan Perez', 'done'],
          ['RUT', '12345678-9', 'done'],
          ['Edad', '35 anos', 'active'],
          ['Antiguedad', '24 meses', 'pending'],
          ['Renta', '$2.500.000', 'pending'],
          ['Estudios', 'Universitario', 'pending']
        ]
      },
      {
        title: 'Simulacion',
        fields: [
          ['Monto', '$5.000.000', 'done'],
          ['Plazo', '24 cuotas', 'done'],
          ['Score', '85/100 - Riesgo BAJO', 'done'],
          ['Tasa', '1.2% mensual', 'active'],
          ['Cuota', '$220.833', 'pending']
        ]
      },
      {
        title: 'Acreditacion',
        fields: [
          ['Renta Documentada', '$2.450.000', 'done'],
          ['Diferencia', '2% menor a 10%', 'done'],
          ['Antiguedad Verificada', '24 meses', 'done'],
          ['Status', 'APROBADO', 'active']
        ]
      },
      {
        title: 'Oferta Final',
        fields: [
          ['Monto', '$5.000.000', 'done'],
          ['Plazo', '24 cuotas', 'done'],
          ['Cuota', '$220.833', 'done'],
          ['Total a Pagar', '$5.300.000', 'active'],
          ['Riesgo', 'BAJO', 'pending']
        ]
      },
      {
        title: 'Firma y Cierre',
        fields: [
          ['OTP', '482957', 'done'],
          ['PDF Generado', 'flux-credit-20260416-001', 'done'],
          ['SHA-256', 'a3f4e8c2...', 'done'],
          ['Status', 'ACTIVO', 'active']
        ]
      }
    ]
  },
  cuenta: {
    label: 'Cuenta Corriente',
    accent: '#7d36d9',
    icon: '🏦',
    historyTitle: 'CUENTA CORRIENTE',
    intro:
      'Hola. Puedo ayudarte a abrir una Cuenta Corriente. Primero validaremos tus datos, luego segmentaremos tu categoria y dejaremos lista la oferta final.',
    milestones: [
      {
        title: 'Datos Personales',
        fields: [
          ['Full Name', 'Maria Garcia', 'done'],
          ['RUT', '11223344-5', 'done'],
          ['Edad', '28 anos', 'done'],
          ['Antiguedad', '18 meses', 'active'],
          ['Renta', '$1.800.000', 'pending'],
          ['Domicilio', 'Av. Principal 123', 'pending']
        ]
      },
      {
        title: 'Segmentacion',
        fields: [
          ['Renta Base', '$1.8MM - MEDIUM', 'done'],
          ['Titulo', 'Postgrado - UPGRADE', 'done'],
          ['Categoria Final', 'ADVANCE', 'active'],
          ['Linea Credito', '$900.000', 'pending']
        ]
      },
      {
        title: 'Acreditacion',
        fields: [
          ['Renta Documentada', '$1.780.000', 'done'],
          ['Diferencia', '1.1% menor a 10%', 'done'],
          ['Titulo Validado', 'Si', 'done'],
          ['Status', 'APROBADO', 'active']
        ]
      },
      {
        title: 'Oferta Final',
        fields: [
          ['Categoria', 'ADVANCE', 'done'],
          ['Renta Verificada', '$1.780.000', 'done'],
          ['Linea Credito', '$890.000', 'active'],
          ['Beneficios', 'Seguros, Asistencia', 'pending']
        ]
      },
      {
        title: 'Firma y Cierre',
        fields: [
          ['OTP', '739284', 'done'],
          ['Numero Cuenta', '1234567890', 'done'],
          ['SHA-256', 'b8d2f1a9...', 'done'],
          ['Status', 'ACTIVA', 'active']
        ]
      }
    ]
  },
  dap: {
    label: 'Deposito a Plazo',
    accent: '#00a86b',
    icon: '💰',
    historyTitle: 'DAP',
    intro:
      'Hola. Podemos simular un Deposito a Plazo, incluso de forma anonima. Indica monto, plazo, moneda y modalidad para calcular la tasa final.',
    milestones: [
      {
        title: 'Datos Personales',
        fields: [
          ['Full Name', 'Opcional', 'active'],
          ['RUT', 'Opcional', 'pending'],
          ['Email/Celular', 'Solo si acepta', 'pending'],
          ['Simulacion anonima', 'Permitida', 'done']
        ]
      },
      {
        title: 'Simulacion',
        fields: [
          ['Monto', '$10.000.000', 'done'],
          ['Plazo', '30 dias', 'done'],
          ['Moneda', 'CLP', 'done'],
          ['Modalidad', 'No Renovable', 'done'],
          ['Tasa Total', '3.5%', 'active'],
          ['Interes Ganado', '$287.500', 'pending']
        ]
      },
      {
        title: 'Acreditacion',
        fields: [
          ['Estado', 'OMITIDO', 'done'],
          ['Validacion documental', 'No requerida', 'done']
        ]
      },
      {
        title: 'Oferta Final',
        fields: [
          ['Inversion', '$10.000.000 CLP', 'done'],
          ['Plazo', '30 dias', 'done'],
          ['Tasa', '3.5% anual', 'active'],
          ['Vencimiento', '$10.287.500', 'pending'],
          ['Retiro anticipado', 'No disponible', 'pending']
        ]
      },
      {
        title: 'Firma y Cierre',
        fields: [
          ['RUT', '19876543-2', 'done'],
          ['Nombre', 'Carlos Lopez', 'done'],
          ['OTP', '562894', 'done'],
          ['Numero Inversion', 'DAP-20260416-0156', 'active'],
          ['Status', 'ACTIVA', 'pending']
        ]
      }
    ]
  }
};

const INITIAL_CHATS = [
  {
    id: crypto.randomUUID(),
    product: 'credito',
    title: PRODUCTS.credito.historyTitle,
    date: '16-04-26',
    time: '09:34',
    activeStep: 0,
    messages: [
      {
        id: crypto.randomUUID(),
        role: 'user',
        text: 'Quiero un credito de consumo'
      },
      {
        id: crypto.randomUUID(),
        role: 'assistant',
        text: PRODUCTS.credito.intro
      }
    ]
  },
  {
    id: crypto.randomUUID(),
    product: 'cuenta',
    title: PRODUCTS.cuenta.historyTitle,
    date: '15-04-26',
    time: '15:41',
    activeStep: 1,
    messages: [
      {
        id: crypto.randomUUID(),
        role: 'assistant',
        text: PRODUCTS.cuenta.intro
      }
    ]
  },
  {
    id: crypto.randomUUID(),
    product: 'dap',
    title: PRODUCTS.dap.historyTitle,
    date: '15-04-26',
    time: '11:08',
    activeStep: 1,
    messages: [
      {
        id: crypto.randomUUID(),
        role: 'assistant',
        text: PRODUCTS.dap.intro
      }
    ]
  }
];

function formatDate(date) {
  return new Intl.DateTimeFormat('es-CL', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit'
  })
    .format(date)
    .replaceAll('/', '-');
}

function formatTime(date) {
  return new Intl.DateTimeFormat('es-CL', {
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
}

function inferProduct(text) {
  const normalized = text.toLowerCase();

  if (normalized.includes('dap') || normalized.includes('deposito') || normalized.includes('plazo')) {
    return 'dap';
  }

  if (normalized.includes('cuenta') || normalized.includes('corriente')) {
    return 'cuenta';
  }

  if (normalized.includes('credito') || normalized.includes('consumo') || normalized.includes('prestamo')) {
    return 'credito';
  }

  return null;
}

function nextAssistantMessage(productKey, stepIndex) {
  const product = PRODUCTS[productKey];
  const step = product.milestones[stepIndex];
  const nextStep = product.milestones[Math.min(stepIndex + 1, product.milestones.length - 1)];

  if (stepIndex === 0) {
    return product.intro;
  }

  if (stepIndex >= product.milestones.length - 1) {
    return `Proceso cerrado para ${product.label}. Firma, registro y status quedan disponibles para visualizacion del frontend.`;
  }

  return `Datos recibidos. Avanzamos desde ${step.title} hacia ${nextStep.title}. Actualizare los datos detectados a medida que el backend confirme la informacion.`;
}

function LoginPage({ onLogin }) {
  const [user, setUser] = useState('');
  const [password, setPassword] = useState('');

  function handleSubmit(event) {
    event.preventDefault();
    onLogin(user || 'AXLTL Audiovisual');
  }

  return (
    <main className="login-screen">
      <header className="login-topbar">
        <span>Banca Digital Fintech Flux chat bot</span>
        <Brand compact />
      </header>

      <section className="login-card" aria-label="Inicio de sesion">
        <Brand large />
        <h1>Bienvenido</h1>
        <p>
          Banca Digital <strong>FLUX</strong>
        </p>

        <form onSubmit={handleSubmit} className="login-form">
          <label>
            User
            <span className="input-shell">
              <span aria-hidden="true">👤</span>
              <input
                value={user}
                onChange={(event) => setUser(event.target.value)}
                placeholder="Ingresa tu usuario"
                autoComplete="username"
              />
            </span>
          </label>

          <label>
            Password
            <span className="input-shell">
              <span aria-hidden="true">🔒</span>
              <input
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                type="password"
                autoComplete="current-password"
              />
            </span>
          </label>

          <button className="primary-button" type="submit">
            Login
          </button>
          <button className="secondary-button" type="button" onClick={() => window.close()}>
            Cerrar App
          </button>
        </form>
      </section>

      <footer>
        © 2026 <strong>FLUX</strong> banking. Todos los derechos reservados.
      </footer>
    </main>
  );
}

function Brand({ large = false, compact = false }) {
  return (
    <span className={`brand ${large ? 'brand-large' : ''} ${compact ? 'brand-compact' : ''}`} aria-label="FLUX">
      <span>FLU</span>
      <span>X</span>
    </span>
  );
}

function Sidebar({ chats, selectedId, onSelectChat, onNewChat }) {
  return (
    <aside className="left-panel">
      <Brand />
      <p className="institution">Banca Digital</p>

      <nav aria-label="Navegacion principal">
        <a className="nav-item active" href="#historial">
          <span>↺</span>
          Historial de Consultas
        </a>
        <a className="nav-item" href="#mercados">
          <span>↗</span>
          Mercados
        </a>
        <a className="nav-item" href="#analisis">
          <span>▣</span>
          Analisis
        </a>
        <a className="nav-item" href="#configuracion">
          <span>⚙</span>
          Configuracion
        </a>
      </nav>

      <div className="recent-heading" id="historial">
        CHATS RECIENTES
      </div>

      <div className="chat-history" aria-label="Chats recientes">
        {chats.map((chat) => {
          const product = PRODUCTS[chat.product];
          const isActive = chat.id === selectedId;
          return (
            <button
              key={chat.id}
              className={`history-card ${isActive ? 'selected' : ''}`}
              onClick={() => onSelectChat(chat.id)}
              type="button"
            >
              <span className="history-icon" aria-hidden="true">
                {product.icon}
              </span>
              <span>
                <strong>{chat.title}</strong>
                <small>
                  {chat.date} · {chat.time}
                </small>
              </span>
            </button>
          );
        })}
      </div>

      <button className="new-chat-button" onClick={onNewChat} type="button">
        <span>＋</span>
        Nuevo Chat
      </button>
    </aside>
  );
}

function ProcessPanel({ chat }) {
  const product = PRODUCTS[chat.product];
  const activeMilestone = product.milestones[chat.activeStep];

  return (
    <aside className="process-panel">
      <div>
        <h2>Proceso Flux</h2>
        <ol className="milestones">
          {product.milestones.map((milestone, index) => {
            const state = index < chat.activeStep ? 'complete' : index === chat.activeStep ? 'active' : 'waiting';

            return (
              <li key={milestone.title} className={state}>
                <span className="milestone-dot" aria-hidden="true" />
                <span>
                  <strong>{milestone.title}</strong>
                  <small>{index < chat.activeStep ? 'Completado' : index === chat.activeStep ? 'En curso' : 'Pendiente'}</small>
                </span>
              </li>
            );
          })}
        </ol>
      </div>

      <section className="detected-card">
        <div className="detected-header">
          <span>DATOS DETECTADOS</span>
          <strong>{product.label}</strong>
        </div>
        <ul>
          {activeMilestone.fields.map(([label, value, status]) => (
            <li key={`${label}-${value}`}>
              <span className={`field-state ${status}`} aria-hidden="true" />
              <span>{label}</span>
              <strong>{value}</strong>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}

function ChatPanel({ chat, onSend, onLogout, userName }) {
  const [message, setMessage] = useState('');
  const fileInputRef = useRef(null);
  const product = PRODUCTS[chat.product];

  function handleSubmit(event) {
    event.preventDefault();
    const cleanMessage = message.trim();

    if (!cleanMessage) {
      return;
    }

    onSend(cleanMessage);
    setMessage('');
  }

  return (
    <section className="chat-panel">
      <header className="chat-header">
        <div className="chat-brand">
          <Brand />
          <span className="online-pill">
            <span aria-hidden="true" />
            En linea
          </span>
        </div>

        <div className="session-actions">
          <span className="profile-pill">{userName}</span>
          <button type="button" aria-label="Perfil">
            ◕
          </button>
          <button type="button" aria-label="Cerrar sesion" onClick={onLogout}>
            ↪
          </button>
        </div>
      </header>

      <div className="chat-window" aria-live="polite">
        <span className="day-pill">Hoy</span>

        {chat.messages.map((item) => (
          <article key={item.id} className={`message ${item.role}`}>
            {item.role === 'assistant' && (
              <span className="bot-avatar" aria-hidden="true">
                ✥
              </span>
            )}
            <p>{item.text}</p>
            {item.role === 'user' && (
              <span className="user-avatar" aria-hidden="true">
                ●
              </span>
            )}
          </article>
        ))}
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <input ref={fileInputRef} className="file-input" type="file" />
        <button
          className="clip-button"
          type="button"
          aria-label="Adjuntar documento"
          onClick={() => fileInputRef.current?.click()}
        >
          📎
        </button>
        <input
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder={`Escribe tu mensaje sobre ${product.label.toLowerCase()}...`}
        />
        <button className="send-button" type="submit" aria-label="Enviar mensaje">
          ▶
        </button>
      </form>
    </section>
  );
}

function Dashboard({ userName, onLogout }) {
  const [chats, setChats] = useState(INITIAL_CHATS);
  const [selectedId, setSelectedId] = useState(INITIAL_CHATS[0].id);

  const selectedChat = useMemo(
    () => chats.find((chat) => chat.id === selectedId) ?? chats[0],
    [chats, selectedId]
  );

  function handleNewChat() {
    const now = new Date();
    const chat = {
      id: crypto.randomUUID(),
      product: 'credito',
      title: 'NUEVO CHAT',
      date: formatDate(now),
      time: formatTime(now),
      activeStep: 0,
      messages: [
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          text:
            'Hola. Soy FLUX. Puedes consultar por Credito de Consumo, Cuenta Corriente o Deposito a Plazo. Te acompano paso a paso.'
        }
      ]
    };

    setChats((current) => [chat, ...current]);
    setSelectedId(chat.id);
  }

  function handleSend(text) {
    setChats((current) =>
      current.map((chat) => {
        if (chat.id !== selectedId) {
          return chat;
        }

        const detectedProduct = inferProduct(text) ?? chat.product;
        const productChanged = detectedProduct !== chat.product || chat.title === 'NUEVO CHAT';
        const baseStep = productChanged ? 0 : chat.activeStep;
        const nextStep = Math.min(baseStep + 1, PRODUCTS[detectedProduct].milestones.length - 1);

        return {
          ...chat,
          product: detectedProduct,
          title: PRODUCTS[detectedProduct].historyTitle,
          activeStep: nextStep,
          messages: [
            ...chat.messages,
            {
              id: crypto.randomUUID(),
              role: 'user',
              text
            },
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              text: nextAssistantMessage(detectedProduct, nextStep)
            }
          ]
        };
      })
    );
  }

  return (
    <main className="app-shell">
      <Sidebar chats={chats} selectedId={selectedChat.id} onSelectChat={setSelectedId} onNewChat={handleNewChat} />
      <ProcessPanel chat={selectedChat} />
      <ChatPanel chat={selectedChat} onSend={handleSend} onLogout={onLogout} userName={userName} />
    </main>
  );
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userName, setUserName] = useState('AXLTL Audiovisual');

  if (!isAuthenticated) {
    return (
      <LoginPage
        onLogin={(name) => {
          setUserName(name);
          setIsAuthenticated(true);
        }}
      />
    );
  }

  return <Dashboard userName={userName} onLogout={() => setIsAuthenticated(false)} />;
}

createRoot(document.getElementById('root')).render(<App />);

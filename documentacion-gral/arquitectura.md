# Arquitectura Flux

## Arquitectura de Capas

### 1 | Capa de Presentación (Frontend - React)
Es la cara visible. No contiene lógica de negocio, solo se encarga de pintar el estado que le envía el servidor.
- Chat Interface: Componente reactivo para la conversación.
- Flux Progress Monitor: Panel visual que muestra en qué nodo del grafo está el usuario (Transparencia).
- Interactive Components: Tarjetas de transparencia (ofertas), inputs de seguridad (OTP) y visores de PDF.

### 2 | Capa de Comunicación (Backend - FastAPI)
El punto de contacto entre el cliente y el cerebro.
- Endpoints REST: Gestión de autenticación y carga de documentos iniciales.
- WebSocket/Stream Handler: Mantiene la conexión bidireccional para que la IA responda en tiempo real
- Auth Middleware: Integración con Supabase Auth para validar quién está hablando.

### 3 | Capa de Orquestación Cognitiva (LangGraph + Gemini)
Aquí reside la "inteligencia". Es el motor que decide qué paso sigue.
- The State Graph: La red de nodos y aristas (Credit, Account, Transversales).
- Intent Router: Clasificador (Gemini) que determina si el usuario quiere un producto o tiene una duda.
- Entity Extractor: Módulo que limpia el lenguaje natural y lo convierte en datos JSON (Renta, RUT).
- RAG Tooling: Interfaz con la API de conocimiento para inyectar contexto legal al chat.

### 4 | Capa de Lógica de Negocio (Módulos de Producto)
El "Monolito Modular". Cada producto es un paquete independiente.
- Credit Module: Contiene el Motor de Riesgo y la lógica de amortización francesa.
- Account Module: Lógica de segmentación (Start, Medium, Advance).
- Deposits Module: Gestión de depósitos a plazo y simulaciones.
- Security Service: Gestión de OTP y el Security Watchdog para bloqueos.
- Document Service: Generación de PDF (ReportLab) y sellado SHA-256.

### 5 | Capa de Datos e Infraestructura (Supabase + Cloud)
La persistencia y los servicios externos.
- PostgreSQL (Supabase): Tablas de users, conversations, messages y financial_applications
- Vector Store (pgvector - Supabase): Almacenamiento de fragmentos de documentos para el RAG
- Object Storage (Bucket): Almacenamiento de los contratos PDF generados. ????que recomiendas???

## Estrcutura de Repositorio (Mono-Repo Modulado)

/flux-project
├── /frontend
│   ├── /src
│   │   ├── /components
│   │   │   ├── /chat           # Burbuja de chat y burbujas de mensajes
│   │   │   ├── /monitor        # El "Progress Tracker" (visualización del Grafo)
│   │   │   └── /widgets        # Tarjetas de oferta, OTP Input, Visor PDF
│   │   ├── /hooks              # useFluxGraph.ts (manejo de WebSockets/Streaming)
│   │   ├── /services           # api.ts (cliente Axios/Fetch para FastAPI)
│   │   └── /store              # Estado global (Context/Zustand) para la sesión
├── /backend
│   ├── /app
│   │   ├── /api
│   │   │   ├── deps.py         # Inyección de dependencias (DB, Auth)
│   │   │   └── v1/             # Versionado de la API
│   │   │       ├── chat.py     # Endpoint principal de LangGraph
│   │   │       └── docs.py     # Descarga de contratos y hashes
│   │   ├── /graph              # EL CEREBRO (LangGraph)
│   │   │   ├── /nodes          # Lógica de transición de estados
│   │   │   │   ├── credit.py   # Nodos de flujo de crédito
│   │   │   │   ├── account.py  # Nodos de flujo de cuenta corriente
│   │   │   │   ├── deposit.py  # Nodos de flujo de DAP
│   │   │   │   └── common.py   # Nodos transversales (RAG, Ambigüedad, Global_End)
│   │   │   ├── edges.py        # Lógica de ruteo (Conditional Edges)
│   │   │   ├── workflow.py     # Definición del StateGraph y compilación
│   │   │   └── state.py        # Definición del TypedDict (Estado global del grafo)
│   │   ├── /modules            # LA LÓGICA (Cálculos puros)
│   │   │   ├── credit_eng.py   # Motor de riesgo y Amortización Francesa
│   │   │   ├── account_eng.py  # Reglas de segmentación (Start/Medium/Advance)
│   │   │   ├── eco_service.py  # Cliente para la API de Indicadores (UF, USD)
│   │   │   ├── security.py     # Generador/Validador de OTP y Watchdog
│   │   │   └── pdf_factory.py  # Generador de PDF con ReportLab + Hashing
│   │   └── /infra              # LA INFRAESTRUCTURA (Clientes externos)
│   │       ├── supabase.py     # Cliente DB, Auth y Storage
│   │       ├── gemini.py       # Wrapper para la API de Google AI
│   │       └── embeddings.py   # Lógica de búsqueda en pgvector
├── /docs                       # Blueprint del sistema (.md)
├── requirements.txt            # Dependencias Python (FastAPI, LangGraph, etc.)
└── .env                        # Variables de entorno
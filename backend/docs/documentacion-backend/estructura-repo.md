# Estructura del Repositorio - Backend

A continuación se detalla la estructura completa y actualizada del directorio `backend`, omitiendo carpetas de caché, entornos virtuales y documentación interna.

```text
/backend
├── /app                    # Directorio raíz de la aplicación
│   ├── /api                # Capa de comunicación (FastAPI)
│   │   ├── /v1             # Versión 1 de la API
│   │   │   ├── chat.py     # Endpoint principal de chat con streaming SSE
│   │   │   └── docs.py     # Endpoints de historial y gestión de documentos
│   │   └── deps.py         # Inyección de dependencias (Autenticación, validación)
│   ├── /graph              # Cerebro de Orquestación (LangGraph)
│   │   ├── /nodes          # Lógica de los nodos del grafo
│   │   │   ├── account.py  # Nodos para flujos de Cuenta Corriente
│   │   │   ├── common.py   # Nodos transversales (Bienvenida, Clasificador de Intención)
│   │   │   ├── credit.py   # Nodos para flujos de Crédito de Consumo
│   │   │   └── deposit.py  # Nodos para flujos de Depósito a Plazo
│   │   ├── edges.py        # Lógica de ruteo condicional entre nodos
│   │   ├── state.py        # Definición del esquema de estado (TypedDict)
│   │   └── workflow.py     # Definición, compilación y exposición del StateGraph
│   ├── /infra              # Infraestructura y Clientes Externos
│   │   ├── checkpointer.py # Persistencia de estados de LangGraph en Supabase
│   │   ├── embeddings.py   # Lógica de generación y búsqueda de embeddings
│   │   ├── gemini_client.py# Cliente Vertex AI (Dual-Init para Chat y Embeddings)
│   │   ├── supabase.py     # Cliente administrativo de Supabase (Admin SDK)
│   │   └── threading.py    # Gestión de sesiones y vinculación de threads a usuarios
│   ├── /modules            # Lógica de Negocio y Motores (Engines)
│   │   ├── account_eng.py  # Reglas de segmentación para cuentas
│   │   ├── credit_eng.py   # Motor de riesgo y cálculos financieros
│   │   ├── eco_service.py  # Consumo de indicadores económicos (UF, USD)
│   │   ├── pdf_factory.py  # Generación de contratos PDF y hashing SHA-256
│   │   └── security.py     # Lógica de seguridad (OTP, validaciones extra)
│   └── config.py           # Configuración global y validación de variables de entorno
├── /migrations             # Scripts SQL de base de datos
│   ├── 000_seed.sql        # Datos iniciales para catálogos y pruebas
│   ├── 001_catalogs.sql    # Definición de tablas de catálogo
│   ├── 002_identity.sql    # Estructura de tablas de usuarios e identidad
│   ├── 003_conversations.sql # Definición de tablas de chat y persistencia
│   └── ...                 # Scripts de aplicaciones y seguridad
├── /secrets                # Almacenamiento de llaves privadas (GCP Credentials)
├── /tests                  # Suite de pruebas automatizadas
│   └── /fase1-dev1         # Pruebas de integración para la Fase 1
│       ├── test_api.py     # Validación de endpoints y streaming
│       ├── test_config.py  # Verificación de carga de configuración
│       ├── test_db.py      # Pruebas de conectividad con Supabase
│       ├── test_gemini.py  # Validación de respuesta del LLM
│       └── test_graph.py   # Pruebas de ruteo y persistencia del grafo
├── main.py                 # Punto de entrada de la aplicación FastAPI
├── requirements.txt        # Definición de dependencias del proyecto
└── .env                    # Variables de entorno y llaves de acceso
```

### Funciones Principales por Directorio

*   **`app/api`**: Define cómo el mundo exterior interactúa con FLUX. Utiliza FastAPI para manejar peticiones asíncronas y validación de identidad vía JWT.
*   **`app/graph`**: Contiene la inteligencia de flujo. LangGraph orquesta qué nodo debe ejecutarse basándose en la intención del usuario y el estado de la conversación.
*   **`app/infra`**: Capa de abstracción para servicios de terceros (Google Vertex AI, Supabase). Centraliza la configuración técnica para que el resto de la app sea agnóstica a la implementación del cliente.
*   **`app/modules`**: Contiene la lógica "pesada" que no depende del estado del chat. Son funciones puras que realizan cálculos financieros, generan documentos o validan reglas de negocio.
*   **`migrations`**: Mantiene el esquema de Supabase sincronizado. Permite recrear la base de datos desde cero con todas las relaciones y políticas de RLS necesarias.

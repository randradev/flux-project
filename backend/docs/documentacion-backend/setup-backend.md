# INSTRUCCIONES PARA SETUP DEL BACKEND DE PROYECTO FLUX

## ESTRUCTURA DE DIRECTORIOS (BACKEND)

Dentro de /backend, crear la siguiente jerarquía de archivos y carpetas:

/backend
├── /app
│   ├── __init__.py
│   ├── config.py           # Gestión de settings con Pydantic
│   ├── /api
│   │   ├── __init__.py
│   │   ├── deps.py         # Inyección de dependencias (Supabase, Auth)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── chat.py     # Endpoint principal (LangGraph Streaming)
│   │       └── docs.py     # Descarga de contratos y verificación de hashes
│   ├── /graph              # EL CEREBRO (LangGraph)
│   │   ├── __init__.py
│   │   ├── /nodes          # Lógica de transición
│   │   │   ├── __init__.py
│   │   │   ├── credit.py
│   │   │   ├── account.py
│   │   │   ├── deposit.py
│   │   │   └── common.py   # RAG, Global_End, Errores
│   │   ├── edges.py        # Ruteo condicional
│   │   ├── workflow.py     # Compilación del StateGraph
│   │   └── state.py        # Definición del TypedDict (Estado global)
│   ├── /modules            # LA LÓGICA (Cálculos puros)
│   │   ├── __init__.py
│   │   ├── credit_eng.py   # Motor de Riesgo / Amortización
│   │   ├── account_eng.py  # Segmentación
│   │   ├── eco_service.py  # Indicadores (UF, USD)
│   │   ├── security.py     # OTP & Watchdog
│   │   └── pdf_factory.py  # ReportLab + SHA-256
│   └── /infra              # LA INFRAESTRUCTURA
│       ├── __init__.py
│       ├── supabase.py     # Cliente DB y Storage
│       ├── gemini_client.py # Wrapper Vertex AI (Dual-Init)
│       └── embeddings.py   # Cliente para pgvector
├── /secrets                # Almacén de llaves JSON (IGNORAR EN GIT)
├── .env                    # Variables de entorno
├── requirements.txt        # Dependencias
└── main.py                 # Punto de entrada FastAPI

## ENTORNO VIRTUAL Y DEPENDENCIAS

En la carpeta /backend:

1. Crear entorno virtual: python -m venv venv.

2. Crear requirements.txt con estas versiones (específicas para Vertex y LangGraph):

fastapi
uvicorn
python-dotenv
langgraph
langchain-google-vertexai  # Integración oficial con Vertex
google-cloud-aiplatform    # SDK base de GCP
supabase                   # Cliente Supabase
pydantic-settings
reportlab                  # Generación de PDF
pandas                     # Para manejo de tablas de amortización
psycopg2-binary            # Driver para Postgres/Supabase

## CONFIGURACIÓN DE VERTEX AI Y .ENV

Importante: No usar GOOGLE_API_KEY. El sistema debe usar el archivo JSON de cuenta de servicio.

ARCHIVO .ENV:

```bash
# Google Cloud / Vertex AI
GOOGLE_CLOUD_PROJECT_ID=tu-id-de-proyecto
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./secrets/gcp-service-account.json

# Supabase
SUPABASE_URL=tu-url-supabase
SUPABASE_KEY=tu-anon-key
SUPABASE_SERVICE_ROLE_KEY=tu-service-role-key

# App Settings
DEBUG=True
```

## LÓGICA DE INICIALIZACIÓN DE GEMINI (gemini_client.py)

Instrucción para el agente: El cliente debe implementar la estrategia de Dual-Init para evitar errores 404:
- **Brazo Regional (us-central1):** Para modelos de Embeddings (gemini-embedding-001).
- **Brazo Global (aiplatform):** Para Chat y Extracción (gemini-3-flash-preview).

## CÓDIGO BASE PARA app/infra/gemini_client.py:

```python
import os
import vertexai
from vertexai.generative_models import GenerativeModel

def init_vertex():
    project = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    
    # Inyectar credenciales en el entorno para el SDK de Google
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
        
    vertexai.init(project=project, location=location)

# Ejemplo de instancia para Chat
model_flash = GenerativeModel("gemini-3-flash-preview")
```

## PRUEBAS DE CONECTIVIDAD

**Configuración de main.py:**

```python
# app/main.py
@app.get("/")
def heartbeat():
    return {
        "status": "alive",
        "service": "FLUX-Backend",
        "engine": "LangGraph + VertexAI",
        "database": "Supabase Connection Ready"
    }
```

**Una vez corriendo:** abrir http://localhost:8000 para confirmar que el corazón late.
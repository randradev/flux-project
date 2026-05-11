# Estructura del Repositorio - FLUX Project

Este documento proporciona una visión detallada de la organización del código en el proyecto FLUX, explicando la responsabilidad de cada carpeta clave y el porqué de su existencia dentro de la arquitectura del sistema.

## Árbol del Repositorio

```text

flux-project/
├── backend/                        # Lógica de servidor, orquestación de IA y servicios core.
│   ├── app/                        # Código fuente principal de la aplicación FastAPI.
│   │   ├── api/                    # Definición de rutas REST y dependencias de entrada.
│   │   │   └── v1/                 # Versionamiento de la API para compatibilidad.
│   │   ├── assets/                 # Recursos estáticos (ej: plantillas de contratos PDF).
│   │   ├── brain/                  # Conocimiento experto y lógica RAG.
│   │   ├── graph/                  # Orquestación con LangGraph (Corazón de FLUX).
│   │   │   ├── nodes/              # Pasos del flujo (account.py, deposit.py, credit.py).
│   │   │   ├── state.py            # Esquema de estado (Memoria de corto/largo plazo).
│   │   │   ├── edges.py            # Lógica de decisión condicional entre nodos.
│   │   │   └── workflow.py         # Definición de la red de estados.
│   │   ├── infra/                  # Adaptadores de infraestructura (BD, LLM, Auth).
│   │   │   ├── supabase.py         # Persistencia y gestión de usuarios.
│   │   │   └── gemini_client.py    # Integración con Google Gemini Pro.
│   │   ├── modules/                # Motores de negocio específicos.
│   │   │   ├── dap_eng.py          # Motor de Depósito a Plazo.
│   │   │   ├── credit_eng.py       # Motor de Evaluación Crediticia.
│   │   │   └── pdf_factory.py      # Generador de contratos legales.
│   │   └── utils/                  # Helpers transversales (formato, logs).
│   ├── migrations/                 # Evolución del esquema de base de datos.
│   └── tests/                      # Validación de flujos y lógica de negocio.
├── frontend/                       # Interfaz de usuario interactiva (React + Vite).
│   ├── src/                        # Código fuente de la UI.
│   │   ├── components/             # Bloques visuales de la aplicación.
│   │   │   ├── widgets/            # Mini-apps dinámicas (Simuladores, OTP).
│   │   │   └── ChatPanel.jsx       # Interface de conversación en tiempo real.
│   │   ├── context/                # Estados globales y sincronización Backend-UI.
│   │   ├── hooks/                  # Lógica reutilizable (ej: useChat, useAuth).
│   │   └── services/               # Comunicación con la API REST.
│   └── documentacion-frontend/     # Guías de estilo y componentes de la UI.
└── documentacion-gral/             # Documentación estratégica del proyecto.

```

---

## Responsabilidades por Carpeta

### 1. Backend (`/backend`)
El backend está construido sobre **FastAPI** y utiliza **LangGraph** para gestionar procesos conversacionales complejos que requieren memoria y estado persistente.

*   **`app/graph/`**: Es la carpeta más crítica. Existe porque FLUX no es un chatbot simple; es una máquina de estados. Aquí se define cómo el sistema salta de una fase (ej: "Evaluando Riesgo") a otra (ej: "Generando Oferta") basándose en la intención del usuario.
*   **`app/modules/`**: Contiene los "motores" (engines) de cada producto (Crédito, Cuentas, DAP). Existe para desacoplar la lógica de negocio pura de la lógica de flujo conversacional. Si las reglas de un crédito cambian, se modifican aquí sin alterar el grafo.
*   **`app/infra/`**: Centraliza la comunicación con servicios externos como Supabase (Base de datos y Auth) y Gemini (LLM). Su existencia garantiza que si decidimos cambiar de proveedor de base de datos o de modelo de IA, solo debamos tocar esta capa.
*   **`app/brain/`**: Almacena la base de conocimiento para el sistema RAG (Retrieval-Augmented Generation). Permite que el asistente responda consultas técnicas basadas en documentos reales.

### 2. Frontend (`/frontend`)
Una aplicación Single Page Application (SPA) moderna que consume los flujos reactivos del backend.

*   **`src/components/widgets/`**: Existe para manejar la naturaleza modular de FLUX. Cada fase del proceso (un simulador, una carga de documentos, una firma) tiene un widget específico que aparece dinámicamente en el panel lateral.
*   **`src/context/`**: Es vital para mantener la sincronía entre el chat y la interfaz visual. Permite que cuando el backend avanza en el grafo, la UI reaccione instantáneamente (ej: abriendo un modal o cambiando un color).
*   **`src/services/`**: Abstrae las llamadas `fetch` o `axios`. Centraliza el manejo de errores de red y la inyección de tokens de autenticación.

### 3. Documentación (`/documentacion-*`)
*   **`documentacion-gral/`**: Espacio para diagramas de arquitectura, guías de despliegue y manuales que afectan a todo el ecosistema FLUX.
*   **`backend/docs/`**: Documentación profunda de las APIs (OpenAPI) y diagramas técnicos de los grafos de estados.

---

## Contratos de Datos y Comunicación

La comunicación entre el Frontend y el Backend en FLUX es **asimétrica y reactiva**, diseñada para manejar la latencia de la IA y mantener la interfaz sincronizada con el estado del proceso bancario.

### 1. Protocolo de Comunicación: Streaming SSE
A diferencia de las APIs REST tradicionales (request-response síncrono), FLUX utiliza **Server-Sent Events (SSE)** via `HTTP StreamingResponse`.

*   **Endpoint Principal**: `POST /api/v1/chat`
*   **Por qué SSE**: Permite que el backend "empuje" información al frontend a medida que el LLM genera texto o que el grafo transiciona entre nodos, sin que el usuario tenga que esperar a que todo el proceso termine.

### 2. Tipos de Eventos (Contrato de Salida)
El backend emite objetos JSON con una estructura de `type` para que el frontend sepa cómo reaccionar:

| Tipo de Evento | Contenido | Reacción del Frontend |
| :--- | :--- | :--- |
| `message` | Fragmentos de texto del asistente. | Renderiza el texto en la burbuja de chat en tiempo real. |
| `node_transition` | Estado del nodo, progreso y datos de negocio (namespaces). | Actualiza los widgets laterales, la barra de progreso y habilita/deshabilita inputs. |
| `error` | Detalle técnico del fallo. | Muestra un feedback visual de error o reconexión. |
| `done` | Confirmación de fin de procesamiento. | Cierra el estado de "escribiendo" y guarda la conversación. |

### 3. Sincronización de Estado (Namespaces)
El "Contrato de Verdad" es el **FluxState**. Cuando ocurre una transición de nodo, el backend envía solo los fragmentos necesarios del estado (namespaces) para que el frontend los consuma:

*   **`transparency_data`**: Datos para renderizar la "Tarjeta de Transparencia" (tasas, montos, plazos).
*   **`collecting_data`**: Campos que el sistema ya extrajo del chat (ej: renta, antigüedad).
*   **`auth_control`**: Estado de validación OTP y bloqueos de seguridad.

### 4. Acciones Directas (Acciones del Usuario)
Para interactuar con elementos visuales (botones de "Aceptar", "Rechazar", "Enviar OTP"), se utiliza el endpoint:
*   **`POST /api/v1/action`**: Este endpoint permite "saltar" pasos del LLM y manipular el grafo directamente, garantizando una respuesta inmediata ante clics en la interfaz.

---
> [!IMPORTANT]
> El Frontend nunca debe intentar calcular lógica de negocio. Su única responsabilidad es **reflejar el estado** que el Backend le envía a través de los eventos `node_transition`.

## Stack de Herramientas e Integraciones

FLUX utiliza un conjunto de herramientas modernas que se integran para proporcionar una experiencia de banca digital fluida y robusta.

### 1. Núcleo de Inteligencia y Orquestación
*   **LangGraph**: Se integra como el motor de ejecución de la lógica conversacional. Permite definir ciclos, reintentos y estados persistentes. Su integración con `langgraph-checkpoint-postgres` asegura que una conversación pueda retomarse exactamente donde quedó, incluso tras un reinicio del servidor.
*   **Google Gemini (via Vertex AI)**: Es el "cerebro" del sistema. Se integra mediante `langchain-google-vertexai` para procesar el lenguaje natural, extraer intenciones y generar respuestas empáticas y precisas.
*   **LangChain**: Actúa como el framework base que conecta los modelos de lenguaje con las herramientas (tools) y la base de conocimiento (RAG).

### 2. Infraestructura y Datos
*   **Supabase**: Funciona como la base de datos principal y sistema de autenticación.
    *   **Integración Backend**: Se usa el SDK de Python para persistir datos de aplicaciones, usuarios y logs de auditoría.
    *   **Integración Frontend**: Se usa `supabase-js` para el manejo de sesiones de usuario y estados en tiempo real.
*   **PostgreSQL**: Utilizado directamente por LangGraph para el checkpointer de estados, garantizando la atomicidad de las transiciones del grafo.

### 3. Desarrollo de Aplicación
*   **FastAPI**: El framework web que expone los endpoints para el frontend. Su integración con Pydantic garantiza que los contratos de datos entre frontend y backend sean estrictos y validados automáticamente.
*   **React (v19) + Vite**: Proporcionan una interfaz de usuario reactiva y de alto rendimiento. Vite permite un ciclo de desarrollo ultrarrápido (HMR).
*   **Fetch Event Source**: Herramienta crítica integrada para manejar el **streaming** de respuestas desde el backend, permitiendo que el texto del asistente aparezca palabra por palabra en la UI.

### 4. Generación de Documentos y Utilidades
*   **ReportLab**: Integrado en `pdf_factory.py` para transformar los datos procesados por el grafo en contratos legales PDF listos para la firma del cliente.
*   **Pytest**: Framework de pruebas integrado para validar que cada nodo del grafo y cada endpoint de la API funcionen según lo esperado antes de cada despliegue.

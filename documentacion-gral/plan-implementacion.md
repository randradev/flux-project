# PLAN IMPLEMENTACIÓN FLUX

## El Equipo
- Dev 1: AI Orchestrator & Backend Lead.
- Dev 2: Frontend & UX Engineer.
- Dev 3: Trust & Fulfillment Architect.

## FASE 1: Cimientos y Modularización
Objetivo: Que el sistema "lata" y el frontend quede ordenado.
### Dev 1 (AI):
- Tareas Principales:
    - **Setup de Infraestructura y Entorno:**
        - Entorno virtual y dependencias
        - Configuración de servidor con soporte REST StreamingResponse (HTTP)
        - Gestión de variables de entorno mediante pydantic-settings.
    - **Capa de Persistencia y Datos (DB):**
        - Diseño y ejecución de migraciones en Supabase
        - Creación del cliente de base de datos en /infra/supabase.py
        - Configuración del PostgresSaver de LangGraph para el checkpointer (persistencia del estado del grafo).
    - **Configuración de Inteligencia Artificial (Vertex AI):**
        - Implementación del cliente gemini_client.py con estrategia Dual-Init (Regional para Embeddings / Global para Flash)
        - Configuración de la autenticación mediante Application Default Credentials (ADC) apuntando al JSON en /secrets.  
    - **Desarrollo del Core del Grafo (LangGraph):**
        - Definición del StateSchema en state.py (TypedDict con mensajes, user_data y flags de control)
        - Codificación del Intent Router Node:Prompt especializado para clasificar la intención inicial del usuario
        - Codificación del Welcome Node: Nodo encargado de saludar y recuperar perfil de usuario existente en DB si existe.
        - Configuración de workflow.py: Definición de nodos, aristas (edges) y compilación del grafo.
    - **Capa de Autenticación y Persistencia de UI:**
        - **Integración de Supabase Auth:** Configurar la validación de JWT en los endpoints de FastAPI para asegurar que cada petición al Grafo esté vinculada a un user_id real.
        - **Lógica de Threading:** Implementar en LangGraph el uso de thread_id vinculado al user_id, para que el Checkpointer sepa exactamente qué estado recuperar cuando un usuario vuelve después de loguearse.
    - **API Endpoints Básicos:**
        - **Endpoint de Chat:** Creación del endpoint /chat para streaming de eventos del grafo (Soporte REST StreamingResponse (HTTP)).
        - **Endpoint de Historial de Chats:** Crear un endpoint REST /history que recupere de la tabla messages los turnos previos de una conversación, permitiendo que el Grafo tenga memoria a largo plazo entre sesiones.
- Entregable Clave:
    - Servidor FastAPI conectado a Supabase y Vertex AI, capaz de recibir un mensaje, persistir la conversación en la DB y responder a través de un grafo básico que detecta si el usuario quiere un crédito, una cuenta o tiene una duda general.
### Dev 2 (FE):
- Tareas Principales:
    - **Refactorización de Arquitectura:**
        - Separar el archivo único en carpetas: /components (Chat, UI), /hooks (Lógica de estado), /services (Llamadas API).
        - Borrar mockdata.
        - Configurar un Global State (Context API o Zustand) para manejar los datos del usuario que llegan desde el backend.
        - Agregar opción de borrar conversaciones previas en el historial.
    - **Implementación de la Capa de Servicio:**
        - Crear services/api.ts para gestionar las peticiones POST al endpoint de chat.
        - Implementar la lógica para leer Streaming del LLM (manejo de Reader en el fetch).
    - **Capa de Autenticación y Persistencia de UI:**
        - **Implementación de Login/Signup:** Adaptar los formularios de acceso para utilizar el SDK de Supabase Auth y proteger las rutas del chat. Dió la impresión, además, de que no había pantalla de registro, solo de login. De ser así, crearla y aplicar la implementación propuesta.
        - **Garantizar consumo de API de Componente Sidebar de Historial:** Adaptar el panel lateral existente al endpoint /history, permitiendo al usuario navegar entre sus conversaciones previas.
        - **Sincronización de Sesión:** Asegurar que el useFluxGraph envíe el token de autenticación en las cabeceras de cada mensaje y maneje la recuperación de la burbuja de chat al cargar una sesión antigua.
    
- Entregable Clave:
    - Frontend modularizado y limpio, capaz de enviar mensajes al backend y mostrar visualmente en qué "Nodo" está el proceso, aunque la respuesta sea solo un saludo.
### Dev 3 (Secure):
- Tareas Principales:
    - **Lógica de OTP (/modules/security.py):**
        - Crear función generate_otp() que genere códigos de 6 dígitos.
        - Implementar verify_otp() con lógica de comparación de hashes (no guardar el código plano).
        - Crear el contador de intentos en la base de datos (relación con tabla financial_applications).
    - **Motor de Documentos Base (/modules/pdf_factory.py):**
        - Configurar ReportLab. Crear un template base con logo de FLUX, pie de página y espacios para variables dinámicas.
        - Implementar la función de Hashing SHA-256: Un método que tome el contenido del PDF y genere su huella digital.
    - **Integración con Supabase Storage:**
        - Crear los buckets de almacenamiento y la lógica para subir el PDF y recuperar la URL pública/firmada.
    - **Pruebas Unitarias:**
        - Asegurar que el PDF se genera correctamente con datos "fake" antes de que el Dev 1 lo llame desde el Grafo.
- Entregables Clave:    
    - Módulos de Seguridad y Documentos testeados y listos para ser importados como funciones por el orquestador de IA.

## FASE 2: El Primer Vuelo (Crédito de Consumo)
Objetivo: Completar el flujo de punta a punta del primer producto.
### Dev 1 (AI):
- Tareas Principales:
    - **Implementación COmpleta de Nodos de Crédito (/app/graph/nodes/credit.py)**
        - LOAN_INIT: Nodo de servicio para recuperación de datos desde Supabase (RUT, nombre, fecha_nacimiento) y cálculo de edad para el State.
        - LOAN_COLLECTING_PROFILE: Nodo de extracción (LLM) para capturar datos declarativos: renta, antigüedad laboral y nivel de estudios.
        - LOAN_COLLECTING_SIMULATION: Nodo de extracción (LLM) para definir variables del crédito: monto solicitado y plazo (meses).
        - LOAN_RISK_ENGINE (El Puente): Nodo de servicio (Python puro) que ejecuta el motor de riesgo (credit_eng.py), calcula scoring, tasa y tabla de amortización, y persiste el resultado.
        - LOAN_PRE_APPROVED: Nodo de respuesta que gatilla la visualización de la "Tarjeta de Transparencia" en el Frontend.
        - LOAN_OTP_VALIDATION: Nodo de orquestación que invoca al módulo de seguridad para envío/verificación de códigos y maneja el contador de intentos.
        - LOAN_FORMALIZATION: Nodo de servicio que invoca la generación de PDF (pdf_factory.py), aplica el Hash SHA-256 y sube el archivo al storage.
        - LOAN_COMPLETED: Nodo de cierre que entrega el documento final y el Hash de integridad.
    - **Lógica de extracción y Control de Flujo:**
        - Implementar with_structured_output en los nodos de recolección para asegurar la captura de entidades en formato JSON.
        - Mapeo de Estado: Configurar la función de actualización del nodo para que las entidades extraídas (renta, monto, etc.) se mapeen directamente a las llaves del State global, asegurando que el Checkpointer las persista automáticamente en Supabase.
        - Desarrollar los nodos de excepción: LOAN_REJECTED_POLICY (rechazo financiero), LOAN_SECURITY_BLOCK (bloqueo por OTP) y LOAN_CLOSED_BY_USER (cancelación manual)
    - **Configuración de Aristas Condicionales (/app/graph/edges.py):**
        - Programar los "Conditional Edges" que validan si el State tiene los datos suficientes para avanzar al motor de riesgo o si debe re-preguntar.
- Entregable Clave:
    - Programar la lógica de ruteo que evalúa la completitud de datos para avanzar entre hitos o activar nodos de error/rechazo.
### Dev 2 (FE):
- Tareas Principales:
    - **Adaptación Dinámica del Flux Progress Monitor:**
        - Configurar el mapeo de PRODUCT_STEPS para el producto Crédito, vinculando los IDs del backend (LOAN_INIT, LOAN_RISK_ENGINE, etc.) con etiquetas amigables para el usuario.
        - Implementar la lógica de actualización automática: el componente debe reaccionar al cambio de current_step en el estado global para marcar hitos como "completados", "activos" o "pendientes".
    - **Implementación de la Tarjeta de Oferta Interactiva (/components/widgets/):**
        - Desarrollar el componente visual de la "Tarjeta de Transparencia" que se gatilla en el estado LOAN_PRE_APPROVED.
        - Visualización dinámica de datos: renderizar monto aprobado, tasa de interés, valor de cuota y CAE recibidos desde el risk_results del backend.
        - Incorporar botones de acción: "Aceptar Oferta" (avanza al nodo OTP) y "Rechazar/Cerrar" (activa el nodo de cancelación).
    - **Desarrollo del Widget de Validación OTP:**
        - Crear la interfaz de entrada de código de 6 dígitos con validación de máscara y estados de error (código incorrecto, intentos agotados).
        - Conectar el widget con la función de envío del hook useFluxGraph.
    - Gestión de UI para Estados de Excepción:
        - Implementar modales o pantallas de cierre para los estados LOAN_REJECTED_POLICY (mensaje de denegación explicativo) y LOAN_SECURITY_BLOCK
- Entregable Clave:
    - Interfaz de usuario reactiva que refleja visualmente cada avance en el Grafo y permite la interacción completa del flujo de crédito (desde la simulación hasta la aceptación de la oferta).
### Dev 3 (Secure):
- Tareas Principales:
    - **Integración y Persistencia de OTP en Supabase:**
        - Conectar la lógica de security.py con la base de datos para almacenar los hashes de los códigos generados vinculados a la application_id.
        - Implementar el sistema de control de expiración (TTL) y el contador de reintentos directamente en la tabla de aplicaciones financieras.
        - Configurar el servicio de mensajería (simulado o vía API) para el envío del código al "celular/email" del usuario.
    - **Automatización de la Fábrica de Documentos:**
        - Implementar el "Trigger" de generación: una función que se activa automáticamente cuando el nodo LOAN_FORMALIZATION detecta que el estado del OTP es VERIFIED
        - Mapeo de Datos Dinámicos en PDF: Vincular los resultados finales del motor de riesgo (monto, tasa, cuotas, tabla de amortización) con los campos del template en pdf_factory.py.
    - **Cierre de Seguridad y Sello de Integridad:**
        - Generar el Hash SHA-256 final una vez el PDF ha sido "escrito" con los datos del usuario.
        - Persistir el Hash en la base de datos y subir el archivo final al Bucket de Supabase Storage con políticas de solo lectura.
    - **Validación de Flujo Completo (Secure Path):**
        - Realizar pruebas de estrés sobre el proceso de validación para asegurar que el PDF no se genere bajo ninguna circunstancia si el OTP no ha sido verificado satisfactoriamente.
- Entregable Clave:
    - Sistema de validación de identidad robusto y motor de generación de contratos automatizado, capaz de entregar un documento legalmente coherente y técnicamente íntegro.

## FASE 3: Expansión y Blindaje (MVP Completo)
Objetivo: Reutilizar lo hecho para Cuenta/DAP y pulir errores.
### Dev 1 (AI):
- Tareas Principales:
    - **Definir nodos definitivos de Cuenta Corriente y DAP, en el plano teórico.**
    - **Implementación de Nodos de Cuenta Corriente (/app/graph/nodes/account.py)** *// Falta definir nodos*
    - **Implementación de Nodos de DAP (/app/graph/nodes/deposit.py)** *// Falta definir nodos*
    - **Consolidación del Grafo Maestro (/app/graph/workflow.py):**
        - Integrar las nuevas ramas de ACCOUNT y DEPOSIT en el StateGraph principal.
        - Configurar el INTENT_ROUTER para redirigir el flujo correctamente a los puntos de entrada de cada producto según el mensaje del usuario.
    - **Implementación de Nodos Transversales (/app/graph/nodes/common.py):**
    - **Sistema de Gestión de Errores Global (SERVICE_ERROR_HANDLER):**
        - GLOBAL_RAG_NODE: Nodo de consulta a la base de conocimientos (PDFs legales, normativas). Se activa cuando el usuario hace preguntas informativas no relacionadas con un proceso activo.
        - AMBIGUITY_HANDLER: Nodo encargado de gestionar respuestas fuera de contexto. Si el usuario dice algo irrelevante durante la captura de datos, este nodo lo reorienta gentilmente al hito actual.
        - GLOBAL_END: Nodo de cierre unificado que gestiona la despedida, limpia variables temporales sensibles y cierra el thread de conversación de forma lógica.
        - SERVICE_ERROR_HANDLER: Nodo centinela encargado de capturar excepciones técnicas de servicios externos (fallos en la API de Gemini, errores de conexión con Supabase o caídas del motor de riesgo). Debe informar al usuario sobre la interrupción técnica de forma amigable y decidir si el flujo puede reintentar el paso anterior o debe finalizar la sesión.
    - **Consolidación del Grafo Maestro (/app/graph/workflow.py):**
        - Integrar las nuevas ramas de ACCOUNT y DEPOSIT en el StateGraph principal.
        - Configurar el INTENT_ROUTER para redirigir el flujo correctamente a los puntos de entrada de cada producto según el mensaje del usuario.
- Entregable Clave:
    - Orquestador único (Monolito Modular) con los tres productos financieros operativos, ruteo inteligente de intenciones y manejo de errores centralizado.
### Dev 2 (FE):
- Tareas Principales:
    - **Implementación del Visor de Contratos Digitales:**
        - Desarrollar el componente PDFViewer integrado en la interfaz de chat utilizando la URL firmada de Supabase proporcionada por el backend.
    - **Interfaz de Integridad y Validación de Hash:**
        - Implementar el componente de "Sello de Veracidad": una sección visual en el hito final que muestra el Hash SHA-256 del documento.
        - Crear un micro-servicio visual o tooltip explicativo que indique al usuario cómo ese código garantiza que su contrato no ha sido alterado.
    - **Pulido de UX y Animaciones de Transición:**
        - Implementar transiciones suaves (ej: Framer Motion) cuando el Flux Progress Monitor avanza entre nodos, para evitar saltos bruscos de interfaz.
        - Añadir estados de carga (Skeletons) específicos, para momentos como cuando el motor de riesgo está procesando la oferta, por ejemplo (identificar otros momentos donde se requiera e implementarlo).
    - **Dashboard de Historial y Perfil:**
        - Finalizar la vista lateral de historial de conversaciones, permitiendo que el usuario retome flujos de productos pendientes o descargue contratos antiguos.
        - Implementar estados visuales de "Éxito" (confeti o checkmarks animados) al finalizar el hito COMPLETED.
- Entregable Clave:
    - Aplicación web con acabado profesional, alta transparencia en la seguridad de los datos (Hash visible) y una experiencia de navegación fluida que elimina la fricción entre los pasos del proceso financiero.
### Dev 3 (Secure):
- Tareas Principales:
    - **Implementación del SECURITY_WATCHDOG (/modules/security.py):**
        - Desarrollar la lógica de "Estado de Bloqueo" en la base de datos: si el contador de intentos fallidos llega a 3, se marca la solicitud y el perfil del usuario como SUSPENDED.
        - Crear la función de verificación de seguridad que el orquestador consultará antes de permitir un nuevo intento de OTP.
        - Implementar alertas internas (logs de sistema) cuando se detecte un comportamiento de fuerza bruta.
    - **Hardening de la Fábrica de Documentos:**
        - Implementar validaciones de seguridad para evitar la inyección de datos maliciosos en los templates de ReportLab.
        - Asegurar que los contratos PDF en el Storage tengan permisos restringidos (Private Buckets) y solo sean accesibles vía URLs firmadas con expiración corta.
    - **Optimización de Procesos de Cierre:**
        - Refinar la velocidad de generación del PDF y la computación del Hash SHA-256 para minimizar la latencia en el nodo final.
- Entregable Clave:
    - Sistema blindado contra intentos de fraude básicos.

## REGLAS DE ORO
1. Soberanía del Estado (State_Schema):
    - El StateSchema en state.py es la única fuente de verdad.
    - Regla: Ningún desarrollador puede modificar este archivo sin el visto bueno del Dev 1 (Orchestrator).
2. Mocks de Interfaz y Desarrollo Paralelo:
    - Evitar a toda costa el bloque por dependencias.
    - Regla: Si una función externa (Ej: risk_engine o pdf_factory) no está lista, se debe implementar una versión "Mock" (datos estáticos) en el nodo para que el Dev 2 (Frontend) pueda seguir trabajando en la UI sin esperar al código final.
3. 3. Sincronía vía DB (Estados de Verdad):
    - La comunicación entre el Grafo (Dev 1), la UI (Dev 2) y los módulos de Seguridad/Fulfillment (Dev 3) se rige exclusivamente por la tabla `financial_applications`.
    - Regla de Escritura (Backend): Cada nodo de servicio debe actualizar obligatoriamente:
        - `current_step_id`: Con el ID del nodo actual para posicionar el GPS del frontend.
        - `step_status`: Pasarlo a 'IN_PROGRESS' al iniciar una tarea pesada y a 'SUCCESS' o 'FAILED' al terminar.
        - `external_engine_status` o `document_status`: Según el módulo que esté operando, para actuar como "semáforo" de finalización.
    - Regla de Lectura (Frontend): El frontend debe consultar estos campos para:
        - Mover el Flux Progress Monitor basado en `current_step_id`.
        - Gatillar Skeletons o mensajes de espera ("isProcessing") si el `step_status` es 'IN_PROGRESS'.
        - Mostrar pantallas finales de éxito o rechazo basándose en el `status_id` (Estado de Negocio).
    - Implicancia: Ningún componente debe asumir en qué estado está el sistema; la base de datos es la única fuente de verdad que garantiza que el usuario pueda retomar su flujo incluso tras refrescar la página.
4. Estándares de documentación de código:
    - Docstring(''' docstring'''): Cada Nodo de LangGraph y cada módulo de lógica, cada función, componente del frontend, etc, debe tener un Docstring inicial explicando: Entrada (State), Proceso (Lógica de Negocio) y Salida (Campos del State que modifica).
    - Comentarios ( # ): Para explicar lineas de código que puedan ser complejas de entender a simple vista.
5. Protocolo de Git: Ramas y Commits:
    - Nomenclatura de Ramas: Se usará el formato tipo/descripcion-corta (Ej: feat/loan-nodes, fix/pdf-margin, refactor/fe-modularization).
    - Commits Atómicos: Los mensajes de commit deben empezar con un verbo en infinitivo y ser descriptivos (Ej: feat: implementar lógica de hashing en pdf_factory).
    - Merge Policy: Solo se integra a la rama main mediante Pull Requests revisados, asegurando que el servidor de FastAPI levante sin errores.
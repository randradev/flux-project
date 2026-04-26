# DATOS REQUERIDOS POR ESTADO PARA DEPÓSITO A PLAZO

## I. FLUJO DE PREPARACIÓN Y DATOS

### 1. DAP_INIT
Nodo inicial, disparador por el frontend al hacer clic en la opción de solicitud de depósito a plazo.
- nombre (INPUT):
    - Tipo: str
    - Descripción: Nombre del usuario
    - Origen: DB (registro de usuario)
- rut (INPUT):
    - Tipo: str
    - Descripción: RUT del usuario
    - Origen: DB (registro de usuario)
- edad (INPUT):
    - Tipo: int
    - Descripción: Edad del usuario
    - Origen: Cálculo a partir de la fecha de nacimiento de la DB (registro de usuario)
- mail (INPUT):
    - Tipo: str
    - Descripción: Correo electrónico del usuario
    - Origen: DB (registro de usuario)

**Nota de Arquitectura:** Este nodo ya no realiza la consulta primaria a la base de datos (DB). Dicha gestión fue centralizada en WELCOME_NODE para optimizar el rendimiento y asegurar que la data esté disponible antes de la segmentación por producto.

**Datos Pre-cargados (Provenientes de preparation_data):**
- nombre, rut, mail, edad (calculada dinámicamente en WELCOME_NODE).

**Nueva Responsabilidad del Nodo (Fase 2):**
- Reset de Contexto: Limpiar el namespace correspondiente en collecting_data para asegurar que el usuario inicie con parámetros limpios si ya tuvo intentos previos.
- Handshake de Producto: Validar que el product_intent en la sesión coincida con el flujo iniciado.
- Transición: Actuar como el punto de entrada lógico que saluda al usuario de forma personalizada usando los datos ya cargados.

**Flujo de Salida:** Al finalizar la lógica (en milisegundos), el grafo transiciona automáticamente al nodo de Recolección de Datos (COLLECT_DATA) sin esperar un nuevo input del usuario.

### 2. DAP_COLLECT_DATA
- monto (INPUT):
    - Tipo: float
    - Descripción: Monto a invertir
    - Origen: Interacción con el usuario (Chat)
- moneda (INPUT):
    - Tipo: str
    - Descripción: Moneda de la inversión. Valores posibles: "CLP", "UF", "USD" (taxonómico)
    - Origen: Interacción con el usuario (Chat)
- plazo (INPUT):
    - Tipo: int
    - Descripción: Plazo de la inversión en días. Valores posibles: "7", "14", "30", "180", "360" (taxonómico)
    - Origen: Interacción con el usuario (Chat)
    - Nota: Debe transformarse el mensaje del usuario a int

## II. FLUJO DE EVALUACIÓN Y OFERTA

### 3. DAP_INVESTMENT_ENGINE (Motor de Cálculo de Inversión)
Este estado es un Nodo de Servicio automático.

**INPUTS (Datos requeridos para el cálculo):**
- monto (proviene de DAP_COLLECT_DATA)
- moneda (proviene de DAP_COLLECT_DATA)
- plazo (proviene de DAP_COLLECT_DATA)
- edad (proviene de DAP_INIT)
- valor_uf (proviene de eco_service.py, que se conecta a una API externa)
- valor_usd (proviene de eco_service.py, que se conecta a una API externa)
- valor_ipc (proviene de eco_service.py, que se conecta a una API externa)

**OUTPUTS (Datos generados por el motor):**
- status_proceso:
    - PRE_APPROVED: Califica e ingresó parámetros permitidos. Avanza a DAP_PRE_APPROVED.
    - REJECTED_POLICY: No cumple edad, o el monto o plazo ingresado no está dentro del rango permitido. Envía a DAP_REJECTED_POLICY. Fin del flujo.
    - ERROR_TECHNICAL: Falló la conexión con el motor o hubo un error matemático. Envía a SERVICE_ERROR (mensaje de "reintenta más tarde")
- is_elegible (bool):
    - Descripción: si cumple edad $\ge$ 18 y el monto convertido a CLP está entre $50k y $50M.
- conversion_rate_used (float):
    - El valor del USD o UF consultado en la API externa el mismo día. Si es CLP, el valor es 1.0. Importado desde app/modules/eco_service.py (API externa).
- ipc_applied (float):
    - Descripción: El valor del $\Delta IPC$ obtenido de la API (solo si moneda es CLP, de lo contrario 0.0). Importado desde app/modules/eco_service.py (API externa) (Solo si moneda es CLP).
- term_premium (float):
    - Descripción: El valor del premio por plazo calculado (0.05% por cada escalón de 30 días). Función matemática: (plazo // 30) * 0.05.
- monthly_rate_total (float):
    - Descripción: La tasa mensual sumada ($i_{base} + P_{plazo} + \Delta IPC$).
- period_rate (float):
    - Descripción: La tasa real aplicada al plazo ($i_{mensual} \times Plazo/30$).
- estimated_gain (float):
    - Descripción: El monto de ganancia proyectado en la moneda original (redondeado: CLP sin decimales, UF/USD a 2 decimales).
- total_return (float):
    - Descripción: Capital inicial + Ganancia estimada (redondeado: CLP sin decimales, UF/USD a 2 decimales).
- motivo_rechazo:
    - Tipo: str
    - Descripción: Código técnico que identifica la política específica que fue vulnerada. Este dato es el que permite al bot dar una respuesta personalizada en el estado de error.
    - Valores posibles (Contrato de Interfaz):
        - "ERR_EDAD": El usuario tiene menos de 18 años.
        - "ERR_MONTO_MIN": El monto ingresado es menor al mínimo permitido.
        - "ERR_MONTO_MAX": El monto ingresado es mayor al máximo permitido.
        - NULL: Si no hay error.

### 4. DAP_PRE_APPROVED (Tarjeta de Transparencia)
Muestra la oferta final tras el éxito del DAP_INVESTMENT_ENGINE

**INPUTS (Datos requeridos para la visualización):**
- monto (proviene de DAP_COLLECT_DATA)
- moneda (proviene de DAP_COLLECT_DATA)
- estimated_gain (proviene de DAP_INVESTMENT_ENGINE)
- total_return (proviene de DAP_INVESTMENT_ENGINE)
- period_rate (proviene de DAP_INVESTMENT_ENGINE)
- conversion_rate_used (proviene de DAP_INVESTMENT_ENGINE, para usar como indicador de referencia si es USD/UF)
- ipc_applied (proviene de DAP_INVESTMENT_ENGINE, para usar como indicador de referencia si es CLP)

**OUTPUTS (Datos generados por el usuario):**
- pre_approval_status:
    - ACCEPTED: El usuario presiona "Aceptar" en la tarjeta. Avanza a DAP_OTP_VALIDATION.
    - REJECTED: El usuario presiona "Rechazar". Transita a DAP_CLOSED_BY_USER (Mensaje de despedida y limpieza de sesión).
- timestamp_acceptance:
    - Tipo: datetime
    - Descripción: Registro exacto del momento de la aceptación (Requerido para el contrato final).

## III. FLUJO DE FORMALIZACIÓN Y CIERRE

### 5. DAP_OTP_VALIDATION (Validación por Email)

**INPUTS:**
- mail:
    - Tipo: str
    - Origen: Persistente. Proviene originalmente de DAP_INIT (recuperado de la base de datos) y se arrastra a través del estado del grafo. 
- otp_generated:
    - Tipo: str (6 dígitos, ej: "542019")
    - Origen: Generado por el sistema. Es creado por una función de utilidad de seguridad al entrar en este nodo.
    - Nota: Se recomienda str y no int para manejar ceros a la izquierda (ej: "001234").
- otp_user_input:
    - Tipo: str
    - Origen: Usuario (Chat). Es el dato que el usuario escribe en la interfaz del chatbot tras recibir el correo.
- otp_attempts:
    - Tipo: int
    - Origen: Contador de estado. Se inicializa en 0 al entrar por primera vez al nodo y se incrementa en +1 con cada fallo en la validación.
    - Límite: Si llega a 3, gatilla la transición al estado transversal SECURITY_WATCHDOG.

**OUTPUTS:**
- otp_status:
    - VERIFIED:
        - Descripción: El código ingresado coincide con el generado.
        - Destino: DAP_FORMALIZATION
    - FAILED:
        - Descripción: El código es incorrecto o ha expirado, pero el usuario aún tiene intentos disponibles (menos de 3).
        - Destino: Se mantiene en el mismo estado (DAP_OTP_VALIDATION). El bot envía un mensaje de error y permite reintentar.
    - BLOCKED:
        - Descripción: El usuario alcanzó el máximo de 3 intentos fallidos.
        - Destino: Se invoca a estado transversal SECURITY_WATCHDOG.

### 6. DAP_FORMALIZATION (Generación y Sellado)
Nodo de servicio para formalización documental.

**INPUTS (Recolección Interna):**
- monto (proviene de DAP_COLLECT_DATA)
- plazo (proviene de DAP_COLLECT_DATA)
- moneda (proviene de DAP_COLLECT_DATA)
- estimated_gain (proviene de DAP_INVESTMENT_ENGINE)
- total_return (proviene de DAP_INVESTMENT_ENGINE)
- period_rate (proviene de DAP_INVESTMENT_ENGINE)
- conversion_rate_used (proviene de DAP_INVESTMENT_ENGINE, para usar como indicador de referencia si es USD/UF)
- ipc_applied (proviene de DAP_INVESTMENT_ENGINE, para usar como indicador de referencia si es CLP)
- rut (Persistente. Proviene originalmente de DAP_INIT (recuperado de la base de datos) y se arrastra a través del estado del grafo.)
- nombre (Persistente. Proviene originalmente de DAP_INIT (recuperado de la base de datos) y se arrastra a través del estado del grafo.)
- timestamp_acceptance (proviene de DAP_PRE_APPROVED)

**OUTPUTS:**
- file_contrato_path: Ruta/URL del PDF generado con ReportLab
- hash_sha256: Hash SHA-256 del contrato generado
- contract_status:
    - SIGNED_AND_STAMPED:
        - Descripción: Éxito total. El PDF existe, tiene su Hash y está guardado..
        - Destino: DAP_COMPLETED
    - GENERATION_FAILED:
        - Descripción: Cualquier error en el proceso (error de ReportLab, error de permisos de carpeta o fallo en el Hashing).
        - Destino: SERVICE_ERROR

### 7. DAP_COMPLETED (Estado Final)

**INPUTS:**
- file_contrato_path:
    - Tipo: str
    - Descripción: Ruta/URL del PDF generado con ReportLab, para que el usuario pueda descargarlo.
    - Origen: DAP_FORMALIZATION
- hash_sha256:
    - Tipo: str
    - Descripción: Hash SHA-256 del contrato generado, para mostrar al usuario como comprobante de seguridad.
    - Origen: DAP_FORMALIZATION
- contract_status:
    - Tipo: str
    - Descripción: Estado del contrato. Funciona como un flag para saber si el contrato se generó correctamente antes de dar las felicitariones, entregar el documento y despedirse.
    - Origen: DAP_FORMALIZATION

**OUTPUTS:**
- status_code: SUCCESS
    - Descripción: Indica que el proceso completo del depósito a plazo terminó exitosamente.
- product_name:
    - Valor: "Depósito a Plazo"
- display_data:
    - download_url: Enlace al documento firmado.
    - main_detail: Dato clave (ej: "Monto: $5.000.000").
    - security_hash: Hash SHA-256 de la transacción.
Destino: GLOBAL_END (estado transversal)

## IV. ESTADOS DE MANEJO DE ERRORES Y EXCEPCIONES

### 8. DAP_REJECTED_POLICY (Rechazo por Políticas)

**INPUTS:**
- nombre:
    - Tipo: str
    - Descripción: Nombre del usuario.
    - Origen: DAP_INIT
- motivo_rechazo:
    - Tipo: str
    - Origen: LOAN_RISK_ENGINE
    - Lógica: Al detectar un fallo, el motor escribe la razón: ERR_EDAD, ERR_MONTO_MIN, ERR_MONTO_MAX.
    - USO: El estado DAP_REJECTED_POLICY toma este string y gatilla el mensaje correspondiente.

**OUTPUTS:**
- status_code: REJECTED
- product_name: "Depósito a Plazo"
- display_data: 
    - reason: El motivo tipificado por el motor de riesgo (por ejemplo ERR_EDAD, etc).

### 9. DAP_SECURITY_BLOCK (Bloqueo de Seguridad)

**INPUTS:**
- rut:
    - Tipo: str
    - Origen: Persistente desde DAP_INIT
- mail:
    - Tipo: str
    - Origen: Persistente desde DAP_INIT
- otp_attempts:
    - Tipo: int
    - Descripción: Contador de intentos fallidos (debe ser 3 al entrar en este estado).
    - Origen: DAP_OTP_VALIDATION
- last_otp_input:
    - Tipo: str
    - Descripción: El último código erróneo ingresado por el usuario (útil para análisis de patrones de fraude).

**OUTPUTS:**
- security_status:
    - Valor: BLOCKED
    - Descripción: Indica que el proceso ha sido bloqueado por seguridad debido a múltiples intentos fallidos.
    - Destino: END (Termina el Grafo)
- block_timestamp:
    - Tipo: datetime
    - Descripción: Fecha y hora exacta del bloqueo. Se utiliza para calcular el periodo de "enfriamiento" (ej: 24 horas) antes de permitir un nuevo intento.
- status:
    - Valor: TERMINATED
    - Destino: END (Termina el Grafo)

### 11. DAP_CLOSED_BY_USER (Cierre Voluntario)

**INPUTS:**
- ultimo_estado_alcanzado:
    - Tipo: str
    - Descripción: Identifica en qué nodo estaba el usuario antes de abandonar (ej: LOAN_PRE_APPROVED, LOAN_OTP_VALIDATION).
    - Origen: Estado del Grafo (Metadata)

- estimated_gain (proviene de DAP_INVESTMENT_ENGINE)
    - Descripción: Permite analizar si el abandono fue por las ganancias estimadas.

- total_return (proviene de DAP_INVESTMENT_ENGINE)
    - Descripción: Permite analizar si el abandono fue por el retorno total.

- close_reason:
    - Tipo: str
    - Descripción: Motivo capturado (Rechazo de oferta).

**OUTPUTS:**
- status_code: CLOSED_BY_USER
- product_name: "Depósito a Plazo"
- display_data: 
    - estimated_gain (proveniente de DAP_INVESTMENT_ENGINE)
    - total_return (proveniente de DAP_INVESTMENT_ENGINE)

## V. INTERACCIÓN CON ESTADOS TRANSVERSALES
Este apartado define las reglas de interrupción y retorno para el Grafo de DAP. Todos los nodos de recolección de datos (DAP_COLLECT_DATA) deben heredar este comportamiento.

1. Lógica de Interrupción (Gateways de Desvío)
Cada vez que el usuario ingresa un mensaje (Input), el sistema debe evaluar tres condiciones antes de procesar el dato para el crédito:
- A. Detección de Consulta (RAG):
    - Condición: Si el LLM detecta que el input es una pregunta técnica, de política o general (ej: "¿El depósito a plazo es automáticamente renovable? ¿Que pasa si necesito el dinero antes?, etc.").
    - Acción: Suspender el estado actual, guardar el ultimo_estado_alcanzado y saltar a KNOWLEDGE_BASE_RAG.
    - Retorno: Tras la respuesta, el sistema debe ejecutar un "re-entry" al nodo original solicitando nuevamente el dato pendiente.
- B. Detección de Ambigüedad/Fuera de Contexto:
    - Condición: Si el input no contiene un dato procesable y no es una duda (ej: "está lloviendo", "no lo sé", "un segundo").
    -  Acción: El sistema responderá de forma empática pero mantendrá el estado actual, volviendo a solicitar la información necesaria sin avanzar en el grafo. No se requiere registro de intentos.
- C. Detección de Amenaza o Bloqueo:
    - Condición: Si el input contiene insultos, intentos de inyección de prompts o fallos críticos en el paso de LOAN_OTP_VALIDATION
    - Acción: Saltar a SECURITY_WATCHDOG. Este estado es terminal; no hay retorno al flujo de crédito

2. Gestión de Errores de Servicio (Resiliencia)
Para los nodos que dependen de servicios externos (LOAN_RISK_ENGINE y LOAN_FORMALIZATION):
- Trigger: Ante cualquier HTTP_ERROR o TIMEOUT de API.
- Acción: Saltar a SERVICE_ERROR_HANDLER
- Persistencia: El estado transversal debe asegurar que los datos ya recolectados (Monto, Plazo, etc.) persistan en la tabla financial_applications con status IN_PROGRESS para permitir que el usuario retome desde el Dashboard.

3. Sincronización con la Interfaz (Dashboard Sync)
- Estado Visual: Mientras el flujo esté en un Estado Transversal (ej: respondiendo una duda), el componente "Proceso Flux" de la UI debe mantener resaltado el nodo de crédito original como "En curso".
- Feedback: El LLM debe usar frases de transición para volver al carril principal: "Respondida tu duda sobre [TEMA], retomemos: me habías dicho que deseas invertir CLP $500.000..., ¿Qué plazo deseas para tu depósito?"

4. Prioridad de Ejecución (Orden de Evaluación)
- 1ERO: Security Check (¿Es un mensaje malicioso?) -> SECURITY_WATCHDOG
- 2DO: Intent Check (¿Es una duda?) -> KNOWLEDGE_BASE_RAG
- 3ERO: Data Extraction (¿Es el dato que pedí?) -> Procesar en Nodo de DAP.
- 4TO: Ambiguity Check (¿Es ruido?) -> AMBIGUITY_HANDLER

**NOTA:** Implementar esta lógica mediante Conditional Edges básicos en LangGraph. El estado global debe mantener un objeto metadata que rastree si el usuario está en un "desvío transversal" para garantizar que el hilo de conversación nunca pierda el objetivo final de la solicitud de DAP.
# DATOS REQUERIDOS POR ESTADO PARA CUENTA CORRIENTE

## I. FLUJO DE PREPARACIÓN Y DATOS

### 1. ACCOUNT_INIT
Nodo inicial, disparador por el frontend al hacer clic en la opción de solicitud de cuenta corriente.
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

### 2. ACCOUNT_COLLECTING_PROFILE
- renta (INPUT):
    - Tipo: int
    - Descripción: Renta líquida declarada por el usuario (en CLP)
    - Origen: Chat
- antiguedad_laboral (INPUT):
    - Tipo: int
    - Descripción: Antigüedad laboral del usuario (en meses)
    - Origen: Chat
- nivel_estudios (INPUT):
    - Tipo: str
    - Descripción: Nivel de estudios del usuario (Categorías: POSTGRADO, UNIVERSITARIO, TECNICO, MEDIA)
    - Origen: Chat

## II. FLUJO DE EVALUACIÓN Y OFERTA

### 3. ACCOUNT_EVALUATION_ENGINE (Motor de Evaluación Comercial)
Este estado es un Nodo de Servicio automático.

**INPUTS (Datos requeridos para el cálculo):**
- renta (proviene de ACCOUNT_COLLECTING_PROFILE)
- antiguedad_laboral (proviene de ACCOUNT_COLLECTING_PROFILE)
- nivel_estudios (proviene de ACCOUNT_COLLECTING_PROFILE)
- edad (proviene de ACCOUNT_INIT)

**OUTPUTS (Datos generados por el motor):**
- status_proceso:
    - PRE_APPROVED: Califica para el producto. Avanza a ACCOUNT_PRE_APPROVED.
    - REJECTED_POLICY: No cumple edad, renta o antigüedad mínima. Envía a ACCOUNT_REJECTED_POLICY. Fin del flujo.
    - ERROR_TECHNICAL: Falló la conexión con el motor o hubo un error matemático. Envía a SERVICE_ERROR (mensaje de "reintenta más tarde")
- is_elegible (bool):
    - Descripción: Resultado de la validación de mínimos (Edad $\ge$ 18, Renta $\ge$ $500.000, Antigüedad $\ge$ 6 meses).
- base_category (str):
    - Descripción: Categoría asignada inicialmente solo por tramo de renta (START, MEDIUM, ADVANCE).
- final_category (str):
    - Descripción: Categoría final tras aplicar el upgrade por Nivel de Estudios (si aplica).
- has_upgrade (bool):
    - Descripción: Flag que indica si el usuario obtuvo una categoría superior gracias a su título profesional (para feedback en la Tarjeta de Transparencia).
- credit_line_amount (int):
    -  Descripción: Monto de la línea de crédito aprobada ($0 si es START o antigüedad < 12 meses; 0.5 * de la renta si es MEDIUM/ADVANCE con antigüedad $\ge$ 12 meses).
- monthly_cost (int):
    - Costo de mantención. Valor fijo: $0 (según Promoción MVP).
- motivo_rechazo (str):
    - Descripción: Código técnico que identifica la política específica que fue vulnerada. Este dato es el que permite al bot dar una respuesta personalizada en el estado de error.
    - Valores posibles (Contrato de Interfaz):
        - "ERR_EDAD": El usuario tiene menos de 18 años.
        - "ERR_RENTA": La renta declarada es inferior al mínimo legal o político.
        - "ERR_ANTIGUEDAD": El usuario lleva menos de 6 meses trabajando.
        -  NULL: Si no hay error.

### 4. ACCOUNT_PRE_APPROVED (Tarjeta de Transparencia)
Muestra la oferta final tras el éxito del ACCOUNT_EVALUATION_ENGINE

**INPUTS (Datos requeridos para la visualización):**
- final_category (proviene de ACCOUNT_EVALUATION_ENGINE)
- has_upgrade (proviene de ACCOUNT_EVALUATION_ENGINE)
- credit_line_amount (proviene de ACCOUNT_EVALUATION_ENGINE)
- monthly_cost (proviene de ACCOUNT_EVALUATION_ENGINE)

**OUTPUTS:**
- pre_approval_status:
    - ACCEPTED: El usuario presiona "Aceptar" en la tarjeta. Avanza a ACCOUNT_OTP_VALIDATION.
    - REJECTED: El usuario presiona "Rechazar". Transita a ACCOUNT_CLOSED_BY_USER (Mensaje de despedida y limpieza de sesión).
- timestamp_acceptance:
    - Tipo: datetime
    - Descripción: Registro exacto del momento de la aceptación (Requerido para el contrato final).

## III. FLUJO DE FORMALIZACIÓN Y CIERRE

### 5. ACCOUNT_OTP_VALIDATION (Validación por Email)

**INPUTS:**
- mail:
    - Tipo: str.
    - Descripción: Correo electrónico del usuario
    - Origen: Persistente. Proviene originalmente de ACCOUNT_INIT (recuperado de la base de datos) y se arrastra a través del estado del grafo.
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
    - Limite: Si llega a 3, gatilla la transición al estado transversal SECURITY_WATCHDOG.

**OUTPUTS:**
- otp_status:
    - VERIFIED:
        - Descripción: El código ingresado coincide con el generado.
        - Destino: ACCOUNT_FORMALIZATION
    - FAILED:
        - Descripción: El código es incorrecto o ha expirado, pero el usuario aún tiene intentos disponibles (menos de 3).
        - Destino: Se mantiene en el mismo estado (ACCOUNT_OTP_VALIDATION). El bot envía un mensaje de error y permite reintentar.
    - BLOCKED:
        - Descripción: El usuario alcanzó el máximo de 3 intentos fallidos.
        - Destino: Se invoca a estado transversal SECURITY_WATCHDOG.

### 6. ACCOUNT_FORMALIZATION (Generación y Sellado)
Nodo de servicio para formalización documental.

**INPUTS (Recolección Interna):**
- final_category (proviene de ACCOUNT_EVALUATION_ENGINE)
- has_upgrade (proviene de ACCOUNT_EVALUATION_ENGINE)
- credit_line_amount (proviene de ACCOUNT_EVALUATION_ENGINE)
- monthly_cost (proviene de ACCOUNT_EVALUATION_ENGINE)
- rut (Persistente. Proviene originalmente de ACCOUNT_INIT (recuperado de la base de datos) y se arrastra a través del estado del grafo.)
- nombre (Persistente. Proviene originalmente de ACCOUNT_INIT (recuperado de la base de datos) y se arrastra a través del estado del grafo.)
- timestamp_acceptance (proviene de ACCOUNT_PRE_APPROVED)

**OUTPUTS:**
- file_contrato_path: Ruta/URL del PDF generado con ReportLab
- hash_sha256: Hash SHA-256 del contrato generado
- contract_status:
    - SIGNED_AND_STAMPED:
        - Descripción: Éxito total. El PDF existe, tiene su Hash y está guardado..
        - Destino: LOAN_COMPLETED
    - GENERATION_FAILED:
        - Descripción: Cualquier error en el proceso (error de ReportLab, error de permisos de carpeta o fallo en el Hashing).
        - Destino: SERVICE_ERROR

### 7. ACCOUNT_COMPLETED

**INPUTS:**
- file_contrato_path:
    - Tipo: str
    - Descripción: Ruta/URL del PDF generado con ReportLab, para que el usuario pueda descargarlo.
    - Origen: ACCOUNT_FORMALIZATION
- hash_sha256:
    - Tipo: str
    - Descripción: Hash SHA-256 del contrato generado, para mostrar al usuario como comprobante de seguridad.
    - Origen: ACCOUNT_FORMALIZATION
- contract_status:
    - Tipo: str
    - Descripción: Estado del contrato. Funciona como un flag para saber si el contrato se generó correctamente antes de dar las felicitariones, entregar el documento y despedirse.
    - Origen: ACCOUNT_FORMALIZATION

**OUTPUTS:**
- status_code: SUCCESS
    - Descripción: Indica que el proceso completo del crédito terminó exitosamente.
- product_name:
    - Valor: "Cuenta Corriente
- display_data:
    - download_url: Enlace al documento firmado.
    - main_detail: Dato clave (ej: "Cuenta: Start").
    - security_hash: Hash SHA-256 de la transacción.
Destino: GLOBAL_END (estado transversal)

## IV. ESTADOS DE MANEJO DE ERRORES Y EXCEPCIONES

### 8. ACCOUNT_REJECTED_POLICY

**INPUTS:**
- nombre:
    - Tipo: str
    - Descripción: Nombre del usuario.
    - Origen: ACCOUNT_INIT
- motivo_rechazo:
    - Tipo: str
    - Origen: ACCOUNT_EVALUATION_ENGINE
    - Lógica: Al detectar un fallo, el motor escribe la razón: ERR_EDAD, ERR_RENTA, ERR_ANTIGUEDAD
    - USO: El estado ACCOUNT_REJECTED_POLICY toma este string y gatilla el mensaje correspondiente.

**OUTPUTS:**
- status_code: REJECTED
- product_name: "Cuenta Corriente"
- display_data: 
    - reason: El motivo tipificado por el motor de evaluación comercial (por ejemplo ERR_RENTA, etc).

### 9. ACCOUNT_SECURITY_BLOCK (Bloqueo de Seguridad)

**INPUTS:**
- rut:
    - Tipo: str
    - Origen: Persistente desde ACCOUNT_INIT
- mail:
    - Tipo: str
    - Origen: Persistente desde ACCOUNT_INIT
- otp_attempts:
    - Tipo: int
    - Descripción: Contador de intentos fallidos (debe ser 3 al entrar en este estado).
    - Origen: ACCOUNT_OTP_VALIDATION
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

### 10. ACCOUNT_CLOSED_BY_USER (Cierre Voluntario)

**INPUTS:**
- ultimo_estado_alcanzado:
    - Tipo: str
    - Descripción: Identifica en qué nodo estaba el usuario antes de abandonar (ej: ACCOUNT_PRE_APPROVED, ACCOUNT_OTP_VALIDATION). Es vital para saber en qué etapa se "caen" los clientes.
    - Origen: Estado del Grafo (Metadata)

- final_category:
    - Tipo: int
    - Descripción: Permite analizar si el abandono fue por la categoría asignada

- credit_line_amount:
    - Tipo: int
    - Descripción: Permite analizar si el abandono fue por el cupo de línea de crédito otorgado.

- close_reason:
    - Tipo: str
    - Descripción: Motivo capturado (Rechazo de oferta)

**OUTPUTS:**
- status_code: CLOSED_BY_USER
- product_name: "Crédito de Consumo"
- display_data: 
    - final_category (proveniente de ACCOUNT_EVALUATION_ENGINE)
    - credit_line_amount (proveniente de ACCOUNT_EVALUATION_ENGINE)

## V. INTERACCIÓN CON ESTADOS TRANSVERSALES
Este apartado define las reglas de interrupción y retorno para el Grafo de Cuenta Corriente. Todos los nodos de recolección de datos (ACCOUNT_COLLECTING_x) deben heredar este comportamiento.

1. Lógica de Interrupción (Gateways de Desvío)
Cada vez que el usuario ingresa un mensaje (Input), el sistema debe evaluar tres condiciones antes de procesar el dato para la cuenta corriente:
- A. Detección de Consulta (RAG):
    - Condición: Si el LLM detecta que el input es una pregunta técnica, de política o general (ej: "¿Qué es la categoría ADVANCE?", "¿Cómo firmo?", etc).
    - Acción: Suspender el estado actual, guardar el ultimo_estado_alcanzado y saltar a KNOWLEDGE_BASE_RAG.
    - Retorno: Tras la respuesta, el sistema debe ejecutar un "re-entry" al nodo original solicitando nuevamente el dato pendiente.
- B. Detección de Ambigüedad/Fuera de Contexto:
    - Condición: Si el input no contiene un dato procesable y no es una duda (ej: "está lloviendo", "no lo sé", "un segundo").
    -  Acción: El sistema responderá de forma empática pero mantendrá el estado actual, volviendo a solicitar la información necesaria sin avanzar en el grafo. No se requiere registro de intentos.
- C. Detección de Amenaza o Bloqueo:
    - Condición: Si el input contiene insultos, intentos de inyección de prompts o fallos críticos en el paso de ACCOUNT_OTP_VALIDATION
    - Acción: Saltar a SECURITY_WATCHDOG. Este estado es terminal; no hay retorno al flujo de cuenta corriente

2. Gestión de Errores de Servicio (Resiliencia)
Para los nodos que dependen de servicios externos (ACCOUNT_EVALUATION_ENGINE y ACCOUNT_FORMALIZATION):
- Trigger: Ante cualquier HTTP_ERROR o TIMEOUT de API.
- Acción: Saltar a SERVICE_ERROR_HANDLER
- Persistencia: El estado transversal debe asegurar que los datos ya recolectados (Renta, Monto, etc.) persistan en la tabla financial_applications con status IN_PROGRESS para permitir que el usuario retome desde el Dashboard.

3. Sincronización con la Interfaz (Dashboard Sync)
- Estado Visual: Mientras el flujo esté en un Estado Transversal (ej: respondiendo una duda), el componente "Proceso Flux" de la UI debe mantener resaltado el nodo de cuenta corriente original como "En curso".
- Feedback: El LLM debe usar frases de transición para volver al carril principal: "Respondida tu duda sobre [TEMA], retomemos: me habías dicho que tu renta es de..., ¿en qué nivel de estudios te encuentras?"

4. Prioridad de Ejecución (Orden de Evaluación)
- 1ERO: Security Check (¿Es un mensaje malicioso?) -> SECURITY_WATCHDOG
- 2DO: Intent Check (¿Es una duda?) -> KNOWLEDGE_BASE_RAG
- 3ERO: Data Extraction (¿Es el dato que pedí?) -> Procesar en Nodo de Cuenta.
- 4TO: Ambiguity Check (¿Es ruido?) -> AMBIGUITY_HANDLER

**NOTA:** Implementar esta lógica mediante Conditional Edges básicos en LangGraph. El estado global debe mantener un objeto metadata que rastree si el usuario está en un "desvío transversal" para garantizar que el hilo de conversación nunca pierda el objetivo final de la solicitud de cuenta corriente.
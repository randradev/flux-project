# DATOS REQUERIDOS POR ESTADO PARA CRÉDITO DE CONSUMO

## I. FLUJO DE PREPARACIÓN Y DATOS

### 1. LOAN_INIT
Nodo inicial, disparador por el frontend al hacer clic en la opción de solicitud de crédito.
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

### 2. LOAN_COLLECTING_PROFILE
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

### 3. LOAN_COLLECTING_SIMULATION
- monto_solicitado (INPUT):
    - Tipo: int
    - Descripción: Monto del crédito solicitado por el usuario (en CLP)
    - Origen: Chat
- plazo_solicitado (INPUT):
    - Tipo: int
    - Descripción: Plazo del crédito solicitado por el usuario (en meses)
    - Origen: Chat

## II. FLUJO DE EVALUACIÓN Y OFERTA

### 4. LOAN_RISK_ENGINE (Motor de Riesgo)
Este estado es un Nodo de Servicio automático.

**INPUTS (Datos requeridos para el cálculo):**
- renta (proviene de LOAN_COLLECTING_PROFILE)
- antiguedad_laboral (proviene de LOAN_COLLECTING_PROFILE)
- nivel_estudios (proviene de LOAN_COLLECTING_PROFILE)
- edad (proviene de LOAN_INIT)
- monto_solicitado (proviene de LOAN_COLLECTING_SIMULATION)
- plazo_solicitado (proviene de LOAN_COLLECTING_SIMULATION)

**OUTPUTS (Datos generados por el motor):**
- status_proceso:
    - PRE_APPROVED: Califica y tiene capacidad de pago. Avanza a LOAN_PRE_APPROVED.
    - REJECTED_POLICY: No cumple edad, renta o antigüedad mínima. Envía a LOAN_REJECTED_POLICY. Fin del flujo.
    - ERROR_TECHNICAL: Falló la conexión con el motor o hubo un error matemático. Envía a SERVICE_ERROR (mensaje de "reintenta más tarde")
- scoring_puntos:
    - Tipo: int
    - Descripción: puntaje total obtenido (0-100), El resultado de la suma de las 4 ponderaciones.
- nivel_riesgo:
    - Tipo: str
    - Descripción: Categoría de riesgo (Bajo, Medio, Alto).
- tasa_interes_mensual:
    - Tipo: float
    - Descripción: Tasa aplicada según riesgo (0.012, 0.020, o 0.035)
- cuota_mensual:
    - Tipo: int
    - Descripción: Monto fijo mensual (Amortización Francesa, redondeado al entero superior: $$M = P \frac{i(1+i)^n}{(1+i)^n - 1}$$)
- cuota_maxima_permitida:
    - Tipo: int
    - Descripción: El valor de renta * 0.30 (para comparar).
- capacidad_pago_valida:
    - Tipo: bool
    - Descripción: true si cuota_mensual <= renta * 0.30, si es false, pasa a REJECTED_POLICY
- ctc (Costo Total del Crédito):
    - Tipo: int
    - Descripción: Monto total a pagar (cuota * plazo)
- total_intereses:
    - Tipo: int
    - Descripción: Diferencia entre CTC y Monto Original
- cae (Carga Anual Equivalente):
    - Tipo: float
    - Descripción: Tasa anual compuesta (formato decimal o porcentaje)
- monto_aprobado:
    - Tipo: int
    - Descripción: El monto final que el banco está dispuesto a prestar tras evaluar el riesgo.
- plazo_aprobado:
    - Tipo: int
    - Descripción: El número de cuotas finales aprobadas para la operación.
- motivo_rechazo:
    - Tipo: str
    - Descripción: Código técnico que identifica la política específica que fue vulnerada. Este dato es el que permite al bot dar una respuesta personalizada en el estado de error.
    - Valores posibles (Contrato de Interfaz):
        - "ERR_EDAD": El usuario tiene menos de 18 años.
        - "ERR_RENTA": La renta declarada es inferior al mínimo legal o político.
        - "ERR_ANTIGUEDAD": El usuario lleva menos de 6 meses trabajando.
        - "ERR_SCORING": El usuario no cumple con el puntaje mínimo requerido.
        - "ERR_CAPACIDAD_PAGO": La cuota supera el 30% de la renta.
        -  NULL: Si no hay error.

### 5. LOAN_PRE_APPROVED (Tarjeta de Transparencia)
Muestra la oferta final tras el éxito del LOAN_RISK_ENGINE

**INPUTS (Datos requeridos para la visualización):**
- monto_aprobado (proviene de LOAN_RISK_ENGINE)
- plazo_aprobado (proviene de LOAN_RISK_ENGINE)
- tasa_interes_mensual (proviene de LOAN_RISK_ENGINE)
- cuota_mensual (proviene de LOAN_RISK_ENGINE)
- ctc (proviene de LOAN_RISK_ENGINE)
- total_intereses (proviene de LOAN_RISK_ENGINE)
- cae (proviene de LOAN_RISK_ENGINE)
- nivel_riesgo (proviene de LOAN_RISK_ENGINE)

**OUTPUTS (Datos generados por el usuario):**
- pre_approval_status:
    - ACCEPTED: El usuario presiona "Aceptar" en la tarjeta. Avanza a LOAN_OTP_VALIDATION.
    - REJECTED: El usuario presiona "Rechazar". Transita a LOAN_CLOSED_BY_USER (Mensaje de despedida y limpieza de sesión).
- timestamp_acceptance:
    - Tipo: datetime
    - Descripción: Registro exacto del momento de la aceptación (Requerido para el contrato final).

## III. FLUJO DE FORMALIZACIÓN Y CIERRE

### 6. LOAN_OTP_VALIDATION (Validación por Email)

**INPUTS:**
- mail:
    - Tipo: str
    - Origen: Persistente. Proviene originalmente de LOAN_INIT (recuperado de la base de datos) y se arrastra a través del estado del grafo. 
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
        - Destino: LOAN_FORMALIZATION
    - FAILED:
        - Descripción: El código es incorrecto o ha expirado, pero el usuario aún tiene intentos disponibles (menos de 3).
        - Destino: Se mantiene en el mismo estado (LOAN_OTP_VALIDATION). El bot envía un mensaje de error y permite reintentar.
    - BLOCKED:
        - Descripción: El usuario alcanzó el máximo de 3 intentos fallidos.
        - Destino: Se invoca a estado transversal SECURITY_WATCHDOG.


### 7. LOAN_FORMALIZATION (Generación y Sellado)
Nodo de servicio para formalización documental.

**INPUTS (Recolección Interna):**
- monto_aprobado (proviene de LOAN_RISK_ENGINE)
- plazo_aprobado (proviene de LOAN_RISK_ENGINE)
- tasa_interes_mensual (proviene de LOAN_RISK_ENGINE)
- cuota_mensual (proviene de LOAN_RISK_ENGINE)
- rut (Persistente. Proviene originalmente de LOAN_INIT (recuperado de la base de datos) y se arrastra a través del estado del grafo.)
- nombre (Persistente. Proviene originalmente de LOAN_INIT (recuperado de la base de datos) y se arrastra a través del estado del grafo.)
- timestamp_acceptance (proviene de LOAN_PRE_APPROVED)

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

### 8. LOAN_COMPLETED (Estado Final)

**INPUTS:**
- file_contrato_path:
    - Tipo: str
    - Descripción: Ruta/URL del PDF generado con ReportLab, para que el usuario pueda descargarlo.
    - Origen: LOAN_FORMALIZATION
- hash_sha256:
    - Tipo: str
    - Descripción: Hash SHA-256 del contrato generado, para mostrar al usuario como comprobante de seguridad.
    - Origen: LOAN_FORMALIZATION
- contract_status:
    - Tipo: str
    - Descripción: Estado del contrato. Funciona como un flag para saber si el contrato se generó correctamente antes de dar las felicitariones, entregar el documento y despedirse.
    - Origen: LOAN_FORMALIZATION

**OUTPUTS:**
- status_code: SUCCESS
    - Descripción: Indica que el proceso completo del crédito terminó exitosamente.
- product_name:
    - Valor: "Crédito de Consumo"
- display_data:
    - download_url: Enlace al documento firmado.
    - main_detail: Dato clave (ej: "Monto: $5.000.000" o "Cuenta: Start").
    - security_hash: Hash SHA-256 de la transacción.
Destino: GLOBAL_END (estado transversal)

## IV. ESTADOS DE MANEJO DE ERRORES Y EXCEPCIONES

### 9. LOAN_REJECTED_POLICY (Rechazo por Políticas)

**INPUTS:**
- nombre:
    - Tipo: str
    - Descripción: Nombre del usuario.
    - Origen: LOAN_INIT
- motivo_rechazo:
    - Tipo: str
    - Origen: LOAN_RISK_ENGINE
    - Lógica: Al detectar un fallo, el motor escribe la razón: ERR_EDAD, ERR_RENTA, ERR_ANTIGUEDAD, ERR_CAPACIDAD_PAGO o ERR_SCORING.
    - USO: El estado LOAN_REJECTED_POLICY toma este string y gatilla el mensaje correspondiente.

**OUTPUTS:**
- status_code: REJECTED
- product_name: "Crédito de Consumo"
- display_data: 
    - reason: El motivo tipificado por el motor de riesgo (por ejemplo ERR_RENTA, etc).

### 10. LOAN_SECURITY_BLOCK (Bloqueo de Seguridad)

**INPUTS:**
- rut:
    - Tipo: str
    - Origen: Persistente desde LOAN_INIT
- mail:
    - Tipo: str
    - Origen: Persistente desde LOAN_INIT
- otp_attempts:
    - Tipo: int
    - Descripción: Contador de intentos fallidos (debe ser 3 al entrar en este estado).
    - Origen: LOAN_OTP_VALIDATION
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

### 11. LOAN_CLOSED_BY_USER (Cierre Voluntario)

**INPUTS:**
- ultimo_estado_alcanzado:
    - Tipo: str
    - Descripción: Identifica en qué nodo estaba el usuario antes de abandonar (ej: LOAN_PRE_APPROVED, LOAN_OTP_VALIDATION). Es vital para saber en qué etapa se "caen" los clientes.
    - Origen: Estado del Grafo (Metadata)

- monto_aprobado:
    - Tipo: int
    - Descripción: Permite analizar si el abandono fue por el costo del crédito.

- cuota_mensual:
    - Tipo: int
    - Descripción: Permite analizar si el abandono fue por el costo del crédito.

- close_reason:
    - Tipo: str
    - Descripción: Motivo capturado (Rechazo de oferta)

**OUTPUTS:**
- status_code: CLOSED_BY_USER
- product_name: "Crédito de Consumo"
- display_data: 
    - monto_aprobado (proveniente de LOAN_RISK_ENGINE)
    - cuota_mensual (proveniente de LOAN_RISK_ENGINE)

## V. INTERACCIÓN CON ESTADOS TRANSVERSALES
Este apartado define las reglas de interrupción y retorno para el Grafo de Crédito. Todos los nodos de recolección de datos (LOAN_COLLECTING_X) deben heredar este comportamiento.

1. Lógica de Interrupción (Gateways de Desvío)
Cada vez que el usuario ingresa un mensaje (Input), el sistema debe evaluar tres condiciones antes de procesar el dato para el crédito:
- A. Detección de Consulta (RAG):
    - Condición: Si el LLM detecta que el input es una pregunta técnica, de política o general (ej: "¿Qué es el CAE?", "¿Cómo firmo?").
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
- Persistencia: El estado transversal debe asegurar que los datos ya recolectados (Renta, Monto, etc.) persistan en la tabla financial_applications con status IN_PROGRESS para permitir que el usuario retome desde el Dashboard.

3. Sincronización con la Interfaz (Dashboard Sync)
- Estado Visual: Mientras el flujo esté en un Estado Transversal (ej: respondiendo una duda), el componente "Proceso Flux" de la UI debe mantener resaltado el nodo de crédito original como "En curso".
- Feedback: El LLM debe usar frases de transición para volver al carril principal: "Respondida tu duda sobre [TEMA], retomemos: me habías dicho que tu renta es de..., ¿en qué nivel de estudios te encuentras?"

4. Prioridad de Ejecución (Orden de Evaluación)
- 1ERO: Security Check (¿Es un mensaje malicioso?) -> SECURITY_WATCHDOG
- 2DO: Intent Check (¿Es una duda?) -> KNOWLEDGE_BASE_RAG
- 3ERO: Data Extraction (¿Es el dato que pedí?) -> Procesar en Nodo de Crédito.
- 4TO: Ambiguity Check (¿Es ruido?) -> AMBIGUITY_HANDLER

**NOTA:** Implementar esta lógica mediante Conditional Edges básicos en LangGraph. El estado global debe mantener un objeto metadata que rastree si el usuario está en un "desvío transversal" para garantizar que el hilo de conversación nunca pierda el objetivo final de la solicitud de crédito.
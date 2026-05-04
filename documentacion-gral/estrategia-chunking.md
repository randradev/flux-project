# CHUNKING PARA RAG: FLUX PRODUCTOS

## Crédito de Consumo (LOAN)

### ID: LOAN_001

PRODUCTO: CRÉDITO DE CONSUMO | SECCIÓN: DESCRIPCIÓN GENERAL | CONTENIDO: Producto financiero orientado a personas naturales que permite obtener financiamiento en dinero, el cual debe ser devuelto en cuotas mensuales con interés.

### ID: LOAN_002

PRODUCTO: CRÉDITO DE CONSUMO | SECCIÓN: DATOS REQUERIDOS | CONTENIDO: Para la solicitud se requiere recolectar: RUT, Nombre, Edad, Renta Líquida, Nivel de Estudios (grado académico), Antigüedad Laboral (meses), Monto solicitado y Plazo (cuotas).

### ID: LOAN_003

PRODUCTO: CRÉDITO DE CONSUMO | SECCIÓN: CONDICIONES Y LÍMITES | CONTENIDO: Requisitos mínimos: Edad mínima 18 años, Renta mínima $500.000, Antigüedad laboral mínima 6 meses. Límites: Montos entre CLP $100.000 y CLP $30.000.000 (según tramo del cliente). Plazos: De 6 a 48 cuotas.

### ID: LOAN_004

PRODUCTO: CRÉDITO DE CONSUMO | SECCIÓN: MOTOR DE RIESGO (SCORING) | CONTENIDO: El sistema aplica puntajes ponderados (0-100 pts) según nivel de estudios, antigüedad laboral, tramo de edad y renta líquida. Este puntaje determina la categoría de riesgo del cliente.

### ID: LOAN_005

PRODUCTO: CRÉDITO DE CONSUMO | SECCIÓN: MOTOR DE RIESGO (CAPACIDAD DE PAGO) | CONTENIDO: Regla de Oro: La cuota mensual no puede exceder el 15% al 25% de la renta líquida del solicitante. Si se excede este umbral, el motor arroja un error de capacidad de pago y detiene el proceso.

### ID: LOAN_006

PRODUCTO: CRÉDITO DE CONSUMO | SECCIÓN: MOTOR DE RIESGO (CÁLCULOS) | CONTENIDO: El motor calcula: 1. CTC (Costo Total del Crédito): Cuota x Plazo (redondeado al entero superior). 2. Total Intereses: CTC menos monto original. 3. CAE (Carga Anual Equivalente): Tasa anual compuesta según fórmula (1 + i)^12 - 1.

### ID: LOAN_007

PRODUCTO: CRÉDITO DE CONSUMO | SECCIÓN: PASOS POSTERIORES (OFERTA) | CONTENIDO: Tras aprobación, se genera la Tarjeta de Transparencia. La aceptación solo es válida mediante el botón "Aceptar" de la tarjeta en la interfaz; no se aceptan confirmaciones vía texto en el chat.

### ID: LOAN_008

PRODUCTO: CRÉDITO DE CONSUMO | SECCIÓN: FORMALIZACIÓN (SEGURIDAD) | CONTENIDO: La aceptación requiere validación OTP. Si falla 3 veces, el crédito se rechaza y se realiza un bloqueo de seguridad. Si es exitoso, se genera un contrato digital con hash SHA-256.

## Cuenta Corriente (ACCOUNT)

### Chunk ID: ACC_001

PRODUCTO: CUENTA CORRIENTE | SECCIÓN: DESCRIPCIÓN GENERAL | CONTENIDO: Producto bancario que permite al cliente administrar su dinero de forma integral, incluyendo la realización de depósitos, retiros y el uso de diversos medios de pago asociados para la gestión diaria.

### Chunk ID: ACC_002

PRODUCTO: CUENTA CORRIENTE | SECCIÓN: DATOS REQUERIDOS | CONTENIDO: Para la apertura de cuenta se requiere recolectar los siguientes datos del cliente: RUT, Nombre completo, Edad, Renta Líquida mensual, Nivel de Estudios (grado académico) y Antigüedad Laboral (medida en meses).

### Chunk ID: ACC_003

PRODUCTO: CUENTA CORRIENTE | SECCIÓN: CONDICIONES Y LÍMITES | CONTENIDO: Requisitos mínimos de apertura: Edad mínima de 18 años, Renta mínima mensual de $500.000 y Antigüedad laboral mínima de 6 meses. El proceso incluye una Evaluación Comercial Obligatoria para definir el perfil del cliente.

### Chunk ID: ACC_004

PRODUCTO: CUENTA CORRIENTE | SECCIÓN: CLASIFICACIÓN DE PLANES | CONTENIDO: El banco ofrece tres niveles de cuenta según el perfil: 1. Cuenta START (nivel básico). 2. Cuenta MEDIUM (nivel medio). 3. Cuenta ADVANCE (nivel alto). La asignación final depende de la renta y posibles beneficios por estudios.

### Chunk ID: ACC_005

PRODUCTO: CUENTA CORRIENTE | SECCIÓN: EVALUACIÓN (TRAMOS DE RENTA) | CONTENIDO: El tramo base se asigna según la renta líquida: Cuenta START (entre $500.000 y $1.000.000), Cuenta MEDIUM (entre $1.000.001 y $2.500.000) y Cuenta ADVANCE (superior a $2.500.001).

### Chunk ID: ACC_006

PRODUCTO: CUENTA CORRIENTE | SECCIÓN: EVALUACIÓN (UPGRADE POR ESTUDIOS) | CONTENIDO: Si el nivel de estudios es "UNIVERSITARIO COMPLETO" o superior, el cliente recibe un Upgrade automático al tramo siguiente (Ej: de START a MEDIUM o de MEDIUM a ADVANCE), generando mayor valor por su nivel académico.

### Chunk ID: ACC_007

PRODUCTO: CUENTA CORRIENTE | SECCIÓN: EVALUACIÓN (LÍNEA DE CRÉDITO) | CONTENIDO: La asignación de Línea de Crédito requiere antigüedad laboral ≥ 12 meses. Si se cumple y el plan es MEDIUM o ADVANCE, se otorga un cupo equivalente al 50% de la renta. En plan START o antigüedad < 12 meses, la línea es de $0.

### Chunk ID: ACC_008

PRODUCTO: CUENTA CORRIENTE | SECCIÓN: PASOS POSTERIORES (OFERTA) | CONTENIDO: Tras la evaluación, se muestra la Tarjeta de Transparencia con el nombre del Plan (START, MEDIUM, ADVANCE), el cupo de línea de crédito y el costo mensual ($0 en promoción MVP). La aceptación es válida solo vía botón en la tarjeta.

### Chunk ID: ACC_009

PRODUCTO: CUENTA CORRIENTE | SECCIÓN: FORMALIZACIÓN (SEGURIDAD) | CONTENIDO: La formalización requiere validar un código OTP enviado al cliente. Si falla 3 veces, el proceso se rechaza por seguridad. Tras el éxito, el bot felicita al cliente y confirma la apertura de la cuenta corriente.

## Depósito a Plazo (DAP)

### Chunk ID: DAP_001

PRODUCTO: DEPÓSITO A PLAZO | SECCIÓN: DESCRIPCIÓN GENERAL | CONTENIDO: Producto de inversión en el cual el cliente entrega una suma de dinero por un período determinado a una tasa de interés fija, obteniendo el capital más una rentabilidad garantizada al finalizar el plazo.

### Chunk ID: DAP_002

PRODUCTO: DEPÓSITO A PLAZO | SECCIÓN: DATOS REQUERIDOS | CONTENIDO: Para simular y contratar un DAP se requiere recolectar: RUT, Nombre, Edad, Monto a invertir, Plazo de inversión (en días corridos) y Tipo de moneda (CLP, UF o USD).

### Chunk ID: DAP_003

PRODUCTO: DEPÓSITO A PLAZO | SECCIÓN: CONDICIONES Y LÍMITES | CONTENIDO: Requisitos y restricciones: Edad mínima 18 años. Monto mínimo de inversión CLP $50.000. Monto máximo CLP $50.000.000 (o su equivalente en otras monedas). No se permite el retiro anticipado de los fondos.

### Chunk ID: DAP_004

PRODUCTO: DEPÓSITO A PLAZO | SECCIÓN: OPCIONES DE INVERSIÓN (PLAZOS Y MONEDAS) | CONTENIDO: Monedas disponibles: CLP, UF y USD. Plazos disponibles para la inversión: 7, 14, 30, 180 y 360 días corridos. La tasa varía según la combinación de plazo y moneda seleccionada.

### Chunk ID: DAP_005

PRODUCTO: DEPÓSITO A PLAZO | SECCIÓN: MOTOR DE CÁLCULO (ELIGIBILIDAD) | CONTENIDO: El motor de inversión realiza: 1. Conversión a CLP (si aplica) para validar límites. 2. Verificación de rango de monto ($50k a $50M CLP). 3. Verificación de mayoría de edad (18 años).

### Chunk ID: DAP_006

PRODUCTO: DEPÓSITO A PLAZO | SECCIÓN: MOTOR DE CÁLCULO (RENTABILIDAD) | CONTENIDO: La rentabilidad se calcula ajustando la tasa mensual proporcionalmente al plazo real (Tasa x Plazo/30). El retorno final es la suma del capital original más la ganancia generada por los intereses del periodo.

### Chunk ID: DAP_007

PRODUCTO: DEPÓSITO A PLAZO | SECCIÓN: PASOS POSTERIORES (OFERTA) | CONTENIDO: Tras los cálculos, se genera la Tarjeta de Transparencia con: Monto Invertido, Ganancia Estimada, Monto Final, Tasa del Periodo e Indicadores de Referencia (IPC o precio de cambio). La aceptación solo es válida vía botón "Aceptar" en la tarjeta.

### Chunk ID: DAP_008

PRODUCTO: DEPÓSITO A PLAZO | SECCIÓN: FORMALIZACIÓN (SEGURIDAD) | CONTENIDO: La inversión requiere validación mediante código OTP. Si el código falla 3 veces, el proceso se rechaza por seguridad y se bloquea la operación. Si es exitoso, se genera el comprobante/contrato de la inversión.

## Información General y FAQ

### Chunk ID: GEN_001

PRODUCTO: GENERAL | SECCIÓN: ¿QUÉ ES FLUX? | CONTENIDO: FLUX es la nueva banca digital chilena diseñada para ser rápida, transparente y 100% móvil. Nuestra misión es eliminar la burocracia bancaria tradicional usando inteligencia artificial para entregarte respuestas y productos financieros en tiempo récord.

### Chunk ID: GEN_002

PRODUCTO: GENERAL | SECCIÓN: PORTAFOLIO DE PRODUCTOS | CONTENIDO: Actualmente, FLUX ofrece tres productos principales: 1. Crédito de Consumo (financiamiento flexible). 2. Cuenta Corriente (gestión diaria con planes START, MEDIUM y ADVANCE). 3. Depósito a Plazo o DAP (inversión con rentabilidad garantizada). Estamos trabajando para sumar seguros e inversiones pronto.

### Chunk ID: GEN_003

PRODUCTO: GENERAL | SECCIÓN: SEGURIDAD Y PRIVACIDAD | CONTENIDO: En FLUX nos tomamos en serio tu seguridad. Utilizamos encriptación de grado bancario, validación de identidad mediante códigos OTP (One Time Password) y contratos digitales con firma electrónica y hash SHA-256 para garantizar que tus operaciones sean privadas e inalterables.

### Chunk ID: GEN_004

PRODUCTO: GENERAL | SECCIÓN: CONTACTO Y SOPORTE | CONTENIDO: Si necesitas ayuda humana, nuestro equipo de soporte está disponible de lunes a viernes de 09:00 a 18:00 hrs. Puedes escribirnos a ayuda@flux.cl o llamarnos al 600 300 4000. También puedes contactarnos por nuestras redes sociales oficiales.

### Chunk ID: GEN_005

PRODUCTO: GENERAL | SECCIÓN: COSTOS Y COMISIONES | CONTENIDO: FLUX se caracteriza por la transparencia. No tenemos "letra chica". Las comisiones de mantención de nuestras cuentas están actualmente en promoción de costo $0 para el periodo MVP, y siempre verás el Costo Total del Crédito (CTC) y la CAE antes de contratar cualquier financiamiento.

### Chunk ID: GEN_006

PRODUCTO: GENERAL | SECCIÓN: REQUISITOS GENERALES | CONTENIDO: Para ser cliente FLUX debes ser persona natural, mayor de 18 años, contar con una cédula de identidad chilena vigente y aprobar nuestra evaluación comercial. No abrimos cuentas a personas jurídicas o empresas por el momento.
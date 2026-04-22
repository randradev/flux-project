# MODELO DE DATOS DEFINITIVO — FLUX
> Versión: 1.0 · Base de datos: PostgreSQL (Supabase) · Normalización: 3FN

---

## PRINCIPIOS DE DISEÑO

Este modelo se rige por los siguientes principios:

- **3FN estricta:** Toda dependencia funcional no trivial entre atributos no clave ha sido eliminada mediante la creación de tablas de catálogo. Los únicos datos calculados que se persisten son aquellos que constituyen un **registro de auditoría** (snapshot en el momento del cálculo), cuya alteración futura en el catálogo no debe invalidar operaciones históricas.
- **Semáforos de sincronía (Regla de Oro #3):** Los campos `current_node_id`, `node_status`, `engine_status` y `document_status` de `financial_applications` son el único canal de comunicación entre el Orquestador (Dev 1), el Frontend (Dev 2) y los Módulos de Seguridad (Dev 3). Su diseño es deliberadamente explícito.
- **Adaptabilidad de módulos:** Las tablas `account_details` y `dap_details` incluyen una columna `metadata JSONB` para acomodar atributos no anticipados sin migraciones destructivas durante la evolución del producto.
- **Integridad referencial completa:** Todo valor con dominio finito y semántica de negocio (niveles de estudio, niveles de riesgo, monedas, plazos) es una FK a una tabla de catálogo, nunca un `VARCHAR` libre.
- **Tipos de dato precisos:** Se usan `NUMERIC(p,s)` para valores monetarios y tasas, `TIMESTAMPTZ` para todas las marcas de tiempo, y `UUID` para las entidades principales.

---

## CAPA 0: CATÁLOGOS (Tablas de Referencia)

Estas tablas son de solo lectura en tiempo de ejecución. Sus valores se insertan en la migración inicial (`seed`) y no cambian salvo por decisión de negocio planificada.

---

### `user_statuses`
Catálogo de estados posibles de un usuario. El campo clave es `BLOCKED_SECURITY`, que el `SECURITY_WATCHDOG` (Dev 3) escribe para que el Orquestador (Dev 1) ni siquiera inicie el grafo.

| Atributo      | Tipo            | Restricciones         | Descripción                                      |
|---------------|-----------------|-----------------------|--------------------------------------------------|
| `id`          | `SMALLINT`      | PK, IDENTITY          | Identificador numérico del catálogo.             |
| `code`        | `VARCHAR(30)`   | UNIQUE, NOT NULL      | Código técnico. Valores: `ACTIVE`, `BLOCKED_SECURITY`, `PROSPECT`. |
| `name`        | `VARCHAR(100)`  | NOT NULL              | Nombre legible para el panel de administración.  |
| `description` | `TEXT`          |                       | Descripción del estado y su impacto en el sistema. |

---

### `user_categories`
Catálogo del tramo o perfil del usuario (`START`, `MEDIUM`, `ADVANCE`). Es reutilizado por `account_details` como FK para representar el plan de cuenta asignado, dado que la semántica es idéntica.

| Atributo      | Tipo           | Restricciones    | Descripción                                    |
|---------------|----------------|------------------|------------------------------------------------|
| `id`          | `SMALLINT`     | PK, IDENTITY     | Identificador numérico del catálogo.           |
| `code`        | `VARCHAR(20)`  | UNIQUE, NOT NULL | Valores: `START`, `MEDIUM`, `ADVANCE`.         |
| `name`        | `VARCHAR(100)` | NOT NULL         | Nombre del tramo/plan.                         |
| `description` | `TEXT`         |                  | Descripción de los beneficios del tramo.       |

---

### `product_types`
Catálogo de los productos financieros ofrecidos por FLUX. `is_enabled` permite activar/desactivar un producto sin modificar código ni datos históricos.

| Atributo     | Tipo           | Restricciones    | Descripción                                           |
|--------------|----------------|------------------|-------------------------------------------------------|
| `id`         | `SMALLINT`     | PK, IDENTITY     | Identificador numérico del catálogo.                  |
| `code`       | `VARCHAR(20)`  | UNIQUE, NOT NULL | Valores: `LOAN`, `ACCOUNT`, `DAP`.                    |
| `name`       | `VARCHAR(100)` | NOT NULL         | Nombre comercial del producto.                        |
| `is_enabled` | `BOOLEAN`      | NOT NULL, DEFAULT TRUE | Interruptor de habilitación para el MVP o mantenimiento. |

---

### `application_statuses`
Catálogo de estados del negocio de una solicitud. Es el campo que lee el Frontend (Dev 2) para renderizar la pantalla final correcta (aprobación, rechazo, etc.).

| Atributo      | Tipo           | Restricciones    | Descripción                                                          |
|---------------|----------------|------------------|----------------------------------------------------------------------|
| `id`          | `SMALLINT`     | PK, IDENTITY     | Identificador numérico del catálogo.                                 |
| `code`        | `VARCHAR(30)`  | UNIQUE, NOT NULL | Valores: `IN_PROGRESS`, `PRE_APPROVED`, `REJECTED`, `COMPLETED`, `CLOSED_BY_USER`. |
| `name`        | `VARCHAR(100)` | NOT NULL         | Nombre legible.                                                      |
| `description` | `TEXT`         |                  | Descripción del impacto en el flujo del usuario.                     |

---

### `education_levels`
Catálogo de niveles académicos. Centraliza las reglas de ponderación del motor de crédito y la lógica de upgrade de cuenta corriente. Si las ponderaciones del scoring cambian, solo se actualiza esta tabla.

| Atributo             | Tipo           | Restricciones    | Descripción                                                                               |
|----------------------|----------------|------------------|-------------------------------------------------------------------------------------------|
| `id`                 | `SMALLINT`     | PK, IDENTITY     | Identificador numérico del catálogo.                                                      |
| `code`               | `VARCHAR(20)`  | UNIQUE, NOT NULL | Valores: `POSTGRADO`, `UNIVERSITARIO`, `TECNICO`, `MEDIA`.                                |
| `name`               | `VARCHAR(100)` | NOT NULL         | Nombre legible del nivel.                                                                 |
| `credit_score_points`| `SMALLINT`     | NOT NULL         | Puntos que aporta al scoring de crédito: `POSTGRADO`=20, `UNIVERSITARIO`=15, `TECNICO`=10, `MEDIA`=5. |
| `grants_account_upgrade` | `BOOLEAN`  | NOT NULL, DEFAULT FALSE | `TRUE` si este nivel activa el beneficio de upgrade de categoría en cuenta corriente (`UNIVERSITARIO`, `POSTGRADO`). |

---

### `risk_levels`
Catálogo de niveles de riesgo crediticio. Almacena los umbrales de scoring y la tasa mensual asociada. Si el negocio ajusta tasas, se actualiza aquí sin tocar el código del motor.

| Atributo       | Tipo           | Restricciones    | Descripción                                                                  |
|----------------|----------------|------------------|------------------------------------------------------------------------------|
| `id`           | `SMALLINT`     | PK, IDENTITY     | Identificador numérico del catálogo.                                         |
| `code`         | `VARCHAR(10)`  | UNIQUE, NOT NULL | Valores: `BAJO`, `MEDIO`, `ALTO`.                                            |
| `name`         | `VARCHAR(50)`  | NOT NULL         | Nombre legible del nivel de riesgo.                                          |
| `min_score`    | `SMALLINT`     | NOT NULL         | Puntaje mínimo para caer en este nivel: `ALTO`=0, `MEDIO`=50, `BAJO`=81.    |
| `max_score`    | `SMALLINT`     | NOT NULL         | Puntaje máximo para caer en este nivel: `ALTO`=49, `MEDIO`=80, `BAJO`=100.  |
| `monthly_rate` | `NUMERIC(6,4)` | NOT NULL         | Tasa mensual asignada: `BAJO`=0.0120, `MEDIO`=0.0200, `ALTO`=0.0350.        |

---

### `rejection_reason_codes`
Catálogo de causales de rechazo de cualquier producto. La columna `code` es el contrato de interfaz entre el motor de cálculo (Dev 1) y la lógica de mensajería del bot. Permite que el bot entregue una respuesta personalizada y empática según el motivo técnico.

| Atributo      | Tipo           | Restricciones    | Descripción                                                              |
|---------------|----------------|------------------|--------------------------------------------------------------------------|
| `id`          | `SMALLINT`     | PK, IDENTITY     | Identificador numérico del catálogo.                                     |
| `code`        | `VARCHAR(30)`  | UNIQUE, NOT NULL | Contrato de interfaz: `ERR_EDAD`, `ERR_RENTA`, `ERR_ANTIGUEDAD`, `ERR_SCORING`, `ERR_CAPACIDAD_PAGO`, `ERR_MONTO`. |
| `description` | `TEXT`         | NOT NULL         | Explicación de la política vulnerada, para uso en mensajes del bot.      |

> **Nota de diseño:** `product_type_id` fue omitido deliberadamente. El contexto del producto es implícito en la tabla de detalle que referencia esta causal (ej.: `ERR_CAPACIDAD_PAGO` solo puede aparecer en `loan_details`). Añadir la FK aquí sería redundante y no aportaría integridad adicional.

---

### `currencies`
Catálogo de monedas disponibles para el DAP. El campo `applies_ipc_adjustment` codifica directamente la regla de negocio que determina si se suma el IPC a la tasa.

| Atributo                | Tipo           | Restricciones         | Descripción                                              |
|-------------------------|----------------|-----------------------|----------------------------------------------------------|
| `id`                    | `SMALLINT`     | PK, IDENTITY          | Identificador numérico del catálogo.                     |
| `code`                  | `VARCHAR(5)`   | UNIQUE, NOT NULL      | Valores: `CLP`, `UF`, `USD`.                             |
| `name`                  | `VARCHAR(50)`  | NOT NULL              | Nombre de la moneda.                                     |
| `applies_ipc_adjustment`| `BOOLEAN`      | NOT NULL, DEFAULT FALSE | `TRUE` solo para `CLP`. Indica si se suma la corrección monetaria (IPC) a la tasa. |

---

### `dap_terms`
Catálogo de plazos disponibles para el DAP. Normaliza la `step function` del premio por plazo: el motor de cálculo solo necesita buscar el `bonus_rate` para el plazo elegido, sin lógica condicional hardcoded.

| Atributo     | Tipo           | Restricciones    | Descripción                                                                                 |
|--------------|----------------|------------------|---------------------------------------------------------------------------------------------|
| `id`         | `SMALLINT`     | PK, IDENTITY     | Identificador numérico del catálogo.                                                        |
| `days`       | `SMALLINT`     | UNIQUE, NOT NULL | Días del plazo. Valores: `7`, `14`, `30`, `180`, `360`.                                     |
| `label`      | `VARCHAR(50)`  | NOT NULL         | Etiqueta para el Frontend: "7 días", "30 días", etc.                                        |
| `bonus_rate` | `NUMERIC(6,4)` | NOT NULL         | Premio por plazo a sumar a la tasa base: `7d`=0.0000, `14d`=0.0000, `30d`=0.0005, `180d`=0.0030, `360d`=0.0060. |

---

### `document_types`
Catálogo de tipos de contrato generables. Establece la relación entre el tipo de documento y el producto al que pertenece.

| Atributo         | Tipo           | Restricciones    | Descripción                                                          |
|------------------|----------------|------------------|----------------------------------------------------------------------|
| `id`             | `SMALLINT`     | PK, IDENTITY     | Identificador numérico del catálogo.                                 |
| `code`           | `VARCHAR(40)`  | UNIQUE, NOT NULL | Valores: `CONTRATO_CREDITO`, `CONTRATO_CUENTA`, `CONTRATO_DAP`.      |
| `name`           | `VARCHAR(100)` | NOT NULL         | Nombre legible del tipo de documento.                                |
| `product_type_id`| `SMALLINT`     | FK → `product_types`, NOT NULL | Producto al que pertenece este tipo de documento.   |

---

### `economic_indicators`
Catálogo de los indicadores económicos externos que el sistema consulta y cachea. Desacopla el código de los strings libres (`"UF"`, `"IPC"`) que existían en la versión anterior.

| Atributo      | Tipo           | Restricciones    | Descripción                                             |
|---------------|----------------|------------------|---------------------------------------------------------|
| `id`          | `SMALLINT`     | PK, IDENTITY     | Identificador numérico del catálogo.                    |
| `code`        | `VARCHAR(10)`  | UNIQUE, NOT NULL | Valores: `UF`, `USD`, `IPC`.                            |
| `name`        | `VARCHAR(100)` | NOT NULL         | Nombre del indicador.                                   |
| `description` | `TEXT`         |                  | Descripción del indicador y su fuente de datos externa. |

---

## CAPA 1: IDENTIDAD Y PERFILAMIENTO

### `users`
Entidad raíz del sistema. Representa a la persona que interactúa con FLUX. El campo `status_id` actúa como el "Interruptor de Seguridad": si su valor es `BLOCKED_SECURITY`, el Orquestador (Dev 1) no inicia ningún grafo de producto.

| Atributo      | Tipo           | Restricciones                          | Descripción                                                        |
|---------------|----------------|----------------------------------------|--------------------------------------------------------------------|
| `id`          | `UUID`         | PK, DEFAULT `gen_random_uuid()`        | Identificador único del usuario.                                   |
| `rut`         | `VARCHAR(12)`  | UNIQUE, NOT NULL                       | RUT chileno (sin puntos, con guion: `12345678-9`).                 |
| `full_name`   | `VARCHAR(200)` | NOT NULL                               | Nombre completo del usuario.                                       |
| `email`       | `VARCHAR(255)` | UNIQUE, NOT NULL                       | Correo electrónico. Medio de envío de OTP.                         |
| `phone`       | `VARCHAR(20)`  |                                        | Teléfono de contacto.                                              |
| `birth_date`  | `DATE`         | NOT NULL                               | Fecha de nacimiento. La edad se calcula dinámicamente desde este campo en cada proceso, nunca se almacena. |
| `status_id`   | `SMALLINT`     | FK → `user_statuses`, NOT NULL         | Estado del usuario. El Security Watchdog escribe aquí para bloqueos. |
| `category_id` | `SMALLINT`     | FK → `user_categories`, NULL           | Tramo del usuario. Puede ser NULL hasta que se complete el primer perfilamiento. |
| `created_at`  | `TIMESTAMPTZ`  | NOT NULL, DEFAULT `NOW()`              | Marca de creación del registro.                                    |
| `updated_at`  | `TIMESTAMPTZ`  | NOT NULL, DEFAULT `NOW()`              | Actualizado automáticamente por un trigger en cada modificación.   |

> **Nota de integridad:** La edad **nunca se almacena** como columna. Se calcula en tiempo de ejecución a partir de `birth_date`. Esto elimina la posibilidad de que un registro tenga una edad incorrecta con el paso del tiempo.

---

## CAPA 2: MOTOR CONVERSACIONAL

### `conversations`
Representa el hilo de conversación de LangGraph. El campo `state_snapshot` es la "Caja Negra" que permite al `RESUME_HANDLER` retomar una sesión exactamente donde se abandonó. El campo `current_node` es el "Marcador de Libro" para el motor de IA.

| Atributo         | Tipo           | Restricciones                         | Descripción                                                              |
|------------------|----------------|---------------------------------------|--------------------------------------------------------------------------|
| `id`             | `UUID`         | PK, DEFAULT `gen_random_uuid()`       | Identificador único del hilo conversacional (equivale al `thread_id` de LangGraph). |
| `user_id`        | `UUID`         | FK → `users`, NOT NULL                | Usuario propietario de este hilo.                                        |
| `product_type_id`| `SMALLINT`     | FK → `product_types`, NULL            | Producto al que se enfoca esta conversación. NULL hasta que el `INTENT_ROUTER` lo detecte. |
| `current_node`   | `VARCHAR(100)` |                                       | Nombre del nodo activo en LangGraph. Usado por el Orquestador para reanudar el grafo. |
| `state_snapshot` | `JSONB`        |                                       | Checkpoint completo del `StateSchema`. Garantiza continuidad entre sesiones. |
| `is_active`      | `BOOLEAN`      | NOT NULL, DEFAULT `TRUE`              | `FALSE` cuando el nodo `GLOBAL_END` cierra la sesión formalmente.        |
| `metadata`       | `JSONB`        |                                       | Datos técnicos de sesión: IP, dispositivo, versión del bot, user-agent.  |
| `created_at`     | `TIMESTAMPTZ`  | NOT NULL, DEFAULT `NOW()`             | Marca de inicio de la conversación.                                      |
| `updated_at`     | `TIMESTAMPTZ`  | NOT NULL, DEFAULT `NOW()`             | Actualizado en cada intercambio de mensajes.                             |

---

### `messages`
Registro inmutable de cada mensaje del hilo. El campo `node_at_time` es esencial para el debugging del grafo y el análisis de embudo.

| Atributo         | Tipo          | Restricciones                         | Descripción                                                               |
|------------------|---------------|---------------------------------------|---------------------------------------------------------------------------|
| `id`             | `BIGSERIAL`   | PK                                    | Identificador autoincremental del mensaje.                                |
| `conversation_id`| `UUID`        | FK → `conversations`, NOT NULL        | Hilo al que pertenece este mensaje.                                       |
| `role`           | `VARCHAR(20)` | NOT NULL, CHECK (`'user'`, `'assistant'`, `'system'`) | Rol del emisor del mensaje.                              |
| `content`        | `TEXT`        | NOT NULL                              | Contenido íntegro del mensaje.                                            |
| `extracted_data` | `JSONB`       |                                       | Entidades estructuradas que el `Entity Extractor` extrajo de este mensaje (ej.: `{"renta": 1500000}`). |
| `node_at_time`   | `VARCHAR(100)`|                                       | Nombre del nodo de LangGraph activo cuando se generó este mensaje. Para auditoría y debugging. |
| `created_at`     | `TIMESTAMPTZ` | NOT NULL, DEFAULT `NOW()`             | Marca de creación. Determina el orden cronológico del hilo.               |

---

## CAPA 3: NÚCLEO DE NEGOCIO (Solicitudes)

### `financial_applications`
La entidad central del sistema. Es el **canal de comunicación entre los tres desarrolladores** (Regla de Oro #3). Conecta la intención conversacional con la ejecución del módulo financiero y con la interfaz visual.

| Atributo          | Tipo           | Restricciones                          | Descripción                                                                                   |
|-------------------|----------------|----------------------------------------|-----------------------------------------------------------------------------------------------|
| `id`              | `UUID`         | PK, DEFAULT `gen_random_uuid()`        | Identificador único de la solicitud.                                                          |
| `user_id`         | `UUID`         | FK → `users`, NOT NULL                 | Usuario que realizó la solicitud.                                                             |
| `product_type_id` | `SMALLINT`     | FK → `product_types`, NOT NULL         | Producto solicitado: Crédito, Cuenta o DAP.                                                   |
| `conversation_id` | `UUID`         | FK → `conversations`, NOT NULL, UNIQUE | La conversación en la que se gestó esta solicitud. Una conversación genera como máximo una solicitud activa. |
| `status_id`       | `SMALLINT`     | FK → `application_statuses`, NOT NULL, DEFAULT `IN_PROGRESS` | **Estado de Negocio.** El Frontend lo lee para mostrar la pantalla final (aprobación, rechazo, etc.). |
| `current_node_id` | `VARCHAR(100)` |                                        | **GPS Visual.** ID exacto del nodo de LangGraph activo (ej.: `LOAN_RISK_ENGINE`). El Dev 1 escribe aquí; el Dev 2 lo lee para mover el Progress Monitor. |
| `node_status`     | `VARCHAR(20)`  | CHECK (`'IN_PROGRESS'`, `'SUCCESS'`, `'FAILED'`) | **Semáforo Técnico.** El Dev 1 lo pasa a `IN_PROGRESS` al iniciar una tarea pesada y a `SUCCESS`/`FAILED` al terminar. El Dev 2 gatilla Skeletons si es `IN_PROGRESS`. |
| `engine_status`   | `VARCHAR(20)`  | DEFAULT `'PENDING'`, CHECK (`'PENDING'`, `'COMPLETED'`, `'FAILED'`, `'NOT_APPLICABLE'`) | **Semáforo del Motor de Cálculo.** El Dev 1 (Orquestador) lo pone en `PENDING` y el módulo de cálculo (Dev 1 Backend) lo pasa a `COMPLETED`. La señal para que el grafo avance al nodo de oferta. `NOT_APPLICABLE` para flujos que no requieren motor (ej.: inicio de DAP). |
| `document_status` | `VARCHAR(20)`  | DEFAULT `'PENDING'`, CHECK (`'PENDING'`, `'GENERATED'`) | **Semáforo de Documentos.** El Dev 3 lo cambia a `GENERATED` cuando el PDF está en el Storage. Solo entonces el Dev 2 muestra el botón de descarga. |
| `metadata`        | `JSONB`        |                                        | Caja de herramientas para datos no planificados (ej.: IP de firma, flags temporales).         |
| `created_at`      | `TIMESTAMPTZ`  | NOT NULL, DEFAULT `NOW()`              | Marca de creación de la solicitud.                                                            |
| `updated_at`      | `TIMESTAMPTZ`  | NOT NULL, DEFAULT `NOW()`              | Actualizado automáticamente por un trigger en cada modificación.                              |

> **Nota de diseño — `node_status`, `engine_status`, `document_status`:** Estos tres campos son de naturaleza operacional (semáforos entre desarrolladores), no catálogos de negocio. Sus valores posibles están contractualmente documentados aquí y se refuerzan mediante `CHECK` constraints en la base de datos. Crear tablas de catálogo separadas para ellos añadiría joins innecesarios sin beneficio de integridad adicional, dado que sus valores son estables y forman parte del contrato de interfaz del equipo.

---

## CAPA 4: DETALLES MODULARES (Monolito Modular)

Cada tabla de esta capa tiene como PK la misma `application_id` que referencia a `financial_applications`. Esto implementa el patrón de **tabla de extensión** (1-a-1 obligatorio), garantizando que una solicitud tenga exactamente un conjunto de detalles correspondiente a su tipo de producto. No puede existir un `loan_details` sin su `financial_application`.

---

### `loan_details`
Almacena todos los inputs, outputs e intermedios del motor de crédito. Los valores calculados se persisten como snapshot de auditoría: si las tasas del catálogo `risk_levels` cambian en el futuro, los contratos históricos siguen siendo correctos.

| Atributo                   | Tipo            | Restricciones                      | Descripción                                                                                  |
|----------------------------|-----------------|------------------------------------|----------------------------------------------------------------------------------------------|
| `application_id`           | `UUID`          | PK, FK → `financial_applications`  | Clave primaria compartida con la solicitud madre.                                            |
| **INPUTS DEL USUARIO**     |                 |                                    |                                                                                              |
| `requested_amount`         | `NUMERIC(14,2)` | NOT NULL, CHECK (100000 a 30000000) | Monto solicitado por el usuario en CLP.                                                      |
| `term_months`              | `SMALLINT`      | NOT NULL, CHECK (6 a 48)           | Plazo solicitado en meses.                                                                   |
| `monthly_income`           | `NUMERIC(14,2)` | NOT NULL                           | Renta líquida declarada por el usuario en CLP.                                               |
| `employment_seniority_months` | `SMALLINT`   | NOT NULL                           | Antigüedad laboral declarada en meses.                                                       |
| `education_level_id`       | `SMALLINT`      | FK → `education_levels`, NOT NULL  | Nivel de estudios declarado. FK normaliza el dominio y sus ponderaciones.                    |
| **OUTPUTS DEL MOTOR DE RIESGO** |           |                                    |                                                                                              |
| `risk_score`               | `NUMERIC(5,2)`  | CHECK (0 a 100)                    | Puntaje total de scoring (suma de las 4 ponderaciones). NULL hasta que corra el motor.       |
| `risk_level_id`            | `SMALLINT`      | FK → `risk_levels`                 | Nivel de riesgo resultante (BAJO/MEDIO/ALTO). NULL hasta evaluación.                        |
| `applied_monthly_rate`     | `NUMERIC(6,4)`  |                                    | **Snapshot de auditoría.** Tasa mensual aplicada en el momento del cálculo.                  |
| `monthly_payment`          | `NUMERIC(14,2)` |                                    | Cuota mensual calculada por Amortización Francesa, redondeada al entero superior.            |
| `max_allowed_payment`      | `NUMERIC(14,2)` |                                    | Límite de capacidad de pago: `monthly_income * 0.30`. Persistido para auditoría del cálculo. |
| `payment_capacity_valid`   | `BOOLEAN`       |                                    | `TRUE` si `monthly_payment ≤ max_allowed_payment`.                                           |
| `total_credit_cost`        | `NUMERIC(14,2)` |                                    | Costo Total del Crédito (CTC): `monthly_payment × term_months`, redondeado al entero superior. |
| `total_interest`           | `NUMERIC(14,2)` |                                    | Intereses totales: `total_credit_cost − requested_amount`.                                   |
| `cae`                      | `NUMERIC(8,6)`  |                                    | Carga Anual Equivalente en formato decimal: `(1 + i_mensual)^12 − 1`.                        |
| `approved_amount`          | `NUMERIC(14,2)` |                                    | Monto final aprobado por el banco. NULL si fue rechazado.                                    |
| `approved_term_months`     | `SMALLINT`      |                                    | Plazo final aprobado. NULL si fue rechazado.                                                 |
| `amortization_schedule`    | `JSONB`         |                                    | Tabla de amortización completa (arreglo de objetos por cuota: número, capital, interés, saldo). Almacenada como JSONB porque es un bloque estructurado que siempre se consulta completo y nunca por fila individual. |
| **RESULTADO Y AUDITORÍA**  |                 |                                    |                                                                                              |
| `rejection_reason_id`      | `SMALLINT`      | FK → `rejection_reason_codes`      | Causal de rechazo. NULL si fue aprobado. Permite al bot entregar un mensaje personalizado.   |
| `calculated_at`            | `TIMESTAMPTZ`   |                                    | Marca exacta del cálculo. Permite validar la "frescura" de la oferta.                        |
| `calculation_log`          | `TEXT`          |                                    | Log técnico del motor. Si el motor falla, el desarrollador escribe aquí el error para diagnóstico desde el panel. |

---

### `account_details`
Almacena los datos del proceso de evaluación comercial de la cuenta corriente. El modelo de dos campos (`base_plan_id` / `final_plan_id`) registra de forma transparente si se aplicó un upgrade por estudios. La columna `metadata` absorbe futuras extensiones del producto sin migraciones destructivas.

| Atributo                    | Tipo            | Restricciones                      | Descripción                                                                             |
|-----------------------------|-----------------|------------------------------------|-----------------------------------------------------------------------------------------|
| `application_id`            | `UUID`          | PK, FK → `financial_applications`  | Clave primaria compartida con la solicitud madre.                                       |
| **INPUTS DEL USUARIO**      |                 |                                    |                                                                                         |
| `monthly_income`            | `NUMERIC(14,2)` | NOT NULL                           | Renta líquida declarada en CLP.                                                         |
| `employment_seniority_months` | `SMALLINT`    | NOT NULL                           | Antigüedad laboral declarada en meses.                                                  |
| `education_level_id`        | `SMALLINT`      | FK → `education_levels`, NOT NULL  | Nivel de estudios. Determina si aplica el upgrade de plan.                              |
| **OUTPUTS DE LA EVALUACIÓN COMERCIAL** |      |                                    |                                                                                         |
| `base_plan_id`              | `SMALLINT`      | FK → `user_categories`             | Plan asignado exclusivamente por renta (antes de aplicar upgrade). Trazabilidad del cálculo. |
| `has_education_upgrade`     | `BOOLEAN`       | NOT NULL, DEFAULT FALSE            | `TRUE` si el nivel de estudios activó el salto de categoría.                            |
| `final_plan_id`             | `SMALLINT`      | FK → `user_categories`             | Plan final asignado al cliente (puede ser igual o superior al `base_plan_id`).          |
| `credit_line_amount`        | `NUMERIC(14,2)` | NOT NULL, DEFAULT 0                | Línea de crédito aprobada. `$0` si el plan final es `START` o la antigüedad es < 12 meses. Si es `MEDIUM` o `ADVANCE` con ≥ 12 meses: `monthly_income × 0.50`. |
| **RESULTADO Y AUDITORÍA**   |                 |                                    |                                                                                         |
| `rejection_reason_id`       | `SMALLINT`      | FK → `rejection_reason_codes`      | Causal de rechazo (ej.: `ERR_EDAD`, `ERR_RENTA`). NULL si fue aprobado.                 |
| `evaluated_at`              | `TIMESTAMPTZ`   |                                    | Marca exacta de la evaluación comercial.                                                |
| `evaluation_log`            | `TEXT`          |                                    | Log técnico del módulo de cuenta. Para diagnóstico de errores desde el panel.           |
| `metadata`                  | `JSONB`         |                                    | **Campo de extensibilidad.** Absorbe atributos futuros del producto sin migraciones destructivas. |

---

### `dap_details`
Almacena los datos del motor de cálculo de inversión del Depósito a Plazo. Los campos de tasa (`base_rate`, `bonus_rate`, `ipc_adjustment`) son **snapshots de auditoría**: aunque los valores del catálogo (`dap_terms.bonus_rate`, el IPC del día) cambien en el futuro, el registro histórico preserva exactamente qué números se usaron para calcular el contrato del cliente.

| Atributo                  | Tipo            | Restricciones                      | Descripción                                                                                      |
|---------------------------|-----------------|------------------------------------|--------------------------------------------------------------------------------------------------|
| `application_id`          | `UUID`          | PK, FK → `financial_applications`  | Clave primaria compartida con la solicitud madre.                                                |
| **INPUTS DEL USUARIO**    |                 |                                    |                                                                                                  |
| `investment_amount`       | `NUMERIC(14,2)` | NOT NULL                           | Monto a invertir en la moneda original declarada.                                                |
| `investment_amount_clp`   | `NUMERIC(14,2)` | NOT NULL                           | Equivalente en CLP del monto invertido, calculado al momento de la evaluación para validar los límites ($50.000–$50.000.000). Snapshot de auditoría. |
| `currency_id`             | `SMALLINT`      | FK → `currencies`, NOT NULL        | Moneda elegida por el usuario.                                                                   |
| `term_id`                 | `SMALLINT`      | FK → `dap_terms`, NOT NULL         | Plazo elegido por el usuario (normalizado en catálogo).                                          |
| **OUTPUTS DEL MOTOR DE CÁLCULO** |          |                                    |                                                                                                  |
| `base_rate`               | `NUMERIC(6,4)`  | NOT NULL                           | **Snapshot.** Tasa base aplicada (valor vigente al momento del cálculo, típicamente 0.0020).     |
| `bonus_rate`              | `NUMERIC(6,4)`  | NOT NULL                           | **Snapshot.** Premio por plazo aplicado. Copiado desde `dap_terms.bonus_rate` para preservar la auditoría. |
| `ipc_adjustment`          | `NUMERIC(6,4)`  | NOT NULL, DEFAULT 0                | **Snapshot.** Corrección monetaria aplicada. Es `0` si la moneda no es CLP.                     |
| `ipc_value_used`          | `NUMERIC(8,4)`  |                                    | Valor exacto del IPC consultado a la API externa. NULL si no aplica.                             |
| `total_monthly_rate`      | `NUMERIC(8,6)`  | NOT NULL                           | Tasa total mensual: `base_rate + bonus_rate + ipc_adjustment`.                                   |
| `period_rate`             | `NUMERIC(8,6)`  | NOT NULL                           | Tasa proporcional al plazo real: `total_monthly_rate × (days / 30)`.                            |
| `index_value_at_start`    | `NUMERIC(14,6)` |                                    | Valor de la UF o USD al momento de la inversión. NULL si la moneda es CLP.                       |
| `projected_gain`          | `NUMERIC(14,2)` | NOT NULL                           | Ganancia estimada: `investment_amount × period_rate`.                                            |
| `final_amount`            | `NUMERIC(14,2)` | NOT NULL                           | Retorno final: `investment_amount + projected_gain`.                                             |
| **RESULTADO Y AUDITORÍA** |                 |                                    |                                                                                                  |
| `rejection_reason_id`     | `SMALLINT`      | FK → `rejection_reason_codes`      | Causal de rechazo (ej.: `ERR_EDAD`, `ERR_MONTO`). NULL si fue aprobado.                          |
| `calculated_at`           | `TIMESTAMPTZ`   |                                    | Marca exacta del cálculo.                                                                        |
| `calculation_log`         | `TEXT`          |                                    | Log técnico del motor. Para diagnóstico de errores.                                              |
| `metadata`                | `JSONB`         |                                    | **Campo de extensibilidad.** Absorbe atributos futuros sin migraciones destructivas.             |

---

## CAPA 5: SEGURIDAD, INTEGRIDAD Y AUDITORÍA

### `security_otp`
Gestiona el ciclo de vida de los códigos de verificación. El código nunca se almacena en texto plano; solo su hash SHA-256. El campo `last_failed_hash` permite análisis de patrones de fraude sin exponer información sensible.

| Atributo             | Tipo           | Restricciones                          | Descripción                                                                           |
|----------------------|----------------|----------------------------------------|---------------------------------------------------------------------------------------|
| `id`                 | `UUID`         | PK, DEFAULT `gen_random_uuid()`        | Identificador único del OTP.                                                          |
| `application_id`     | `UUID`         | FK → `financial_applications`, NOT NULL, UNIQUE | Una solicitud tiene como máximo un OTP activo en cada momento.           |
| `otp_hash`           | `VARCHAR(64)`  | NOT NULL                               | Hash SHA-256 del código OTP de 6 dígitos. Nunca se almacena el código en texto plano. |
| `attempts`           | `SMALLINT`     | NOT NULL, DEFAULT 0, CHECK (0 a 3)     | **Contador de Vida.** El Dev 3 lo incrementa en cada fallo. Al llegar a 3, el orquestador activa el `SECURITY_WATCHDOG`. |
| `last_failed_hash`   | `VARCHAR(64)`  |                                        | Hash del último intento fallido. Para análisis de patrones de fraude (fuerza bruta). NULL hasta el primer fallo. |
| `is_verified`        | `BOOLEAN`      | NOT NULL, DEFAULT FALSE                | `TRUE` solo si el código fue ingresado correctamente y dentro del tiempo de expiración. |
| `expires_at`         | `TIMESTAMPTZ`  | NOT NULL                               | Ventana de validez del código. El motor valida que `NOW() < expires_at`.              |
| `created_at`         | `TIMESTAMPTZ`  | NOT NULL, DEFAULT `NOW()`              | Marca de creación del OTP.                                                            |

> **Nota de 3FN:** El campo `reference_flow` del modelo anterior fue **eliminado**. Era un atributo transitivamente dependiente: `otp.application_id` → `financial_applications.product_type_id` ya proporciona el tipo de producto. La validación de que el OTP corresponde a la solicitud correcta se garantiza verificando que `application_id` coincida, sin necesidad de un campo redundante.

---

### `documents`
Registro de los contratos PDF generados. La restricción de `is_active` garantiza que solo un documento por solicitud sea el vigente en todo momento.

| Atributo             | Tipo           | Restricciones                         | Descripción                                                                              |
|----------------------|----------------|---------------------------------------|------------------------------------------------------------------------------------------|
| `id`                 | `UUID`         | PK, DEFAULT `gen_random_uuid()`       | Identificador único del documento.                                                       |
| `application_id`     | `UUID`         | FK → `financial_applications`, NOT NULL | Solicitud a la que pertenece este contrato.                                            |
| `document_type_id`   | `SMALLINT`     | FK → `document_types`, NOT NULL       | Tipo de contrato generado.                                                               |
| `storage_path`       | `VARCHAR(500)` | NOT NULL                              | Ruta interna en Supabase Storage. El Dev 3 la genera; el Dev 2 la usa para solicitar la URL firmada de descarga. |
| `sha256_hash`        | `VARCHAR(64)`  | NOT NULL                              | **Sello de Lacre.** Huella digital SHA-256 del PDF. El Dev 2 la muestra en la UI como garantía de integridad. |
| `is_active`          | `BOOLEAN`      | NOT NULL, DEFAULT TRUE                | Solo un documento por `application_id` puede estar en `TRUE`. Antes de insertar uno nuevo, el Dev 3 debe marcar los anteriores como `FALSE`. |
| `generated_at`       | `TIMESTAMPTZ`  | NOT NULL                              | Momento exacto en que el archivo fue creado y almacenado. Permite al Frontend mostrar el botón de descarga solo después de que el documento fue generado. |
| `created_at`         | `TIMESTAMPTZ`  | NOT NULL, DEFAULT `NOW()`             | Marca de inserción del registro en la DB.                                                |
| `external_error_log` | `TEXT`         |                                       | Si el generador de PDF falla (ReportLab, Storage), el Dev 3 escribe el error aquí para gestión desde el orquestador. |

---

### `economic_history`
Caché de los valores de indicadores económicos externos (UF, USD, IPC). Permite que el sistema funcione aunque la API externa falle temporalmente. La restricción `UNIQUE (indicator_id, date)` previene duplicados y permite upserts eficientes.

| Atributo       | Tipo            | Restricciones                          | Descripción                                                          |
|----------------|-----------------|----------------------------------------|----------------------------------------------------------------------|
| `id`           | `BIGSERIAL`     | PK                                     | Identificador autoincremental.                                       |
| `indicator_id` | `SMALLINT`      | FK → `economic_indicators`, NOT NULL   | Indicador al que corresponde este registro.                          |
| `value`        | `NUMERIC(14,6)` | NOT NULL                               | Valor del indicador. Alta precisión para UF y USD.                   |
| `date`         | `DATE`          | NOT NULL                               | Fecha de vigencia del valor.                                         |
|                |                 | UNIQUE (`indicator_id`, `date`)        | Restricción compuesta para prevenir duplicados y facilitar upserts.  |

---

## RESUMEN DE RELACIONES

### Diagrama Textual

```
user_statuses ←── users ──→ user_categories
                    │
              conversations ──→ product_types
                    │
                messages
                    │
          financial_applications ──→ application_statuses
                    │
          ┌─────────┼──────────┐
          │         │          │
    loan_details  account_details  dap_details
          │         │          │
   education_levels  user_categories  dap_terms
   risk_levels       education_levels  currencies
   rejection_reason_codes   rejection_reason_codes  economic_indicators
          │                                             │
    financial_applications ──→ security_otp       economic_history
          │
       documents ──→ document_types ──→ product_types
```

### Tabla de Relaciones Clave

| Relación                                              | Cardinalidad | Descripción                                                             |
|-------------------------------------------------------|--------------|-------------------------------------------------------------------------|
| `users` → `user_statuses`                             | N:1          | Un usuario tiene un estado vigente.                                     |
| `users` → `user_categories`                           | N:1          | Un usuario pertenece a un tramo (puede ser NULL en inicio).             |
| `users` → `conversations`                             | 1:N          | Un usuario puede tener múltiples hilos de conversación.                 |
| `conversations` → `messages`                          | 1:N          | Un hilo contiene múltiples mensajes.                                    |
| `conversations` → `financial_applications`            | 1:0..1       | Una conversación puede generar como máximo una solicitud activa.        |
| `financial_applications` → `loan_details`             | 1:0..1       | Una solicitud de LOAN tiene exactamente un detalle de crédito.          |
| `financial_applications` → `account_details`          | 1:0..1       | Una solicitud de ACCOUNT tiene exactamente un detalle de cuenta.        |
| `financial_applications` → `dap_details`              | 1:0..1       | Una solicitud de DAP tiene exactamente un detalle de depósito.          |
| `financial_applications` → `security_otp`             | 1:0..1       | Una solicitud activa tiene como máximo un OTP vigente.                  |
| `financial_applications` → `documents`                | 1:N          | Una solicitud puede tener múltiples versiones de documento (solo una activa). |
| `loan_details` → `education_levels`                   | N:1          | Normaliza el nivel educativo y sus ponderaciones de scoring.            |
| `loan_details` → `risk_levels`                        | N:1          | Normaliza el nivel de riesgo y su tasa mensual asociada.                |
| `loan_details` → `rejection_reason_codes`             | N:1          | Causal de rechazo tipificada. NULL si fue aprobado.                     |
| `account_details` → `education_levels`                | N:1          | Determina si aplica el upgrade de plan por estudios.                    |
| `account_details` → `user_categories` (base_plan_id) | N:1          | Plan asignado por renta antes del upgrade.                              |
| `account_details` → `user_categories` (final_plan_id)| N:1          | Plan final asignado (puede incluir upgrade).                            |
| `dap_details` → `currencies`                          | N:1          | Normaliza la moneda y si aplica ajuste por IPC.                         |
| `dap_details` → `dap_terms`                           | N:1          | Normaliza el plazo disponible y su bonus_rate asociado.                 |
| `documents` → `document_types`                        | N:1          | Normaliza el tipo de contrato.                                          |
| `document_types` → `product_types`                    | N:1          | Vincula cada tipo de documento con su producto.                         |
| `economic_history` → `economic_indicators`            | N:1          | Normaliza el código del indicador (elimina strings libres).             |

---

## DECISIONES DE DISEÑO DOCUMENTADAS

### 1. Eliminación de `reference_flow` en `security_otp`
El campo original `reference_flow` (tipo del producto) fue eliminado por ser transitivamente dependiente: `security_otp.application_id → financial_applications.product_type_id`. La validación de que el OTP corresponde al producto correcto se garantiza verificando `application_id`, sin redundancia.

### 2. `amortization_schedule` como `JSONB`
La tabla de amortización es un bloque estructurado (arreglo de ~48 objetos) que siempre se consulta completo y nunca por fila individual. Normalizarla en una tabla `loan_amortization_rows` generaría hasta 48 filas por solicitud sin beneficio de consulta, degradando el rendimiento. El almacenamiento como `JSONB` es el patrón correcto para este caso.

### 3. Snapshots de tasas en tablas de detalle
Los campos `applied_monthly_rate` en `loan_details` y `base_rate`, `bonus_rate`, `ipc_adjustment` en `dap_details` **duplican intencionalmente** valores presentes en los catálogos `risk_levels` y `dap_terms`. Esta es la única excepción documentada a la 3FN: su propósito es preservar la integridad de auditoría histórica. Si el negocio modifica las tasas del catálogo en el futuro, los contratos ya emitidos deben conservar los valores que efectivamente se calcularon y firmaron.

### 4. `user_categories` reutilizado en `account_details`
Los planes de cuenta corriente (START, MEDIUM, ADVANCE) son semánticamente idénticos a las categorías de usuario. Se reutiliza `user_categories` como FK en lugar de crear una tabla `account_plan_types` redundante. `account_details` usa dos FKs a esta misma tabla (`base_plan_id` y `final_plan_id`) para registrar de forma trazable el antes y el después del upgrade educativo.

### 5. Edad calculada dinámicamente
La edad del usuario **no se almacena** como columna. Se calcula en tiempo de ejecución desde `users.birth_date`. Almacenar la edad generaría una anomalía de actualización: el registro envejecería incorrectamente sin intervención del sistema.

### 6. Campos `node_status`, `engine_status`, `document_status` como `VARCHAR` con `CHECK`
Estos tres campos son semáforos operacionales (contrato entre desarrolladores), no catálogos de negocio. Sus valores son estables, están completamente documentados aquí y se refuerzan con `CHECK` constraints en la base de datos. Crear tablas de catálogo para ellos añadiría tres joins sin valor semántico adicional.

### 7. `metadata JSONB` en entidades sujetas a cambios
Las tablas `financial_applications`, `account_details` y `dap_details` incluyen una columna `metadata JSONB`. Dado que los productos de Cuenta Corriente y DAP están sujetos a refinamiento, esta columna actúa como válvula de escape para atributos emergentes, evitando migraciones disruptivas durante el desarrollo activo del MVP.

### 8. `UNIQUE` en `conversations.id` → `financial_applications`
La relación `conversation_id` en `financial_applications` tiene restricción `UNIQUE`, garantizando que una conversación no pueda generar más de una solicitud activa. Si el usuario abandona y retoma, el orquestador retoma la solicitud existente (mediante el `state_snapshot`) en lugar de crear una duplicada.

---

## ÍNDICES RECOMENDADOS (Referencia para implementación)

| Tabla                    | Columna(s)                         | Tipo    | Justificación                                              |
|--------------------------|------------------------------------|---------|------------------------------------------------------------|
| `users`                  | `rut`                              | UNIQUE  | Búsqueda frecuente de usuario por RUT al iniciar sesión.  |
| `users`                  | `email`                            | UNIQUE  | Validación de Supabase Auth.                               |
| `conversations`          | `user_id`                          | B-Tree  | Consultas de historial por usuario.                        |
| `conversations`          | `user_id, is_active`               | B-Tree  | Recuperar conversaciones activas de un usuario.            |
| `messages`               | `conversation_id, created_at`      | B-Tree  | Reconstrucción del hilo en orden cronológico.              |
| `financial_applications` | `user_id`                          | B-Tree  | Dashboard de historial por usuario.                        |
| `financial_applications` | `conversation_id`                  | UNIQUE  | Garantía de una solicitud por conversación.                |
| `security_otp`           | `application_id`                   | UNIQUE  | Un OTP activo por solicitud.                               |
| `documents`              | `application_id, is_active`        | B-Tree  | Consultar el contrato vigente de una solicitud.            |
| `economic_history`       | `indicator_id, date`               | UNIQUE  | Prevenir duplicados y búsqueda eficiente del valor del día.|
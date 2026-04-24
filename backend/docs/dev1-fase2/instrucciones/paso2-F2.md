# PASO 2: Capa de Persistencia para Crédito

## 2.0 — Apertura del Checkpoint

Crear `/backend/tests/fase2-dev1/CP-02-dev1-fase2.md` con encabezado estándar.

Commit: `chore: iniciar CP-02 fase2 dev1 - helpers supabase crédito`

⛔ **DETENCIÓN OBLIGATORIA.** Reportar y solicitar confirmación para Sub-paso 2.1.

---

## Sub-paso 2.1 — Implementar `create_financial_application()`

**Archivo:** `app/infra/supabase.py` (agregar al final del archivo, sin modificar las funciones existentes)

**Tarea:** Agregar la función helper para crear el registro en `financial_applications`:

```python
def create_financial_application(
    user_id: str,
    conversation_id: str,
    product_type_code: str = "LOAN"
) -> dict:
    """
    Crea un nuevo registro en financial_applications para iniciar un flujo de producto.

    INPUT:
        user_id (str): UUID del usuario.
        conversation_id (str): UUID de la conversación (thread_id de LangGraph).
        product_type_code (str): Código del producto (ej. "LOAN"). Default: "LOAN".

    PROCESO:
        1. Obtener el id del product_type desde la tabla product_types por code.
        2. Obtener el id del status "IN_PROGRESS" desde application_statuses.
        3. Crear el registro en financial_applications con:
           - node_status = "IN_PROGRESS"
           - engine_status = "PENDING"
           - document_status = "PENDING"

    OUTPUT: dict — Registro creado con su id (application_id).

    NOTA: Usar supabase_admin para bypass de RLS.
          Si ya existe una financial_application para este conversation_id
          (constraint UNIQUE), capturar la excepción y retornar el registro
          existente en lugar de lanzar error.
    """
```

**Verificación de nomenclatura:** Los valores de `node_status`, `engine_status`, `document_status` deben coincidir exactamente con los `CHECK` constraints definidos en `modelo-datos.md`.

**Reporte al CP-02:** Sección "Sub-paso 2.1".

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 2.2.

---

## Sub-paso 2.2 — Implementar `update_application_status()`

**Archivo:** `app/infra/supabase.py`

**Tarea:**

```python
def update_application_status(
    application_id: str,
    current_node_id: str | None = None,
    node_status: str | None = None,      # "IN_PROGRESS" | "SUCCESS" | "FAILED"
    engine_status: str | None = None,    # "PENDING" | "COMPLETED" | "FAILED" | "NOT_APPLICABLE"
    document_status: str | None = None,  # "PENDING" | "GENERATED"
    status_code: str | None = None       # "IN_PROGRESS" | "PRE_APPROVED" | "REJECTED" | "COMPLETED" | "CLOSED_BY_USER"
) -> None:
    """
    Actualiza los campos de semáforo de sincronía en financial_applications.
    Es el canal de comunicación entre el Orquestador (Dev 1), Frontend (Dev 2)
    y Módulos de Seguridad (Dev 3) (Regla de Oro #3).

    INPUT: application_id y los campos a actualizar (todos opcionales).
    PROCESO:
        Construir dict `data` solo con los campos no-None provistos.
        Si status_code se provee, resolver el status_id desde application_statuses.
        Ejecutar UPDATE en financial_applications donde id = application_id.
    OUTPUT: None. Lanza excepción si el registro no existe o la actualización falla.

    NOTA DE IMPLEMENTACIÓN:
        No incluir en `data` los campos que lleguen como None.
        Usar patrón: data = {k: v for k, v in {...}.items() if v is not None}
    """
```

**Verificación de nomenclatura:** Los valores de los parámetros deben coincidir con los `CHECK` constraints del modelo de datos. Documentar en el CP la tabla completa de valores válidos por campo.

**Reporte al CP-02:** Sección "Sub-paso 2.2".

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 2.3.

---

## Sub-paso 2.3 — Implementar `upsert_loan_details()`

**Archivo:** `app/infra/supabase.py`

**Tarea:** Función que crea o actualiza el registro en `loan_details`:

```python
def upsert_loan_details(
    application_id: str,
    data: dict
) -> dict:
    """
    Crea o actualiza el registro de detalles de crédito en loan_details.

    INPUT:
        application_id (str): UUID de la financial_application padre.
        data (dict): Campos a insertar/actualizar. Puede contener tanto
                     los inputs del usuario como los outputs del motor,
                     dependiendo del nodo que invoca la función.

    PROCESO:
        Ejecutar un UPSERT en loan_details con conflict_target = application_id.
        Esto permite llamar a esta función tanto en LOAN_COLLECTING_SIMULATION
        (solo inputs) como en LOAN_RISK_ENGINE (inputs + outputs del motor).

    OUTPUT: dict — Registro actualizado de loan_details.

    NOTAS:
        - education_level_id: resolver el id desde education_levels por code
          antes del upsert si se recibe el código en string.
        - risk_level_id: resolver el id desde risk_levels por code si se
          recibe el código en string.
        - rejection_reason_id: resolver desde rejection_reason_codes si aplica.
    """
```

**Verificación de nomenclatura:** Los campos del dict `data` deben mapear exactamente a los nombres de columnas de `loan_details` en `modelo-datos.md`. Documentar el mapeo explícito en el CP.

**Reporte al CP-02:** Sección "Sub-paso 2.3" con tabla de mapeo campo del motor → columna de DB.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 2.4.

---

## Sub-paso 2.4 — Implementar helpers de `security_otp`

**Archivo:** `app/infra/supabase.py`

**Tarea:** Implementar cuatro funciones para gestionar el ciclo de vida del OTP:

```python
def create_otp_record(application_id: str, otp_hash: str, expires_at: str) -> dict:
    """
    Crea un registro OTP en security_otp para una solicitud activa.
    Si ya existe un OTP para este application_id, eliminarlo antes de crear el nuevo
    (solo puede haber uno activo por solicitud, constraint UNIQUE).
    """

def get_active_otp(application_id: str) -> dict | None:
    """
    Recupera el registro OTP activo para una solicitud.
    Retorna None si no existe o si ya fue verificado (is_verified=True).
    """

def increment_otp_attempts(application_id: str, failed_hash: str) -> int:
    """
    Incrementa el contador de intentos fallidos en 1 y actualiza last_failed_hash.
    Retorna el nuevo valor del contador (para que el nodo decida si bloquear).
    """

def mark_otp_verified(application_id: str) -> None:
    """
    Marca el OTP como verificado (is_verified = True).
    Llamar solo cuando el código ingresado coincide con el hash almacenado.
    """
```

**Decisión técnica a documentar:** Cómo se maneja la eliminación del OTP previo antes de crear uno nuevo (en caso de reenvío).

**Verificación de nomenclatura:** Confirmar que los campos manipulados (`otp_hash`, `attempts`, `last_failed_hash`, `is_verified`, `expires_at`) coinciden con `security_otp` en `modelo-datos.md`.

**Reporte al CP-02:** Sección "Sub-paso 2.4".

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 2.5.

---

## Sub-paso 2.5 — Implementar `register_document()` y `get_application_for_conversation()`

**Archivo:** `app/infra/supabase.py`

**Tarea:** Implementar dos funciones:

```python
def register_document(
    application_id: str,
    storage_path: str,
    sha256_hash: str,
    product_type_code: str = "LOAN"
) -> dict:
    """
    Registra el contrato PDF generado en la tabla documents.

    PROCESO:
        1. Resolver document_type_id desde document_types por code "CONTRATO_CREDITO".
        2. Insertar en documents: application_id, document_type_id,
           storage_path, sha256_hash, is_active=True, generated_at=NOW().
        3. Actualizar financial_applications: document_status = "GENERATED".
    OUTPUT: dict — Registro creado.
    """

def get_application_for_conversation(conversation_id: str) -> dict | None:
    """
    Recupera la financial_application activa para una conversación dada.
    Permite al Orquestador retomar un flujo en curso en lugar de crear duplicados.

    INPUT: conversation_id (str).
    OUTPUT: dict con los datos de la solicitud, o None si no existe.
    """
```

**Verificación de nomenclatura:** El código de tipo de documento `"CONTRATO_CREDITO"` debe coincidir con `document_types.code` en `modelo-datos.md`.

**Reporte al CP-02:** Sección "Sub-paso 2.5".

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para ejecutar el Checkpoint 2.

---

## ✅ CHECKPOINT 2 — Pruebas de Integración con Supabase

**Archivo de pruebas:** `tests/fase2-dev1/test_credit_db.py`

**Prerrequisito:** El servidor de Supabase debe estar activo y el `.env` configurado.

### Test 2.A — Crear y recuperar financial_application
```python
# Objetivo: Verificar creación correcta del registro de solicitud.
# Diseño: Crear una application con user_id y conversation_id de prueba.
# Resultado esperado: dict con id, node_status="IN_PROGRESS",
#                     engine_status="PENDING", document_status="PENDING".
```

### Test 2.B — Actualizar semáforos de sincronía
```python
# Objetivo: Verificar que update_application_status actualiza solo los campos provistos.
# Diseño: Llamar con solo current_node_id="LOAN_RISK_ENGINE" y node_status="IN_PROGRESS".
# Resultado esperado: Solo esos dos campos cambian; los demás permanecen igual.
```

### Test 2.C — Upsert de loan_details en dos fases
```python
# Objetivo: Verificar que el upsert funciona en dos llamadas sucesivas sin crear duplicados.
# Fase 1 (inputs): Insertar requested_amount, term_months, monthly_income, etc.
# Fase 2 (outputs): Agregar risk_score, monthly_payment, cae, etc.
# Resultado esperado: Solo 1 registro en loan_details al final; campos de ambas fases presentes.
```

### Test 2.D — Ciclo de vida completo del OTP
```python
# Objetivo: Crear, consultar, incrementar intentos y verificar el OTP.
# Diseño:
#   1. create_otp_record → verificar creación.
#   2. get_active_otp → verificar recuperación.
#   3. increment_otp_attempts → verificar que attempts = 1.
#   4. increment_otp_attempts → verificar que attempts = 2.
#   5. mark_otp_verified → verificar is_verified = True.
# Resultado esperado: Cada operación refleja el estado esperado.
```

### Test 2.E — Unicidad de financial_application por conversación
```python
# Objetivo: Verificar que el constraint UNIQUE en conversation_id previene duplicados.
# Diseño: Llamar create_financial_application dos veces con el mismo conversation_id.
# Resultado esperado: Segunda llamada retorna el registro existente (no lanza error).
```

**Instrucción de ejecución:** `cd /backend && python -m pytest tests/fase2-dev1/test_credit_db.py -v`

**Reporte de Cierre del Paso 2 en CP-02:** Sección "REPORTE COMPLETO — PASO 2".

Commit final: `feat: agregar helpers de persistencia de crédito en supabase.py`

⛔ **DETENCIÓN OBLIGATORIA.** Reportar resultado del Checkpoint 2 y solicitar confirmación para iniciar Paso 3.

---
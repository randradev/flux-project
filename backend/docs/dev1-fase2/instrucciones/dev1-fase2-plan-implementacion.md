# PLAN DE IMPLEMENTACIÓN — FASE 2: EL PRIMER VUELO
## Dev 1 (AI Orchestrator) · Crédito de Consumo
### Proyecto FLUX · Backend LangGraph

---

> **Documento de Referencia de Ejecución para Agente Antigravity**
>
> **Regla de Oro de Operación:** El agente debe respetar estrictamente cada punto de pausa (`⛔ DETENCIÓN OBLIGATORIA`), solicitar confirmación explícita del desarrollador antes de continuar, y nunca realizar cambios fuera del scope del sub-paso activo. Ante cualquier ambigüedad técnica no contemplada en este plan, el agente debe **reportar y preguntar**, nunca asumir ni proceder.

---

## ÍNDICE DE PASOS

| Paso | Nombre | Archivos Principales |
|------|--------|---------------------|
| 1 | Motor de Riesgo Financiero | `app/modules/credit_eng.py` |
| 2 | Capa de Persistencia para Crédito | `app/infra/supabase.py` |
| 3 | Nodos de Recolección de Datos | `app/graph/nodes/credit.py` |
| 4 | Nodo Motor de Riesgo (Servicio) | `app/graph/nodes/credit.py` |
| 5 | Nodos de Oferta y Validación OTP | `app/graph/nodes/credit.py` |
| 6 | Nodos de Cierre y Manejo de Errores | `app/graph/nodes/credit.py` |
| 7 | Integración del Grafo | `app/graph/edges.py`, `app/graph/workflow.py` |

---

## CONVENCIONES DEL PLAN

### Nomenclatura de Archivos de Checkpoint
Cada paso crea y actualiza su propio archivo:
```
/backend/tests/fase2-dev1/CP-01-dev1-fase2.md   ← Paso 1
/backend/tests/fase2-dev1/CP-02-dev1-fase2.md   ← Paso 2
...
/backend/tests/fase2-dev1/CP-07-dev1-fase2.md   ← Paso 7
```

### Protocolo de Sub-paso
Al completar cada sub-paso, el agente debe:
1. Agregar al `CP-0X-dev1-fase2.md` activo un reporte del sub-paso completado.
2. Declarar explícitamente cualquier decisión técnica adoptada.
3. Emitir la frase literal: **"Sub-paso X.Y completado. Solicito confirmación para continuar con Sub-paso X.Z."**

### Verificación de Nomenclatura (Mandato Universal)
En **cada** sub-paso, antes de escribir o modificar cualquier código, el agente debe verificar y documentar en el CP:
- Nombres de funciones: `snake_case`, describen acción + sujeto (ej. `calculate_credit_score`, no `calc_score` ni `creditScore`).
- Nombres de nodos en el State: deben coincidir exactamente con los definidos en `credito-datos.md` (ej. `LOAN_INIT`, `LOAN_RISK_ENGINE`).
- Claves de `collected_data`: deben coincidir con los nombres del modelo de datos (ej. `renta`, `antiguedad_laboral`, `monto_solicitado`).
- Campos del State: jamás se crean nuevas claves en `FluxState` sin aprobación; toda escritura va a `collected_data` (dict libre) o `control_flags` (dict libre).
- Nombres de tablas y columnas de Supabase: deben coincidir exactamente con `modelo-datos.md`.

### Restricciones Técnicas Absolutas
1. **`with_structured_output` es obligatorio** en todos los nodos de recolección LLM (Collecting Profile, Collecting Simulation). No se acepta parseo manual de strings.
2. **`financial_applications` debe actualizarse** en cada nodo de servicio (LOAN_INIT, LOAN_RISK_ENGINE, LOAN_FORMALIZATION, LOAN_COMPLETED, y todos los nodos de error). Mínimo obligatorio: `current_node_id` + `node_status`.
3. **Los eventos SSE `node_transition` deben preservarse**: cada nodo debe actualizar `session["current_node"]` en el State para que el generador de streaming los emita automáticamente.
4. **`state.py` es sagrado**: el agente no puede modificar `FluxState`, `UserData` ni `SessionData`. Toda información nueva del flujo de crédito va en `collected_data` (TypedDict libre).
5. **Rama de Git**: todos los commits de esta fase van en la rama `feat/fase2-dev1/credito-consumo`.

---

---

# PASO 1: Motor de Riesgo Financiero

## 1.0 — Apertura del Checkpoint

**Acción inicial obligatoria:** Antes de escribir una sola línea de código, el agente debe:

1. Crear el archivo `/backend/tests/fase2-dev1/CP-01-dev1-fase2.md` con el siguiente encabezado:

```markdown
# CP-01-dev1-fase2 — Motor de Riesgo Financiero
**Fecha de inicio:** [FECHA]
**Rama Git:** feat/fase2-dev1/credito-consumo
**Archivo objetivo:** app/modules/credit_eng.py
**Estado:** EN CURSO
```

2. Hacer el primer commit: `chore: iniciar CP-01 fase2 dev1 - motor de riesgo`.

⛔ **DETENCIÓN OBLIGATORIA.** Reportar creación del CP y solicitar confirmación para Sub-paso 1.1.

---

## Sub-paso 1.1 — Crear estructura base del módulo `credit_eng.py`

**Archivo:** `app/modules/credit_eng.py`

**Tarea:** Crear el archivo con la estructura de módulo completa, sin implementar lógica aún. Incluir:
- Docstring de módulo (INPUT/PROCESO/SALIDA según estándar del proyecto).
- Imports necesarios: `math`, `datetime`, `typing`.
- Declaración de constantes del negocio con comentarios explicativos:
  ```python
  # Políticas mínimas de elegibilidad
  MIN_AGE = 18
  MIN_MONTHLY_INCOME = 500_000   # CLP
  MIN_EMPLOYMENT_MONTHS = 6
  
  # Límites del producto
  MIN_LOAN_AMOUNT = 100_000      # CLP
  MAX_LOAN_AMOUNT = 30_000_000   # CLP
  MIN_TERM_MONTHS = 6
  MAX_TERM_MONTHS = 48
  
  # Capacidad de pago
  MAX_PAYMENT_INCOME_RATIO = 0.30
  
  # Tablas de scoring (ponderaciones por categoría)
  SCORING_EDUCATION = {
      "POSTGRADO": 20, "UNIVERSITARIO": 15, "TECNICO": 10, "MEDIA": 5
  }
  SCORING_SENIORITY = {
      "GT_2Y": 20,    # > 24 meses
      "GT_1Y": 10,    # 12-24 meses
      "LT_1Y": 5      # < 12 meses
  }
  SCORING_AGE = {
      "PRIME": 20,    # 25-55 años
      "YOUNG": 5,     # 18-24 años
      "SENIOR": 5     # 56-65 años
  }
  SCORING_INCOME = {
      "HIGH": 40,     # > 3.000.000
      "MID": 25,      # 1.000.000 - 3.000.000
      "LOW": 10       # < 1.000.000
  }
  
  # Niveles de riesgo y tasas (snapshot; la fuente canónica es la tabla risk_levels)
  RISK_LEVELS = {
      "BAJO":  {"min_score": 81, "max_score": 100, "monthly_rate": 0.0120},
      "MEDIO": {"min_score": 50, "max_score": 80,  "monthly_rate": 0.0200},
      "ALTO":  {"min_score": 0,  "max_score": 49,  "monthly_rate": 0.0350},
  }
  ```
- Declaración vacía (con `pass`) de cada función que se implementará en los sub-pasos siguientes.
- **Verificación de nomenclatura:** confirmar que los nombres de constantes usan `SCREAMING_SNAKE_CASE` y que los valores coinciden con `credito-rn.md` y `modelo-datos.md`.

**Reporte al CP-01:** Agregar sección "Sub-paso 1.1" describiendo la estructura creada y confirmando la homologación de nomenclatura de constantes vs. catálogos del modelo de datos.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 1.2.

---

## Sub-paso 1.2 — Implementar `check_minimum_eligibility()`

**Archivo:** `app/modules/credit_eng.py`

**Tarea:** Implementar la función que valida las condiciones mínimas de política antes de ejecutar cualquier cálculo:

```python
def check_minimum_eligibility(
    age: int,
    monthly_income: int,
    employment_months: int
) -> tuple[bool, str | None]:
    """
    Verifica que el solicitante cumple los requisitos mínimos de política.

    INPUT:
        age (int): Edad calculada desde birth_date.
        monthly_income (int): Renta líquida declarada en CLP.
        employment_months (int): Antigüedad laboral en meses.

    PROCESO:
        Evalúa secuencialmente cada política mínima en orden de prioridad.
        Retorna al primer incumplimiento encontrado (fail-fast).

    OUTPUT:
        tuple[bool, str | None]:
            - (True, None): El solicitante cumple todos los requisitos.
            - (False, "ERR_EDAD"): Menor de 18 años.
            - (False, "ERR_RENTA"): Renta inferior al mínimo.
            - (False, "ERR_ANTIGUEDAD"): Antigüedad laboral insuficiente.
    """
```

Lógica de implementación:
- Verificar `age >= MIN_AGE`; si falla: retornar `(False, "ERR_EDAD")`.
- Verificar `monthly_income >= MIN_MONTHLY_INCOME`; si falla: retornar `(False, "ERR_RENTA")`.
- Verificar `employment_months >= MIN_EMPLOYMENT_MONTHS`; si falla: retornar `(False, "ERR_ANTIGUEDAD")`.
- Si pasa todo: retornar `(True, None)`.

**Verificación de nomenclatura:** Los códigos de error (`ERR_EDAD`, `ERR_RENTA`, `ERR_ANTIGUEDAD`) deben coincidir exactamente con los valores de la tabla `rejection_reason_codes` en `modelo-datos.md` y con el contrato de interfaz de `credito-datos.md`.

**Reporte al CP-01:** Sección "Sub-paso 1.2" con la función implementada, los códigos de error usados y su homologación con `modelo-datos.md`.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 1.3.

---

## Sub-paso 1.3 — Implementar `calculate_credit_score()`

**Archivo:** `app/modules/credit_eng.py`

**Tarea:** Implementar la función que calcula el scoring de 0 a 100 puntos:

```python
def calculate_credit_score(
    education_level: str,   # Código: POSTGRADO, UNIVERSITARIO, TECNICO, MEDIA
    employment_months: int,
    age: int,
    monthly_income: int
) -> int:
    """
    Calcula el puntaje de scoring crediticio (0-100 pts).

    INPUT: education_level, employment_months, age, monthly_income.
    PROCESO: Aplica las 4 ponderaciones definidas en credito-rn.md
             y suma los puntos obtenidos en cada categoría.
    OUTPUT: int — Puntaje total (suma de las 4 ponderaciones).
    """
```

Lógica de implementación:
- **Estudios** (`SCORING_EDUCATION`): lookup directo por `education_level`. Si el código no existe en el dict, lanzar `ValueError` con mensaje descriptivo.
- **Antigüedad** (`SCORING_SENIORITY`): `GT_2Y` si `employment_months > 24`, `GT_1Y` si `12 <= employment_months <= 24`, `LT_1Y` si `employment_months < 12`.
- **Edad** (`SCORING_AGE`): `PRIME` si `25 <= age <= 55`, `YOUNG` si `18 <= age <= 24`, `SENIOR` si `56 <= age <= 65`. Para edades fuera de rango (>65), asignar 0 puntos con comentario explicativo.
- **Renta** (`SCORING_INCOME`): `HIGH` si `income > 3_000_000`, `MID` si `1_000_000 <= income <= 3_000_000`, `LOW` si `income < 1_000_000`.
- Retornar la suma de los 4 componentes.

**Verificación de nomenclatura:** El parámetro `education_level` debe recibir los mismos códigos que define `education_levels.code` en `modelo-datos.md`.

**Reporte al CP-01:** Sección "Sub-paso 1.3" con la función implementada y confirmación de que los rangos de ponderación coinciden exactamente con `credito-rn.md`.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 1.4.

---

## Sub-paso 1.4 — Implementar `assign_risk_level_and_rate()`

**Archivo:** `app/modules/credit_eng.py`

**Tarea:** Implementar la función que asigna nivel de riesgo y tasa según el scoring:

```python
def assign_risk_level_and_rate(score: int) -> tuple[str, float]:
    """
    Asigna el nivel de riesgo y la tasa mensual según el puntaje de scoring.

    INPUT: score (int) — Resultado de calculate_credit_score (0-100).
    PROCESO: Consulta la tabla RISK_LEVELS para determinar el nivel
             correspondiente al rango en que cae el puntaje.
    OUTPUT:
        tuple[str, float]:
            - risk_level (str): "BAJO", "MEDIO" o "ALTO".
            - monthly_rate (float): 0.0120, 0.0200 o 0.0350.

    NOTA: Los umbrales son >= min_score y <= max_score.
          Riesgo BAJO: 81-100; MEDIO: 50-80; ALTO: 0-49.
    """
```

**Nota técnica:** Iterar sobre `RISK_LEVELS` verificando `min_score <= score <= max_score`. Si ningún nivel aplica (caso imposible en producción), lanzar `ValueError`. Asegurar que el umbral entre MEDIO y BAJO es score >= 81 (no > 80), conforme a `modelo-datos.md` donde `risk_levels.min_score` para BAJO es 81.

**Verificación de nomenclatura:** Los códigos de nivel de riesgo (`BAJO`, `MEDIO`, `ALTO`) deben coincidir con `risk_levels.code` en `modelo-datos.md`.

**Reporte al CP-01:** Sección "Sub-paso 1.4" con decisión técnica documentada sobre el umbral exacto BAJO/MEDIO.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 1.5.

---

## Sub-paso 1.5 — Implementar `calculate_monthly_payment()`

**Archivo:** `app/modules/credit_eng.py`

**Tarea:** Implementar el cálculo de cuota mensual por Amortización Francesa:

```python
def calculate_monthly_payment(
    principal: int,        # Monto del préstamo en CLP
    monthly_rate: float,   # Tasa mensual decimal (ej. 0.0120)
    term_months: int       # Número de cuotas
) -> int:
    """
    Calcula la cuota mensual fija por el método de Amortización Francesa.

    INPUT: principal, monthly_rate, term_months.
    PROCESO: Aplica la fórmula M = P * [i*(1+i)^n] / [(1+i)^n - 1]
             donde P=principal, i=monthly_rate, n=term_months.
             Redondea el resultado al entero superior (math.ceil).
    OUTPUT: int — Cuota mensual en CLP (entero superior).

    NOTA DE PRECISIÓN: Usar math.pow() o el operador ** para la
    exponenciación. Jamás usar aproximaciones de redondeo intermedias.
    """
```

**Verificación de nomenclatura:** La variable interna de la fórmula debe tener comentarios que referencien los símbolos matemáticos del documento `credito-rn.md`.

**Reporte al CP-01:** Sección "Sub-paso 1.5" con la fórmula usada y un ejemplo manual de verificación (ej. P=5.000.000, i=0.020, n=24 → cuota esperada calculada a mano).

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 1.6.

---

## Sub-paso 1.6 — Implementar `validate_payment_capacity()`

**Archivo:** `app/modules/credit_eng.py`

**Tarea:**

```python
def validate_payment_capacity(
    monthly_payment: int,
    monthly_income: int
) -> tuple[bool, int]:
    """
    Valida que la cuota mensual no supere el 30% de la renta líquida.

    INPUT: monthly_payment, monthly_income.
    PROCESO: Calcula el techo de capacidad de pago (renta * 0.30).
             Evalúa si la cuota cabe dentro del techo.
    OUTPUT:
        tuple[bool, int]:
            - (True, max_payment): La cuota es válida.
            - (False, max_payment): La cuota supera el techo.
    """
```

**Verificación de nomenclatura:** El retorno debe incluir el `max_allowed_payment` calculado, ya que es un campo requerido en `loan_details.max_allowed_payment` del modelo de datos.

**Reporte al CP-01:** Sección "Sub-paso 1.6".

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 1.7.

---

## Sub-paso 1.7 — Implementar métricas financieras: CTC, intereses y CAE

**Archivo:** `app/modules/credit_eng.py`

**Tarea:**

```python
def calculate_financial_metrics(
    monthly_payment: int,
    term_months: int,
    principal: int,
    monthly_rate: float
) -> dict:
    """
    Calcula el Costo Total del Crédito, los intereses totales y la CAE.

    INPUT: monthly_payment, term_months, principal, monthly_rate.
    PROCESO:
        - CTC = math.ceil(monthly_payment * term_months)
        - Total Intereses = CTC - principal
        - CAE = (1 + monthly_rate)^12 - 1  (tasa anual compuesta)
    OUTPUT:
        dict con claves:
            - "total_credit_cost" (int): CTC redondeado al entero superior.
            - "total_interest" (int): Diferencia entre CTC y principal.
            - "cae" (float): Carga Anual Equivalente en formato decimal.
    """
```

**Nota técnica:** La CAE se calcula como `(1 + monthly_rate) ** 12 - 1`. El resultado es un decimal (ej. 0.2682 para tasa ALTO), NO un porcentaje. Preservar precisión de 6 decimales.

**Verificación de nomenclatura:** Las claves del dict retornado deben coincidir exactamente con los campos de `loan_details` en `modelo-datos.md` (`total_credit_cost`, `total_interest`, `cae`).

**Reporte al CP-01:** Sección "Sub-paso 1.7" con un ejemplo de CAE calculado para cada nivel de riesgo.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 1.8.

---

## Sub-paso 1.8 — Implementar `build_amortization_schedule()`

**Archivo:** `app/modules/credit_eng.py`

**Tarea:**

```python
def build_amortization_schedule(
    principal: int,
    monthly_rate: float,
    term_months: int,
    monthly_payment: int
) -> list[dict]:
    """
    Genera la tabla de amortización cuota por cuota (Método Francés).

    INPUT: principal, monthly_rate, term_months, monthly_payment.
    PROCESO:
        Itera desde la cuota 1 hasta term_months.
        Para cada cuota:
            - interest = math.ceil(remaining_balance * monthly_rate)
            - principal_paid = monthly_payment - interest
            - remaining_balance -= principal_paid
        En la última cuota, ajustar para cerrar el saldo en 0 exacto.
    OUTPUT:
        list[dict] — Cada dict tiene:
            {
                "installment": int,       # Número de cuota (1..n)
                "monthly_payment": int,   # Cuota fija
                "interest": int,          # Interés de la cuota
                "principal_paid": int,    # Amortización del capital
                "remaining_balance": int  # Saldo restante tras la cuota
            }

    NOTA: Este arreglo se almacenará como JSONB en loan_details.amortization_schedule.
    """
```

**Decisión técnica a documentar:** El ajuste de la última cuota para cerrar el saldo exactamente en 0 puede generar una cuota final diferente a `monthly_payment`. El agente debe documentar cómo resuelve este ajuste.

**Verificación de nomenclatura:** Las claves del dict de cada fila deben documentarse en el CP como el "esquema del JSONB" de `loan_details.amortization_schedule`.

**Reporte al CP-01:** Sección "Sub-paso 1.8" con la estrategia de ajuste de la última cuota.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 1.9.

---

## Sub-paso 1.9 — Implementar la función orquestadora `run_risk_engine()`

**Archivo:** `app/modules/credit_eng.py`

**Tarea:** Implementar la función principal que orquesta todo el flujo del motor:

```python
def run_risk_engine(
    age: int,
    monthly_income: int,
    employment_months: int,
    education_level: str,
    requested_amount: int,
    term_months: int
) -> dict:
    """
    Función principal del motor de riesgo crediticio.

    INPUT:
        Todos los datos recolectados en LOAN_COLLECTING_PROFILE
        y LOAN_COLLECTING_SIMULATION, más la edad de LOAN_INIT.

    PROCESO:
        1. Validar elegibilidad mínima (check_minimum_eligibility).
           Si falla → retornar dict con status="REJECTED_POLICY".
        2. Calcular scoring (calculate_credit_score).
        3. Verificar scoring mínimo (>= 50 para MEDIO; si < 50 puede seguir
           como ALTO, pero si < umbral de negocio definido → REJECTED_POLICY).
           NOTA: Por las reglas de negocio actuales, NO hay rechazo
           automático por scoring bajo; la tasa ALTA absorbe el riesgo.
           Solo se rechaza por políticas (edad, renta, antigüedad, capacidad de pago).
        4. Asignar nivel de riesgo y tasa (assign_risk_level_and_rate).
        5. Calcular cuota mensual (calculate_monthly_payment).
        6. Validar capacidad de pago (validate_payment_capacity).
           Si falla → retornar dict con status="REJECTED_POLICY",
           rejection_reason="ERR_CAPACIDAD_PAGO".
        7. Calcular métricas financieras (calculate_financial_metrics).
        8. Generar tabla de amortización (build_amortization_schedule).
        9. Retornar dict con status="PRE_APPROVED" y todos los resultados.

    OUTPUT:
        dict con:
            "status": "PRE_APPROVED" | "REJECTED_POLICY" | "ERROR_TECHNICAL"
            "rejection_reason": str | None   # ERR_EDAD, ERR_RENTA, etc.
            "risk_score": int
            "risk_level": str                # BAJO, MEDIO, ALTO
            "monthly_rate": float
            "monthly_payment": int
            "max_allowed_payment": int
            "payment_capacity_valid": bool
            "total_credit_cost": int
            "total_interest": int
            "cae": float
            "approved_amount": int           # = requested_amount si aprobado
            "approved_term_months": int      # = term_months si aprobado
            "amortization_schedule": list[dict]
    """
```

**Manejo de excepciones:** Envolver toda la lógica en un `try/except Exception as e`. Si ocurre cualquier error inesperado, retornar `{"status": "ERROR_TECHNICAL", "error_detail": str(e)}`.

**Verificación de nomenclatura:** Verificar que todas las claves del dict de output coinciden exactamente con los campos de `loan_details` en `modelo-datos.md` y con los `OUTPUTS` definidos en `credito-datos.md`.

**Reporte al CP-01:** Sección "Sub-paso 1.9" con el flujo completo del motor y tabla de decisión de estados posibles.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para ejecutar el Checkpoint.

---

## ✅ CHECKPOINT 1 — Pruebas del Motor de Riesgo

**Archivo de pruebas:** `tests/fase2-dev1/test_credit_engine.py`

El agente debe crear este archivo e implementar los siguientes casos de prueba. Tras ejecutar cada prueba, registrar en `CP-01-dev1-fase2.md` el resultado y la interpretación.

---

### Test 1.A — Elegibilidad: menor de edad
```python
# Objetivo: Verificar que ERR_EDAD se devuelve para edad < 18.
# Diseño: age=17, income=800_000, months=12
# Resultado esperado: (False, "ERR_EDAD")
```

### Test 1.B — Elegibilidad: renta insuficiente
```python
# Objetivo: Verificar que ERR_RENTA se devuelve para renta < 500.000.
# Diseño: age=25, income=400_000, months=12
# Resultado esperado: (False, "ERR_RENTA")
```

### Test 1.C — Elegibilidad: antigüedad insuficiente
```python
# Objetivo: Verificar que ERR_ANTIGUEDAD se devuelve para < 6 meses.
# Diseño: age=25, income=800_000, months=3
# Resultado esperado: (False, "ERR_ANTIGUEDAD")
```

### Test 1.D — Scoring máximo (Riesgo BAJO)
```python
# Objetivo: Verificar scoring máximo esperado.
# Diseño: education="POSTGRADO", months=36, age=35, income=4_000_000
# Cálculo manual: 20 + 20 + 20 + 40 = 100 pts → Riesgo BAJO
# Resultado esperado: score=100, risk_level="BAJO", monthly_rate=0.0120
```

### Test 1.E — Scoring mínimo aprobable (Riesgo ALTO)
```python
# Objetivo: Verificar scoring bajo que produce tasa alta.
# Diseño: education="MEDIA", months=7, age=20, income=600_000
# Cálculo manual: 5 + 5 + 5 + 10 = 25 pts → Riesgo ALTO
# Resultado esperado: score=25, risk_level="ALTO", monthly_rate=0.0350
```

### Test 1.F — Cuota mensual (fórmula)
```python
# Objetivo: Verificar precisión de la Amortización Francesa.
# Diseño: principal=5_000_000, rate=0.0200, n=24
# Cálculo manual:
#   factor = 0.02 * (1.02)^24 / ((1.02)^24 - 1)
#   (1.02)^24 ≈ 1.60844
#   numerador = 0.02 * 1.60844 = 0.032169
#   denominador = 0.60844
#   M = 5_000_000 * (0.032169 / 0.60844) ≈ 264.157 → math.ceil → 264.157
#   Resultado esperado: 264_157 CLP aproximado (verificar con valor exacto)
# Resultado esperado: int (verificar con cálculo manual exacto del agente)
```

### Test 1.G — Rechazo por capacidad de pago
```python
# Objetivo: Verificar rechazo cuando la cuota supera el 30% de la renta.
# Diseño: run_risk_engine(age=25, monthly_income=500_000,
#           employment_months=12, education_level="UNIVERSITARIO",
#           requested_amount=20_000_000, term_months=6)
# La cuota de 20MM a 6 cuotas con cualquier tasa superará 500.000 * 0.30 = 150.000
# Resultado esperado: {"status": "REJECTED_POLICY", "rejection_reason": "ERR_CAPACIDAD_PAGO"}
```

### Test 1.H — Happy Path completo
```python
# Objetivo: Verificar que un perfil aprobable genera todos los campos esperados.
# Diseño: age=30, monthly_income=2_000_000, employment_months=24,
#         education_level="UNIVERSITARIO", requested_amount=5_000_000, term_months=24
# Resultado esperado:
#   - status = "PRE_APPROVED"
#   - risk_score >= 50 (MEDIO o BAJO)
#   - monthly_payment = int
#   - payment_capacity_valid = True
#   - len(amortization_schedule) == 24
#   - amortization_schedule[-1]["remaining_balance"] == 0
#   - total_credit_cost = monthly_payment * 24 (aprox)
#   - cae = (1 + monthly_rate)^12 - 1
```

**Instrucción de ejecución:** `cd /backend && python -m pytest tests/fase2-dev1/test_credit_engine.py -v`

**Reporte de Cierre del Paso 1 en CP-01:** Agregar sección "REPORTE COMPLETO — PASO 1" con:
- Descripción de la implementación del motor.
- Tabla de resultados de todos los tests (Objetivo / Resultado Real / ¿Pasa? / Interpretación).
- Decisiones técnicas adoptadas (umbral de scoring, ajuste última cuota, precisión CAE).
- Estado final: `COMPLETADO` o `BLOQUEADO` con motivo.

Commit final del paso: `feat: implementar motor de riesgo crediticio en credit_eng.py`

⛔ **DETENCIÓN OBLIGATORIA.** Reportar resultado del Checkpoint 1 y solicitar confirmación para iniciar Paso 2.

---

---

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

---

# PASO 3: Nodos de Recolección de Datos

## 3.0 — Apertura del Checkpoint

Crear `/backend/tests/fase2-dev1/CP-03-dev1-fase2.md`.

Commit: `chore: iniciar CP-03 fase2 dev1 - nodos recolección`

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 3.1.

---

## Sub-paso 3.1 — Crear estructura base de `nodes/credit.py`

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:** Reemplazar el contenido del stub actual (`loan_init_node`) con la estructura completa del módulo. El stub actual solo debe ser el punto de partida; el agente debe crear la estructura real.

Incluir:
- Docstring de módulo completo.
- Imports: LangChain/LangGraph, Pydantic, `FluxState`, `gemini_client`, helpers de `supabase`, `credit_eng`.
- Comentario de sección para cada grupo de nodos (Recolección, Servicio, Oferta/OTP, Cierre/Error).
- Declaración vacía de cada función-nodo que se implementará.
- Una función de utilidad `_update_node_gps(state: FluxState, node_name: str) -> dict` que construye el fragmento de actualización del State para el GPS:
  ```python
  def _update_node_gps(state: FluxState, node_name: str) -> dict:
      """
      Construye el fragmento de actualización del session para el GPS visual.
      Debe ser llamada al inicio de cada nodo para actualizar current_node.
      Esto garantiza que el streamer SSE emita el evento node_transition correcto.
      """
      return {
          "session": {
              **state.get("session", {}),
              "current_node": node_name,
              "previous_node": state.get("session", {}).get("current_node")
          }
      }
  ```

**Decisión técnica a documentar:** Estrategia de importación del cliente Gemini desde `gemini_client.py` (obtener la instancia del modelo de chat para `with_structured_output`).

**Verificación de nomenclatura:** Los nombres de las funciones-nodo declaradas deben seguir el patrón `{producto}_{estado_en_snake}_node` (ej. `loan_init_node`, `loan_collecting_profile_node`). Verificar que cada nombre de nodo tiene su equivalente exacto en `credito-datos.md`.

**Reporte al CP-03:** Sección "Sub-paso 3.1" con la lista completa de funciones declaradas y su mapeo a los estados de `credito-datos.md`.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 3.2.

---

## Sub-paso 3.2 — Implementar `loan_init_node`

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:** Implementar el nodo de servicio que inicializa el flujo de crédito:

```python
async def loan_init_node(state: FluxState) -> dict:
    """
    Nodo de servicio de inicialización del flujo de crédito.

    INPUT (State):
        - state["user_data"]: Contiene user_id, full_name, email, rut, birth_date.

    PROCESO:
        1. Actualizar GPS: session["current_node"] = "LOAN_INIT".
        2. Calcular edad desde user_data["birth_date"] (ISO8601 → date → hoy).
        3. Crear o recuperar financial_application en Supabase usando
           get_application_for_conversation() + create_financial_application().
        4. Actualizar financial_applications: current_node_id="LOAN_INIT",
           node_status="IN_PROGRESS".
        5. Persistir application_id en session["application_id"].
        6. Mapear datos del usuario a collected_data:
           {"nombre": ..., "rut": ..., "edad": ..., "mail": ...}
        7. Generar mensaje de saludo/invitación a comenzar el proceso.
        8. Actualizar financial_applications: node_status="SUCCESS".

    OUTPUT (Fragmento de State a actualizar):
        - session: {current_node, application_id, product_intent="LOAN"}
        - collected_data: {nombre, rut, edad, mail}
        - messages: [AIMessage de bienvenida al flujo]
    """
```

**Nota crítica sobre `birth_date`:** Calcular edad como `(date.today() - birth_date).days // 365`. No usar librerías externas. Documentar la decisión.

**Nota SSE:** La actualización de `session["current_node"] = "LOAN_INIT"` al inicio del nodo garantiza que el streamer emita el evento `node_transition` con `current_node: "LOAN_INIT"` antes de que llegue el primer token del mensaje.

**Verificación de nomenclatura:** Las claves en `collected_data` (`nombre`, `rut`, `edad`, `mail`) deben coincidir con los campos `INPUT` del estado `LOAN_INIT` en `credito-datos.md`.

**Reporte al CP-03:** Sección "Sub-paso 3.2".

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 3.3.

---

## Sub-paso 3.3 — Definir schemas Pydantic para extracción con `with_structured_output`

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:** Definir los modelos Pydantic que usa `with_structured_output` para los dos nodos de recolección. Estos deben ir antes de las funciones de nodo correspondientes.

```python
from pydantic import BaseModel, Field
from typing import Literal

class ProfileExtractionSchema(BaseModel):
    """
    Schema de extracción para los datos de perfil financiero del usuario.
    Usado por loan_collecting_profile_node con with_structured_output.
    """
    renta: int | None = Field(
        default=None,
        description="Renta líquida mensual declarada en CLP (entero, sin puntos ni símbolos). "
                    "Ej: si el usuario dice 'gano 1 millón 500', extraer 1500000."
    )
    antiguedad_laboral: int | None = Field(
        default=None,
        description="Antigüedad laboral en meses (entero). "
                    "Convertir años a meses si es necesario. Ej: '2 años' = 24."
    )
    nivel_estudios: Literal["POSTGRADO", "UNIVERSITARIO", "TECNICO", "MEDIA"] | None = Field(
        default=None,
        description="Nivel educativo más alto completado. "
                    "Debe ser exactamente uno de: POSTGRADO, UNIVERSITARIO, TECNICO, MEDIA."
    )
    datos_completos: bool = Field(
        description="True solo si los tres campos anteriores tienen valores no-None válidos."
    )

class SimulationExtractionSchema(BaseModel):
    """
    Schema de extracción para los parámetros del crédito solicitado.
    Usado por loan_collecting_simulation_node con with_structured_output.
    """
    monto_solicitado: int | None = Field(
        default=None,
        description="Monto del crédito en CLP (entero). "
                    "Convertir abreviaciones: '5 millones' = 5000000. "
                    "Rango válido: 100000 a 30000000."
    )
    plazo_solicitado: int | None = Field(
        default=None,
        description="Número de cuotas mensuales (entero). "
                    "Rango válido: 6 a 48. Si el usuario dice 'años', convertir: 2 años = 24."
    )
    datos_completos: bool = Field(
        description="True solo si ambos campos tienen valores no-None y están en rango válido."
    )
```

**Verificación de nomenclatura:** Los nombres de campo (`renta`, `antiguedad_laboral`, `nivel_estudios`, `monto_solicitado`, `plazo_solicitado`) deben coincidir exactamente con los campos `INPUT` de los estados `LOAN_COLLECTING_PROFILE` y `LOAN_COLLECTING_SIMULATION` en `credito-datos.md`.

**Reporte al CP-03:** Sección "Sub-paso 3.3" con los schemas y justificación de los `Field(description=...)` como guía de extracción para el LLM.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 3.4.

---

## Sub-paso 3.4 — Implementar `loan_collecting_profile_node`

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:**

```python
async def loan_collecting_profile_node(state: FluxState) -> dict:
    """
    Nodo de recolección de datos de perfil financiero mediante LLM.

    INPUT (State):
        - state["messages"]: Historial de conversación para contexto.
        - state["collected_data"]: Campos ya recolectados en la sesión activa.
        - state["user_data"]["full_name"]: Para personalización del mensaje.

    PROCESO:
        1. Actualizar GPS: session["current_node"] = "LOAN_COLLECTING_PROFILE".
        2. Actualizar financial_applications: current_node_id="LOAN_COLLECTING_PROFILE",
           node_status="IN_PROGRESS".
        3. Verificar si ya hay datos parciales en collected_data (renta, antigüedad, estudios).
           Si los hay, incluirlos en el prompt de sistema para que el LLM no los re-solicite.
        4. Construir el prompt del sistema que instruye al LLM a:
           a) Solicitar amablemente los datos faltantes (solo los que faltan).
           b) Usar with_structured_output(ProfileExtractionSchema) para extraer entidades.
           c) Si datos_completos=False, generar mensaje de seguimiento.
        5. Invocar el LLM con with_structured_output.
        6. Si datos_completos=True:
           a) Mapear a collected_data: renta, antiguedad_laboral, nivel_estudios.
           b) Actualizar loan_details en Supabase (upsert inputs).
           c) Actualizar financial_applications: node_status="SUCCESS".
        7. Si datos_completos=False:
           a) Generar mensaje de re-solicitud de datos faltantes.
           b) Mantener node_status="IN_PROGRESS".

    OUTPUT (Fragmento de State):
        - session: {current_node: "LOAN_COLLECTING_PROFILE"}
        - collected_data: {renta?, antiguedad_laboral?, nivel_estudios?}
        - messages: [AIMessage con la respuesta del LLM]

    NOTA DE DISEÑO: Este nodo puede ser llamado múltiples veces hasta que
    datos_completos=True (el edge condicional decidirá si avanzar o re-entrar).
    """
```

**Implementación de `with_structured_output`:**
```python
llm = get_chat_model()   # desde gemini_client.py
structured_llm = llm.with_structured_output(ProfileExtractionSchema)
result: ProfileExtractionSchema = await structured_llm.ainvoke(messages_with_system)
```

**Verificación de nomenclatura:** `node_status="IN_PROGRESS"` mientras el nodo espera datos, `"SUCCESS"` cuando `datos_completos=True`.

**Reporte al CP-03:** Sección "Sub-paso 3.4" con la estrategia de prompt para manejo de datos parciales.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 3.5.

---

## Sub-paso 3.5 — Implementar `loan_collecting_simulation_node`

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:** Implementar de forma análoga al Sub-paso 3.4, pero con `SimulationExtractionSchema`. El nodo solicita `monto_solicitado` y `plazo_solicitado`. Misma lógica de datos parciales, actualización de GPS, `financial_applications` y `loan_details`.

Adicionalmente, al recibir `monto_solicitado`, verificar en el nodo que esté dentro del rango válido (100.000 – 30.000.000). Si está fuera de rango, generar mensaje de corrección y mantener `datos_completos=False`.

**Reporte al CP-03:** Sección "Sub-paso 3.5".

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para ejecutar el Checkpoint 3.

---

## ✅ CHECKPOINT 3 — Pruebas de los Nodos de Recolección

**Archivo de pruebas:** `tests/fase2-dev1/test_credit_nodes_collecting.py`

### Test 3.A — `loan_init_node`: cálculo de edad
```python
# Objetivo: Verificar que la edad se calcula correctamente desde birth_date.
# Diseño: Crear un state mock con birth_date="1990-05-15".
#         La edad esperada depende de la fecha de ejecución (calcularla dinámicamente).
# Resultado esperado: collected_data["edad"] == (today.year - 1990) ajustado por mes.
```

### Test 3.B — `loan_init_node`: creación de financial_application
```python
# Objetivo: Verificar que se crea el registro en financial_applications.
# Diseño: Ejecutar el nodo con un state mock válido.
# Resultado esperado: session["application_id"] es un UUID válido.
#                     El registro existe en financial_applications en la DB.
```

### Test 3.C — `ProfileExtractionSchema`: extracción con abreviaciones
```python
# Objetivo: Verificar que el LLM extrae correctamente con with_structured_output.
# Diseño: Simular mensaje de usuario "Gano un millón y medio, llevo 3 años trabajando,
#         soy técnico en informática."
# Resultado esperado:
#   renta = 1_500_000
#   antiguedad_laboral = 36
#   nivel_estudios = "TECNICO"
#   datos_completos = True
```

### Test 3.D — `ProfileExtractionSchema`: datos incompletos
```python
# Objetivo: Verificar que datos_completos=False cuando faltan campos.
# Diseño: Mensaje "Gano 2 millones" (sin antigüedad ni estudios).
# Resultado esperado: renta=2000000, antiguedad_laboral=None,
#                     nivel_estudios=None, datos_completos=False.
```

### Test 3.E — `SimulationExtractionSchema`: monto fuera de rango
```python
# Objetivo: Verificar detección de monto inválido.
# Diseño: Mensaje "quiero 50 millones a 12 meses".
# Resultado esperado: datos_completos=False (monto fuera de rango MAX_LOAN_AMOUNT).
```

**Instrucción de ejecución:** `cd /backend && python -m pytest tests/fase2-dev1/test_credit_nodes_collecting.py -v`

**Reporte de Cierre del Paso 3 en CP-03:** Sección "REPORTE COMPLETO — PASO 3".

Commit final: `feat: implementar nodos de recolección LOAN_INIT, LOAN_COLLECTING_PROFILE, LOAN_COLLECTING_SIMULATION`

⛔ **DETENCIÓN OBLIGATORIA.** Reportar resultado y solicitar confirmación para Paso 4.

---

---

# PASO 4: Nodo Motor de Riesgo (LOAN_RISK_ENGINE)

## 4.0 — Apertura del Checkpoint

Crear `/backend/tests/fase2-dev1/CP-04-dev1-fase2.md`.

Commit: `chore: iniciar CP-04 fase2 dev1 - nodo LOAN_RISK_ENGINE`

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 4.1.

---

## Sub-paso 4.1 — Implementar skeleton de `loan_risk_engine_node`

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:** Crear el nodo con la estructura y docstring completo, sin implementar aún la lógica interna:

```python
async def loan_risk_engine_node(state: FluxState) -> dict:
    """
    Nodo de servicio del motor de riesgo crediticio (Python puro, sin LLM).

    INPUT (State):
        - state["user_data"]["birth_date"]: Para calcular edad (ya disponible en collected_data["edad"]).
        - state["collected_data"]: renta, antiguedad_laboral, nivel_estudios,
                                   monto_solicitado, plazo_solicitado, edad.
        - state["session"]["application_id"]: Para actualizar financial_applications.

    PROCESO:
        1. GPS + semáforos: current_node="LOAN_RISK_ENGINE",
           node_status="IN_PROGRESS", engine_status="PENDING".
        2. Extraer todos los inputs del collected_data.
        3. Invocar run_risk_engine() de credit_eng.py.
        4. Según el resultado:
           - Si PRE_APPROVED: mapear outputs a collected_data, actualizar loan_details,
             actualizar semáforos a SUCCESS + engine_status="COMPLETED".
           - Si REJECTED_POLICY: mapear motivo_rechazo, actualizar semáforos a FAILED,
             actualizar status_code a "REJECTED" en financial_applications.
           - Si ERROR_TECHNICAL: actualizar semáforos a FAILED.
        5. Generar mensaje de transición (sin revelar resultados aún; eso es LOAN_PRE_APPROVED).

    OUTPUT (Fragmento de State):
        - session: {current_node: "LOAN_RISK_ENGINE"}
        - collected_data: {todos los outputs del motor si PRE_APPROVED,
                           motivo_rechazo si REJECTED_POLICY}
        - control_flags: {service_error: bool, error_detail?: str}
        - messages: [AIMessage de transición]
    """
    pass  # Implementar en sub-pasos siguientes
```

**Reporte al CP-04:** Sección "Sub-paso 4.1" con el docstring.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 4.2.

---

## Sub-paso 4.2 — Implementar la invocación al motor y mapeo de resultados

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:** Completar la lógica de `loan_risk_engine_node`:

1. **Extracción de inputs desde el State:**
   ```python
   cd = state.get("collected_data", {})
   engine_inputs = {
       "age":               cd["edad"],
       "monthly_income":    cd["renta"],
       "employment_months": cd["antiguedad_laboral"],
       "education_level":   cd["nivel_estudios"],
       "requested_amount":  cd["monto_solicitado"],
       "term_months":       cd["plazo_solicitado"]
   }
   ```

2. **Invocación del motor:**
   ```python
   from app.modules.credit_eng import run_risk_engine
   result = run_risk_engine(**engine_inputs)
   ```

3. **Mapeo de outputs al State (`collected_data`)** si `status == "PRE_APPROVED"`:
   ```python
   # Mapeo completo de outputs del motor a collected_data
   collected_data_update = {
       "status_proceso": "PRE_APPROVED",
       "scoring_puntos": result["risk_score"],
       "nivel_riesgo": result["risk_level"],
       "tasa_interes_mensual": result["monthly_rate"],
       "cuota_mensual": result["monthly_payment"],
       "cuota_maxima_permitida": result["max_allowed_payment"],
       "capacidad_pago_valida": result["payment_capacity_valid"],
       "ctc": result["total_credit_cost"],
       "total_intereses": result["total_interest"],
       "cae": result["cae"],
       "monto_aprobado": result["approved_amount"],
       "plazo_aprobado": result["approved_term_months"],
   }
   ```

4. **Actualización de `loan_details` en Supabase** con todos los outputs del motor.

5. **Actualización de `financial_applications`:**
   - Si PRE_APPROVED: `node_status="SUCCESS"`, `engine_status="COMPLETED"`, `status_code="PRE_APPROVED"`.
   - Si REJECTED_POLICY: `node_status="FAILED"`, `engine_status="FAILED"`, `status_code="REJECTED"`.

**Verificación de nomenclatura:** Las claves en `collected_data_update` deben coincidir con los nombres `OUTPUTS` de `LOAN_RISK_ENGINE` en `credito-datos.md`.

**Reporte al CP-04:** Sección "Sub-paso 4.2" con tabla completa de mapeo motor → State.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 4.3.

---

## Sub-paso 4.3 — Implementar manejo de errores y mensajes de transición

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:** Completar los tres flujos alternativos del nodo:

1. **Mensaje de transición (PRE_APPROVED):** El bot NO revela los números de la oferta aquí (eso es responsabilidad de `LOAN_PRE_APPROVED`). Solo indica que el análisis fue exitoso y que mostrará la propuesta.
   ```
   Ejemplo: "He completado el análisis de tu solicitud. Enseguida te mostraré 
   los detalles de tu oferta personalizada."
   ```

2. **Mensaje de rechazo por política:** El bot explica el motivo con empatía.
   ```python
   REJECTION_MESSAGES = {
       "ERR_EDAD": "Lamentablemente, ...",
       "ERR_RENTA": "...",
       "ERR_ANTIGUEDAD": "...",
       "ERR_CAPACIDAD_PAGO": "...",
   }
   ```
   El mensaje se elige por `result["rejection_reason"]`.

3. **Mensaje de error técnico:** Mensaje genérico de "reintenta más tarde". Actualizar `control_flags["service_error"] = True`, `control_flags["error_detail"] = result.get("error_detail")`.

**Verificación de nomenclatura:** Los códigos de rechazo en `REJECTION_MESSAGES` deben coincidir con los valores de `rejection_reason_codes.code` en `modelo-datos.md`.

**Reporte al CP-04:** Sección "Sub-paso 4.3".

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para ejecutar Checkpoint 4.

---

## ✅ CHECKPOINT 4 — Pruebas del Nodo LOAN_RISK_ENGINE

**Archivo de pruebas:** `tests/fase2-dev1/test_risk_engine_node.py`

### Test 4.A — Happy Path: nodo produce PRE_APPROVED
```python
# Objetivo: Verificar que el nodo mapea correctamente los outputs del motor al State.
# Diseño: State con collected_data válido (perfil aprobable), application_id mock.
# Resultado esperado:
#   - collected_data["status_proceso"] == "PRE_APPROVED"
#   - collected_data["monto_aprobado"] == collected_data["monto_solicitado"]
#   - financial_applications en DB: engine_status="COMPLETED", node_status="SUCCESS"
#   - loan_details en DB: risk_score, monthly_payment, cae presentes.
```

### Test 4.B — Rechazo por capacidad de pago
```python
# Objetivo: Verificar que ERR_CAPACIDAD_PAGO actualiza correctamente la DB.
# Diseño: State con renta=500_000, monto=20_000_000, plazo=6.
# Resultado esperado:
#   - collected_data["status_proceso"] == "REJECTED_POLICY"
#   - financial_applications: status_code="REJECTED", engine_status="FAILED"
#   - loan_details: rejection_reason_id apunta a ERR_CAPACIDAD_PAGO
```

### Test 4.C — Actualización de semáforos SSE
```python
# Objetivo: Verificar que session["current_node"] se actualiza.
# Diseño: Ejecutar el nodo y verificar el fragmento de State retornado.
# Resultado esperado: state_update["session"]["current_node"] == "LOAN_RISK_ENGINE"
```

**Instrucción de ejecución:** `cd /backend && python -m pytest tests/fase2-dev1/test_risk_engine_node.py -v`

**Reporte de Cierre del Paso 4 en CP-04:** Sección "REPORTE COMPLETO — PASO 4".

Commit final: `feat: implementar nodo LOAN_RISK_ENGINE con integración al motor de crédito`

⛔ **DETENCIÓN OBLIGATORIA.** Reportar y solicitar confirmación para Paso 5.

---

---

# PASO 5: Nodos de Oferta y Validación OTP

## 5.0 — Apertura del Checkpoint

Crear `/backend/tests/fase2-dev1/CP-05-dev1-fase2.md`.

Commit: `chore: iniciar CP-05 fase2 dev1 - LOAN_PRE_APPROVED y LOAN_OTP_VALIDATION`

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 5.1.

---

## Sub-paso 5.1 — Implementar `loan_pre_approved_node`

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:**

```python
async def loan_pre_approved_node(state: FluxState) -> dict:
    """
    Nodo de presentación de la oferta crediticia.
    Emite la estructura de la "Tarjeta de Transparencia" para el Frontend.

    INPUT (State):
        - state["collected_data"]: monto_aprobado, plazo_aprobado,
          tasa_interes_mensual, cuota_mensual, ctc, total_intereses, cae, nivel_riesgo.
        - state["session"]["application_id"]: Para actualizar financial_applications.

    PROCESO:
        1. GPS: current_node = "LOAN_PRE_APPROVED".
        2. Actualizar financial_applications: current_node_id="LOAN_PRE_APPROVED",
           node_status="IN_PROGRESS".
        3. Construir el objeto "tarjeta_transparencia" con todos los datos de oferta.
        4. Emitir un AIMessage con:
           a) Texto introductorio cálido (el usuario logró la pre-aprobación).
           b) Un marcador especial en el contenido que el Frontend detecta para
              renderizar el componente visual: usar el convención acordada.
              Propuesta de convención: incluir en el mensaje un JSON embebido
              con tipo "TRANSPARENCY_CARD" y todos los campos de la tarjeta.
              Formato: ```json\n{"type": "TRANSPARENCY_CARD", "data": {...}}\n```
        5. Actualizar financial_applications: node_status="IN_PROGRESS"
           (el nodo queda "en espera" de la respuesta del usuario:
           ACCEPTED o REJECTED en la tarjeta de transparencia).

    OUTPUT (Fragmento de State):
        - session: {current_node: "LOAN_PRE_APPROVED"}
        - messages: [AIMessage con texto + JSON de la tarjeta]

    NOTA IMPORTANTE: La aceptación de la oferta NO puede venir por texto del chat.
    Solo puede venir a través del botón "Aceptar" del widget de la Tarjeta de
    Transparencia. El siguiente mensaje del usuario debe ser procesado por el
    edge condicional para detectar si es "ACCEPTED" o "REJECTED" (vendrá del FE
    como un mensaje estructurado, no como texto libre).
    """
```

**Decisión técnica a documentar:** El formato del JSON embebido en el AIMessage para señalizar la Tarjeta de Transparencia al Frontend. Esto es un contrato de interfaz entre Dev 1 y Dev 2. Documentar en el CP.

**Verificación de nomenclatura:** Los campos del objeto `data` en el JSON de la tarjeta deben coincidir con los `INPUTS` de `LOAN_PRE_APPROVED` en `credito-datos.md`.

**Reporte al CP-05:** Sección "Sub-paso 5.1" con el contrato de interfaz del JSON de la tarjeta.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 5.2.

---

## Sub-paso 5.2 — Implementar `loan_otp_validation_node` — Fase de Generación

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:** Implementar la primera parte del nodo OTP: generación y envío del código.

```python
async def loan_otp_validation_node(state: FluxState) -> dict:
    """
    Nodo de orquestación de validación OTP por email.

    INPUT (State):
        - state["collected_data"]["mail"]: Correo del usuario.
        - state["session"]["application_id"]: Para crear/consultar el OTP en DB.
        - state["control_flags"]["otp_attempts"]: Contador de intentos (int, 0-3).
        - state["messages"][-1]: El último mensaje del usuario (código OTP ingresado
          o mensaje de entrada al nodo por primera vez).

    PROCESO:
        A) Si es la primera vez que se entra al nodo (otp_attempts no existe o == 0):
           1. GPS: current_node = "LOAN_OTP_VALIDATION".
           2. Importar desde app.modules.security: generate_otp().
           3. Generar OTP de 6 dígitos.
           4. Calcular hash SHA-256 del código generado.
           5. Calcular expires_at = ahora + 10 minutos.
           6. Crear registro en security_otp (via create_otp_record()).
           7. Enviar OTP por email (llamar a función de security.py —
              si no está implementada por Dev 3, usar MOCK: log en consola).
           8. Actualizar control_flags["otp_attempts"] = 0.
           9. Emitir AIMessage solicitando el código al usuario + emitir
              marcador JSON para que el FE renderice el widget de input OTP:
              ```json {"type": "OTP_INPUT_WIDGET"} ```

        B) Si ya hay un OTP activo (otp_attempts >= 1 o estado de re-entrada):
           → Ir a Sub-paso 5.3 (verificación).
    ...
    """
```

**Nota sobre la dependencia de Dev 3:** `generate_otp()` y el servicio de envío de email pertenecen a `app/modules/security.py` (Dev 3). Si no están disponibles, implementar un **mock temporal** según Regla de Oro #2:
```python
# MOCK TEMPORAL — Reemplazar cuando Dev 3 entregue security.py
def _mock_generate_otp() -> str:
    import random
    return str(random.randint(100000, 999999))

def _mock_send_otp_email(email: str, otp: str) -> None:
    print(f"[MOCK OTP] Código {otp} enviado a {email}")
```
Documentar explícitamente en el CP que estos son mocks temporales.

**Verificación de nomenclatura:** Las claves en `control_flags` (`otp_attempts`) deben coincidir con la estructura documentada en `state.py`.

**Reporte al CP-05:** Sección "Sub-paso 5.2" con decisión sobre el mock y el contrato del widget `OTP_INPUT_WIDGET`.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 5.3.

---

## Sub-paso 5.3 — Implementar verificación OTP (VERIFIED / FAILED / BLOCKED)

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:** Completar `loan_otp_validation_node` con la lógica de verificación:

Cuando el usuario responde con un código (parte B del nodo):
1. Obtener el registro OTP activo via `get_active_otp(application_id)`.
2. Verificar expiración: si `NOW() > expires_at` → tratar como `FAILED` con mensaje de expiración.
3. Calcular SHA-256 del código ingresado por el usuario.
4. Comparar con `otp_record["otp_hash"]`:
   - **Coincide:** Llamar a `mark_otp_verified()`. Actualizar `control_flags["otp_status"] = "VERIFIED"`. Emitir mensaje de éxito.
   - **No coincide:**
     - Llamar a `increment_otp_attempts(failed_hash=hash_del_intento)`.
     - Nuevo `attempts = otp_record["attempts"] + 1`.
     - Si `attempts < 3`: Actualizar `control_flags["otp_attempts"]`, emitir mensaje de error con intentos restantes.
     - Si `attempts >= 3`: Actualizar `control_flags["otp_status"] = "BLOCKED"`, `control_flags["security_blocked"] = True`. Emitir mensaje de bloqueo.
5. Actualizar `financial_applications` según el resultado.

**Nota sobre hashing:** Calcular SHA-256 con `hashlib.sha256(otp_code.encode()).hexdigest()`. Este es el método estándar que Dev 3 usará también; documentar en el CP para garantizar compatibilidad.

**Verificación de nomenclatura:** Los valores de `otp_status` (`VERIFIED`, `FAILED`, `BLOCKED`) deben coincidir con los `OUTPUTS` de `LOAN_OTP_VALIDATION` en `credito-datos.md`.

**Reporte al CP-05:** Sección "Sub-paso 5.3" con la estrategia de hashing documentada (contrato con Dev 3).

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para el Checkpoint 5.

---

## ✅ CHECKPOINT 5 — Pruebas de OTP y Oferta

**Archivo de pruebas:** `tests/fase2-dev1/test_otp_and_offer.py`

### Test 5.A — Generación del OTP
```python
# Objetivo: Verificar que el nodo genera el OTP y lo persiste en la DB.
# Diseño: Ejecutar loan_otp_validation_node con estado de primera entrada.
# Resultado esperado:
#   - Existe registro en security_otp para el application_id.
#   - otp_hash es un SHA-256 válido (64 chars hex).
#   - attempts = 0, is_verified = False.
#   - expires_at > NOW().
```

### Test 5.B — Verificación exitosa del OTP
```python
# Objetivo: Verificar flujo VERIFIED.
# Diseño: Crear OTP manualmente, luego llamar al nodo con el código correcto.
# Resultado esperado:
#   - security_otp.is_verified = True.
#   - control_flags["otp_status"] = "VERIFIED".
#   - financial_applications actualizado.
```

### Test 5.C — Fallo con 2 intentos y bloqueo al 3ro
```python
# Objetivo: Verificar la escalada de intentos hasta el bloqueo.
# Diseño: Enviar 3 códigos incorrectos secuencialmente.
# Resultado esperado:
#   - Intento 1: attempts=1, otp_status=FAILED.
#   - Intento 2: attempts=2, otp_status=FAILED.
#   - Intento 3: attempts=3, otp_status=BLOCKED, security_blocked=True.
```

### Test 5.D — OTP expirado
```python
# Objetivo: Verificar que un OTP con expires_at en el pasado se trata como FAILED.
# Diseño: Crear registro en security_otp con expires_at en el pasado.
# Resultado esperado: El nodo detecta la expiración y emite mensaje correspondiente.
```

### Test 5.E — `loan_pre_approved_node`: estructura del JSON de la tarjeta
```python
# Objetivo: Verificar que el AIMessage contiene el JSON de la Tarjeta de Transparencia.
# Diseño: Ejecutar el nodo con collected_data completo (post-motor).
# Resultado esperado: El contenido del AIMessage contiene:
#   - "TRANSPARENCY_CARD" en el texto.
#   - JSON parseable con monto_aprobado, cuota_mensual, cae, ctc, etc.
```

**Instrucción de ejecución:** `cd /backend && python -m pytest tests/fase2-dev1/test_otp_and_offer.py -v`

**Reporte de Cierre del Paso 5 en CP-05:** Sección "REPORTE COMPLETO — PASO 5".

Commit final: `feat: implementar nodos LOAN_PRE_APPROVED y LOAN_OTP_VALIDATION`

⛔ **DETENCIÓN OBLIGATORIA.** Reportar y solicitar confirmación para Paso 6.

---

---

# PASO 6: Nodos de Cierre y Manejo de Errores

## 6.0 — Apertura del Checkpoint

Crear `/backend/tests/fase2-dev1/CP-06-dev1-fase2.md`.

Commit: `chore: iniciar CP-06 fase2 dev1 - nodos de cierre y error`

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 6.1.

---

## Sub-paso 6.1 — Implementar `loan_formalization_node` (con mock de PDF)

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:**

```python
async def loan_formalization_node(state: FluxState) -> dict:
    """
    Nodo de servicio para la generación y sellado del contrato.

    INPUT (State):
        - state["collected_data"]: monto_aprobado, plazo_aprobado, tasa_interes_mensual,
          cuota_mensual, rut, nombre, timestamp_acceptance.
        - state["session"]["application_id"].

    PROCESO:
        1. GPS: current_node = "LOAN_FORMALIZATION".
        2. Actualizar financial_applications: node_status="IN_PROGRESS".
        3. Intentar importar y llamar a pdf_factory.generate_loan_contract().
           SI el módulo existe y funciona:
             a) Generar PDF con los datos del contrato.
             b) Calcular SHA-256 del PDF generado.
             c) Subir al Storage (si la función del Dev 3 está disponible).
             d) Registrar en documents via register_document().
           SI el módulo NO está disponible (Dev 3 no entregó aún):
             a) Usar MOCK: generar un path de placeholder y un hash ficticio.
             b) Documentar explícitamente en el mensaje de log: "[MOCK PDF ACTIVO]"
        4. Actualizar financial_applications:
           - Si SIGNED_AND_STAMPED: node_status="SUCCESS", document_status="GENERATED",
             status_code="COMPLETED".
           - Si GENERATION_FAILED: node_status="FAILED", control_flags["service_error"]=True.
        5. Mapear a collected_data: file_contrato_path, hash_sha256, contract_status.

    OUTPUT (Fragmento de State):
        - session: {current_node: "LOAN_FORMALIZATION"}
        - collected_data: {file_contrato_path, hash_sha256, contract_status}
        - control_flags: {service_error?: bool}
    """
```

**Mock temporal para `pdf_factory` (Regla de Oro #2):**
```python
# MOCK TEMPORAL — Eliminar cuando Dev 3 entregue pdf_factory.py
def _mock_generate_pdf(contract_data: dict) -> tuple[str, str]:
    """Retorna (storage_path, sha256_hash) ficticios para testing."""
    import hashlib, json
    mock_content = json.dumps(contract_data, default=str).encode()
    mock_hash = hashlib.sha256(mock_content).hexdigest()
    mock_path = f"contracts/mock_{contract_data.get('rut', 'unknown')}_{mock_hash[:8]}.pdf"
    return mock_path, mock_hash
```

**Verificación de nomenclatura:** `contract_status` debe tomar los valores `"SIGNED_AND_STAMPED"` o `"GENERATION_FAILED"` exactamente como define `credito-datos.md`.

**Reporte al CP-06:** Sección "Sub-paso 6.1" con la estrategia de mock y el contrato de interfaz con `pdf_factory`.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 6.2.

---

## Sub-paso 6.2 — Implementar `loan_completed_node`

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:**

```python
async def loan_completed_node(state: FluxState) -> dict:
    """
    Nodo de cierre exitoso del flujo de crédito.

    INPUT (State):
        - state["collected_data"]: file_contrato_path, hash_sha256, contract_status.
        - state["user_data"]["full_name"]: Para mensaje de felicitación personalizado.

    PROCESO:
        1. GPS: current_node = "LOAN_COMPLETED".
        2. Verificar contract_status == "SIGNED_AND_STAMPED" antes de celebrar.
        3. Actualizar financial_applications: current_node_id="LOAN_COMPLETED",
           node_status="SUCCESS", status_code="COMPLETED".
        4. Generar AIMessage de felicitación que incluya:
           - Mensaje cálido personalizado.
           - JSON con "type": "COMPLETION_CARD" conteniendo:
             download_url (file_contrato_path), security_hash (hash_sha256).
        5. Marcar conversación como no activa en Supabase (is_active=False).

    OUTPUT (Fragmento de State):
        - session: {current_node: "LOAN_COMPLETED"}
        - messages: [AIMessage de felicitación + COMPLETION_CARD]
    """
```

**Reporte al CP-06:** Sección "Sub-paso 6.2" con el contrato del `COMPLETION_CARD` JSON para Dev 2.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 6.3.

---

## Sub-paso 6.3 — Implementar nodos de error: `loan_rejected_policy_node`, `loan_security_block_node`, `loan_closed_by_user_node`

**Archivo:** `app/graph/nodes/credit.py`

**Tarea:** Implementar los tres nodos terminales de error/cierre. Cada uno sigue el mismo patrón:

**`loan_rejected_policy_node`:**
- GPS + actualización de DB.
- Leer `collected_data["motivo_rechazo"]`.
- Emitir mensaje empático basado en el motivo (reutilizar `REJECTION_MESSAGES` del Paso 4).
- Actualizar `financial_applications`: `status_code="REJECTED"`, `node_status="FAILED"`.
- Cerrar conversación (`is_active=False`).

**`loan_security_block_node`:**
- GPS + actualización de DB.
- Emitir mensaje de bloqueo de seguridad.
- Actualizar `financial_applications`: `status_code="REJECTED"`, `node_status="FAILED"`.
- Actualizar `users.status_id` a `BLOCKED_SECURITY` (FK a `user_statuses`).
  - **Nota:** Esta actualización toca la tabla `users`, lo cual es sensible. Documentar la decisión en el CP. Si esto debe ser responsabilidad del Dev 3 (Security Watchdog), usar una función delegada y documentarlo.
- Cerrar conversación.

**`loan_closed_by_user_node`:**
- GPS + actualización de DB.
- Emitir mensaje de despedida cálido.
- Actualizar `financial_applications`: `status_code="CLOSED_BY_USER"`, `node_status="FAILED"`.
- Cerrar conversación.

**Verificación de nomenclatura:** Los valores de `status_code` deben coincidir con `application_statuses.code` en `modelo-datos.md`.

**Reporte al CP-06:** Sección "Sub-paso 6.3" con la decisión técnica sobre el bloqueo de usuario (Dev 1 vs Dev 3).

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para ejecutar Checkpoint 6.

---

## ✅ CHECKPOINT 6 — Pruebas de Nodos de Cierre

**Archivo de pruebas:** `tests/fase2-dev1/test_credit_nodes_terminal.py`

### Test 6.A — `loan_formalization_node`: mock activo
```python
# Objetivo: Verificar que el nodo funciona con el mock de PDF.
# Diseño: State con datos post-OTP válidos. Dev 3 sin entregar pdf_factory.
# Resultado esperado:
#   - contract_status = "SIGNED_AND_STAMPED" (el mock siempre tiene éxito).
#   - hash_sha256 es un string hexadecimal de 64 chars.
#   - financial_applications: document_status="GENERATED", status_code="COMPLETED".
#   - Registro en tabla documents creado.
```

### Test 6.B — `loan_completed_node`: estructura del COMPLETION_CARD
```python
# Objetivo: Verificar la estructura del mensaje de cierre.
# Diseño: State con contract_status="SIGNED_AND_STAMPED".
# Resultado esperado:
#   - AIMessage contiene "COMPLETION_CARD" JSON con download_url y security_hash.
#   - conversations.is_active = False en la DB.
```

### Test 6.C — `loan_rejected_policy_node`: mensaje por motivo
```python
# Objetivo: Verificar que el mensaje varía según el motivo de rechazo.
# Diseño: Ejecutar el nodo con motivo_rechazo = "ERR_RENTA".
# Resultado esperado: El mensaje menciona la renta o los requisitos de ingreso.
#                     financial_applications.status_code = "REJECTED".
```

### Test 6.D — `loan_security_block_node`: actualización de usuario
```python
# Objetivo: Verificar que el bloqueo se refleja en la tabla users.
# Diseño: Ejecutar el nodo con un user_id de prueba.
# Resultado esperado: users.status_id apunta a BLOCKED_SECURITY.
#                     financial_applications.status_code = "REJECTED".
```

### Test 6.E — `loan_closed_by_user_node`
```python
# Objetivo: Verificar cierre voluntario.
# Diseño: State con status de pre-aprobado.
# Resultado esperado: financial_applications.status_code = "CLOSED_BY_USER".
#                     conversations.is_active = False.
```

**Instrucción de ejecución:** `cd /backend && python -m pytest tests/fase2-dev1/test_credit_nodes_terminal.py -v`

**Reporte de Cierre del Paso 6 en CP-06:** Sección "REPORTE COMPLETO — PASO 6".

Commit final: `feat: implementar nodos terminales LOAN_FORMALIZATION, LOAN_COMPLETED, LOAN_REJECTED_POLICY, LOAN_SECURITY_BLOCK, LOAN_CLOSED_BY_USER`

⛔ **DETENCIÓN OBLIGATORIA.** Reportar y solicitar confirmación para Paso 7.

---

---

# PASO 7: Integración del Grafo

## 7.0 — Apertura del Checkpoint

Crear `/backend/tests/fase2-dev1/CP-07-dev1-fase2.md`.

Commit: `chore: iniciar CP-07 fase2 dev1 - integración grafo`

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 7.1.

---

## Sub-paso 7.1 — Actualizar `edges.py` con lógica de ruteo del crédito

**Archivo:** `app/graph/edges.py`

**Tarea:** Agregar las funciones de ruteo condicional para el flujo de crédito. Estas funciones reciben el `FluxState` y retornan un string que identifica el siguiente nodo.

```python
def route_after_loan_init(state: FluxState) -> str:
    """
    Ruteo después de LOAN_INIT.
    Si hay error técnico → "loan_rejected_policy" (raro, pero defensivo).
    Si todo OK → "loan_collecting_profile".
    """

def route_after_collecting_profile(state: FluxState) -> str:
    """
    Ruteo después de LOAN_COLLECTING_PROFILE.
    Si datos_completos en collected_data → "loan_collecting_simulation".
    Si datos incompletos → "loan_collecting_profile" (re-entrada al mismo nodo).
    NOTA: Para detectar re-entrada, verificar que renta, antiguedad_laboral
    y nivel_estudios estén presentes en collected_data y sean no-None.
    """

def route_after_collecting_simulation(state: FluxState) -> str:
    """
    Ruteo después de LOAN_COLLECTING_SIMULATION.
    Si datos_completos → "loan_risk_engine".
    Si incompletos → "loan_collecting_simulation" (re-entrada).
    """

def route_after_risk_engine(state: FluxState) -> str:
    """
    Ruteo después de LOAN_RISK_ENGINE.
    Según collected_data["status_proceso"]:
      "PRE_APPROVED" → "loan_pre_approved"
      "REJECTED_POLICY" → "loan_rejected_policy"
    Según control_flags["service_error"]:
      True → "service_error_handler" (placeholder; implementar en Fase 3)
              Por ahora → "loan_rejected_policy" con mensaje técnico.
    """

def route_after_pre_approved(state: FluxState) -> str:
    """
    Ruteo después de LOAN_PRE_APPROVED.
    El último mensaje del usuario debe ser un evento estructurado del FE:
      "ACCEPTED" → "loan_otp_validation"
      "REJECTED" → "loan_closed_by_user"
    Si el mensaje no es ninguno de los dos, re-entrar a "loan_pre_approved".
    NOTA: Los mensajes del botón vendrán como texto plano: "OFFER_ACCEPTED" u "OFFER_REJECTED".
    Acordar el protocolo exacto con Dev 2 y documentarlo en el CP.
    """

def route_after_otp_validation(state: FluxState) -> str:
    """
    Ruteo después de LOAN_OTP_VALIDATION.
    Según control_flags["otp_status"]:
      "VERIFIED" → "loan_formalization"
      "FAILED"   → "loan_otp_validation" (re-entrada para nuevo intento)
      "BLOCKED"  → "loan_security_block"
    """

def route_after_formalization(state: FluxState) -> str:
    """
    Ruteo después de LOAN_FORMALIZATION.
    Según collected_data["contract_status"]:
      "SIGNED_AND_STAMPED" → "loan_completed"
      "GENERATION_FAILED"  → Placeholder para SERVICE_ERROR_HANDLER (Fase 3).
                             Por ahora → "loan_rejected_policy" con mensaje técnico.
    """
```

**Verificación de nomenclatura:** Los strings retornados deben coincidir exactamente con los nombres de nodo que se registrarán en `workflow.py` en el Sub-paso 7.2.

**Reporte al CP-07:** Sección "Sub-paso 7.1" con tabla completa de ruteo: función → condición → nodo destino.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 7.2.

---

## Sub-paso 7.2 — Actualizar `workflow.py`: registrar nodos y aristas

**Archivo:** `app/graph/workflow.py`

**Tarea:** Actualizar `build_graph()` para registrar todos los nodos de crédito y sus aristas condicionales.

Reemplazar `graph.add_edge("loan_init", END)` por el subgrafo completo del crédito:

```python
# ── Importar nodos de crédito ────────────────────────────────
from app.graph.nodes.credit import (
    loan_init_node,
    loan_collecting_profile_node,
    loan_collecting_simulation_node,
    loan_risk_engine_node,
    loan_pre_approved_node,
    loan_otp_validation_node,
    loan_formalization_node,
    loan_completed_node,
    loan_rejected_policy_node,
    loan_security_block_node,
    loan_closed_by_user_node,
)

# ── Importar funciones de ruteo del crédito ─────────────────
from app.graph.edges import (
    # ... (existentes)
    route_after_loan_init,
    route_after_collecting_profile,
    route_after_collecting_simulation,
    route_after_risk_engine,
    route_after_pre_approved,
    route_after_otp_validation,
    route_after_formalization,
)
```

Dentro de `build_graph()`:

```python
# ── Nodos de Crédito ──────────────────────────────────────────
graph.add_node("loan_init",                  loan_init_node)
graph.add_node("loan_collecting_profile",    loan_collecting_profile_node)
graph.add_node("loan_collecting_simulation", loan_collecting_simulation_node)
graph.add_node("loan_risk_engine",           loan_risk_engine_node)
graph.add_node("loan_pre_approved",          loan_pre_approved_node)
graph.add_node("loan_otp_validation",        loan_otp_validation_node)
graph.add_node("loan_formalization",         loan_formalization_node)
graph.add_node("loan_completed",             loan_completed_node)
graph.add_node("loan_rejected_policy",       loan_rejected_policy_node)
graph.add_node("loan_security_block",        loan_security_block_node)
graph.add_node("loan_closed_by_user",        loan_closed_by_user_node)

# ── Punto de entrada del crédito (reemplaza el stub loan_init) ──
# El nodo "loan_init" del workflow actual redirige a "loan_init"
# Estrategia: Renombrar loan_init_node a loan_init_node directamente.
# ATENCIÓN: Si el stub "loan_init" ya está en el grafo del welcome flow,
# evaluar si conviene mantener el nombre o actualizar el edge de bienvenida.
# Documentar la decisión en el CP.

# ── Aristas Condicionales del Crédito ────────────────────────
graph.add_conditional_edges(
    "loan_init",
    route_after_loan_init,
    {"loan_collecting_profile": "loan_collecting_profile",
     "loan_rejected_policy": "loan_rejected_policy"}
)
graph.add_conditional_edges(
    "loan_collecting_profile",
    route_after_collecting_profile,
    {"loan_collecting_profile": "loan_collecting_profile",
     "loan_collecting_simulation": "loan_collecting_simulation"}
)
graph.add_conditional_edges(
    "loan_collecting_simulation",
    route_after_collecting_simulation,
    {"loan_collecting_simulation": "loan_collecting_simulation",
     "loan_risk_engine": "loan_risk_engine"}
)
graph.add_conditional_edges(
    "loan_risk_engine",
    route_after_risk_engine,
    {"loan_pre_approved": "loan_pre_approved",
     "loan_rejected_policy": "loan_rejected_policy"}
)
graph.add_conditional_edges(
    "loan_pre_approved",
    route_after_pre_approved,
    {"loan_otp_validation": "loan_otp_validation",
     "loan_closed_by_user": "loan_closed_by_user",
     "loan_pre_approved": "loan_pre_approved"}
)
graph.add_conditional_edges(
    "loan_otp_validation",
    route_after_otp_validation,
    {"loan_formalization": "loan_formalization",
     "loan_otp_validation": "loan_otp_validation",
     "loan_security_block": "loan_security_block"}
)
graph.add_conditional_edges(
    "loan_formalization",
    route_after_formalization,
    {"loan_completed": "loan_completed",
     "loan_rejected_policy": "loan_rejected_policy"}
)

# ── Aristas Finales (nodos terminales) ─────────────────────
graph.add_edge("loan_completed",       END)
graph.add_edge("loan_rejected_policy", END)
graph.add_edge("loan_security_block",  END)
graph.add_edge("loan_closed_by_user",  END)
```

**Decisión técnica crítica a documentar:** El nodo `"loan_init"` del grafo actual (stub de Fase 1) y su relación con `"loan_init"`. Opciones:
- a) Renombrar `"loan_init"` a `"loan_init"` en todo el grafo (requiere actualizar `route_after_welcome` en `edges.py`).
- b) Mantener `"loan_init"` como pass-through que llama a `loan_init_node`.

El agente debe elegir la opción A (renombrar) por ser más limpia, pero debe documentarlo en el CP y verificar que no rompe el ruteo de bienvenida.

**Verificación de nomenclatura:** Todos los nombres de nodo registrados en `add_node` deben ser consistentes con los nombres retornados por las funciones de ruteo en `edges.py`.

**Reporte al CP-07:** Sección "Sub-paso 7.2" con el grafo completo del crédito (nodos + aristas).

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 7.3.

---

## Sub-paso 7.3 — Verificar emisión de eventos SSE `node_transition`

**Archivo:** `app/api/v1/chat.py` (solo lectura — verificar sin modificar si es posible)

**Tarea:** Verificar (no modificar) que el generador de streaming SSE existente emite eventos `node_transition` basándose en el campo `session["current_node"]` del State. Si el mecanismo de emisión ya funciona automáticamente al detectar cambios en el State, el agente solo debe confirmar que cada nodo implementado en los pasos anteriores actualiza correctamente `session["current_node"]` al inicio.

Realizar la siguiente verificación en el CP:
- Para cada nodo implementado, confirmar que la primera acción es `_update_node_gps(state, "NOMBRE_NODO")`.
- Listar en el CP los nodos que emiten su GPS y los que eventualmente no lo hacen.

Si se detecta que algún nodo no actualiza el GPS, corregirlo sin modificar `chat.py`.

**Reporte al CP-07:** Sección "Sub-paso 7.3" con la tabla de verificación GPS por nodo.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para Sub-paso 7.4.

---

## Sub-paso 7.4 — Verificar que el servidor FastAPI levanta sin errores

**Tarea:** Ejecutar el servidor en modo local y verificar que no hay errores de importación ni de compilación del grafo.

```bash
cd /backend
uvicorn main:app --reload --port 8000
```

El agente debe:
1. Verificar que el servidor inicia sin excepciones.
2. Verificar que el grafo se compila correctamente (acceder al endpoint de salud si existe, o ejecutar `get_active_graph()` en un script de prueba).
3. Si hay errores de importación circular u otros, resolverlos antes de continuar.

**Reporte al CP-07:** Sección "Sub-paso 7.4" con el log de inicio del servidor.

⛔ **DETENCIÓN OBLIGATORIA.** Solicitar confirmación para el Checkpoint 7.

---

## ✅ CHECKPOINT 7 — Pruebas de Integración End-to-End del Grafo

**Archivo de pruebas:** `tests/fase2-dev1/test_credit_flow_integration.py`

Este checkpoint es el más crítico: prueba el flujo completo del crédito a través del grafo de LangGraph.

### Test 7.A — Compilación del grafo
```python
# Objetivo: Verificar que el grafo compila sin errores.
# Diseño: Llamar a get_active_graph() y verificar que retorna un CompiledGraph.
# Resultado esperado: No hay excepciones. La instancia es de tipo CompiledGraph.
```

### Test 7.B — Ruteo: INTENT_ROUTER → LOAN_INIT
```python
# Objetivo: Verificar que el grafo enruta correctamente desde la intención de crédito.
# Diseño: Invocar el grafo con un mensaje de usuario "quiero un crédito de consumo".
#         Usar un thread_id de prueba y un state con user_data completo.
# Resultado esperado: El estado del grafo después de la ejecución tiene
#                     session["current_node"] == "LOAN_COLLECTING_PROFILE"
#                     (LOAN_INIT completó y avanzó automáticamente).
```

### Test 7.C — Ciclo de recolección: re-entrada por datos incompletos
```python
# Objetivo: Verificar que el edge condicional re-entra al nodo si los datos están incompletos.
# Diseño: Primer mensaje: "gano 1 millón". Segundo mensaje: "llevo 2 años, soy universitario".
# Resultado esperado:
#   - Después del 1er mensaje: current_node = "LOAN_COLLECTING_PROFILE"
#     (re-entrada porque falta antigüedad y estudios).
#   - Después del 2do mensaje: current_node = "LOAN_COLLECTING_SIMULATION"
#     (avanza porque los datos están completos).
```

### Test 7.D — Flujo Happy Path completo (simulado)
```python
# Objetivo: Recorrer todos los nodos del flujo exitoso usando mocks donde sea necesario.
# Diseño:
#   1. Ingresar datos de perfil (renta=2MM, 24 meses, UNIVERSITARIO).
#   2. Ingresar monto y plazo (5MM, 24 cuotas).
#   3. Verificar que LOAN_RISK_ENGINE produce PRE_APPROVED.
#   4. Simular aceptación de oferta (mensaje "OFFER_ACCEPTED").
#   5. Simular OTP correcto.
#   6. Verificar que LOAN_FORMALIZATION completa con mock PDF.
#   7. Verificar LOAN_COMPLETED y cierre.
# Resultado esperado:
#   - financial_applications.status_code = "COMPLETED" en la DB.
#   - documents: 1 registro con is_active=True.
#   - conversations.is_active = False.
```

### Test 7.E — Flujo de rechazo por capacidad de pago
```python
# Objetivo: Verificar el flujo completo hasta LOAN_REJECTED_POLICY.
# Diseño: Perfil con renta=600.000, solicitar 20MM a 6 meses.
# Resultado esperado:
#   - LOAN_RISK_ENGINE produce REJECTED_POLICY con ERR_CAPACIDAD_PAGO.
#   - El grafo termina en loan_rejected_policy.
#   - financial_applications.status_code = "REJECTED".
```

### Test 7.F — Persistencia y reanudación (Checkpointer)
```python
# Objetivo: Verificar que el estado persiste entre invocaciones del grafo.
# Diseño:
#   1. Ingresar datos de perfil en una primera invocación.
#   2. "Cerrar la sesión" (no llamar al grafo por un rato).
#   3. Invocar el grafo nuevamente con el mismo thread_id y un nuevo mensaje.
# Resultado esperado: El grafo retoma desde LOAN_COLLECTING_SIMULATION
#                     (los datos de perfil persisten en el checkpointer).
```

### Test 7.G — Eventos SSE `node_transition` durante el streaming
```python
# Objetivo: Verificar que los eventos SSE se emiten con los nombres de nodo correctos.
# Diseño: Consumir el stream del endpoint /api/v1/chat durante una interacción.
# Resultado esperado: Se emiten eventos de tipo "node_transition" con
#                     current_node = "LOAN_INIT", "LOAN_COLLECTING_PROFILE", etc.
#                     en el orden correcto del flujo.
```

**Instrucción de ejecución:**
```bash
cd /backend
python -m pytest tests/fase2-dev1/test_credit_flow_integration.py -v --timeout=60
```

**Reporte de Cierre del Paso 7 en CP-07:** Sección "REPORTE COMPLETO — PASO 7" con:
- Resultado de cada test (Objetivo / Resultado Real / ¿Pasa? / Interpretación).
- Diagrama ASCII del flujo del grafo implementado.
- Decisiones técnicas tomadas durante la integración.
- Mocks activos pendientes de reemplazo por entregables de Dev 3.

Commit final: `feat: integrar flujo completo de crédito en workflow.py y edges.py`

⛔ **DETENCIÓN OBLIGATORIA.** Reportar resultado del Checkpoint 7 y solicitar confirmación del desarrollador para declarar la Fase 2 del Dev 1 como **COMPLETADA**.

---

---

## CIERRE DE LA FASE 2 — Dev 1

Al completar todos los pasos, el agente debe:

1. **Consolidar todos los CPs** en un resumen ejecutivo en el archivo `tests/fase2-dev1/RESUMEN-FASE2-DEV1.md`.

2. **Lista de Mocks Activos** (pendientes de reemplazo por Dev 3):
   - `_mock_generate_otp()` y `_mock_send_otp_email()` en `nodes/credit.py`.
   - `_mock_generate_pdf()` en `nodes/credit.py`.

3. **Contratos de Interfaz a comunicar:**
   - Al **Dev 2 (FE):** Protocolo de mensajes `TRANSPARENCY_CARD`, `OTP_INPUT_WIDGET`, `COMPLETION_CARD` y el protocolo `OFFER_ACCEPTED`/`OFFER_REJECTED`.
   - Al **Dev 3 (Secure):** Protocolo de hashing SHA-256 para OTP (usando `hashlib`), contrato de llamada a `pdf_factory.generate_loan_contract()`.

4. **Pull Request a `main`:** El PR debe pasar el checklist:
   - [ ] El servidor FastAPI levanta sin errores.
   - [ ] Los 7 Checkpoints tienen todos sus tests en verde.
   - [ ] Todos los nodos actualizan `session["current_node"]`.
   - [ ] Todos los nodos de servicio actualizan `financial_applications`.
   - [ ] No hay strings hardcodeados que debieran ser FKs a catálogos.
   - [ ] `state.py` no fue modificado.

5. Commit final: `chore: cerrar fase2 dev1 - flujo completo crédito de consumo`

⛔ **DETENCIÓN FINAL.** Presentar al desarrollador el resumen de la Fase 2 y solicitar revisión del PR antes del merge a `main`.

---

*Documento generado para uso exclusivo del agente Antigravity bajo supervisión del Dev 1 (Human). Versión: 1.0 · FLUX Phase 2.*
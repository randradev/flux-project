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
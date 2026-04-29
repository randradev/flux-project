# Bitácora de Vuelo - Fase 2, FIX LLM, Paso 8: Estabilización de Extracción y Flujo de Continuidad

**ID del Reporte:** CP-08-fase2-llm  
**Proyecto:** FLUX  
**Módulo:** Crédito  
**Objetivo:** Documentar la arquitectura final de extracción estructurada, el blindaje contra alucinaciones (Rule of 0/DESCONOCIDO), la continuidad conversacional entre nodos y la integración del motor de riesgo real.

---

## 1. RESUMEN DE CAMBIOS ARQUITECTÓNICOS

### A. Blindaje de Extracción (Chain of Thought + Centinelas)
Se implementó un patrón de "Doble Blindaje" para eliminar alucinaciones del LLM cuando el usuario no entrega todos los datos.
- **Campo `razonamiento`:** Se agregó como primer campo en los esquemas Pydantic. Obliga al modelo a realizar un razonamiento verbal antes de asignar valores numéricos.
- **Regla del Cero (Sentinela Numérico):** Se instruyó al LLM a devolver `0` en campos financieros ausentes (renta, antigüedad, monto, plazo) en lugar de `null`, ya que los LLM tienden a alucinar valores cuando ven un campo opcional.
- **Regla del 'DESCONOCIDO' (Sentinela de Literal):** Para el nivel de estudios, se agregó la opción `DESCONOCIDO` al Literal. Esto evita que el modelo elija una opción al azar (alucinación por fobia al null).

### B. Continuidad Conversacional (Memoria de Transición)
Para evitar que Flux salude como un extraño al cambiar de nodo, se implementó un sistema de flags de sesión.
- **Flag `profile_just_completed`:** El nodo de Perfil lo activa al finalizar. El nodo de Simulación lo lee, agradece el paso anterior y lo apaga inmediatamente.
- **Inyección de `last_user_msg`:** El generador de respuestas ahora "ve" el último mensaje del usuario, permitiendo que Flux responda: *"¡Te entendí lo de los 2 millones! Pero me faltó saber el plazo"* en lugar de un genérico *"¿Qué plazo quieres?"*.

---

## 2. DETALLE DE ARCHIVOS Y FUNCIONALIDADES

### 📂 `backend/app/graph/nodes/schemas/loan_schemas.py`
- **Clases:** `LoanProfileExtraction`, `LoanSimExtraction`.
- **Cambios:**
    - Inclusión de `razonamiento: str = Field(default="")`.
    - Agregado `"DESCONOCIDO"` a `Literal` de `nivel_estudios`.
    - **Validadores Pydantic:** Se implementaron `clean_finance_data` y `clean_estudios` que convierten los `0` y `"DESCONOCIDO"` de vuelta a `None` para mantener la pureza del `State`.

### 📂 `backend/app/graph/nodes/credit.py`
- **Funciones:** `loan_collecting_profile_node`, `loan_collecting_sim_node`.
- **Merge Defensivo Robusto:** Refactorización de la lógica de integración para que solo los datos explícitamente detectados actualicen el `State`, evitando sobrescrituras accidentales.
- **Context Builders:** Actualización de `_build_profile_generation_context` y `_build_sim_generation_context` para incluir `last_msg` y `razonamiento`, permitiendo respuestas más humanas.
- **Nodo de Riesgo Real:** Se reemplazó el mock en `loan_risk_engine_node` por la clase `CreditEngine` de `app.modules.credit_eng`, manejando excepciones de negocio (`PolicyRejectionError`, `PaymentCapacityError`).

### 📂 `backend/app/graph/nodes/credit.py` (Prompts)
- **Extracción:** Se añadieron instrucciones de conversión (Años a Meses, Mapeo de Profesiones a Grados Académicos) y un "Ejemplo Dorado" multi-variable.
- **Generación:** Se añadieron instrucciones de resiliencia para manejar fallos de extracción de forma simpática y no repetitiva.

---

## 3. PROCESOS AJENOS A LA EXTRACCIÓN
- **Integración del Motor de Riesgo:** Este cambio implica la comunicación con la lógica de negocio pura. Se implementó un wrapper de excepciones que traduce errores técnicos y de política en estados de proceso (`PRE_APPROVED`, `REJECTED`, `ERROR`).
- **Actualización de Semáforos:** Se integró la llamada a `update_application_semaphores` en el motor de riesgo para persistir el estado del motor en la base de datos (Supabase/Postgres).

---

## 4. ESTADO FINAL DE VERIFICACIÓN
- **Prueba End-to-End:** Superada exitosamente en `loan_playground-2.py`.
- **Hallucinaciones:** 0% detectadas en pruebas de estrés de datos faltantes.
- **Sensación de Continuidad:** Lograda mediante el paso de contexto histórico al generador.

> [!IMPORTANT]
> Para futuros nodos de extracción (ej. Seguros, Depósitos), se DEBE replicar el patrón de **Chain of Thought (razonamiento)** y **Sentinelas (0/DESCONOCIDO)** para garantizar la estabilidad del grafo.

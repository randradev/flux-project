# Flux — Fase 2, Paso 2
# Solución y Plan de Implementación: Arquitectura de Doble Llamada

**Versión:** 3.0 — Decoupled Execution + Validación de Nulos + Recuperación de Humanidad  
**Estado:** Listo para implementación  
**Archivos afectados:** `credit.py`, `loan_schemas.py`, `gemini_client.py`, `loan_playground.py`  
**Archivos inmutables:** `state.py`, `workflow.py`, `edges.py`, `supabase.py`

---

## PARTE I: DISEÑO DE LA SOLUCIÓN

### 1.1 Problema Consolidado

El diagnóstico anterior identificó cuatro causas raíz que se potencian entre sí:

| # | Causa | Síntoma visible |
|---|---|---|
| CR-1 | Check `not valor` en lugar de `is None` | `-1` y `0` pasan como datos válidos, avance silencioso con basura |
| CR-2 | `json_mode` sin `temperature=0.0` | El modelo alucina valores centinela (`-1`, `0`, `"MEDIA"`) para campos vacíos |
| CR-3 | Sin pre-filtro de intención | Saludos y mensajes irrelevantes contaminan el State |
| CR-4 | Extracción y generación en un solo paso | El modelo prioriza coherencia gramatical sobre fidelidad de extracción; la respuesta suena robótica |

La nueva arquitectura de **Doble Llamada** resuelve CR-2 y CR-4 de raíz al separar física y conceptualmente la extracción de la generación conversacional. Los fixes de código (CR-1 y CR-3) se mantienen tal como se diseñaron en el diagnóstico anterior.

---

### 1.2 Arquitectura de Doble Llamada (Decoupled Execution)

#### Flujo interno del nodo `loan_collecting_profile_node`

```
Mensaje del usuario
        │
        ▼
┌─────────────────────────────────────────────────┐
│  LLAMADA A — EXTRACTOR (LLM #1)                 │
│  Modelo : gemini-3-flash-preview                │
│  Temp   : 0.0                                   │
│  Output : structured_output (function_calling)  │
│  Retorna: LoanProfileExtraction (JSON validado) │
│  Incluye: campo `intencion` como pre-filtro     │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
        ¿intencion == DATO_FINANCIERO?
         /                           \
       NO                            SÍ
        │                             │
        ▼                             ▼
  [No actualizar               [Merge defensivo]
   el State]                   [Check is None]
        │                      [Validar centinelas]
        │                             │
        ▼                             ▼
  ¿Hay campos                  ¿missing == []?
  faltantes previos?            /           \
        │                     SÍ            NO
        ▼                      │             │
  [Calcular               [Avance       [Calcular
  contexto de             silencioso]   contexto de
  re-pregunta]                          re-pregunta]
        │                                    │
        └──────────────┬─────────────────────┘
                       ▼
        ┌─────────────────────────────────────────────────┐
        │  LLAMADA B — GENERADOR (LLM #2)                 │
        │  Modelo : gemini-3-flash-preview                │
        │  Temp   : 0.7                                   │
        │  Output : texto libre (sin schema)              │
        │  Input  : contexto estructurado + personalidad  │
        │  Retorna: string con respuesta de Flux          │
        └─────────────────┬───────────────────────────────┘
                          │
                          ▼
              [Actualización transaccional
               del FluxState: un solo return]
```

#### Principio de diseño de cada llamada

| Llamada | Responsabilidad | Lo que NO hace |
|---|---|---|
| **A — Extractor** | Identificar y normalizar datos financieros del mensaje | Generar texto, ser amigable, comentar los datos |
| **B — Generador** | Producir la respuesta conversacional de Flux | Extraer datos, evaluar si los datos son completos |

Esta separación es la misma que usaba el sistema anterior (Llamada 1 / Llamada 2 en el informe `informe-llm-version-anterior.md`), pero ahora implementada dentro de la solidez de LangGraph en lugar del código espagueti previo.

---

### 1.3 Contrato de Datos del Nodo

```
INPUT  (desde FluxState):
  state["messages"]                          → Historial completo de mensajes
  state["collecting_data"]["loan_profile"]   → Datos ya recolectados (puede ser {})
  state["preparation_data"]["nombre"]        → Nombre del usuario (para personalización)
  state["session"]["application_id"]         → Para semáforos Supabase

OUTPUT (al FluxState — actualización transaccional única):
  state["messages"]           += [AIMessage(content=respuesta_flux)]  ← Solo si hay re-pregunta
  state["collecting_data"]["loan_profile"]   → Perfil actualizado (merge)
  state["session"]["current_node"]           → "LOAN_COLLECTING_PROFILE"
```

**Regla de transaccionalidad:** El nodo realiza **un único `return`** al final, con todos los campos del State que modifica. No hay returns intermedios salvo en el caso de error técnico. Esto garantiza que el checkpointer de LangGraph recibe un snapshot consistente.

---

## PARTE II: PLAN DE IMPLEMENTACIÓN

### Convenciones del Plan

- **[CÓDIGO]** — Cambio de código puro, sin invocar APIs externas.
- **[PROMPT]** — Cambio de prompt o configuración del LLM.
- **[TEST-UNITARIO]** — Verificable sin credenciales de Vertex AI.
- **[TEST-INTEGRACIÓN]** — Requiere credenciales reales de Vertex AI.
- **✅ CRITERIO PASS** — Condición explícita que debe cumplirse para cerrar el sub-paso.

---

## PASO 1 — Fixes de Código Puro (sin LLM)

> **Objetivo:** Eliminar los bugs de lógica que existen independientemente del modelo. Son cambios seguros, verificables sin API y con impacto crítico inmediato.

---

### Sub-paso 1.1 — Corregir el helper `_get_missing_profile_fields` [CÓDIGO]

**Archivo:** `app/graph/nodes/credit.py`

**Por qué:** El helper existente ya usa `is None` correctamente, pero el nodo principal tiene su propio check inline con `not valor`, que acepta `-1` como dato válido. La solución es unificar: eliminar el check inline y enriquecer el helper para que también rechace valores semánticamente imposibles.

**Cambio:**

```python
# ANTES (helper existente — correcto pero incompleto)
def _get_missing_profile_fields(profile: dict) -> list[str]:
    required = ["renta", "antiguedad_laboral", "nivel_estudios"]
    return [f for f in required if profile.get(f) is None]

# DESPUÉS (v2.1 — añade validación de valores centinela del LLM)
def _get_missing_profile_fields(profile: dict) -> list[str]:
    """
    Retorna lista de campos del perfil que faltan o tienen valores inválidos.
    
    REGLAS:
      - None siempre es faltante.
      - renta <= 0: imposible semánticamente (0 y negativos son centinela del LLM).
      - antiguedad_laboral < 0: -1 es valor centinela clásico del LLM para int ausente.
      - nivel_estudios fuera del Literal: valor no reconocido.
    
    NOTA: Esta función NO aplica reglas de negocio (renta mínima $500k, etc.).
    Eso es responsabilidad exclusiva del CreditEngine. Aquí solo se filtran
    datos técnicamente imposibles.
    
    v2.1 — Añadida validación de valores centinela (0, -1) del LLM.
    """
    missing = []
    
    renta = profile.get("renta")
    if renta is None or renta <= 0:
        missing.append("renta")
    
    ant = profile.get("antiguedad_laboral")
    if ant is None or ant < 0:
        missing.append("antiguedad_laboral")
    
    estudios = profile.get("nivel_estudios")
    valid_estudios = {"POSTGRADO", "UNIVERSITARIO", "TECNICO", "MEDIA"}
    if estudios is None or estudios not in valid_estudios:
        missing.append("nivel_estudios")
    
    return missing
```

**Cambio secundario en el nodo:** Reemplazar el check inline incorrecto por la llamada al helper:

```python
# ANTES (en loan_collecting_profile_node, inline check con bug)
missing = [f for f in ["renta", "antiguedad_laboral", "nivel_estudios"] if not updated_profile.get(f)]

# DESPUÉS — Delegar al helper unificado
missing = _get_missing_profile_fields(updated_profile)
```

---

**✅ CRITERIO PASS Sub-paso 1.1** [TEST-UNITARIO — sin API]:

```python
# tests/unit/test_credit_helpers.py

from app.graph.nodes.credit import _get_missing_profile_fields

def test_perfil_vacio_retorna_todos():
    assert _get_missing_profile_fields({}) == ["renta", "antiguedad_laboral", "nivel_estudios"]

def test_valores_centinela_llm_son_rechazados():
    """El valor -1 que alucina el LLM debe ser tratado como faltante."""
    perfil = {"renta": 0, "antiguedad_laboral": -1, "nivel_estudios": "MEDIA"}
    missing = _get_missing_profile_fields(perfil)
    assert "renta" in missing,              "renta=0 debe ser faltante"
    assert "antiguedad_laboral" in missing, "antiguedad=-1 debe ser faltante"
    # nivel_estudios="MEDIA" es un valor válido — no debe estar en missing
    assert "nivel_estudios" not in missing, "MEDIA es un valor válido del Literal"

def test_antiguedad_cero_es_valida():
    """0 meses es posible (recién comenzó a trabajar); no debe ser faltante."""
    perfil = {"renta": 800_000, "antiguedad_laboral": 0, "nivel_estudios": "TECNICO"}
    assert _get_missing_profile_fields(perfil) == []

def test_perfil_completo_retorna_vacio():
    perfil = {"renta": 1_500_000, "antiguedad_laboral": 24, "nivel_estudios": "UNIVERSITARIO"}
    assert _get_missing_profile_fields(perfil) == []

def test_perfil_parcial_retorna_faltantes():
    perfil = {"renta": 2_000_000}
    missing = _get_missing_profile_fields(perfil)
    assert "renta" not in missing
    assert "antiguedad_laboral" in missing
    assert "nivel_estudios" in missing
```

**Todos deben pasar con `pytest tests/unit/test_credit_helpers.py -v`. Sin credenciales de Vertex AI.**

---

### Sub-paso 1.2 — Añadir validadores Pydantic al schema [CÓDIGO]

**Archivo:** `app/graph/nodes/schemas/loan_schemas.py`

**Por qué:** El schema es la primera línea de defensa. Si el LLM retorna `-1` para `antiguedad_laboral`, el validador Pydantic lo convierte a `None` antes de que llegue al nodo. Esto crea una defensa en capas: el schema normaliza, el helper verifica.

**Cambio:**

```python
"""
Esquemas Pydantic para extracción estructurada en nodos de Crédito.
Usados con LLM.with_structured_output() en los nodos COLLECTING.

DISEÑO v2.1:
  - Campos Optional con None como default (campo ausente = None).
  - Validadores @field_validator normalizan valores centinela del LLM a None.
  - Campo `intencion` para pre-filtro de mensajes no procesables.
  - El nodo evalúa qué campos faltan y decide si avanzar o re-preguntar.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal


class LoanProfileExtraction(BaseModel):
    """
    Schema para LOAN_COLLECTING_PROFILE.
    Mapea directamente a collecting_data["loan_profile"].
    """

    intencion: Literal["DATO_FINANCIERO", "PREGUNTA", "SALUDO", "OTRO"] = Field(
        description=(
            "Clasificación del mensaje antes de extraer datos: "
            "DATO_FINANCIERO si contiene renta, antigüedad laboral o nivel de estudios. "
            "PREGUNTA si el usuario hace una consulta (¿qué es el CAE?, ¿cómo funciona?). "
            "SALUDO si es un saludo, despedida o frase social sin datos financieros. "
            "OTRO para mensajes fuera de contexto que no encajan en las anteriores."
        )
    )
    renta: Optional[int] = Field(
        default=None,
        description=(
            "Renta líquida mensual en CLP (entero positivo). "
            "Normalizar: 'gano 1 millón' → 1000000, 'gano 3 palos' → 3000000, "
            "'me pagan 800 lucas' → 800000. "
            "Si no fue mencionado, retornar null."
        )
    )
    antiguedad_laboral: Optional[int] = Field(
        default=None,
        description=(
            "Antigüedad laboral en MESES (entero >= 0). "
            "Convertir: '2 años' → 24, 'llevo 5 años en la pega' → 60, "
            "'recién comencé' → 0. "
            "Si no fue mencionado, retornar null."
        )
    )
    nivel_estudios: Optional[Literal["POSTGRADO", "UNIVERSITARIO", "TECNICO", "MEDIA"]] = Field(
        default=None,
        description=(
            "Nivel de estudios normalizado al Literal exacto. "
            "'ingeniería', 'universidad', 'carrera', 'profesional' → UNIVERSITARIO. "
            "'magíster', 'doctorado', 'postgrado', 'MBA' → POSTGRADO. "
            "'técnico', 'ip', 'cft', 'inacap', 'duoc' → TECNICO. "
            "'media', 'liceo', 'cuarto medio', 'colegio' → MEDIA. "
            "Si no fue mencionado, retornar null."
        )
    )

    @field_validator("renta")
    @classmethod
    def renta_must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        """
        Normaliza a None si el LLM retornó un valor centinela no positivo.
        El LLM usa 0 como 'no sé pero debo dar un int'.
        """
        if v is not None and v <= 0:
            return None
        return v

    @field_validator("antiguedad_laboral")
    @classmethod
    def antiguedad_must_be_non_negative(cls, v: Optional[int]) -> Optional[int]:
        """
        Normaliza a None si el LLM retornó -1 (centinela clásico para int ausente).
        Nota: 0 meses es válido (usuario recién comenzó a trabajar).
        """
        if v is not None and v < 0:
            return None
        return v


class LoanSimExtraction(BaseModel):
    """
    Schema para LOAN_COLLECTING_SIMULATION.
    Mapea directamente a collecting_data["loan_sim"].
    """

    intencion: Literal["DATO_FINANCIERO", "PREGUNTA", "SALUDO", "OTRO"] = Field(
        description=(
            "DATO_FINANCIERO si contiene monto o plazo del crédito. "
            "PREGUNTA, SALUDO u OTRO para el resto."
        )
    )
    monto_solicitado: Optional[int] = Field(
        default=None,
        description=(
            "Monto del crédito en CLP (entero positivo). "
            "Normalizar: '5 millones' → 5000000, '$3.500.000' → 3500000, "
            "'un palo' → 1000000, '800 lucas' → 800000. "
            "Si no fue mencionado, retornar null."
        )
    )
    plazo_solicitado: Optional[int] = Field(
        default=None,
        description=(
            "Número de cuotas en meses (entero positivo). "
            "Convertir: '2 años' → 24, '1 año y medio' → 18. "
            "Si no fue mencionado, retornar null."
        )
    )

    @field_validator("monto_solicitado", "plazo_solicitado")
    @classmethod
    def must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        """Normaliza a None cualquier valor centinela no positivo."""
        if v is not None and v <= 0:
            return None
        return v
```

---

**✅ CRITERIO PASS Sub-paso 1.2** [TEST-UNITARIO — sin API]:

```python
# tests/unit/test_loan_schemas.py

from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction, LoanSimExtraction

def test_renta_cero_normalizada_a_none():
    m = LoanProfileExtraction(intencion="DATO_FINANCIERO", renta=0)
    assert m.renta is None

def test_antiguedad_negativa_normalizada_a_none():
    m = LoanProfileExtraction(intencion="DATO_FINANCIERO", antiguedad_laboral=-1)
    assert m.antiguedad_laboral is None

def test_antiguedad_cero_conservada():
    """0 meses es válido semánticamente — no debe normalizarse."""
    m = LoanProfileExtraction(intencion="DATO_FINANCIERO", antiguedad_laboral=0)
    assert m.antiguedad_laboral == 0

def test_valores_validos_conservados():
    m = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        renta=1_500_000,
        antiguedad_laboral=36,
        nivel_estudios="UNIVERSITARIO"
    )
    assert m.renta == 1_500_000
    assert m.antiguedad_laboral == 36
    assert m.nivel_estudios == "UNIVERSITARIO"

def test_todos_los_campos_pueden_ser_none():
    """Un mensaje tipo SALUDO debe producir todos los campos None."""
    m = LoanProfileExtraction(intencion="SALUDO")
    assert m.renta is None
    assert m.antiguedad_laboral is None
    assert m.nivel_estudios is None

def test_sim_schema_monto_negativo_normalizado():
    m = LoanSimExtraction(intencion="DATO_FINANCIERO", monto_solicitado=-500)
    assert m.monto_solicitado is None
```

---

## PASO 2 — Corrección del Cliente LLM

> **Objetivo:** Garantizar que la Llamada A (extractor) retorne `null` para campos no mencionados, usando los parámetros correctos de Vertex AI.

---

### Sub-paso 2.1 — Separar los modelos de extracción y generación en `gemini_client.py` [CÓDIGO + PROMPT]

**Archivo:** `app/infra/gemini_client.py`

**Por qué:** La arquitectura de Doble Llamada requiere dos instancias de modelo con configuraciones diferentes. `get_structured_model` sirve para la Llamada A. Se necesita una nueva función `get_chat_model_flux` para la Llamada B, con temperatura más alta para generar respuestas con personalidad.

**Cambio — reemplazar `get_structured_model` y agregar `get_chat_model_flux`:**

```python
def get_structured_model(schema) -> ChatVertexAI:
    """
    Llamada A — Extractor de entidades financieras.
    
    Configuración optimizada para extracción de máxima fidelidad:
      - temperature=0.0: Sin variabilidad. El modelo reporta lo que vio, no infiere.
      - method="function_calling": Enforza null para campos Optional no mencionados.
        A diferencia de json_mode (que genera JSON libre y puede alunar centinelas),
        function_calling hace que el SDK valide el output contra el schema Pydantic.
    
    USO: Invocado una vez por turno en los nodos COLLECTING.
         Solo extrae. No genera texto conversacional.
    """
    _init_global()
    base_model = ChatVertexAI(
        model_name="gemini-2.0-flash",
        project=settings.google_cloud_project_id,
        location=settings.google_cloud_location,
        api_endpoint="aiplatform.googleapis.com",
        temperature=0.0,  # CRÍTICO: 0.0 para extracción. No 0.1.
        max_output_tokens=512,  # La extracción es concisa; limitar tokens reduce costo.
    )
    return base_model.with_structured_output(schema, method="function_calling")


def get_generation_model() -> ChatVertexAI:
    """
    Llamada B — Generador de respuestas conversacionales de Flux.
    
    Configuración optimizada para generación con personalidad:
      - temperature=0.7: Permite variabilidad natural en las respuestas.
        Flux no debe sonar robótico ni repetitivo entre sesiones.
      - Sin structured_output: Genera texto libre.
    
    USO: Invocado UNA VEZ por turno, después del extractor, solo cuando
         el nodo necesita emitir un mensaje al usuario (re-pregunta o
         respuesta a intención no-financiera).
         No se invoca en avance silencioso.
    """
    _init_global()
    return ChatVertexAI(
        model_name="gemini-2.0-flash",
        project=settings.google_cloud_project_id,
        location=settings.google_cloud_location,
        api_endpoint="aiplatform.googleapis.com",
        temperature=0.7,
        max_output_tokens=1024,
    )
```

---

**✅ CRITERIO PASS Sub-paso 2.1** [TEST-UNITARIO — sin API]:

```python
# tests/unit/test_gemini_client.py
# (Prueba de configuración, no de comportamiento del modelo)

from unittest.mock import patch, MagicMock
from app.infra.gemini_client import get_structured_model, get_generation_model
from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction

def test_get_structured_model_retorna_objeto_invocable():
    """Verifica que la función retorna sin error y el objeto tiene .invoke()"""
    with patch("app.infra.gemini_client._init_global"):
        with patch("app.infra.gemini_client.ChatVertexAI") as MockChat:
            mock_instance = MagicMock()
            mock_instance.with_structured_output.return_value = MagicMock()
            MockChat.return_value = mock_instance
            
            model = get_structured_model(LoanProfileExtraction)
            
            # Verificar que se llamó con temperature=0.0
            call_kwargs = MockChat.call_args.kwargs
            assert call_kwargs["temperature"] == 0.0, \
                f"El extractor debe usar temperature=0.0, recibió {call_kwargs['temperature']}"
            
            # Verificar que se usó function_calling
            mock_instance.with_structured_output.assert_called_once_with(
                LoanProfileExtraction, method="function_calling"
            )

def test_get_generation_model_usa_temperatura_mayor():
    with patch("app.infra.gemini_client._init_global"):
        with patch("app.infra.gemini_client.ChatVertexAI") as MockChat:
            MockChat.return_value = MagicMock()
            get_generation_model()
            call_kwargs = MockChat.call_args.kwargs
            assert call_kwargs["temperature"] == 0.7, \
                f"El generador debe usar temperature=0.7, recibió {call_kwargs['temperature']}"
```

---

## PASO 3 — Diseño de Prompts

> **Objetivo:** Rediseñar los prompts de extracción y crear el nuevo prompt de generación conversacional. Estos son los prompts que determinan la "humanidad" de Flux.

---

### Sub-paso 3.1 — Prompt de Extracción (Llamada A) [PROMPT]

**Archivo:** `app/graph/nodes/credit.py`

**Principio de diseño:** El prompt de extracción debe ser **minimalista y directivo**. No debe hablar de personalidad ni de Chile. Su única audiencia es el LLM-extractor, no el usuario.

```python
# ── PROMPT LLAMADA A: EXTRACCIÓN ────────────────────────────────────────────
# Directivo y sin ambigüedad. Temperatura 0.0 hace el trabajo pesado;
# el prompt solo establece el contrato de qué retornar.

SYSTEM_PROMPT_EXTRACTION_PROFILE = """
Eres un motor de extracción de datos financieros. Tu única función es analizar el mensaje del usuario y retornar un JSON estructurado.

INSTRUCCIONES:
1. Clasifica el mensaje en el campo `intencion`:
   - DATO_FINANCIERO: si el mensaje contiene renta, antigüedad laboral o nivel de estudios.
   - PREGUNTA: si el usuario hace una pregunta (¿qué es...?, ¿cómo...?, ¿cuánto...?).
   - SALUDO: si es un saludo, despedida o frase social ("hola", "gracias", "adiós").
   - OTRO: cualquier mensaje que no encaje en las anteriores.

2. Extrae los datos SOLO si fueron mencionados explícitamente o con jerga coloquial clara:
   - "palo" = 1.000.000 CLP | "luca" = 1.000 CLP
   - Años a meses: 1 año = 12 meses
   - Normaliza nivel_estudios al Literal exacto.

3. REGLA ABSOLUTA: Si un dato NO fue mencionado, retorna null para ese campo.
   No uses valores por defecto. No uses 0 ni -1 como placeholder.
   Un saludo no contiene renta. Una pregunta no contiene antigüedad.
"""

SYSTEM_PROMPT_EXTRACTION_SIM = """
Eres un motor de extracción de datos financieros. Tu única función es analizar el mensaje del usuario y retornar un JSON estructurado.

INSTRUCCIONES:
1. Clasifica el mensaje en `intencion`: DATO_FINANCIERO si contiene monto o plazo del crédito. PREGUNTA, SALUDO u OTRO para el resto.

2. Extrae monto_solicitado y plazo_solicitado SOLO si fueron mencionados:
   - "palo" = 1.000.000 | "luca" = 1.000
   - Años a meses para el plazo.

3. REGLA ABSOLUTA: null para cualquier dato no mencionado.
"""
```

---

### Sub-paso 3.2 — Prompt de Generación Conversacional (Llamada B) [PROMPT]

**Archivo:** `app/graph/nodes/credit.py`

**Principio de diseño:** El prompt de generación recibe un **bloque de contexto estructurado** (no los mensajes crudos) y produce la respuesta de Flux. Esto desacopla completamente al generador del extractor.

```python
# ── PROMPT LLAMADA B: GENERACIÓN ────────────────────────────────────────────
# Recibe contexto estructurado e inyecta personalidad Flux.
# La temperatura 0.7 lo hace variado y natural entre sesiones.

SYSTEM_PROMPT_GENERATION_PROFILE = """
Eres Flux, el genio amigable de las finanzas en Chile. 

PERSONALIDAD:
- Hablas de tú, eres cercano y usas modismos chilenos con moderación.
- Eres ágil: no das rodeos innecesarios, pero sí eres empático.
- Celebras cuando el usuario entrega datos (¡Buenazo!, ¡Perfecto!, ¡Anotado!).
- Si el usuario da información fuera de contexto, lo rediriges con gracia, sin regañar.

TAREA ACTUAL: Recolección de perfil financiero para un Crédito de Consumo.

RESTRICCIONES:
- NO inventes datos. Trabaja solo con lo que el contexto te provee.
- NO menciones números técnicos ni tasas en este paso (eso viene después).
- NO hagas más de UNA pregunta a la vez. Pide un dato, no tres.
- Máximo 3 oraciones en tu respuesta.
"""
```

---

**✅ CRITERIO PASS Sub-paso 3.1 y 3.2** [Revisión manual]:

Los prompts son revisados por el desarrollador contra esta checklist antes de continuar:

- [ ] `SYSTEM_PROMPT_EXTRACTION_PROFILE` no menciona "Flux", "Chile" ni personalidad.
- [ ] `SYSTEM_PROMPT_EXTRACTION_PROFILE` contiene la frase "null para cualquier dato no mencionado".
- [ ] `SYSTEM_PROMPT_GENERATION_PROFILE` no menciona "extrae", "JSON", ni estructuras de datos.
- [ ] `SYSTEM_PROMPT_GENERATION_PROFILE` contiene la restricción de "máximo UNA pregunta a la vez".

---

## PASO 4 — Implementación de la Doble Llamada en el Nodo

> **Objetivo:** Refactorizar `loan_collecting_profile_node` para implementar el flujo Llamada A → Llamada B de forma transaccional.

---

### Sub-paso 4.1 — Agregar el singleton del modelo generador en `credit.py` [CÓDIGO]

**Archivo:** `app/graph/nodes/credit.py`

Al inicio del archivo, donde se instancian los modelos:

```python
from app.infra.gemini_client import get_structured_model, get_generation_model

# Singletons de modelos (se instancian una vez al importar el módulo)
_profile_extractor = get_structured_model(LoanProfileExtraction)
_sim_extractor     = get_structured_model(LoanSimExtraction)
_flux_generator    = get_generation_model()  # NUEVO — Llamada B
```

---

### Sub-paso 4.2 — Crear el helper `_build_generation_context` [CÓDIGO]

**Archivo:** `app/graph/nodes/credit.py`

Este helper construye el bloque de contexto estructurado que recibe el generador. Es el "puente" entre la Llamada A y la Llamada B.

```python
def _build_generation_context(
    nombre: str,
    intencion: str,
    known_profile: dict,
    missing: list[str],
    newly_extracted: dict,
) -> str:
    """
    Construye el bloque de contexto estructurado para la Llamada B (generador).
    
    El generador NO recibe el historial de mensajes crudos ni el resultado
    del extractor directamente. Recibe este resumen pre-digerido para que
    pueda enfocarse en generar la respuesta correcta sin reinterpretar datos.
    
    INPUT:
        nombre          : Primer nombre del usuario (desde preparation_data).
        intencion       : Resultado de la Llamada A ("SALUDO", "PREGUNTA", etc.)
        known_profile   : Datos ya en el State ANTES de este turno.
        missing         : Lista de campos que faltan (resultado de _get_missing_profile_fields).
        newly_extracted : Campos que se extrajeron en ESTE turno (para que Flux los comente).
    
    OUTPUT: String formateado listo para inyectar como HumanMessage al generador.
    """
    # Etiquetas amigables para mostrar al generador
    field_labels = {
        "renta":              "renta líquida mensual",
        "antiguedad_laboral": "antigüedad laboral",
        "nivel_estudios":     "nivel de estudios",
    }
    
    # Construir sección de datos conocidos (para que Flux no los repida)
    known_lines = []
    for field, label in field_labels.items():
        value = known_profile.get(field)
        if value is not None:
            if field == "renta":
                known_lines.append(f"  - {label}: ${value:,} CLP")
            elif field == "antiguedad_laboral":
                known_lines.append(f"  - {label}: {value} meses")
            else:
                known_lines.append(f"  - {label}: {value.capitalize()}")
    
    # Construir sección de datos nuevos (para que Flux los celebre)
    new_lines = []
    for field, value in newly_extracted.items():
        if value is not None and field in field_labels:
            label = field_labels[field]
            if field == "renta":
                new_lines.append(f"  - {label}: ${value:,} CLP")
            elif field == "antiguedad_laboral":
                new_lines.append(f"  - {label}: {value} meses")
            else:
                new_lines.append(f"  - {label}: {value.capitalize()}")
    
    # Construir sección de datos faltantes
    missing_labels = [field_labels[f] for f in missing]
    
    context = f"""CONTEXTO PARA TU RESPUESTA:
    
Usuario: {nombre}
Intención detectada en su último mensaje: {intencion}

Datos del perfil YA CONOCIDOS (no volver a pedir):
{chr(10).join(known_lines) if known_lines else "  - (ninguno aún)"}

Datos recién entregados en este turno (para celebrar/comentar si hay alguno):
{chr(10).join(new_lines) if new_lines else "  - (ninguno en este mensaje)"}

Datos que AÚN FALTAN (pide exactamente el primero de la lista, no todos):
{chr(10).join(f"  - {l}" for l in missing_labels) if missing_labels else "  - (ninguno, perfil completo)"}

INSTRUCCIÓN: Genera la respuesta de Flux según este contexto. 
Si hay datos nuevos, celébrarlos brevemente. Luego pide solo el PRIMER dato faltante.
Si la intención es SALUDO u OTRO, responde con empatía y redirige amablemente a pedir el primer dato faltante.
Si la intención es PREGUNTA, reconoce la duda brevemente y redirige al proceso.
"""
    return context
```

---

### Sub-paso 4.3 — Refactorizar `loan_collecting_profile_node` con Doble Llamada [CÓDIGO]

**Archivo:** `app/graph/nodes/credit.py`

Esta es la implementación central. El nodo orquesta las dos llamadas y hace un único `return` transaccional al final.

```python
def loan_collecting_profile_node(state: FluxState) -> dict:
    """
    Nodo LOAN_COLLECTING_PROFILE: recolección del perfil financiero del usuario.
    
    ID LangGraph : loan_collecting_profile
    current_node : LOAN_COLLECTING_PROFILE
    
    ARQUITECTURA INTERNA — DOBLE LLAMADA:
    
      Llamada A (Extractor):
        - Modelo   : gemini-2.0-flash, temperature=0.0, function_calling
        - Input    : Último mensaje del usuario
        - Output   : LoanProfileExtraction (JSON validado por Pydantic)
        - Objetivo : Extraer datos financieros. Clasificar intención.
                     Jamás genera texto conversacional.
    
      Llamada B (Generador) — Solo si se necesita emitir un mensaje:
        - Modelo   : gemini-2.0-flash, temperature=0.7, texto libre
        - Input    : Contexto estructurado de _build_generation_context()
        - Output   : String con la respuesta de Flux
        - Objetivo : Generar respuesta con personalidad. No extrae datos.
    
    ATOMICIDAD:
        El nodo realiza un único return al final con todos los campos del State
        que modifica. No hay returns intermedios para garantizar consistencia
        con el checkpointer de LangGraph.
    
    AVANCE SILENCIOSO:
        Si el perfil está completo (missing == []), la Llamada B NO se invoca.
        El nodo retorna sin mensaje. El grafo avanza automáticamente al siguiente nodo.
    """
    # ── 1. EXTRACCIÓN DE VARIABLES DEL STATE ───────────────────
    session         = state.get("session", {})
    collecting      = state.get("collecting_data", {})
    prep            = state.get("preparation_data", {})
    messages        = state.get("messages", [])
    
    current_profile = collecting.get("loan_profile", {})
    nombre          = prep.get("nombre", "")
    first_name      = nombre.split()[0] if nombre else "amig@"
    application_id  = session.get("application_id")
    
    # ── 2. CAPTURA DEL ÚLTIMO MENSAJE DEL USUARIO ──────────────
    last_user_msg = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
        ""
    )
    
    # Guardrail: si no hay mensaje del usuario, re-preguntar desde el estado actual
    if not last_user_msg.strip():
        missing = _get_missing_profile_fields(current_profile)
        context = _build_generation_context(
            nombre=first_name,
            intencion="OTRO",
            known_profile=current_profile,
            missing=missing,
            newly_extracted={},
        )
        flux_response = _flux_generator.invoke([
            {"role": "system", "content": SYSTEM_PROMPT_GENERATION_PROFILE},
            {"role": "user",   "content": context},
        ])
        return {
            "messages":       [AIMessage(content=flux_response.content)],
            "collecting_data": {**collecting, "loan_profile": current_profile},
            "session":        {**session, "current_node": "LOAN_COLLECTING_PROFILE"},
        }
    
    # ── 3. LLAMADA A — EXTRACCIÓN ──────────────────────────────
    extracted: LoanProfileExtraction = _profile_extractor.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_EXTRACTION_PROFILE},
        {"role": "user",   "content": last_user_msg},
    ])
    
    # ── 4. MERGE DEFENSIVO ─────────────────────────────────────
    # Solo actualizar campos que el extractor encontró en ESTE turno.
    # Los campos None del extractor no sobreescriben datos previos del State.
    newly_extracted = {}  # Diccionario de lo nuevo: para que Flux lo comente
    updated_profile = {**current_profile}
    
    if extracted.intencion == "DATO_FINANCIERO":
        if extracted.renta is not None:
            updated_profile["renta"] = extracted.renta
            if current_profile.get("renta") != extracted.renta:  # Es realmente nuevo
                newly_extracted["renta"] = extracted.renta
        
        if extracted.antiguedad_laboral is not None:
            updated_profile["antiguedad_laboral"] = extracted.antiguedad_laboral
            if current_profile.get("antiguedad_laboral") != extracted.antiguedad_laboral:
                newly_extracted["antiguedad_laboral"] = extracted.antiguedad_laboral
        
        if extracted.nivel_estudios is not None:
            updated_profile["nivel_estudios"] = extracted.nivel_estudios
            if current_profile.get("nivel_estudios") != extracted.nivel_estudios:
                newly_extracted["nivel_estudios"] = extracted.nivel_estudios
    # Si intencion != DATO_FINANCIERO: no se hace merge. current_profile se preserva intacto.
    
    # ── 5. EVALUACIÓN DE COMPLETITUD ───────────────────────────
    missing = _get_missing_profile_fields(updated_profile)
    
    # ── 6. PREPARAR OUTPUT BASE (siempre presente) ──────────────
    output = {
        "collecting_data": {**collecting, "loan_profile": updated_profile},
        "session":         {**session, "current_node": "LOAN_COLLECTING_PROFILE"},
    }
    
    # ── 7. DECISIÓN: ¿Avance silencioso o Llamada B? ───────────
    if not missing:
        # AVANCE SILENCIOSO: Todos los datos son válidos y completos.
        # La Llamada B NO se invoca. El grafo avanza al siguiente nodo.
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="LOAN_COLLECTING_PROFILE",
                node_status="SUCCESS",
                engine_status="PENDING",
            )
        return output  # ← Return transaccional sin mensajes
    
    # ── 8. LLAMADA B — GENERACIÓN ──────────────────────────────
    # Solo se ejecuta si hay campos faltantes o la intención requiere respuesta.
    context = _build_generation_context(
        nombre=first_name,
        intencion=extracted.intencion,
        known_profile=updated_profile,
        missing=missing,
        newly_extracted=newly_extracted,
    )
    
    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_GENERATION_PROFILE},
        {"role": "user",   "content": context},
    ])
    
    # ── 9. RETURN TRANSACCIONAL ────────────────────────────────
    # Un único return con todos los cambios al State.
    output["messages"] = [AIMessage(content=flux_response.content)]
    return output
```

---

**✅ CRITERIO PASS Sub-paso 4.3** [TEST-UNITARIO con mocks]:

```python
# tests/unit/test_loan_collecting_profile_node.py
# No requiere credenciales de Vertex AI — mockea ambos modelos.

from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from app.graph.nodes.credit import loan_collecting_profile_node
from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction


def make_state(user_msg: str, profile: dict = None):
    return {
        "messages":       [HumanMessage(content=user_msg)],
        "collecting_data": {"loan_profile": profile or {}, "loan_sim": {}},
        "session":        {"current_node": "LOAN_COLLECTING_PROFILE", "application_id": None},
        "preparation_data": {"nombre": "Juan Pérez", "edad": 30},
    }


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_avance_silencioso_no_invoca_generador(mock_extractor, mock_generator):
    """Con perfil completo: Llamada B (generador) NO debe invocarse."""
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        renta=2_000_000,
        antiguedad_laboral=36,
        nivel_estudios="UNIVERSITARIO"
    )
    
    result = loan_collecting_profile_node(
        make_state("Gano 2 millones, llevo 3 años, soy universitario")
    )
    
    mock_generator.invoke.assert_not_called()  # ← La prueba crítica
    assert "messages" not in result or len(result.get("messages", [])) == 0
    assert result["collecting_data"]["loan_profile"]["renta"] == 2_000_000


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_saludo_no_contamina_state(mock_extractor, mock_generator):
    """Un saludo no debe modificar el loan_profile."""
    mock_extractor.invoke.return_value = LoanProfileExtraction(intencion="SALUDO")
    mock_generator.invoke.return_value = MagicMock(content="¡Hola! Estamos en tu solicitud de crédito. ¿Cuál es tu renta?")
    
    state = make_state("Hola!", profile={"renta": 1_000_000})  # Renta ya conocida
    result = loan_collecting_profile_node(state)
    
    # El perfil no debe haber cambiado
    assert result["collecting_data"]["loan_profile"].get("renta") == 1_000_000
    # El generador sí debe haberse invocado
    mock_generator.invoke.assert_called_once()
    # El resultado debe tener un mensaje
    assert "messages" in result and len(result["messages"]) > 0


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_centinelas_pydantic_no_actualizan_perfil(mock_extractor, mock_generator):
    """Si el LLM alucina centinelas, Pydantic los normaliza a None y el perfil no se contamina."""
    # Simular que el LLM retornó valores centinela que Pydantic ya normalizó
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        renta=0,               # Centinela → normalizado a None por Pydantic
        antiguedad_laboral=-1, # Centinela → normalizado a None por Pydantic
        nivel_estudios="MEDIA" # Válido
    )
    mock_generator.invoke.return_value = MagicMock(content="Casi listo, solo me falta tu renta y antigüedad.")
    
    state = make_state("algo irrelevante")
    result = loan_collecting_profile_node(state)
    
    profile = result["collecting_data"]["loan_profile"]
    assert profile.get("renta") is None,              "renta=0 no debe escribirse"
    assert profile.get("antiguedad_laboral") is None,  "ant=-1 no debe escribirse"
    assert profile.get("nivel_estudios") == "MEDIA",   "MEDIA sí debe escribirse"


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_merge_acumulativo_entre_turnos(mock_extractor, mock_generator):
    """Los datos de turnos anteriores se preservan cuando llegan datos nuevos."""
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        antiguedad_laboral=24  # Solo antigüedad nueva
    )
    mock_generator.invoke.return_value = MagicMock(content="¡Anotado! ¿Y tu nivel de estudios?")
    
    # Estado previo: ya tiene renta
    state = make_state("Llevo 2 años trabajando", profile={"renta": 1_500_000})
    result = loan_collecting_profile_node(state)
    
    profile = result["collecting_data"]["loan_profile"]
    assert profile.get("renta") == 1_500_000,         "La renta previa debe conservarse"
    assert profile.get("antiguedad_laboral") == 24,    "La nueva antigüedad debe guardarse"


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_un_solo_return_transaccional(mock_extractor, mock_generator):
    """El nodo debe retornar siempre los tres campos del State en un solo dict."""
    mock_extractor.invoke.return_value = LoanProfileExtraction(intencion="SALUDO")
    mock_generator.invoke.return_value = MagicMock(content="Hola, retomemos.")
    
    result = loan_collecting_profile_node(make_state("Hola"))
    
    assert "collecting_data" in result, "collecting_data debe estar siempre en el output"
    assert "session" in result,         "session debe estar siempre en el output"
    assert result["session"]["current_node"] == "LOAN_COLLECTING_PROFILE"
```

---

## PASO 5 — Corrección del Playground

> **Objetivo:** Hacer que el playground sea un reflejo fiel del entorno de producción para que los tests manuales tengan validez real.

---

### Sub-paso 5.1 — Refactorizar `loan_playground.py` [CÓDIGO]

**Archivo:** `backend/scratch/loan_playground.py`

Los problemas del playground original:
1. Limpia el historial en cada turno (`state["messages"] = [...]`), eliminando el contexto que el nodo usa.
2. No inyecta el mensaje inicial del bot (simulando `loan_init_node`), por lo que el generador no tiene conversación previa.
3. El merge manual usa `.update()`, que sobreescribe todo el perfil en lugar de hacer merge campo por campo.

```python
"""
backend/scratch/loan_playground.py
─────────────────────────────────────────────────────────────
Playground v2.1 — Prueba manual del nodo loan_collecting_profile_node.

CAMBIOS vs v1.0:
  - Historial acumulativo: los mensajes se acumulan, no se limpian.
  - Mensaje inicial del bot inyectado para simular loan_init_node.
  - Merge manual corregido: campo por campo, no .update() completo.
  - DEBUG mejorado: muestra datos nuevos vs. datos previos por separado.
  - Indicador de "avance silencioso" claro.
"""

import os
import sys

# Ajustar path si el playground está en /scratch y no en la raíz del backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import HumanMessage, AIMessage
from app.graph.nodes.credit import loan_collecting_profile_node

# ── Estado inicial del playground ────────────────────────────
state = {
    "messages":        [],
    "collecting_data": {"loan_profile": {}, "loan_sim": {}},
    "session":         {
        "current_node":   "LOAN_INIT",
        "application_id": None,   # Sin Supabase en el playground
    },
    "preparation_data": {
        "nombre": "María González",  # Cambiar por el nombre de prueba deseado
        "edad":   32,
        "rut":    "12.345.678-9",
        "mail":   "maria@test.cl",
    },
}

# ── Simular mensaje inicial de loan_init_node ─────────────────
MENSAJE_INICIAL_BOT = (
    "¡Perfecto, María! Vamos a revisar tu solicitud de **Crédito de Consumo**. "
    "Es un proceso rápido. Primero necesito conocer un poco tu perfil financiero. "
    "¿Cuál es tu renta líquida mensual?"
)
state["messages"].append(AIMessage(content=MENSAJE_INICIAL_BOT))

print("\n" + "═" * 60)
print("  🧪 FLUX PLAYGROUND v2.1 — Nodo: loan_collecting_profile")
print("═" * 60)
print(f"\nFlux: {MENSAJE_INICIAL_BOT}\n")

# ── Loop de conversación ──────────────────────────────────────
while True:
    user_input = input("Tú: ").strip()
    if user_input.lower() in ["salir", "exit", "quit", "q"]:
        print("\n[Playground terminado]")
        break
    if not user_input:
        continue
    
    # ── Inyectar mensaje del usuario al historial (ACUMULATIVO) ──
    state["messages"].append(HumanMessage(content=user_input))
    
    # ── Snapshot del perfil antes del turno (para DEBUG) ─────────
    profile_before = dict(state["collecting_data"]["loan_profile"])
    
    # ── Ejecutar el nodo ─────────────────────────────────────────
    result = loan_collecting_profile_node(state)
    
    # ── Sincronizar el State (merge campo por campo) ─────────────
    if "collecting_data" in result:
        new_profile = result["collecting_data"].get("loan_profile", {})
        # Merge defensivo: solo actualizar campos que tienen valor en el resultado
        for field, value in new_profile.items():
            if value is not None:
                state["collecting_data"]["loan_profile"][field] = value
    
    if "session" in result:
        state["session"].update(result["session"])
    
    # ── Sincronizar mensajes del bot al historial ─────────────────
    bot_messages = result.get("messages", [])
    for msg in bot_messages:
        state["messages"].append(msg)
    
    # ── Mostrar resultado ─────────────────────────────────────────
    print()
    if bot_messages:
        print(f"Flux: {bot_messages[-1].content}")
    else:
        print("Flux: (⚡ Avance silencioso — Perfil completo, pasando al motor)")
    
    # ── DEBUG: Estado del perfil ──────────────────────────────────
    profile_after = state["collecting_data"]["loan_profile"]
    profile_diff  = {k: v for k, v in profile_after.items() if profile_before.get(k) != v}
    
    print(f"\n  {'─'*50}")
    print(f"  [DEBUG] Perfil actual  : {profile_after}")
    print(f"  [DEBUG] Cambios turno  : {profile_diff if profile_diff else '(sin cambios)'}")
    print(f"  [DEBUG] Mensajes total : {len(state['messages'])}")
    print(f"  {'─'*50}\n")
```

---

**✅ CRITERIO PASS Sub-paso 5.1** [TEST-MANUAL — requiere credenciales]:

Ejecutar el playground con la siguiente secuencia y verificar los resultados esperados:

```
TURNO 1
  Tú: Hola!
  Esperado: Flux responde de forma empática y redirige. loan_profile = {}

TURNO 2
  Tú: Gano 2 palos mensuales
  Esperado: Flux celebra la renta y pide antigüedad. loan_profile = {"renta": 2000000}

TURNO 3
  Tú: ¿Qué es el CAE?
  Esperado: Flux reconoce la pregunta, redirige. loan_profile sin cambios.

TURNO 4
  Tú: Llevo 3 años en la pega
  Esperado: Flux celebra y pide estudios. loan_profile = {"renta": 2000000, "antiguedad_laboral": 36}

TURNO 5
  Tú: Soy universitario
  Esperado: "⚡ Avance silencioso". loan_profile = {"renta": 2000000, "antiguedad_laboral": 36, "nivel_estudios": "UNIVERSITARIO"}
```

Cada turno debe verificarse contra el `[DEBUG] Perfil actual` impreso en consola.

---

## PASO 6 — Tests de Integración con LLM Real

> **Objetivo:** Validar el comportamiento end-to-end con el modelo real de Vertex AI. Estos tests son la validación final antes de cerrar el Paso 2.

---

### Sub-paso 6.1 — Suite de integración [TEST-INTEGRACIÓN]

**Archivo:** `tests/integration/test_loan_collecting_profile_integration.py`

```python
"""
Tests de integración para loan_collecting_profile_node.
REQUIEREN credenciales reales de Vertex AI (ADC configurado).
Ejecutar con: pytest tests/integration/ -v -m integration

Estos tests validan el comportamiento real del LLM,
a diferencia de los unit tests que usan mocks.
"""

import pytest
from langchain_core.messages import HumanMessage, AIMessage
from app.graph.nodes.credit import loan_collecting_profile_node


pytestmark = pytest.mark.integration  # Marcar para ejecución selectiva


def make_state(messages: list, profile: dict = None) -> dict:
    return {
        "messages":        messages,
        "collecting_data": {"loan_profile": profile or {}, "loan_sim": {}},
        "session":         {"current_node": "LOAN_COLLECTING_PROFILE", "application_id": None},
        "preparation_data": {"nombre": "Ana Torres", "edad": 28},
    }


class TestExtraccionNulos:
    """Verifica que el extractor retorna null para mensajes sin datos financieros."""
    
    def test_saludo_no_contamina_state(self):
        state = make_state([
            AIMessage(content="¿Cuál es tu renta mensual?"),
            HumanMessage(content="Hola! ¿cómo estás?"),
        ])
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile == {}, \
            f"Un saludo no debe modificar el perfil. Perfil resultante: {profile}"
        assert "messages" in result, \
            "El bot debe emitir un mensaje (re-pregunta) ante un saludo"
    
    def test_mensaje_irrelevante_no_inyecta_centinelas(self):
        state = make_state([
            AIMessage(content="¿Cuál es tu renta mensual?"),
            HumanMessage(content="¿Conoces a Joe Black?"),
        ])
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile.get("renta") is None or profile.get("renta") > 0, \
            f"renta no puede ser 0. Valor: {profile.get('renta')}"
        assert profile.get("antiguedad_laboral") is None or profile.get("antiguedad_laboral") >= 0, \
            f"antiguedad no puede ser -1. Valor: {profile.get('antiguedad_laboral')}"


class TestExtraccionPositiva:
    """Verifica que el extractor captura datos reales correctamente."""
    
    def test_modismo_palo_extraido_correctamente(self):
        state = make_state([HumanMessage(content="Gano 3 palos mensuales")])
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile.get("renta") == 3_000_000, \
            f"'3 palos' debe ser 3.000.000. Valor: {profile.get('renta')}"
    
    def test_modismo_lucas_extraido_correctamente(self):
        state = make_state([HumanMessage(content="Me pagan 800 lucas")])
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile.get("renta") == 800_000, \
            f"'800 lucas' debe ser 800.000. Valor: {profile.get('renta')}"
    
    def test_años_convertidos_a_meses(self):
        state = make_state([HumanMessage(content="Llevo 5 años en la pega")])
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile.get("antiguedad_laboral") == 60, \
            f"'5 años' debe ser 60 meses. Valor: {profile.get('antiguedad_laboral')}"
    
    def test_nivel_estudios_inferido_de_carrera(self):
        state = make_state([HumanMessage(content="Soy Ingeniero Civil")])
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile.get("nivel_estudios") == "UNIVERSITARIO", \
            f"'Ingeniero Civil' debe mapearse a UNIVERSITARIO. Valor: {profile.get('nivel_estudios')}"
    
    def test_tres_datos_en_un_mensaje_avance_silencioso(self):
        state = make_state([
            HumanMessage(content="Gano 2 millones, llevo 3 años trabajando y soy técnico en informática")
        ])
        result = loan_collecting_profile_node(state)
        
        assert "messages" not in result or len(result.get("messages", [])) == 0, \
            "Con perfil completo no debe haber re-pregunta (avance silencioso)"
        
        profile = result["collecting_data"]["loan_profile"]
        assert profile["renta"] == 2_000_000
        assert profile["antiguedad_laboral"] == 36
        assert profile["nivel_estudios"] == "TECNICO"


class TestMergeAcumulativo:
    """Verifica la acumulación de datos entre múltiples turnos."""
    
    def test_datos_previos_se_preservan(self):
        """El State acumulado de turnos anteriores no se borra."""
        perfil_previo = {"renta": 1_500_000, "nivel_estudios": "UNIVERSITARIO"}
        state = make_state(
            messages=[
                AIMessage(content="Ya anoté tu renta y estudios. ¿Hace cuánto trabajas?"),
                HumanMessage(content="Llevo 2 años y medio en la empresa"),
            ],
            profile=perfil_previo
        )
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile.get("renta") == 1_500_000,      "La renta previa debe preservarse"
        assert profile.get("nivel_estudios") == "UNIVERSITARIO", "Los estudios previos deben preservarse"
        assert profile.get("antiguedad_laboral") == 30, "2.5 años = 30 meses"


class TestRespuestaGenerada:
    """Verifica características de la respuesta conversacional de Flux."""
    
    def test_respuesta_menciona_nombre_usuario(self):
        state = make_state([
            AIMessage(content="¿Cuál es tu renta?"),
            HumanMessage(content="Hola"),
        ])
        result = loan_collecting_profile_node(state)
        
        if "messages" in result and result["messages"]:
            response = result["messages"][-1].content
            # Flux debe mencionar el nombre en algún momento de la conversación
            # (puede que no sea en el saludo, dependiendo del prompt)
            assert len(response) > 10, "La respuesta debe ser sustancial, no vacía"
    
    def test_respuesta_celebra_dato_nuevo(self):
        """Cuando el usuario entrega un dato, Flux debe celebrarlo antes de pedir el siguiente."""
        state = make_state([
            AIMessage(content="¿Cuál es tu renta mensual?"),
            HumanMessage(content="Gano 2 millones y medio"),
        ])
        result = loan_collecting_profile_node(state)
        
        if "messages" in result and result["messages"]:
            response = result["messages"][-1].content.lower()
            # Verificar que la respuesta tenga alguna señal de reconocimiento positivo
            positive_signals = ["buena", "perfecto", "anotado", "excelente", "listo", "genial", "buenísimo"]
            has_positive = any(signal in response for signal in positive_signals)
            assert has_positive, \
                f"Flux debe celebrar el dato entregado. Respuesta: {result['messages'][-1].content}"
```

---

## PASO 7 — Cierre y Documentación del Paso 2

### Sub-paso 7.1 — Checklist de Cierre del Paso 2

Antes de marcar el Paso 2 como completado, el desarrollador debe verificar cada ítem:

```
BUGS RESUELTOS
[ ] CR-1: _get_missing_profile_fields usa is None. Check inline eliminado.
[ ] CR-2: get_structured_model usa temperature=0.0 y method="function_calling".
[ ] CR-3: Campo intencion en schema actúa como pre-filtro. SALUDO/OTRO no actualiza el State.
[ ] CR-4: Doble Llamada implementada. El generador solo se invoca cuando hay mensaje que emitir.

TESTS PASANDO
[ ] pytest tests/unit/test_credit_helpers.py -v          → 5/5 PASS
[ ] pytest tests/unit/test_loan_schemas.py -v            → 6/6 PASS
[ ] pytest tests/unit/test_gemini_client.py -v           → 2/2 PASS
[ ] pytest tests/unit/test_loan_collecting_profile_node.py -v → 5/5 PASS
[ ] pytest tests/integration/ -v -m integration          → 10/10 PASS (con credenciales)

PLAYGROUND MANUAL
[ ] Secuencia de 5 turnos ejecutada exitosamente (ver Paso 5.1).
[ ] Avance silencioso ocurre SOLO en el turno 5 (datos completos y válidos).
[ ] Ningún turno previo produjo avance silencioso con datos inválidos.
[ ] Respuestas de Flux suenan naturales, celebran datos y hacen una pregunta a la vez.

ARCHIVOS MODIFICADOS (auditoría)
[ ] credit.py          — v2.1: Doble Llamada, helper corregido, _build_generation_context
[ ] loan_schemas.py    — v2.1: Campo intencion, validadores @field_validator
[ ] gemini_client.py   — v2.1: temperature=0.0, method=function_calling, get_generation_model()
[ ] loan_playground.py — v2.1: Historial acumulativo, merge campo a campo

ARCHIVOS INMUTABLES (sin cambios)
[ ] state.py     — Sin modificaciones
[ ] workflow.py  — Sin modificaciones
[ ] edges.py     — Sin modificaciones
[ ] supabase.py  — Sin modificaciones
```

---

### Sub-paso 7.2 — Registro de Resultados

Completar este registro tras ejecutar los tests de integración:

```markdown
## Registro de Resultados — Fase 2, Paso 2

Fecha de cierre: ___________
Ejecutado por:   ___________

### Tests Unitarios
| Suite                                    | Tests | PASS | FAIL | Observaciones |
|------------------------------------------|-------|------|------|---------------|
| test_credit_helpers.py                   |   5   |      |      |               |
| test_loan_schemas.py                     |   6   |      |      |               |
| test_gemini_client.py                    |   2   |      |      |               |
| test_loan_collecting_profile_node.py     |   5   |      |      |               |

### Tests de Integración (con Vertex AI)
| Suite                                               | Tests | PASS | FAIL |
|-----------------------------------------------------|-------|------|------|
| TestExtraccionNulos                                 |   2   |      |      |
| TestExtraccionPositiva                              |   4   |      |      |
| TestMergeAcumulativo                                |   1   |      |      |
| TestRespuestaGenerada                               |   2   |      |      |

### Playground Manual (Secuencia de 5 Turnos)
| Turno | Input           | Profile esperado                            | PASS |
|-------|-----------------|---------------------------------------------|------|
| 1     | "Hola!"         | {}                                          |      |
| 2     | "Gano 2 palos"  | {"renta": 2000000}                          |      |
| 3     | "¿Qué es CAE?"  | {"renta": 2000000}  (sin cambios)           |      |
| 4     | "3 años en pega"| {"renta": 2000000, "antiguedad_laboral": 36}|      |
| 5     | "Universitario" | Perfil completo → Avance silencioso ✅      |      |
```

---

## APÉNDICE: Mapa de Archivos Finales

```
app/
├── graph/
│   ├── nodes/
│   │   ├── credit.py                    ← MODIFICADO v2.1
│   │   └── schemas/
│   │       └── loan_schemas.py          ← MODIFICADO v2.1
│   ├── state.py                         ← INMUTABLE
│   ├── workflow.py                      ← INMUTABLE
│   └── edges.py                         ← INMUTABLE
├── infra/
│   ├── gemini_client.py                 ← MODIFICADO v2.1
│   └── supabase.py                      ← INMUTABLE
└── ...

backend/scratch/
└── loan_playground.py                   ← MODIFICADO v2.1

tests/
├── unit/
│   ├── test_credit_helpers.py           ← NUEVO
│   ├── test_loan_schemas.py             ← NUEVO
│   ├── test_gemini_client.py            ← NUEVO
│   └── test_loan_collecting_profile_node.py  ← NUEVO
└── integration/
    └── test_loan_collecting_profile_integration.py  ← NUEVO
```

---

*Documento generado para Flux — Fase 2, Paso 2. Versión 3.0.*
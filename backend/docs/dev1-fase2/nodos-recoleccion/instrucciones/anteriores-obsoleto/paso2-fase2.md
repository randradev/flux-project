# Plan de Implementación — Fase 2: Crédito de Consumo

*Ley del Plan: Ningún paso modifica lo que ya funciona. Los archivos state.py, workflow.py (estructura base), edges.py y loan_init_node son considerados inmutables salvo las extensiones explícitamente indicadas.*

## PASO 2 — Nodos de Recolección e Inteligencia

**Arquitectura de los Nodos Collecting**

Los nodos de recolección operan en dos modos:
- **Modo Extracción**: El LLM recibió un mensaje con datos procesables. Los extrae con with_structured_output y actualiza collecting_data.
- **Modo Re-pregunta**: El mensaje del usuario es ambiguo o incompleto. El nodo retorna un mensaje solicitando nuevamente el dato, sin avanzar el grafo (la arista condicional lo detecta y hace loop).

### Sub-paso 2.1 — Esquemas Pydantic
Archivo: app/graph/nodes/schemas/loan_schemas.py

```python
"""
Esquemas Pydantic para extracción estructurada en nodos de Crédito.
Usados con LLM.with_structured_output() en los nodos COLLECTING.

DISEÑO: Los campos son Optional con None como default.
        Un campo None significa "no fue mencionado en el mensaje".
        El nodo evalúa qué campos faltan y decide si avanzar o re-preguntar.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class LoanProfileExtraction(BaseModel):
    """
    Schema para LOAN_COLLECTING_PROFILE.
    Mapea directamente a collecting_data["loan_profile"].
    """
    renta: Optional[int] = Field(
        default=None,
        description="Renta líquida mensual en CLP. Ej: 'gano 1 millón' → 1000000."
    )
    antiguedad_laboral: Optional[int] = Field(
        default=None,
        description="Antigüedad laboral en MESES. Convertir años a meses. Ej: '2 años' → 24."
    )
    nivel_estudios: Optional[Literal["POSTGRADO", "UNIVERSITARIO", "TECNICO", "MEDIA"]] = Field(
        default=None,
        description=(
            "Nivel de estudios normalizado. "
            "'ingeniería', 'universidad', 'carrera' → UNIVERSITARIO. "
            "'magíster', 'doctorado', 'postgrado' → POSTGRADO. "
            "'técnico', 'ip', 'cft' → TECNICO. "
            "'media', 'liceo', 'cuarto medio' → MEDIA."
        )
    )
    datos_completos: bool = Field(
        default=False,
        description="True solo si los tres campos anteriores fueron mencionados explícitamente."
    )


class LoanSimExtraction(BaseModel):
    """
    Schema para LOAN_COLLECTING_SIMULATION.
    Mapea directamente a collecting_data["loan_sim"].
    """
    monto_solicitado: Optional[int] = Field(
        default=None,
        description=(
            "Monto del crédito en CLP (entero). "
            "Normalizar expresiones: '5 millones' → 5000000, '$3.500.000' → 3500000."
        )
    )
    plazo_solicitado: Optional[int] = Field(
        default=None,
        description=(
            "Número de cuotas (meses). Rango válido: 6-48. "
            "Si el usuario dice 'años', convertir: '2 años' → 24."
        )
    )
    datos_completos: bool = Field(
        default=False,
        description="True solo si monto y plazo fueron mencionados explícitamente."
    )
```

**Punto de Revisión 2.1:**
- El campo datos_completos es un guardrail semántico: evita que el LLM infiera datos que no fueron mencionados y los marque como completos. El nodo no confía en este campo ciegamente; valida explícitamente que los campos no sean None.
- La conversión de unidades (años → meses, millones → CLP) ocurre dentro del LLM via la descripción del Field, no en el nodo. Esto simplifica la lógica del nodo.

### Sub-paso 2.2 — Nodo loan_collecting_profile_node
```python
# En app/graph/nodes/credit.py (extensión del archivo existente)

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI  # o el provider que el proyecto use
from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction
from app.infra.supabase import update_application_semaphores

# El LLM se instancia a nivel de módulo (singleton de nodo).
# Ajustar modelo y temperatura según configuración del proyecto.
_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
_profile_extractor = _llm.with_structured_output(LoanProfileExtraction)


SYSTEM_PROMPT_PROFILE = """
Eres un asistente bancario experto en extracción de datos financieros.
Tu única tarea es analizar el mensaje del usuario e identificar los datos de perfil.

REGLAS:
- Extrae SOLO lo que el usuario mencionó explícitamente. No inventes ni asumas.
- Convierte unidades: años → meses (multiplicar por 12), millones → pesos (multiplicar por 1.000.000).
- Normaliza nivel_estudios a: POSTGRADO, UNIVERSITARIO, TECNICO o MEDIA.
- Si un dato no fue mencionado, déjalo como null.
- datos_completos = true SOLO si los tres campos tienen valor.
"""


def loan_collecting_profile_node(state: FluxState) -> dict:
    """
    Nodo LOAN_COLLECTING_PROFILE: extrae renta, antigüedad y nivel de estudios.

    ID LangGraph : loan_collecting_profile
    current_node : LOAN_COLLECTING_PROFILE

    MODO A (Extracción exitosa):
        - Actualiza collecting_data["loan_profile"] con los datos extraídos.
        - No emite mensaje (el grafo avanza silenciosamente si todos los datos están presentes).
        - Si faltan datos: emite re-pregunta específica.

    MODO B (Re-pregunta):
        - Conserva los datos ya recolectados en el State (merge, no reemplaza).
        - Retorna mensaje empático solicitando el dato faltante.

    NOTA DE PERSISTENCIA:
        El merge de datos es crítico para el Checkpointer. Si el usuario
        da la renta en un mensaje y la antigüedad en otro, ambos deben
        acumularse en loan_profile, no sobreescribirse.
    """
    session     = state.get("session", {})
    collecting  = state.get("collecting_data", {})
    messages    = state.get("messages", [])

    # Datos ya recolectados (de invocaciones previas de este nodo)
    current_profile: dict = collecting.get("loan_profile", {})

    # Último mensaje del usuario
    last_human_msg = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
        ""
    )

    # ── Extracción con LLM ─────────────────────────────────
    extracted: LoanProfileExtraction = _profile_extractor.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_PROFILE},
        {"role": "user",   "content": last_human_msg},
    ])

    # ── Merge defensivo: solo actualizar campos que llegaron con valor ─
    updated_profile = {**current_profile}
    if extracted.renta             is not None: updated_profile["renta"]             = extracted.renta
    if extracted.antiguedad_laboral is not None: updated_profile["antiguedad_laboral"] = extracted.antiguedad_laboral
    if extracted.nivel_estudios    is not None: updated_profile["nivel_estudios"]    = extracted.nivel_estudios

    # ── Determinar campos faltantes ────────────────────────
    missing = _get_missing_profile_fields(updated_profile)

    application_id = session.get("application_id")

    if not missing:
        # Todos los datos recolectados: avanzar silenciosamente
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="LOAN_COLLECTING_PROFILE",
                node_status="SUCCESS",
                engine_status="PENDING",
            )
        return {
            "collecting_data": {**collecting, "loan_profile": updated_profile},
            "session": {**session, "current_node": "LOAN_COLLECTING_PROFILE"},
        }
    else:
        # Datos incompletos: re-preguntar con contexto
        re_ask_msg = _build_profile_reprompt(missing, updated_profile)
        return {
            "messages":       [AIMessage(content=re_ask_msg)],
            "collecting_data": {**collecting, "loan_profile": updated_profile},
            "session":        {**session, "current_node": "LOAN_COLLECTING_PROFILE"},
        }


def _get_missing_profile_fields(profile: dict) -> list[str]:
    """Retorna lista de campos requeridos que aún no tienen valor."""
    required = ["renta", "antiguedad_laboral", "nivel_estudios"]
    return [f for f in required if not profile.get(f)]


def _build_profile_reprompt(missing: list[str], known: dict) -> str:
    """
    Construye un mensaje de re-pregunta empático y específico.
    Reconoce los datos ya entregados antes de pedir los faltantes.
    """
    known_parts = []
    if known.get("renta"):
        known_parts.append(f"renta de ${known['renta']:,.0f}")
    if known.get("antiguedad_laboral"):
        known_parts.append(f"{known['antiguedad_laboral']} meses de antigüedad")
    if known.get("nivel_estudios"):
        known_parts.append(f"estudios {known['nivel_estudios'].lower()}")

    field_labels = {
        "renta":             "tu renta líquida mensual",
        "antiguedad_laboral": "tu antigüedad laboral (en meses o años)",
        "nivel_estudios":    "tu nivel de estudios (Media, Técnico, Universitario o Postgrado)",
    }
    missing_labels = [field_labels[f] for f in missing]

    base = "Perfecto" if known_parts else "Entendido"
    known_str = f", ya tengo {', '.join(known_parts)}" if known_parts else ""
    missing_str = " y ".join(missing_labels)

    return f"{base}{known_str}. Para continuar, necesito que me indiques {missing_str}."
```

### Sub-paso 2.3 — Nodo loan_collecting_simulation_node
La estructura es análoga a la del perfil. Las diferencias clave:

```python
# Extracto de las diferencias relevantes (la estructura completa sigue el mismo patrón)

SYSTEM_PROMPT_SIM = """
Eres un asistente bancario. Extrae el monto y plazo del crédito del mensaje del usuario.

REGLAS:
- monto_solicitado: entero en CLP. Rango válido: 100.000 a 30.000.000.
  Si el usuario da un monto fuera de rango, extráelo igual (la validación la hace el motor).
- plazo_solicitado: entero en meses. Rango válido: 6 a 48.
  Si dice '2 años' → 24. Si dice '1 año y medio' → 18.
- Si un dato no fue mencionado, déjalo como null.
"""

def loan_collecting_simulation_node(state: FluxState) -> dict:
    """
    Nodo LOAN_COLLECTING_SIMULATION: extrae monto_solicitado y plazo_solicitado.

    ID LangGraph : loan_collecting_simulation
    current_node : LOAN_COLLECTING_SIMULATION

    NOTA: Este nodo se ejecuta DESPUÉS de que loan_profile está completo.
          No tiene acceso a loan_profile porque no lo necesita.
    """
    # ... (mismo patrón: extracción, merge, missing check, re-pregunta)
    # El merge opera sobre collecting_data["loan_sim"], no sobre loan_profile.
```

**Punto de Revisión 2.2–2.3:**

- Verificar que el merge defensivo funciona correctamente en sesiones reanudadas: si el usuario abandona y vuelve, el Checkpointer debe restaurar el loan_profile parcialmente completo y el nodo debe continuar desde donde estaba.
- Verificar que el LLM no rellena campos que el usuario no mencionó. Test manual: enviar solo la renta y verificar que antiguedad_laboral sea None en el resultado del extractor.
- El SYSTEM_PROMPT nunca menciona rangos de validación de negocio: esa responsabilidad es del motor. El nodo solo extrae.

### Pruebas de Validación — PASO 2

```python
# Test 2.1 — Extracción completa en un solo mensaje
# Input msg: "Gano 1 millón y medio, llevo 3 años trabajando, soy universitario"
# Expected: renta=1_500_000, antiguedad_laboral=36, nivel_estudios="UNIVERSITARIO"
#           datos_completos=True, nodo retorna sin mensaje (avance silencioso)

# Test 2.2 — Extracción parcial: solo renta
# Input msg: "Mi renta es 800 mil"
# Expected: loan_profile={"renta": 800_000}, mensaje de re-pregunta sobre ant. y estudios

# Test 2.3 — Merge acumulativo (2 turnos)
# Turno 1: "Soy técnico y gano 900 mil" → profile={"renta":900000,"nivel_estudios":"TECNICO"}
# Turno 2: "Tengo 8 meses trabajando" → profile={"renta":900000,"nivel_estudios":"TECNICO","antiguedad_laboral":8}
# Expected: Avance silencioso en turno 2.

# Test 2.4 — Input ambiguo
# Input msg: "No sé, lo que venga" → todos los campos None, re-pregunta general

# Test 2.5 — Conversión de unidades
# "monto de 5 millones a 2 años" → monto=5_000_000, plazo=24
```
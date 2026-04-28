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
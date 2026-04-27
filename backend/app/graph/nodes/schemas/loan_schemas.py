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
        description="Renta líquida mensual en CLP. Ej: 'gano 1 millón' → 1000000, 'gano 3 palos' → 3000000, 'me pagan 800 lucas' → 800000."
    )
    antiguedad_laboral: Optional[int] = Field(
        default=None,
        description="Antigüedad laboral en MESES. Convertir años a meses. Ej: '2 años' → 24, 'llevo 5 años en la pega' → 60."
    )
    nivel_estudios: Optional[Literal["POSTGRADO", "UNIVERSITARIO", "TECNICO", "MEDIA"]] = Field(
        default=None,
        description=(
            "Nivel de estudios normalizado. "
            "'ingeniería', 'universidad', 'carrera', 'profesional', 'titulado', 'egresado', 'licenciado' → UNIVERSITARIO. "
            "'magíster', 'doctorado', 'postgrado', 'MBA', 'máster', 'especialidad médica' → POSTGRADO. "
            "'técnico', 'ip', 'cft', 'inacap', 'duoc', 'instituto profesional', 'centro de formación técnica' → TECNICO. "
            "'media', 'liceo', 'cuarto medio', 'colegio', 'escuela', 'enseñanza media' → MEDIA."
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
            "Normalizar expresiones: '5 millones' → 5000000, '$3.500.000' → 3500000, 'un palo' → 1000000, '800 lucas' → 800000."
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
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
            "Clasificación del mensaje antes de extraer datos: "
            "DATO_FINANCIERO si contiene monto solicitado o plazo solicitado. "
            "PREGUNTA si el usuario hace una consulta (¿qué es el CAE?, ¿cómo funciona?). "
            "SALUDO si es un saludo, despedida o frase social sin datos financieros. "
            "OTRO para mensajes fuera de contexto que no encajan en las anteriores."
        )
    )
    razonamiento: str = Field(
        description="Justifica brevemente por qué extraes o dejas en null cada campo basándote SOLO en el mensaje actual."
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
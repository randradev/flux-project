"""
Esquemas Pydantic para extracción estructurada en nodos de Cuenta Corriente.
Usados con LLM.with_structured_output() en los nodos COLLECTING.

DISEÑO v2.1:
  - Campos Optional con None como default (campo ausente = None).
  - Validadores @field_validator normalizan valores centinela del LLM a None.
  - Campo `intencion` para pre-filtro de mensajes no procesables.
  - El nodo evalúa qué campos faltan y decide si avanzar o re-preguntar.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal


class AccountProfileExtraction(BaseModel):
    """
    Schema para ACCOUNT_COLLECTING_PROFILE.
    Mapea directamente a collecting_data["account_profile"].
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
    razonamiento: str = Field(
        default="",
        description="Justifica brevemente por qué extraes o dejas en null cada campo basándote SOLO en el mensaje actual. Texto plano, sin comillas, una sola línea."
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
    nivel_estudios: Optional[Literal["POSTGRADO", "UNIVERSITARIO", "TECNICO", "MEDIA", "DESCONOCIDO"]] = Field(
        default="DESCONOCIDO",
        description=(
            "Nivel de estudios normalizado al Literal exacto. "
            "'ingeniería', 'universidad', 'carrera', 'profesional' → UNIVERSITARIO. "
            "'magíster', 'doctorado', 'postgrado', 'MBA' → POSTGRADO. "
            "'técnico', 'ip', 'cft', 'inacap', 'duoc' → TECNICO. "
            "'media', 'liceo', 'cuarto medio', 'colegio' → MEDIA. "
            "Si no fue mencionado, retornar 'DESCONOCIDO'."
        )
    )
    # Ayudar al LLM a encasillar la respuesta en el Literal exacto
    @field_validator("nivel_estudios", mode="before")
    @classmethod
    def normalize_estudios(cls, v: str) -> str:
        if not v: return "DESCONOCIDO"
        v = v.upper()
        if "MEDIA" in v: return "MEDIA"
        if "UNIV" in v: return "UNIVERSITARIO"
        if "TECNI" in v: return "TECNICO"
        if "POST" in v or "MAGI" in v or "DOCTO" in v: return "POSTGRADO"
        return v
    

class AccountDecisionExtraction(BaseModel):
    decision: str = Field(description="ACCEPTED, REJECTED, PREGUNTA, u OTRO")
    razonamiento: str = Field(description="Breve explicación de la elección")

class AccountOTPExtraction(BaseModel):
    """
    Extracción de intención en el paso de validación OTP.
    """
    intent: Literal["OTP_CODE", "PREGUNTA", "OTRO"] = Field(
        description="OTP_CODE si parece un código de 6 dígitos, PREGUNTA si es una duda, OTRO para ruido."
    )
    otp_value: str | None = Field(
        None, description="El código de 6 dígitos encontrado, si aplica."
    )
    razonamiento: str = Field(
        description="Breve explicación de por qué se clasificó así."
    )

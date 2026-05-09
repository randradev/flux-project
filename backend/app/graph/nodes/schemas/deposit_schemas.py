"""
Esquemas Pydantic para extracción estructurada en nodos de Depósito a Plazo.
Usados con LLM.with_structured_output() en los nodos COLLECTING.

DISEÑO v2.1:
  - Campos Optional con None como default (campo ausente = None).
  - Validadores @field_validator normalizan valores centinela del LLM a None.
  - Campo `intencion` para pre-filtro de mensajes no procesables.
  - El nodo evalúa qué campos faltan y decide si avanzar o re-preguntar.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
import re

class DapDataExtraction(BaseModel):
    """
    Schema para DAP_COLLECTING_DATA.
    Mapea directamente a collecting_data["dap_params"].
    """

    intencion: Literal["DATO_FINANCIERO", "PREGUNTA", "SALUDO", "OTRO"] = Field(
        description=(
            "Clasificación del mensaje antes de extraer datos: "
            "DATO_FINANCIERO si contiene monto a invertir, moneda o plazo de inversión. "
            "PREGUNTA si el usuario hace una consulta (¿En qué divisas se puede invertir? ¿Cómo funciona?). "
            "SALUDO si es un saludo, despedida o frase social sin datos financieros. "
            "OTRO para mensajes fuera de contexto que no encajan en las anteriores."
        )
    )
    razonamiento: str = Field(
        default="",
        description="Justifica brevemente por qué extraes o dejas en null cada campo basándote SOLO en el mensaje actual. Texto plano, sin comillas, una sola línea."
    )
    monto: Optional[float] = Field(
        default=None,
        description=(
            "Monto a invertir(float). "
            "Normalizar: 'quiero invertir 1 millón' → 1000000.0, 'quiero depositar 3.5 palos' → 3500000.0, "
            "'quiero hacer un depósito de 800 lucas' → 800000.0. "
            "Si no fue mencionado, retornar null."
        )
    )
    plazo: Optional[int] = Field(
        default=None,
        description=(
            "Número de cuotas en días (entero positivo). "
            "Convertir: '1 mes' → 30, 'dos semanas' → 14. "
            "Si no fue mencionado, retornar null."
        )
    )
    moneda: Optional[Literal["CLP", "USD", "UF", "DESCONOCIDO"]] = Field(
        default="DESCONOCIDO",
        description=(
            "Moneda normalizado al Literal exacto. "
            "'dolares', 'dolar', 'US$200' → USD. "
            "'UF', 'unidades de fomento', '200 UF' → UF. "
            "'pesos', 'CLP', '$1000' → CLP. "
            "Si no fue mencionado, retornar 'DESCONOCIDO'."
        )
    )

    @field_validator("monto", mode="before")
    @classmethod
    def clean_monto(cls, v):
        if isinstance(v, str):
            clean_v = re.sub(r'[.$ ]', '', v)
            try: return float(clean_v)
            except: return None
        return v

    # Ayudar al LLM a encasillar la respuesta en el Literal exacto
    @field_validator("moneda", mode="before")
    @classmethod
    def normalize_moneda(cls, v: str) -> str:
        if not v: return "DESCONOCIDO"
        v = v.upper()
        if any(kw in v for kw in ["USD", "DOLAR", "DÓLAR"]): return "USD"
        if "UF" in v: return "UF"
        if any(kw in v for kw in ["CLP", "PESOS", "PESO"]): return "CLP"
        return v
    

class DapDecisionExtraction(BaseModel):
    decision: str = Field(description="ACCEPTED, REJECTED, PREGUNTA, u OTRO")
    razonamiento: str = Field(description="Breve explicación de la elección")

class DapOTPExtraction(BaseModel):
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
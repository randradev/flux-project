"""
app/graph/nodes/schemas/common_schemas.py
─────────────────────────────────────────────────────────────
Esquemas Pydantic para extracción estructurada en nodos transversales.
Usados con LLM.with_structured_output() en los nodos COMMON.

ESTILO: Mismo contrato que loan_schemas.py.
  - Campos Optional con None como default.
  - Validadores @field_validator normalizan valores centinela.
  - Campo `razonamiento` para trazabilidad del LLM.
  - Campo `confianza` para logging y futuros umbrales de decisión.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal


class IntentExtractionSchema(BaseModel):
    """
    Schema para INTENT_ROUTER_NODE.
    Clasifica la intención del usuario en un producto financiero o consulta general.

    Usado en: app/graph/nodes/common.py → intent_router_node
    """

    razonamiento: str = Field(
        default="",
        description=(
            "Justificación breve de por qué se clasifica en esta categoría, "
            "basada ÚNICAMENTE en el texto del mensaje del usuario."
        )
    )
    intencion: Literal["LOAN", "ACCOUNT", "DAP", "GENERAL"] = Field(
        description=(
            "Categoría de intención detectada:\n"
            "  LOAN    — Crédito, préstamo, financiamiento, plata prestada.\n"
            "  ACCOUNT — Cuenta corriente, cuenta bancaria, abrir cuenta.\n"
            "  DAP     — Depósito a plazo, inversión, ahorrar con intereses.\n"
            "  GENERAL — Saludo, pregunta general, duda, o mensaje fuera de categoría. También aplica a mensajes ambiguos o que no coinciden con nada."
            "  Protocolo ante ambigüedad: No intentes adivinar si no hay keywords claras, DEBES marcarlo como GENERAL."
        )
    )
    confianza: Optional[Literal["ALTA", "MEDIA", "BAJA"]] = Field(
        default="MEDIA",
        description=(
            "Nivel de certeza de la clasificación:\n"
            "  ALTA  — El mensaje es explícito y no hay ambigüedad.\n"
            "  MEDIA — El mensaje es probable pero podría interpretarse de otra forma.\n"
            "  BAJA  — Poca información; la clasificación es una suposición razonada."
            "  Protocolo ante ambigüedad: Si el usuario es vago, marca BAJA."
        )
    )

    @field_validator("intencion", "confianza", mode="before")
    @classmethod
    def vertex_placeholder_cleaner(cls, v, info):
        """
        Maneja la 'Alucinación por Presión' de Vertex AI.
        Si detecta placeholders o valores inventados fuera de rango, 
        fuerza el ruteo a GENERAL con confianza BAJA.
        """
        # 1. Placeholders comunes de 'escape' que Gemini usa cuando no sabe qué poner
        placeholders = {None, "NULL", "NONE", "DESCONOCIDO", "UNKNOWN", "", "N/A"}
        
        is_placeholder = v in placeholders or str(v).upper() in placeholders

        # 2. Si detectamos un placeholder, devolvemos el valor de seguridad
        if is_placeholder:
            if info.field_name == "intencion":
                return "GENERAL"
            return "BAJA"

        # 3. Si llega un string, validamos que sea uno de los permitidos
        if isinstance(v, str):
            val = v.upper().strip()
            
            if info.field_name == "intencion":
                valid_intents = {"LOAN", "ACCOUNT", "DAP", "GENERAL"}
                # Si el valor no es válido, Gemini se lo inventó -> GENERAL + BAJA (en el siguiente paso)
                return val if val in valid_intents else "GENERAL"
            
            if info.field_name == "confianza":
                valid_conf = {"ALTA", "MEDIA", "BAJA"}
                return val if val in valid_conf else "BAJA"

        # 4. Fallback final
        return v
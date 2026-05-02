"""
app/graph/constants.py
─────────────────────────────────────────────────────────────
Constantes de negocio compartidas por nodos y edges.

REGLA: Cualquier string que viaje en session["just_completed_step"]
       DEBE estar definido aquí. Nunca usar strings literales sueltos.
"""


class CompletedStep:
    """
    Valores válidos para session["just_completed_step"].
    Flag volátil: vive exactamente un turno.
    Se setea al completar un paso; se limpia en el return del nodo generador.
    """
    # ── Recolección (ya existentes) ───────────────────────────
    LOAN_PROFILE    = "LOAN_PROFILE"
    LOAN_SIMULATION = "LOAN_SIMULATION"
    ACCOUNT_PROFILE = "ACCOUNT_PROFILE"
    DAP_DATA        = "DAP_DATA"

    # ── Evaluación y Oferta (NUEVOS) ──────────────────────────
    LOAN_RISK_SUCCESS  = "LOAN_RISK_SUCCESS"   # Motor calculó y aprobó
    LOAN_RISK_REJECTED = "LOAN_RISK_REJECTED"  # Motor calculó y rechazó por política

    # ── Formalización (NUEVOS) ────────────────────────────────
    LOAN_PRE_APPROVED  = "LOAN_PRE_APPROVED"   # Usuario aceptó la oferta
    LOAN_OTP_SUCCESS   = "LOAN_OTP_SUCCESS"    # OTP validado correctamente

    # ── Excepciones (NUEVOS) ──────────────────────────────────
    LOAN_SECURITY_BLOCK  = "LOAN_SECURITY_BLOCK"   # 3 intentos OTP fallidos
    LOAN_CLOSED_BY_USER  = "LOAN_CLOSED_BY_USER"   # Usuario rechazó la oferta


class ProductPrefix:
    """
    Prefijos de producto para inferir el producto desde current_node.
    Usados en route_after_welcome para detectar cambio de intención (P0).
    """
    LOAN    = "LOAN"
    ACCOUNT = "ACCOUNT"
    DAP     = "DAP"

    # Mapa: prefijo del current_node (UPPER) → código de producto
    NODE_TO_PRODUCT: dict[str, str] = {
        "LOAN":    LOAN,
        "ACCOUNT": ACCOUNT,
        "DAP":     DAP,
    }

    @classmethod
    def from_node(cls, current_node: str) -> str | None:
        """Infiere el producto desde el current_node. Ej: 'LOAN_COLLECTING_PROFILE' → 'LOAN'."""
        for prefix, product in cls.NODE_TO_PRODUCT.items():
            if current_node.startswith(prefix):
                return product
        return None
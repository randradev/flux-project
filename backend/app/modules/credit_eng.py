"""
app/modules/credit_eng.py
─────────────────────────────────────────────────────────────
Motor de Cálculo de Riesgo para Crédito de Consumo.

DISEÑO: Función pura. No lee ni escribe el State de LangGraph.
        El nodo loan_risk_engine_node actúa como adaptador.

INPUTS: Diccionarios de preparation_data y collecting_data
        (sub-cajones loan_profile y loan_sim).

OUTPUT: Diccionario compatible con LoanEngineResult (state.py).

EXCEPCIONES CONTROLADAS:
  - PolicyRejectionError: Incumplimiento de requisitos de negocio.
  - PaymentCapacityError: Cuota supera el 30% de la renta.
  - EngineCalculationError: Error matemático no esperado.
"""

import math
from dataclasses import dataclass

# ── Excepciones de Dominio ─────────────────────────────────

class PolicyRejectionError(Exception):
    """
    Se lanza cuando el cliente no cumple las condiciones mínimas de elegibilidad.
    Transporta el código de motivo_rechazo para ser escrito en el State.
    """
    def __init__(self, motivo: str):
        self.motivo = motivo  # ERR_EDAD | ERR_RENTA | ERR_ANTIGUEDAD
        # NOTA AUDITORÍA: ERR_SCORING definido en state.py no se implementa en Fase 2
        # ya que el scoring solo determina tasa, no es motivo de rechazo según RN.
        super().__init__(motivo)

class PaymentCapacityError(Exception):
    """
    Se lanza cuando la cuota calculada supera el 30% de la renta.
    La cuota calculada se transporta para poder registrarla en el State.
    """
    def __init__(self, cuota_calculada: int, cuota_maxima: int):
        self.cuota_calculada = cuota_calculada
        self.cuota_maxima = cuota_maxima
        super().__init__("ERR_CAPACIDAD_PAGO")

class EngineCalculationError(Exception):
    """Wrapper para errores matemáticos inesperados (división por cero, overflow)."""
    pass


# ── Constantes de Negocio ──────────────────────────────────
# Centralizadas aquí: cualquier cambio de política solo toca este bloque.

ELEGIBILIDAD = {
    "edad_min": 18,
    "renta_min": 500_000,
    "antiguedad_min_meses": 6,
    "plazo_min": 6,   # <--- NUEVO
    "plazo_max": 48,  # <--- NUEVO
    "monto_min": 100_000,      # <--- NUEVO
    "monto_max": 30_000_000,   # <--- NUEVO
}

SCORING_PONDERACIONES = {
    "estudios": {
        "POSTGRADO": 20, "UNIVERSITARIO": 15, "TECNICO": 10, "MEDIA": 5,
    },
    "antiguedad": {          # Umbrales en meses
        "senior": (24, 20),  # >= 24 meses → +20 pts
        "mid":    (12, 10),  # 12–23 meses → +10 pts
        "junior": (0,   5),  # < 12 meses  → +5 pts
    },
    "edad": {
        "prime":  ((25, 55), 20),
        "young":  ((18, 24),  5),
        "mature": ((56, 65),  5),
    },
    "renta": {
        "alta":  (3_000_000, 40),
        "media": (1_000_000, 25),
        "baja":  (0,         10),
    },
}

TASAS_POR_RIESGO = {
    "Bajo":  0.012,
    "Medio": 0.020,
    "Alto":  0.035,
}

TRAMOS_RIESGO = {
    "Bajo":  80,   # scoring > 80 → Riesgo Bajo
    "Medio": 50,   # 50–80 → Riesgo Medio; < 50 → Alto
}


# ── Motor Principal ────────────────────────────────────────

class CreditEngine:
    """
    Motor de cálculo de riesgo para Crédito de Consumo.

    INSTANCIACIÓN:
        engine = CreditEngine(preparation_data, loan_profile, loan_sim)
        result = engine.run()

    OUTPUT: Diccionario compatible con LoanEngineResult de state.py.

    CONTRATO DE INPUTS:
        preparation_data: {"edad": int, "nombre": str, "rut": str, "mail": str}
        loan_profile:     {"renta": int, "antiguedad_laboral": int, "nivel_estudios": str}
        loan_sim:         {"monto_solicitado": int, "plazo_solicitado": int}
    """

    def __init__(
        self,
        preparation_data: dict,
        loan_profile: dict,
        loan_sim: dict,
    ):
        # Extraer campos directamente. Los nodos de recolección garantizan
        # la presencia de estos campos antes de invocar al motor.
        self.edad              = preparation_data["edad"]
        self.renta             = loan_profile["renta"]
        self.antiguedad_meses  = loan_profile["antiguedad_laboral"]
        self.nivel_estudios    = loan_profile["nivel_estudios"]
        self.monto_solicitado  = loan_sim["monto_solicitado"]
        self.plazo             = loan_sim["plazo_solicitado"]

    # ── Método Orquestador ─────────────────────────────────

    def run(self) -> dict:
        """
        Punto de entrada único del motor.

        PROCESO:
          1. Verificar elegibilidad mínima (lanza PolicyRejectionError si falla).
          2. Calcular scoring → nivel de riesgo → tasa de interés.
          3. Calcular cuota mensual (Amortización Francesa).
          4. Validar capacidad de pago (lanza PaymentCapacityError si falla).
          5. Calcular CTC, Total Intereses y CAE.
          6. Retornar diccionario de resultado.

        EXCEPCIONES: PolicyRejectionError, PaymentCapacityError, EngineCalculationError.
        """
        try:
            self._verificar_elegibilidad()

            scoring        = self._calcular_scoring()
            nivel_riesgo   = self._determinar_nivel_riesgo(scoring)
            tasa           = TASAS_POR_RIESGO[nivel_riesgo]

            cuota          = self._calcular_cuota_francesa(self.monto_solicitado, tasa, self.plazo)
            cuota_max      = math.floor(self.renta * 0.30)

            self._validar_capacidad_pago(cuota, cuota_max)

            ctc             = math.ceil(cuota * self.plazo)
            total_intereses = ctc - self.monto_solicitado
            cae             = self._calcular_cae(tasa)

            return {
                "status_proceso":         "PRE_APPROVED",
                "scoring_puntos":          scoring,
                "nivel_riesgo":            nivel_riesgo,
                "tasa_interes_mensual":    tasa,
                "cuota_mensual":           cuota,
                "cuota_maxima_permitida":  cuota_max,
                "capacidad_pago_valida":   True,
                "ctc":                     ctc,
                "total_intereses":         total_intereses,
                "cae":                     round(cae, 6),
                "monto_aprobado":          self.monto_solicitado,
                "plazo_aprobado":          self.plazo,
                "motivo_rechazo":          None,
            }

        except (PolicyRejectionError, PaymentCapacityError):
            raise  # El nodo wrapper los captura y arma el dict de rechazo.

        except Exception as e:
            raise EngineCalculationError(f"Error interno del motor: {e}") from e

    # ── Métodos Privados ───────────────────────────────────

    def _verificar_elegibilidad(self) -> None:
        """
        Verifica las tres condiciones mínimas de política, en orden de prioridad.
        Lanza PolicyRejectionError con el código específico al primer fallo.
        """
        if self.edad < ELEGIBILIDAD["edad_min"]:
            raise PolicyRejectionError("ERR_EDAD")
        if self.renta < ELEGIBILIDAD["renta_min"]:
            raise PolicyRejectionError("ERR_RENTA")
        if self.antiguedad_meses < ELEGIBILIDAD["antiguedad_min_meses"]:
            raise PolicyRejectionError("ERR_ANTIGUEDAD")

        if not (ELEGIBILIDAD["plazo_min"] <= self.plazo <= ELEGIBILIDAD["plazo_max"]):
            raise PolicyRejectionError("ERR_PLAZO")
        if not (ELEGIBILIDAD["monto_min"] <= self.monto_solicitado <= ELEGIBILIDAD["monto_max"]):
            raise PolicyRejectionError("ERR_MONTO")

    def _calcular_scoring(self) -> int:
        """
        Aplica las cuatro ponderaciones y retorna el puntaje total (0-100).
        Fórmula: S = P_estudios + P_antiguedad + P_edad + P_renta
        """
        p_estudios    = SCORING_PONDERACIONES["estudios"].get(self.nivel_estudios, 5)
        p_antiguedad  = self._puntaje_antiguedad()
        p_edad        = self._puntaje_edad()
        p_renta       = self._puntaje_renta()

        return p_estudios + p_antiguedad + p_edad + p_renta

    def _puntaje_antiguedad(self) -> int:
        ant = self.antiguedad_meses
        senior_umbral, senior_pts = SCORING_PONDERACIONES["antiguedad"]["senior"]
        mid_umbral,    mid_pts    = SCORING_PONDERACIONES["antiguedad"]["mid"]
        _,             junior_pts = SCORING_PONDERACIONES["antiguedad"]["junior"]

        if ant >= senior_umbral:
            return senior_pts
        elif ant >= mid_umbral:
            return mid_pts
        else:
            return junior_pts

    def _puntaje_edad(self) -> int:
        e = self.edad
        for label, (rango, pts) in SCORING_PONDERACIONES["edad"].items():
            if rango[0] <= e <= rango[1]:
                return pts
        return 0  # Fuera de rango (>65): no aporta puntos.

    def _puntaje_renta(self) -> int:
        r = self.renta
        alta_umbral,  alta_pts  = SCORING_PONDERACIONES["renta"]["alta"]
        media_umbral, media_pts = SCORING_PONDERACIONES["renta"]["media"]
        _,            baja_pts  = SCORING_PONDERACIONES["renta"]["baja"]

        if r > alta_umbral:
            return alta_pts
        elif r >= media_umbral:
            return media_pts
        else:
            return baja_pts

    @staticmethod
    def _determinar_nivel_riesgo(scoring: int) -> str:
        if scoring > TRAMOS_RIESGO["Bajo"]:
            return "Bajo"
        elif scoring >= TRAMOS_RIESGO["Medio"]:
            return "Medio"
        else:
            return "Alto"

    @staticmethod
    def _calcular_cuota_francesa(monto: int, tasa: float, plazo: int) -> int:
        """
        Amortización Francesa: M = P * [i(1+i)^n] / [(1+i)^n - 1]
        Redondea al entero superior (math.ceil).

        GUARDRAIL: Si tasa == 0 (imposible por contrato, pero defensivo),
                   retorna math.ceil(monto / plazo).
        """
        if tasa == 0:
            return math.ceil(monto / plazo)

        factor = (1 + tasa) ** plazo
        cuota  = monto * (tasa * factor) / (factor - 1)
        return math.ceil(cuota)

    @staticmethod
    def _validar_capacidad_pago(cuota: int, cuota_max: int) -> None:
        """Lanza PaymentCapacityError si la cuota supera el 30% de la renta."""
        if cuota > cuota_max:
            raise PaymentCapacityError(
                cuota_calculada=cuota,
                cuota_maxima=cuota_max,
            )

    @staticmethod
    def _calcular_cae(tasa_mensual: float) -> float:
        """
        CAE = (1 + i)^12 - 1
        Retorna decimal. Ej: 0.268 (26.8% anual).
        """
        return (1 + tasa_mensual) ** 12 - 1
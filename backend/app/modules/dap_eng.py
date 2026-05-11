"""
app/modules/dap_eng.py
─────────────────────────────────────────────────────────────
Motor de Cálculo de Inversión para Depósito a Plazo (DAP).

DISEÑO: Función pura. No lee ni escribe el State de LangGraph directamente.
        El nodo dap_investment_engine_node actúa como adaptador.

INPUTS: Diccionarios de preparation_data y collecting_data
        (sub-cajón dap_params).

OUTPUT: Diccionario compatible con DapEngineResult (state.py).

EXCEPCIONES CONTROLADAS:
  - PolicyRejectionError: Incumplimiento de requisitos de negocio.
  - EngineCalculationError: Error de procesamiento no esperado.
"""

# ── Excepciones de Dominio ─────────────────────────────────

class PolicyRejectionError(Exception):
    """
    Se lanza cuando el cliente no cumple las condiciones mínimas de elegibilidad.
    Transporta el código de motivo_rechazo (ERR_EDAD | ERR_MONTO_MIN | ERR_MONTO_MAX).
    """
    def __init__(self, motivo: str):
        self.motivo = motivo
        super().__init__(motivo)

class EngineCalculationError(Exception):
    """
    Se lanza cuando hay un fallo en la lógica interna del motor (ej: datos faltantes
    cruciales que no fueron atajados en la recolección, o errores de parseo).
    """
    def __init__(self, mensaje: str):
        super().__init__(f"Error crítico en el cálculo del motor de DAP: {mensaje}")


# ── Constantes de Negocio (Reglas de dap-rn.md) ────────────

EDAD_MINIMA          = 18
MONTO_MINIMO_CLP     = 50_000
MONTO_MAXIMO_CLP     = 50_000_000

PLAZOS_VALIDOS       = {7, 14, 30, 180, 360}
PLAZO_MIN_DIAS       = 7
PLAZO_MAX_DIAS       = 360

MONEDAS_VALIDAS      = {"CLP", "UF", "USD"}

TASA_BASE_MENSUAL    = 0.002        # 0.2% mensual fijo
PREMIO_PLAZO_STEP    = 0.0005       # 0.05% por cada 30 días completos de permanencia

# ── Valores de Referencia para Conversión ──────────────────
# TODO: Reemplazar con consumo real de API externa (valor del día).
# El motor usa estos placeholders en ausencia de conexión a la fuente de datos.
VALOR_UF_CLP         = 38_000.0    # Valor referencial de la UF en CLP
VALOR_USD_CLP        = 950.0        # Valor referencial del USD en CLP

# ── IPC de Referencia ──────────────────────────────────────
# TODO: Reemplazar con consumo real de API externa (IPC vigente).
# Solo se aplica como ajuste sumatorio cuando la moneda escogida es CLP.
IPC_MENSUAL_VIGENTE  = 0.003        # 0.3% — corrección monetaria de referencia


# ── Motor Principal ────────────────────────────────────────

class DapEngine:
    """
    Contiene la lógica core para calcular la rentabilidad de un Depósito a Plazo.
    Todos sus métodos internos son estáticos e idempotentes.
    """
    def __init__(self, preparation_data: dict, dap_params: dict):
        self.preparation_data = preparation_data
        self.dap_params = dap_params
        # Inicializamos para evitar AttributeError en el nodo si hay un rechazo temprano
        self.conversion_rate_used = 1.0
        self.ipc_applied = 0.0
        self.term_premium = 0.0
        self.monthly_rate_total = 0.0
        self.period_rate = 0.0
        self.estimated_gain = 0.0
        self.total_return = 0.0

    def run(self) -> dict:
        # Ejecutamos la lógica
        res = self.evaluate(self.preparation_data, self.dap_params)

        # Seteamos atributos en el objeto para que el nodo (el calco) pueda leerlos en el except
        self.conversion_rate_used = res.get("conversion_rate_used", 1.0)
        self.ipc_applied          = res.get("ipc_applied", 0.0)
        self.term_premium         = res.get("term_premium", 0.0)
        self.monthly_rate_total   = res.get("monthly_rate_total", 0.0)
        self.period_rate          = res.get("period_rate", 0.0)
        self.estimated_gain       = res.get("estimated_gain", 0.0)
        self.total_return         = res.get("total_return", 0.0)

        return res

    @staticmethod
    def evaluate(preparation_data: dict, dap_params: dict) -> dict:
        """
        Ejecuta el flujo completo de cálculo de inversión para el Depósito a Plazo.
        """
        try:
            # 1. Extracción y normalización de datos
            edad   = int(preparation_data.get("edad", 0))
            monto  = float(dap_params.get("monto", 0.0))
            moneda = str(dap_params.get("moneda", "")).strip().upper()
            plazo  = int(dap_params.get("plazo", 0))

            if monto == 0.0 or not moneda or plazo == 0:
                raise EngineCalculationError("Faltan parámetros de inversión requeridos para la evaluación")

            if moneda not in MONEDAS_VALIDAS:
                raise EngineCalculationError(f"Moneda no reconocida: '{moneda}'. Valores válidos: {MONEDAS_VALIDAS}")

            if plazo < PLAZO_MIN_DIAS or plazo > PLAZO_MAX_DIAS:
                raise PolicyRejectionError("ERR_FUERA_PLAZO")

            # 2. Conversión a CLP para validación de rango (puede lanzar EngineCalculationError)
            monto_clp, conversion_rate = DapEngine._convertir_a_clp(monto, moneda)

            # 3. Elegibilidad (puede lanzar PolicyRejectionError)
            DapEngine._validar_elegibilidad_minima(edad, monto_clp)

            # 4. Resolución del ajuste IPC (solo si la moneda es CLP)
            ipc_aplicado = DapEngine._resolver_ipc(moneda)

            # 5. Cálculo de Premio por Plazo (step function sobre 30 días)
            term_premium = DapEngine._calcular_premio_plazo(plazo)

            # 6. Cálculo de Tasa Mensual Total
            monthly_rate_total = DapEngine._calcular_tasa_mensual(term_premium, ipc_aplicado)

            # 7. Cálculo de Tasa del Periodo (proporcional a los días exactos)
            period_rate = DapEngine._calcular_tasa_periodo(monthly_rate_total, plazo)

            # 8. Cálculo de Ganancia y Retorno Final (en moneda original del usuario)
            estimated_gain, total_return = DapEngine._calcular_retorno(monto, period_rate)

            # 9. Retorno de Éxito (Mapea a DapEngineResult)
            return {
                "status_proceso":       "PRE_APPROVED",
                "is_elegible":          True,
                "monto":                monto,    
                "plazo":                plazo,    
                "moneda":               moneda,   
                "conversion_rate_used": conversion_rate,
                "ipc_applied":          ipc_aplicado,
                "term_premium":         term_premium,
                "monthly_rate_total":   monthly_rate_total,
                "period_rate":          period_rate,
                "estimated_gain":       estimated_gain,
                "total_return":         total_return,
                "motivo_rechazo":       None,
            }

        except (PolicyRejectionError, EngineCalculationError):
            # Dejamos que estas pasen directo al nodo
            raise
        except Exception as e:
            # Cualquier otra cosa (TypeErrors, etc.) sí es un error de cálculo
            raise EngineCalculationError(str(e))

    # ── Métodos de Lógica Interna ──────────────────────────────

    @staticmethod
    def _convertir_a_clp(monto: float, moneda: str) -> tuple[float, float]:
        """
        Convierte el monto ingresado por el usuario a CLP para la validación de rango.
        Retorna: (monto_en_clp, tasa_de_conversion_usada)
        Si la moneda ya es CLP, la tasa de conversión retornada es 1.0.
        """
        if moneda == "CLP":
            return monto, 1.0
        elif moneda == "UF":
            return monto * VALOR_UF_CLP, VALOR_UF_CLP
        elif moneda == "USD":
            return monto * VALOR_USD_CLP, VALOR_USD_CLP
        else:
            # Guardia adicional: el flujo ya valida la moneda antes de llegar aquí
            raise EngineCalculationError(f"Moneda no convertible: '{moneda}'")

    @staticmethod
    def _validar_elegibilidad_minima(edad: int, monto_clp: float) -> None:
        """
        Verifica el cumplimiento de los pisos y techos mínimos.
        El orden de validación es importante para entregar el error más relevante.
        """
        if edad < EDAD_MINIMA:
            raise PolicyRejectionError("ERR_EDAD")

        if monto_clp < MONTO_MINIMO_CLP:
            raise PolicyRejectionError("ERR_MONTO_MIN")

        if monto_clp > MONTO_MAXIMO_CLP:
            raise PolicyRejectionError("ERR_MONTO_MAX")

    @staticmethod
    def _resolver_ipc(moneda: str) -> float:
        """
        Retorna el ajuste por IPC vigente si la moneda es CLP, de lo contrario 0.0.
        El IPC es un factor sumatorio sobre la tasa mensual total (solo CLP).
        """
        if moneda == "CLP":
            return IPC_MENSUAL_VIGENTE
        return 0.0

    @staticmethod
    def _calcular_premio_plazo(plazo: int) -> float:
        """
        Calcula el premio por plazo como step function: 0.05% por cada 30 días completos.
        Lógica de escalones (no lineal): solo suma si plazo >= 30 días.
        Ej: 7d → 0%, 14d → 0%, 30d → 0.05%, 180d → 0.30%, 360d → 0.60%
        """
        return (plazo // 30) * PREMIO_PLAZO_STEP

    @staticmethod
    def _calcular_tasa_mensual(term_premium: float, ipc_aplicado: float) -> float:
        """
        Compone la tasa mensual total sumando los 3 factores:
          i_total = i_base + premio_plazo + ajuste_ipc
        """
        return TASA_BASE_MENSUAL + term_premium + ipc_aplicado

    @staticmethod
    def _calcular_tasa_periodo(monthly_rate_total: float, plazo: int) -> float:
        """
        Calcula la tasa real proporcional a los días exactos de la inversión.
        Fórmula: i_periodo = i_mensual * (plazo_dias / 30)
        """
        return monthly_rate_total * (plazo / 30)

    @staticmethod
    def _calcular_retorno(monto: float, period_rate: float) -> tuple[float, float]:
        """
        Proyecta la ganancia estimada y el retorno final sobre el capital en moneda original.
        La ganancia y el retorno se expresan en la misma moneda en que el usuario invirtió.
        Retorna: (ganancia_estimada, retorno_total)
        """
        estimated_gain = monto * period_rate
        total_return   = monto + estimated_gain
        return estimated_gain, total_return
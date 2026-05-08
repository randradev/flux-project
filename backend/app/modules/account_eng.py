"""
app/modules/account_eng.py
─────────────────────────────────────────────────────────────
Motor de Evaluación Comercial para Cuenta Corriente.

DISEÑO: Función pura. No lee ni escribe el State de LangGraph directamente.
        El nodo account_evaluation_engine_node actúa como adaptador.

INPUTS: Diccionarios de preparation_data y collecting_data
        (sub-cajón account_profile).

OUTPUT: Diccionario compatible con AccountEngineResult (state.py).

EXCEPCIONES CONTROLADAS:
  - PolicyRejectionError: Incumplimiento de requisitos de negocio.
  - EngineCalculationError: Error de procesamiento no esperado.
"""

# ── Excepciones de Dominio ─────────────────────────────────

class PolicyRejectionError(Exception):
    """
    Se lanza cuando el cliente no cumple las condiciones mínimas de elegibilidad.
    Transporta el código de motivo_rechazo (ERR_EDAD | ERR_RENTA | ERR_ANTIGUEDAD).
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
        super().__init__(f"Error crítico en el cálculo del motor de cuenta: {mensaje}")


# ── Constantes de Negocio (Reglas de cuenta-rn.md) ─────────

EDAD_MINIMA = 18
RENTA_MINIMA = 500000
ANTIGUEDAD_MINIMA = 6
ANTIGUEDAD_LINEA_CREDITO = 12

TRAMO_START_MAX = 1000000
TRAMO_MEDIUM_MAX = 2500000

CATEGORIAS = {
    "START": "START",
    "MEDIUM": "MEDIUM",
    "ADVANCE": "ADVANCE"
}

NIVELES_UPGRADE = ["UNIVERSITARIO", "POSTGRADO"]


# ── Motor Principal ────────────────────────────────────────

class AccountEngine:
    """
    Contiene la lógica core para asignar perfil, upgrades y línea de crédito.
    Todos sus métodos internos son estáticos e idempotentes.
    """
    def __init__(self, preparation_data: dict, account_profile: dict):
        self.preparation_data = preparation_data
        self.account_profile = account_profile
        # Inicializamos para evitar AttributeError en el nodo si hay un rechazo temprano
        self.base_category = ""
        self.final_category = ""
        self.has_upgrade = False
        self.credit_line = 0
        self.monthly_cost = 0
    
    def run(self) -> dict:
        # Ejecutamos la lógica
        res = self.evaluate(self.preparation_data, self.account_profile)
        
        # Seteamos atributos en el objeto para que el nodo (el calco) pueda leerlos en el except
        self.base_category = res.get("base_category", "")
        self.final_category = res.get("final_category", "")
        self.has_upgrade = res.get("has_upgrade", False)
        self.credit_line = res.get("credit_line_amount", 0)
        self.monthly_cost = res.get("monthly_cost", 0)
        
        return res
    @staticmethod
    def evaluate(preparation_data: dict, account_profile: dict) -> dict:
        """
        Ejecuta el flujo completo de evaluación comercial para la cuenta corriente.
        """
        try:
            # 1. Extracción y normalización de datos
            edad = int(preparation_data.get("edad", 0))
            renta = int(account_profile.get("renta", 0))
            antiguedad = int(account_profile.get("antiguedad_laboral", 0))
            nivel_estudios = str(account_profile.get("nivel_estudios", "")).strip().upper()

            if renta == 0 or antiguedad == 0 or not nivel_estudios:
                 raise EngineCalculationError("Faltan datos financieros requeridos para la evaluación")

            # 2. Elegibilidad (puede lanzar PolicyRejectionError)
            AccountEngine._validar_elegibilidad_minima(edad, renta, antiguedad)

            # 3. Asignación de Categoría Base
            base_category = AccountEngine._asignar_categoria_base(renta)

            # 4. Evaluación de Upgrade por Estudios
            final_category, has_upgrade = AccountEngine._aplicar_upgrade(base_category, nivel_estudios)

            # 5. Cálculo de Línea de Crédito
            credit_line = AccountEngine._calcular_linea_credito(final_category, antiguedad, renta)

            # 6. Retorno de Éxito (Mapea a AccountEngineResult)
            return {
                "status_proceso": "PRE_APPROVED",
                "is_elegible": True,
                "base_category": base_category,
                "final_category": final_category,
                "has_upgrade": has_upgrade,
                "credit_line_amount": credit_line,
                "monthly_cost": 0,  # Fijo por promoción MVP según RN
                "motivo_rechazo": None
            }
        
        except (PolicyRejectionError, EngineCalculationError):
            # Dejamos que estas pasen directo al nodo
            raise
        except Exception as e:
            # Cualquier otra cosa (TypeErrors, etc.) sí es un error de cálculo
            raise EngineCalculationError(str(e))

    # ── Métodos de Lógica Interna ──────────────────────────────

    @staticmethod
    def _validar_elegibilidad_minima(edad: int, renta: int, antiguedad: int) -> None:
        """
        Verifica el cumplimiento de los pisos mínimos.
        El orden de validación es importante para entregar el error más relevante.
        """
        if edad < EDAD_MINIMA:
            raise PolicyRejectionError("ERR_EDAD")
        
        if renta < RENTA_MINIMA:
            raise PolicyRejectionError("ERR_RENTA")
            
        if antiguedad < ANTIGUEDAD_MINIMA:
            raise PolicyRejectionError("ERR_ANTIGUEDAD")

    @staticmethod
    def _asignar_categoria_base(renta: int) -> str:
        """
        Asigna el tramo base estrictamente según los montos de renta.
        """
        if renta <= TRAMO_START_MAX:
            return CATEGORIAS["START"]
        elif renta <= TRAMO_MEDIUM_MAX:
            return CATEGORIAS["MEDIUM"]
        else:
            return CATEGORIAS["ADVANCE"]

    @staticmethod
    def _aplicar_upgrade(base_category: str, nivel_estudios: str) -> tuple[str, bool]:
        """
        Aplica un nivel de upgrade si el usuario posee título universitario o postgrado.
        Retorna: (categoria_final, has_upgrade)
        """
        if nivel_estudios in NIVELES_UPGRADE:
            if base_category == CATEGORIAS["START"]:
                return CATEGORIAS["MEDIUM"], True
            elif base_category == CATEGORIAS["MEDIUM"]:
                return CATEGORIAS["ADVANCE"], True
            # Si ya es ADVANCE, se mantiene ADVANCE pero consideramos que no hubo "salto" efectivo
            
        return base_category, False

    @staticmethod
    def _calcular_linea_credito(final_category: str, antiguedad: int, renta: int) -> int:
        """
        Calcula el cupo de la línea de crédito según las restricciones de RN.
        """
        # Si es categoría básica o no tiene la antigüedad suficiente
        if final_category == CATEGORIAS["START"] or antiguedad < ANTIGUEDAD_LINEA_CREDITO:
            return 0
            
        # Si cumple (MEDIUM/ADVANCE y >= 12 meses), obtiene el 50% de la renta líquida
        return int(renta * 0.5)
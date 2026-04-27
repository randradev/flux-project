Plan de Implementación — Fase 2: Crédito de Consumo

Ley del Plan: Ningún paso modifica lo que ya funciona. Los archivos state.py, workflow.py (estructura base), edges.py y loan_init_node son considerados inmutables salvo las extensiones explícitamente indicadas.


PASO 1 — El Motor de Cálculo (modules/credit_eng.py)
Contexto de Diseño
El motor es una función pura y determinista: mismos inputs → mismo output. No tiene side effects, no escribe en el State, no toca Supabase. El nodo loan_risk_engine_node en credit.py es simplemente el adaptador que extrae datos del State, llama al motor, y escribe el resultado en evaluation_results["loan_engine"]. Esta separación hace al motor testeable unitariamente sin LangGraph.
Sub-paso 1.1 — Estructura y Contrato de Clase
Archivo: app/modules/credit_eng.py
python"""
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
Punto de Revisión 1.1:

¿Los tres tipos de excepción cubren todos los motivo_rechazo del contrato de datos? Verificar contra credito-datos.md §4: ERR_EDAD, ERR_RENTA, ERR_ANTIGUEDAD → PolicyRejectionError. ERR_CAPACIDAD_PAGO → PaymentCapacityError. ✅
ERR_SCORING no existe en las reglas de negocio actuales (el scoring no tiene puntaje mínimo, solo determina la tasa). Está en el contrato de state.py como posibilidad futura. El motor no lo lanzará en Fase 2. Documentar esto explícitamente en el código.


Sub-paso 1.2 — Implementación de CreditEngine
python# ── Constantes de Negocio ──────────────────────────────────
# Centralizadas aquí: cualquier cambio de política solo toca este bloque.

ELEGIBILIDAD = {
    "edad_min": 18,
    "renta_min": 500_000,
    "antiguedad_min_meses": 6,
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
    "BAJO":  0.012,
    "MEDIO": 0.020,
    "ALTO":  0.035,
}

TRAMOS_RIESGO = {
    "BAJO":  80,   # scoring > 80 → Riesgo Bajo
    "MEDIO": 50,   # 50–80 → Riesgo Medio; < 50 → Alto
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
        if scoring > TRAMOS_RIESGO["BAJO"]:
            return "BAJO"
        elif scoring >= TRAMOS_RIESGO["MEDIO"]:
            return "MEDIO"
        else:
            return "ALTO"

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
Pruebas de Validación — PASO 1

Protocolo PASS: Todos los tests deben ejecutarse con pytest en modo aislado (sin LangGraph, sin Supabase). El motor es una caja negra pura.

Tests Unitarios requeridos en tests/test_credit_eng.py:
python# Caso 1 — PASS: Pre-aprobado con riesgo BAJO
# Input: edad=30, renta=2_000_000, ant=36m, estudios=UNIVERSITARIO,
#        monto=5_000_000, plazo=24
# Expected: status=PRE_APPROVED, nivel_riesgo=BAJO, tasa=0.012,
#           capacidad_pago_valida=True

# Caso 2 — PASS: Pre-aprobado con riesgo ALTO
# Input: edad=20, renta=700_000, ant=7m, estudios=MEDIA,
#        monto=1_000_000, plazo=12
# Expected: nivel_riesgo=ALTO, tasa=0.035

# Caso 3 — PASS: Rechazo por ERR_EDAD
# Input: edad=17 → raises PolicyRejectionError(motivo="ERR_EDAD")

# Caso 4 — PASS: Rechazo por ERR_RENTA
# Input: renta=400_000 → raises PolicyRejectionError(motivo="ERR_RENTA")

# Caso 5 — PASS: Rechazo por ERR_ANTIGUEDAD
# Input: ant=5 → raises PolicyRejectionError(motivo="ERR_ANTIGUEDAD")

# Caso 6 — PASS: Rechazo por ERR_CAPACIDAD_PAGO
# Input: renta=500_100, monto=28_000_000, plazo=6
# Expected: raises PaymentCapacityError

# Caso 7 — PASS: Verificación matemática de cuota francesa
# Input: monto=1_000_000, tasa=0.020, plazo=12
# Expected: cuota = math.ceil(1_000_000 * (0.020 * 1.020^12) / (1.020^12 - 1))
#           = math.ceil(92_560.xx) → valor preciso calculado externamente

# Caso 8 — PASS: CAE para tasa baja
# Input: tasa=0.012 → cae = round((1.012)^12 - 1, 6) = 0.153946 aprox.

PASO 2 — Nodos de Recolección e Inteligencia
Arquitectura de los Nodos Collecting
Los nodos de recolección operan en dos modos:

Modo Extracción: El LLM recibió un mensaje con datos procesables. Los extrae con with_structured_output y actualiza collecting_data.
Modo Re-pregunta: El mensaje del usuario es ambiguo o incompleto. El nodo retorna un mensaje solicitando nuevamente el dato, sin avanzar el grafo (la arista condicional lo detecta y hace loop).

Sub-paso 2.1 — Esquemas Pydantic
Archivo: app/graph/nodes/schemas/loan_schemas.py
python"""
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
        description="Renta líquida mensual en CLP. Ej: 'gano 1 millón' → 1000000."
    )
    antiguedad_laboral: Optional[int] = Field(
        default=None,
        description="Antigüedad laboral en MESES. Convertir años a meses. Ej: '2 años' → 24."
    )
    nivel_estudios: Optional[Literal["POSTGRADO", "UNIVERSITARIO", "TECNICO", "MEDIA"]] = Field(
        default=None,
        description=(
            "Nivel de estudios normalizado. "
            "'ingeniería', 'universidad', 'carrera' → UNIVERSITARIO. "
            "'magíster', 'doctorado', 'postgrado' → POSTGRADO. "
            "'técnico', 'ip', 'cft' → TECNICO. "
            "'media', 'liceo', 'cuarto medio' → MEDIA."
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
            "Normalizar expresiones: '5 millones' → 5000000, '$3.500.000' → 3500000."
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
Punto de Revisión 2.1:

El campo datos_completos es un guardrail semántico: evita que el LLM infiera datos que no fueron mencionados y los marque como completos. El nodo no confía en este campo ciegamente; valida explícitamente que los campos no sean None.
La conversión de unidades (años → meses, millones → CLP) ocurre dentro del LLM via la descripción del Field, no en el nodo. Esto simplifica la lógica del nodo.


Sub-paso 2.2 — Nodo loan_collecting_profile_node
python# En app/graph/nodes/credit.py (extensión del archivo existente)

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI  # o el provider que el proyecto use
from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction
from app.infra.supabase import update_application_semaphores

# El LLM se instancia a nivel de módulo (singleton de nodo).
# Ajustar modelo y temperatura según configuración del proyecto.
_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
_profile_extractor = _llm.with_structured_output(LoanProfileExtraction)


SYSTEM_PROMPT_PROFILE = """
Eres un asistente bancario experto en extracción de datos financieros.
Tu única tarea es analizar el mensaje del usuario e identificar los datos de perfil.

REGLAS:
- Extrae SOLO lo que el usuario mencionó explícitamente. No inventes ni asumas.
- Convierte unidades: años → meses (multiplicar por 12), millones → pesos (multiplicar por 1.000.000).
- Normaliza nivel_estudios a: POSTGRADO, UNIVERSITARIO, TECNICO o MEDIA.
- Si un dato no fue mencionado, déjalo como null.
- datos_completos = true SOLO si los tres campos tienen valor.
"""


def loan_collecting_profile_node(state: FluxState) -> dict:
    """
    Nodo LOAN_COLLECTING_PROFILE: extrae renta, antigüedad y nivel de estudios.

    ID LangGraph : loan_collecting_profile
    current_node : LOAN_COLLECTING_PROFILE

    MODO A (Extracción exitosa):
        - Actualiza collecting_data["loan_profile"] con los datos extraídos.
        - No emite mensaje (el grafo avanza silenciosamente si todos los datos están presentes).
        - Si faltan datos: emite re-pregunta específica.

    MODO B (Re-pregunta):
        - Conserva los datos ya recolectados en el State (merge, no reemplaza).
        - Retorna mensaje empático solicitando el dato faltante.

    NOTA DE PERSISTENCIA:
        El merge de datos es crítico para el Checkpointer. Si el usuario
        da la renta en un mensaje y la antigüedad en otro, ambos deben
        acumularse en loan_profile, no sobreescribirse.
    """
    session     = state.get("session", {})
    collecting  = state.get("collecting_data", {})
    messages    = state.get("messages", [])

    # Datos ya recolectados (de invocaciones previas de este nodo)
    current_profile: dict = collecting.get("loan_profile", {})

    # Último mensaje del usuario
    last_human_msg = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
        ""
    )

    # ── Extracción con LLM ─────────────────────────────────
    extracted: LoanProfileExtraction = _profile_extractor.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_PROFILE},
        {"role": "user",   "content": last_human_msg},
    ])

    # ── Merge defensivo: solo actualizar campos que llegaron con valor ─
    updated_profile = {**current_profile}
    if extracted.renta             is not None: updated_profile["renta"]             = extracted.renta
    if extracted.antiguedad_laboral is not None: updated_profile["antiguedad_laboral"] = extracted.antiguedad_laboral
    if extracted.nivel_estudios    is not None: updated_profile["nivel_estudios"]    = extracted.nivel_estudios

    # ── Determinar campos faltantes ────────────────────────
    missing = _get_missing_profile_fields(updated_profile)

    application_id = session.get("application_id")

    if not missing:
        # Todos los datos recolectados: avanzar silenciosamente
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="LOAN_COLLECTING_PROFILE",
                node_status="SUCCESS",
                engine_status="PENDING",
            )
        return {
            "collecting_data": {**collecting, "loan_profile": updated_profile},
            "session": {**session, "current_node": "LOAN_COLLECTING_PROFILE"},
        }
    else:
        # Datos incompletos: re-preguntar con contexto
        re_ask_msg = _build_profile_reprompt(missing, updated_profile)
        return {
            "messages":       [AIMessage(content=re_ask_msg)],
            "collecting_data": {**collecting, "loan_profile": updated_profile},
            "session":        {**session, "current_node": "LOAN_COLLECTING_PROFILE"},
        }


def _get_missing_profile_fields(profile: dict) -> list[str]:
    """Retorna lista de campos requeridos que aún no tienen valor."""
    required = ["renta", "antiguedad_laboral", "nivel_estudios"]
    return [f for f in required if not profile.get(f)]


def _build_profile_reprompt(missing: list[str], known: dict) -> str:
    """
    Construye un mensaje de re-pregunta empático y específico.
    Reconoce los datos ya entregados antes de pedir los faltantes.
    """
    known_parts = []
    if known.get("renta"):
        known_parts.append(f"renta de ${known['renta']:,.0f}")
    if known.get("antiguedad_laboral"):
        known_parts.append(f"{known['antiguedad_laboral']} meses de antigüedad")
    if known.get("nivel_estudios"):
        known_parts.append(f"estudios {known['nivel_estudios'].lower()}")

    field_labels = {
        "renta":             "tu renta líquida mensual",
        "antiguedad_laboral": "tu antigüedad laboral (en meses o años)",
        "nivel_estudios":    "tu nivel de estudios (Media, Técnico, Universitario o Postgrado)",
    }
    missing_labels = [field_labels[f] for f in missing]

    base = "Perfecto" if known_parts else "Entendido"
    known_str = f", ya tengo {', '.join(known_parts)}" if known_parts else ""
    missing_str = " y ".join(missing_labels)

    return f"{base}{known_str}. Para continuar, necesito que me indiques {missing_str}."
Sub-paso 2.3 — Nodo loan_collecting_simulation_node
La estructura es análoga a la del perfil. Las diferencias clave:
python# Extracto de las diferencias relevantes (la estructura completa sigue el mismo patrón)

SYSTEM_PROMPT_SIM = """
Eres un asistente bancario. Extrae el monto y plazo del crédito del mensaje del usuario.

REGLAS:
- monto_solicitado: entero en CLP. Rango válido: 100.000 a 30.000.000.
  Si el usuario da un monto fuera de rango, extráelo igual (la validación la hace el motor).
- plazo_solicitado: entero en meses. Rango válido: 6 a 48.
  Si dice '2 años' → 24. Si dice '1 año y medio' → 18.
- Si un dato no fue mencionado, déjalo como null.
"""

def loan_collecting_simulation_node(state: FluxState) -> dict:
    """
    Nodo LOAN_COLLECTING_SIMULATION: extrae monto_solicitado y plazo_solicitado.

    ID LangGraph : loan_collecting_simulation
    current_node : LOAN_COLLECTING_SIMULATION

    NOTA: Este nodo se ejecuta DESPUÉS de que loan_profile está completo.
          No tiene acceso a loan_profile porque no lo necesita.
    """
    # ... (mismo patrón: extracción, merge, missing check, re-pregunta)
    # El merge opera sobre collecting_data["loan_sim"], no sobre loan_profile.
Punto de Revisión 2.2–2.3:

Verificar que el merge defensivo funciona correctamente en sesiones reanudadas: si el usuario abandona y vuelve, el Checkpointer debe restaurar el loan_profile parcialmente completo y el nodo debe continuar desde donde estaba.
Verificar que el LLM no rellena campos que el usuario no mencionó. Test manual: enviar solo la renta y verificar que antiguedad_laboral sea None en el resultado del extractor.
El SYSTEM_PROMPT nunca menciona rangos de validación de negocio: esa responsabilidad es del motor. El nodo solo extrae.


Pruebas de Validación — PASO 2
python# Test 2.1 — Extracción completa en un solo mensaje
# Input msg: "Gano 1 millón y medio, llevo 3 años trabajando, soy universitario"
# Expected: renta=1_500_000, antiguedad_laboral=36, nivel_estudios="UNIVERSITARIO"
#           datos_completos=True, nodo retorna sin mensaje (avance silencioso)

# Test 2.2 — Extracción parcial: solo renta
# Input msg: "Mi renta es 800 mil"
# Expected: loan_profile={"renta": 800_000}, mensaje de re-pregunta sobre ant. y estudios

# Test 2.3 — Merge acumulativo (2 turnos)
# Turno 1: "Soy técnico y gano 900 mil" → profile={"renta":900000,"nivel_estudios":"TECNICO"}
# Turno 2: "Tengo 8 meses trabajando" → profile={"renta":900000,"nivel_estudios":"TECNICO","antiguedad_laboral":8}
# Expected: Avance silencioso en turno 2.

# Test 2.4 — Input ambiguo
# Input msg: "No sé, lo que venga" → todos los campos None, re-pregunta general

# Test 2.5 — Conversión de unidades
# "monto de 5 millones a 2 años" → monto=5_000_000, plazo=24

PASO 3 — El Cableado del Grafo
Sub-paso 3.1 — Nuevos Nodos a Registrar en workflow.py

Ley: Solo se agregan líneas. No se modifica ningún nodo o arista existente hasta que los nuevos estén validados.

python# Incorporar a build_graph() en workflow.py

# Nodos de Recolección (Crédito)
graph.add_node("loan_collecting_profile",    loan_collecting_profile_node)
graph.add_node("loan_collecting_simulation", loan_collecting_simulation_node)

# Nodos de Evaluación y Oferta
graph.add_node("loan_pre_approved",          loan_pre_approved_node)

# Nodos de Formalización
graph.add_node("loan_otp_validation",        loan_otp_validation_node)
graph.add_node("loan_formalization",         loan_formalization_node)
graph.add_node("loan_completed",             loan_completed_node)

# Nodos de Error y Cierre
graph.add_node("loan_rejected_policy",       loan_rejected_policy_node)
graph.add_node("loan_security_block",        loan_security_block_node)
graph.add_node("loan_closed_by_user",        loan_closed_by_user_node)
Sub-paso 3.2 — Mapa de Aristas Completo del Flujo de Crédito
loan_init
  └─[edge]──► loan_collecting_profile
                └─[cond: ¿profile completo?]
                    ├─ completo  ──► loan_collecting_simulation
                    └─ faltan datos ──► loan_collecting_profile (loop)

loan_collecting_simulation
  └─[cond: ¿sim completa?]
      ├─ completo ──► loan_risk_engine
      └─ faltan datos ──► loan_collecting_simulation (loop)

loan_risk_engine
  └─[cond: status_proceso]
      ├─ PRE_APPROVED      ──► loan_pre_approved
      ├─ REJECTED_POLICY   ──► loan_rejected_policy
      └─ ERROR_TECHNICAL   ──► [service_error — Fase 3]

loan_pre_approved
  └─[cond: pre_approval_status]
      ├─ ACCEPTED  ──► loan_otp_validation
      └─ REJECTED  ──► loan_closed_by_user

loan_otp_validation
  └─[cond: otp_status]
      ├─ VERIFIED ──► loan_formalization
      ├─ FAILED   ──► loan_otp_validation (loop)
      └─ BLOCKED  ──► loan_security_block

loan_formalization
  └─[cond: contract_status]
      ├─ SIGNED_AND_STAMPED ──► loan_completed
      └─ GENERATION_FAILED  ──► [service_error — Fase 3]

loan_completed      ──► END
loan_rejected_policy ──► END
loan_security_block  ──► END
loan_closed_by_user  ──► END
Sub-paso 3.3 — Funciones de Ruteo en edges.py
python# Agregar a app/graph/edges.py

def route_after_loan_collecting_profile(state: FluxState) -> str:
    """
    Ruta después de LOAN_COLLECTING_PROFILE.
    Si hay mensaje nuevo en la cola → el nodo ya hizo el loop (re-pregunta).
    La arista solo decide si avanzar o hacer loop basándose en el State.
    """
    profile = state.get("collecting_data", {}).get("loan_profile", {})
    required = ["renta", "antiguedad_laboral", "nivel_estudios"]
    if all(profile.get(f) for f in required):
        return "loan_collecting_simulation"
    return "loan_collecting_profile"  # loop


def route_after_loan_collecting_simulation(state: FluxState) -> str:
    loan_sim = state.get("collecting_data", {}).get("loan_sim", {})
    if loan_sim.get("monto_solicitado") and loan_sim.get("plazo_solicitado"):
        return "loan_risk_engine"
    return "loan_collecting_simulation"  # loop


def route_after_loan_risk_engine(state: FluxState) -> str:
    loan_engine = state.get("evaluation_results", {}).get("loan_engine", {})
    status = loan_engine.get("status_proceso", "ERROR_TECHNICAL")
    if status == "PRE_APPROVED":
        return "loan_pre_approved"
    elif status == "REJECTED_POLICY":
        return "loan_rejected_policy"
    else:
        return "loan_pre_approved"  # Fallback temporal hasta que exista service_error_node


def route_after_loan_pre_approved(state: FluxState) -> str:
    offer = state.get("offer_data", {}).get("loan", {})
    status = offer.get("pre_approval_status")
    if status == "ACCEPTED":
        return "loan_otp_validation"
    elif status == "REJECTED":
        return "loan_closed_by_user"
    # Estado intermedio: usuario aún no ha respondido (esperando input)
    return "loan_pre_approved"  # loop (el nodo debe emitir la tarjeta de transparencia)


def route_after_loan_otp_validation(state: FluxState) -> str:
    auth = state.get("auth_control", {})
    if auth.get("security_blocked"):
        return "loan_security_block"
    otp_generated = auth.get("otp_generated")
    otp_input     = auth.get("otp_user_input")
    if otp_generated and otp_input and otp_generated == otp_input:
        return "loan_formalization"
    return "loan_otp_validation"  # loop (fallo o primer ingreso)


def route_after_loan_formalization(state: FluxState) -> str:
    offer = state.get("offer_data", {}).get("loan", {})
    if offer.get("contract_status") == "SIGNED_AND_STAMPED":
        return "loan_completed"
    return "loan_completed"  # Fallback hasta que exista service_error_node
Punto de Revisión 3.1–3.3:

Los loops de re-pregunta son el riesgo más alto de este paso. Verificar que LangGraph no entra en un loop infinito si el LLM no puede extraer ningún dato. El nodo siempre debe emitir un mensaje cuando no hay datos suficientes, lo que garantiza que el grafo espera input del usuario antes de re-ejecutarse.
Confirmar que la arista condicional de loan_pre_approved funciona en dos tiempos: primera ejecución (sin pre_approval_status) → emite la tarjeta y espera. Segunda ejecución (con ACCEPTED/REJECTED) → avanza.


Pruebas de Validación — PASO 3
python# Test de Integración 3.1 — Ruta feliz completa (mock LLM, motor real)
# Simular el flujo: loan_init → collecting_profile (1 turno) →
#                  collecting_sim (1 turno) → risk_engine → pre_approved
# Expected: status_proceso = PRE_APPROVED, flujo llega a loan_pre_approved

# Test de Integración 3.2 — Loop de re-pregunta
# Simular collecting_profile con 2 turnos:
#   Turno 1: solo renta → permanece en loan_collecting_profile
#   Turno 2: ant + estudios → avanza a loan_collecting_simulation

# Test de Integración 3.3 — Ruta de rechazo
# Input motor → ERR_RENTA → flujo termina en loan_rejected_policy → END
# Expected: flow_result.status_code = REJECTED

# Test de Integración 3.4 — Flujo OTP (3 fallos → bloqueo)
# Simular 3 inputs incorrectos en loan_otp_validation
# Expected: auth_control.security_blocked = True, flujo llega a loan_security_block

PASO 4 — Gestión de Errores, Stubs y Estados Finales
Sub-paso 4.1 — Nodos de Error y Cierre
python# app/graph/nodes/credit.py (continuación)

from datetime import datetime, timezone


def loan_rejected_policy_node(state: FluxState) -> dict:
    """
    Nodo LOAN_REJECTED_POLICY: cierre por incumplimiento de política.
    Lee motivo_rechazo del motor y emite mensaje personalizado.

    ID LangGraph : loan_rejected_policy
    current_node : LOAN_REJECTED_POLICY
    """
    session       = state.get("session", {})
    prep          = state.get("preparation_data", {})
    loan_engine   = state.get("evaluation_results", {}).get("loan_engine", {})

    nombre        = prep.get("nombre", "").split()[0] or "amig@"
    motivo        = loan_engine.get("motivo_rechazo", "ERR_DESCONOCIDO")

    MENSAJES_RECHAZO = {
        "ERR_EDAD":           f"Lo sentimos, {nombre}. Para solicitar un crédito debes tener al menos 18 años.",
        "ERR_RENTA":          f"Lo sentimos, {nombre}. La renta mínima requerida es de $500.000 líquidos mensuales.",
        "ERR_ANTIGUEDAD":     f"Lo sentimos, {nombre}. Necesitas al menos 6 meses de antigüedad laboral.",
        "ERR_CAPACIDAD_PAGO": f"Lo sentimos, {nombre}. La cuota mensual supera el 30% de tu renta, lo que excede nuestra política de capacidad de pago.",
    }
    msg = MENSAJES_RECHAZO.get(motivo, f"Lo sentimos, {nombre}. Tu solicitud no pudo ser aprobada en esta oportunidad.")

    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_REJECTED_POLICY",
            node_status="SUCCESS",
            engine_status="COMPLETED",
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session":  {**session, "current_node": "LOAN_REJECTED_POLICY"},
        "flow_result": {
            "status_code":  "REJECTED",
            "close_reason": motivo,
            "product_name": "Crédito de Consumo",
            "closed_at":    datetime.now(timezone.utc).isoformat(),
        },
    }


def loan_security_block_node(state: FluxState) -> dict:
    """
    Nodo LOAN_SECURITY_BLOCK: bloqueo por intentos OTP fallidos.
    Escribe block_timestamp y marca security_blocked en auth_control.

    ID LangGraph : loan_security_block
    current_node : LOAN_SECURITY_BLOCK
    """
    session = state.get("session", {})
    prep    = state.get("preparation_data", {})
    auth    = state.get("auth_control", {})

    nombre    = prep.get("nombre", "").split()[0] or "amig@"
    timestamp = datetime.now(timezone.utc).isoformat()

    msg = (
        f"Por tu seguridad, {nombre}, hemos bloqueado temporalmente esta solicitud "
        f"tras {auth.get('otp_attempts', 3)} intentos de autenticación fallidos. "
        f"Podrás intentarlo nuevamente en 24 horas."
    )

    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_SECURITY_BLOCK",
            node_status="FAILED",
            engine_status="NOT_APPLICABLE",
        )

    return {
        "messages":    [AIMessage(content=msg)],
        "session":     {**session, "current_node": "LOAN_SECURITY_BLOCK"},
        "auth_control": {
            **auth,
            "security_blocked": True,
            "block_timestamp":  timestamp,
        },
        "flow_result": {
            "status_code":  "SECURITY_BLOCKED",
            "close_reason": "MAX_OTP_ATTEMPTS",
            "product_name": "Crédito de Consumo",
            "closed_at":    timestamp,
        },
    }


def loan_closed_by_user_node(state: FluxState) -> dict:
    """
    Nodo LOAN_CLOSED_BY_USER: cierre voluntario (usuario rechaza la oferta).

    ID LangGraph : loan_closed_by_user
    current_node : LOAN_CLOSED_BY_USER
    """
    session     = state.get("session", {})
    prep        = state.get("preparation_data", {})
    loan_engine = state.get("evaluation_results", {}).get("loan_engine", {})

    nombre = prep.get("nombre", "").split()[0] or "amig@"

    msg = (
        f"Entendemos, {nombre}. Has decidido no continuar con la solicitud. "
        f"Si en el futuro deseas retomar o explorar otras opciones, estaremos aquí. ¡Hasta pronto!"
    )

    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_CLOSED_BY_USER",
            node_status="SUCCESS",
            engine_status="NOT_APPLICABLE",
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session":  {**session, "current_node": "LOAN_CLOSED_BY_USER"},
        "flow_result": {
            "status_code":  "CLOSED_BY_USER",
            "close_reason": "USER_REJECTED_OFFER",
            "product_name": "Crédito de Consumo",
            "closed_at":    datetime.now(timezone.utc).isoformat(),
        },
    }

Sub-paso 4.2 — Stubs de security.py y pdf_factory.py

Ley del Stub: El stub debe ser invocable sin errores desde el nodo. Firma idéntica a la que tendrá el módulo real. Retorno hardcodeado documentado explícitamente.

Archivo: app/modules/security.py
python"""
app/modules/security.py
─────────────────────────────────────────────────────────────
STUB — Fase 2. Módulo de seguridad OTP.
ESTADO: Stub funcional. La lógica real la implementa el equipo de Seguridad.

CONTRATO DE INTERFAZ (no modificar):
  - generate_otp() → str: 6 dígitos como string
  - send_otp_email(mail: str, otp: str) → bool: True si el envío fue exitoso

MOCK: generate_otp retorna siempre "123456". send_otp_email siempre retorna True.
TODO Fase 3: Reemplazar con generación segura (secrets.randbelow) y envío SMTP.
"""

import secrets  # Importado pero no usado en stub; listo para el swap.


def generate_otp() -> str:
    """
    STUB: Retorna "123456" para desarrollo.
    REAL: return str(secrets.randbelow(900000) + 100000)
    """
    return "123456"  # MOCK — reemplazar en Fase 3


def send_otp_email(mail: str, otp: str) -> bool:
    """
    STUB: Simula envío exitoso sin llamar a ningún servicio externo.
    REAL: Llamada al servicio de email (SendGrid, SES, etc.)
    """
    print(f"[STUB] OTP {otp} 'enviado' a {mail}")
    return True  # MOCK — reemplazar en Fase 3
Archivo: app/modules/pdf_factory.py
python"""
app/modules/pdf_factory.py
─────────────────────────────────────────────────────────────
STUB — Fase 2. Módulo de generación de contratos PDF.
ESTADO: Stub funcional. La lógica real la implementa el equipo de Documentación.

CONTRATO DE INTERFAZ (no modificar):
  generate_loan_contract(data: dict) → tuple[str, str]:
    - Retorna (file_path, sha256_hash)
    - file_path: ruta del PDF generado (str)
    - sha256_hash: hash SHA-256 del archivo (str)

MOCK: Retorna una tupla de valores hardcodeados sin crear ningún archivo.
TODO Fase 3: Implementar con ReportLab + hashlib.sha256.
"""

import hashlib


def generate_loan_contract(data: dict) -> tuple[str, str]:
    """
    STUB: Retorna path y hash ficticios.
    REAL: Generará un PDF con ReportLab y calculará SHA-256.

    data esperado: {
        "nombre": str, "rut": str, "monto_aprobado": int,
        "plazo_aprobado": int, "tasa_interes_mensual": float,
        "cuota_mensual": int, "timestamp_acceptance": str
    }
    """
    mock_path = f"/contracts/loan_{data.get('rut','000000')}_MOCK.pdf"
    # Hash determinista basado en el RUT para trazabilidad en tests
    mock_hash = hashlib.sha256(data.get("rut", "").encode()).hexdigest()
    print(f"[STUB] Contrato 'generado': {mock_path} | Hash: {mock_hash[:8]}...")
    return mock_path, mock_hash
Sub-paso 4.3 — Nodo loan_otp_validation_node (invoca el stub)
pythonfrom app.modules.security import generate_otp, send_otp_email

def loan_otp_validation_node(state: FluxState) -> dict:
    """
    Nodo LOAN_OTP_VALIDATION: gestión de autenticación OTP.

    PRIMERA EJECUCIÓN (otp_generated no existe en state):
      - Genera OTP via security.generate_otp() [STUB].
      - Envía OTP via security.send_otp_email() [STUB].
      - Emite mensaje indicando que se envió el código.

    EJECUCIONES SIGUIENTES (otp_generated ya existe):
      - Compara otp_user_input con otp_generated.
      - Incrementa otp_attempts si falla.
      - Marca security_blocked si llega a 3 intentos.
    """
    session  = state.get("session", {})
    auth     = state.get("auth_control", {})
    prep     = state.get("preparation_data", {})
    messages = state.get("messages", [])

    mail          = prep.get("mail", "")
    otp_generated = auth.get("otp_generated")
    otp_attempts  = auth.get("otp_attempts", 0)

    # Primera ejecución: generar y enviar OTP
    if not otp_generated:
        new_otp = generate_otp()
        send_otp_email(mail, new_otp)
        return {
            "messages":    [AIMessage(content=f"Te hemos enviado un código de 6 dígitos a {mail}. Por favor ingrésalo aquí para finalizar.")],
            "auth_control": {**auth, "otp_generated": new_otp, "otp_attempts": 0},
            "session":     {**session, "current_node": "LOAN_OTP_VALIDATION"},
        }

    # Siguientes ejecuciones: validar input del usuario
    last_human_msg = next(
        (m.content.strip() for m in reversed(messages) if isinstance(m, HumanMessage)),
        ""
    )
    otp_input = last_human_msg  # El usuario escribió solo el código

    if otp_input == otp_generated:
        # OTP correcto
        return {
            "auth_control": {**auth, "otp_user_input": otp_input},
            "session":      {**session, "current_node": "LOAN_OTP_VALIDATION"},
        }
    else:
        # OTP incorrecto
        new_attempts = otp_attempts + 1
        if new_attempts >= 3:
            return {
                "auth_control": {
                    **auth,
                    "otp_attempts":    new_attempts,
                    "otp_user_input":  otp_input,
                    "last_otp_input":  otp_input,
                    "security_blocked": True,
                },
                "session": {**session, "current_node": "LOAN_OTP_VALIDATION"},
            }
        remaining = 3 - new_attempts
        return {
            "messages":    [AIMessage(content=f"El código ingresado no es correcto. Te quedan {remaining} intento(s).")],
            "auth_control": {**auth, "otp_attempts": new_attempts, "last_otp_input": otp_input},
            "session":     {**session, "current_node": "LOAN_OTP_VALIDATION"},
        }
Pruebas de Validación — PASO 4
python# Test 4.1 — Mensajes de rechazo por política
# Para cada motivo_rechazo: ERR_EDAD, ERR_RENTA, ERR_ANTIGUEDAD, ERR_CAPACIDAD_PAGO
# Expected: mensaje contiene el nombre del usuario, flow_result.status_code = REJECTED

# Test 4.2 — Bloqueo OTP
# 3 inputs incorrectos → auth_control.security_blocked = True
# Expected: flujo termina en loan_security_block, block_timestamp seteado en ISO8601

# Test 4.3 — OTP exitoso con stub
# otp_generated = "123456", otp_user_input = "123456"
# Expected: route_after_loan_otp_validation → "loan_formalization"

# Test 4.4 — Stub de PDF invocable sin error
# generate_loan_contract({"rut": "12345678-9", ...}) → (str, str)
# Expected: retorna tupla, no lanza excepciones, path contiene RUT

# Test 4.5 — Flujo E2E completo (con mocks)
# Simular grafo completo desde loan_init hasta loan_completed
# Expected: flow_result.status_code = SUCCESS, offer_data.loan.contract_status = SIGNED_AND_STAMPED

Tabla de Semáforos — Referencia Rápida
Nodo (UPPER)node_statusengine_statusLOAN_INITSUCCESSPENDINGLOAN_COLLECTING_PROFILESUCCESSPENDINGLOAN_COLLECTING_SIMULATIONSUCCESSPENDINGLOAN_RISK_ENGINESUCCESSCOMPLETEDLOAN_PRE_APPROVEDSUCCESSNOT_APPLICABLELOAN_OTP_VALIDATIONSUCCESSNOT_APPLICABLELOAN_FORMALIZATIONSUCCESSNOT_APPLICABLELOAN_COMPLETEDSUCCESSNOT_APPLICABLELOAN_REJECTED_POLICYSUCCESSCOMPLETEDLOAN_SECURITY_BLOCKFAILEDNOT_APPLICABLELOAN_CLOSED_BY_USERSUCCESSNOT_APPLICABLE

Orden de Entrega Recomendado
Semana 1:  credit_eng.py + tests unitarios (Paso 1)
Semana 2:  loan_schemas.py + nodos collecting + tests extracción (Paso 2)
Semana 3:  workflow.py + edges.py + tests de integración de rutas (Paso 3)
Semana 4:  nodos de error + stubs + test E2E completo (Paso 4)
El swap de stubs (security.py y pdf_factory.py) es una operación de una línea por función y no requiere tocar el grafo ni el State, lo que garantiza que otros equipos puedan trabajar en paralelo sin bloquear el flujo principal.
"""
app/graph/nodes/credit.py
─────────────────────────────────────────────────────────────
Nodos del flujo de Crédito de Consumo.

Ruta del grafo: loan_init → loan_risk_engine → END
  - loan_init        (ID LangGraph) → current_node = "LOAN_INIT"
  - loan_risk_engine  (ID LangGraph) → current_node = "LOAN_RISK_ENGINE"
"""

from langchain_core.messages import AIMessage
from app.graph.state import FluxState
from app.infra.supabase import update_application_semaphores


# ── LOAN_INIT (loan_init) ───────────────────────────────────

def loan_init_node(state: FluxState) -> dict:
    """
    Nodo LOAN_INIT: punto de entrada al flujo de Crédito de Consumo.

    ID LangGraph : loan_init
    current_node : LOAN_INIT   ← valor semántico para GPS y Supabase

    INPUT (State):
        - state["preparation_data"]: Datos del usuario (nombre, rut, mail, edad).
        - state["session"]: Para verificar product_intent == "LOAN".
        - state["collecting_data"]["loan_profile"]: Se limpiará (reset).
        - state["collecting_data"]["loan_sim"]: Se limpiará (reset).

    PROCESO:
        1. Handshake: Verificar que product_intent == "LOAN".
        2. Reset: Limpiar loan_profile y loan_sim.
        3. Saludo personalizado con datos de preparation_data.
        4. Actualizar semáforo: LOAN_INIT / SUCCESS / PENDING.

    OUTPUT (campos del State que modifica):
        - messages: Saludo de bienvenida al flujo de crédito.
        - session["current_node"]: "LOAN_INIT".
        - collecting_data["loan_profile"]: {} (limpio).
        - collecting_data["loan_sim"]: {} (limpio).
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})

    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    product_intent = session.get("product_intent")
    if product_intent != "LOAN":
        msg = "Hubo un error de navegación. Por favor, indica nuevamente qué necesitas."
    else:
        msg = (
            f"¡Perfecto, {first_name}! Vamos a revisar tu solicitud de **Crédito de Consumo**. "
            f"Es un proceso rápido. Primero necesito conocer un poco tu perfil financiero. "
            f"¿Cuál es tu renta líquida mensual?"
        )

    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_INIT",   # Valor semántico UPPER_CASE para Supabase
            node_status="SUCCESS",         # El INIT es síncrono: terminó al retornar
            engine_status="PENDING",       # El motor aún no ha arrancado
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "LOAN_INIT"},
        "collecting_data": {
            "loan_profile": {},
            "loan_sim": {},
        },
    }


# ── LOAN_RISK_ENGINE (loan_risk_engine) ───────────────────────

def loan_risk_engine_node(state: FluxState) -> dict:
    """
    Nodo LOAN_RISK_ENGINE: motor de riesgo para crédito de consumo.

    ID LangGraph : loan_risk_engine
    current_node : LOAN_RISK_ENGINE   ← valor semántico para GPS y Supabase

    INPUT (State leído):
        - state["collecting_data"]["loan_profile"]: renta, antiguedad_laboral, nivel_estudios
        - state["collecting_data"]["loan_sim"]: monto_solicitado, plazo_solicitado
        - state["preparation_data"]["edad"]: edad del usuario

    PROCESO:
        1. Extraer inputs de los namespaces correctos.
        2. Invocar al motor de scoring y cálculo financiero (modules/credit_eng.py).
        3. Escribir todos los outputs en evaluation_results["loan_engine"].
        4. Actualizar semáforo: LOAN_RISK_ENGINE / SUCCESS / COMPLETED.

    OUTPUT (campos del State que modifica):
        - evaluation_results["loan_engine"]: Resultado completo del motor.
        - session["current_node"]: "LOAN_RISK_ENGINE".

    NOTA ARQUITECTURA:
        Este nodo es un wrapper de flujo. La lógica de cálculo pesada debe residir
        en módulos independientes (modules/credit_eng.py) para facilitar tests unitarios.
    """
    session = state.get("session", {})
    prep = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})

    loan_profile = collecting.get("loan_profile", {})
    loan_sim = collecting.get("loan_sim", {})

    renta = loan_profile.get("renta", 0)
    monto_solicitado = loan_sim.get("monto_solicitado", 0)
    plazo_solicitado = loan_sim.get("plazo_solicitado", 0)

    # TODO Fase 2: engine_result = credit_eng.calculate_risk_score(...)
    engine_result = {
        "status_proceso": "PRE_APPROVED",
        "scoring_puntos": 0,
        "nivel_riesgo": "",
        "tasa_interes_mensual": 0.0,
        "cuota_mensual": 0,
        "cuota_maxima_permitida": int(renta * 0.30),
        "capacidad_pago_valida": True,
        "ctc": 0,
        "total_intereses": 0,
        "cae": 0.0,
        "monto_aprobado": monto_solicitado,
        "plazo_aprobado": plazo_solicitado,
        "motivo_rechazo": None,
    }

    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_RISK_ENGINE",
            node_status="SUCCESS",
            engine_status="COMPLETED",
        )

    return {
        "evaluation_results": {
            "loan_engine": engine_result,
        },
        "session": {**session, "current_node": "LOAN_RISK_ENGINE"},
    }
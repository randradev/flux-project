from langchain_core.messages import AIMessage
from app.graph.state import FluxState
from app.infra.supabase import update_application_semaphores

def loan_entry_node(state: FluxState) -> dict:
    """
    Nodo LOAN_INIT: punto de entrada al flujo de Crédito de Consumo.

    INPUT (State):
        - state["preparation_data"]: Datos del usuario (nombre, rut, mail, edad).
        - state["session"]: Para verificar product_intent == "LOAN".
        - state["collecting_data"]["loan_profile"]: Se limpiará (reset).
        - state["collecting_data"]["loan_sim"]: Se limpiará (reset).

    PROCESO (Fase 2):
        1. Handshake: Verificar que product_intent == "LOAN".
        2. Reset: Limpiar loan_profile y loan_sim.
        3. Saludo personalizado con datos de preparation_data.

    OUTPUT (campos del State que modifica):
        - messages: Saludo de bienvenida al flujo de crédito.
        - session["current_node"]: "LOAN_INIT".
        - collecting_data["loan_profile"]: {} (limpio).
        - collecting_data["loan_sim"]: {} (limpio).

    NOTA FASE 1: Este nodo es un stub. Solo hace el reset y confirma la intención.
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})

    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    # Handshake: verificar intención (defensa en profundidad)
    product_intent = session.get("product_intent")
    if product_intent != "LOAN":
        # Esto no debería ocurrir si edges.py está bien configurado
        # pero es una salvaguarda explícita
        msg = "Hubo un error de navegación. Por favor, indica nuevamente qué necesitas."
    else:
        msg = (
            f"¡Perfecto, {first_name}! Vamos a revisar tu solicitud de **Crédito de Consumo**. "
            f"Es un proceso rápido. Primero necesito conocer un poco tu perfil financiero. "
            f"¿Cuál es tu renta líquida mensual?"
        )

    # Actualizamos semáforo para notificar que el Nodo de Inicio del Flujo terminó
    application_id = session.get("application_id")

    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_INIT", # Cambia según el nodo
            node_status="SUCCESS",       # Avisamos que el INIT terminó
            engine_status="PENDING"      # El motor de producto aún no arranca
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "LOAN_INIT"},
        # ── RESET del namespace del producto ─────────────────────
        # Limpia datos de intentos anteriores sin tocar los otros productos.
        "collecting_data": {
            "loan_profile": {},
            "loan_sim": {},
        },
    }


def loan_risk_engine_node(state: FluxState) -> dict:
    """
    Nodo LOAN_RISK_ENGINE: motor de riesgo para crédito de consumo.

    INPUT (State leído):
        - state["collecting_data"]["loan_profile"]: renta, antiguedad_laboral, nivel_estudios
        - state["collecting_data"]["loan_sim"]: monto_solicitado, plazo_solicitado
        - state["preparation_data"]["edad"]: edad del usuario

    PROCESO:
        1. Extraer inputs de los namespaces correctos.
        2. Invocar al motor de scoring y cálculo financiero (modules/credit_eng.py).
        3. Escribir todos los outputs en evaluation_results["loan_engine"].

    OUTPUT (campos del State que modifica):
        - evaluation_results["loan_engine"]: Resultado completo del motor.
        - session["current_node"]: "LOAN_RISK_ENGINE".

    NOTA ARQUITECTURA: 
    Este nodo actúa como 'wrapper'. La lógica de cálculo pesada debe residir 
    en módulos independientes para facilitar tests unitarios.
    """
    session = state.get("session", {})
    prep = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})

    # ── Lectura de inputs desde los namespaces correctos ──────────
    loan_profile = collecting.get("loan_profile", {})
    loan_sim = collecting.get("loan_sim", {})

    renta = loan_profile.get("renta", 0)
    antiguedad_laboral = loan_profile.get("antiguedad_laboral", 0)
    nivel_estudios = loan_profile.get("nivel_estudios", "")
    monto_solicitado = loan_sim.get("monto_solicitado", 0)
    plazo_solicitado = loan_sim.get("plazo_solicitado", 0)
    edad = prep.get("edad", 0)

    # ── Lógica del motor (Orquestación) ──────────────────────────
    # TODO: En Fase 2, delegar este cálculo a: 
    # engine_result = credit_eng.calculate_risk_score(renta, monto, edad, etc.)

    # Por ahora, stub de cumplimiento arquitectónico:
    engine_result = {
        "status_proceso": "PRE_APPROVED",  # Stub
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

    # ── Sincronía ──────────────────────────────
    # Notificamos que el procesamiento del motor ha terminado con éxito
    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_RISK_ENGINE",
            node_status="SUCCESS",     # El nodo finalizó su ejecución
            engine_status="COMPLETED"  # El motor terminó su proceso
        )

    return {
        "evaluation_results": {
            "loan_engine": engine_result,
        },
        "session": {**session, "current_node": "LOAN_RISK_ENGINE"},
    }
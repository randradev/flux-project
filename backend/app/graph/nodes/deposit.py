"""
app/graph/nodes/deposit.py
─────────────────────────────────────────────────────────────
Nodos del flujo de Depósito a Plazo.

Ruta del grafo: dap_init → dap_investment_engine → END
  - dap_init              (ID LangGraph) → current_node = "DAP_INIT"
  - dap_investment_engine  (ID LangGraph) → current_node = "DAP_INVESTMENT_ENGINE"
"""

from langchain_core.messages import AIMessage
from app.graph.state import FluxState
from app.infra.supabase import update_application_semaphores

# ── DAP_INIT (dap_init) ────────────────────────────

def dap_init_node(state: FluxState) -> dict:
    """
    Nodo DAP_INIT: punto de entrada al flujo de Depósito a Plazo.

    ID LangGraph : dap_init
    current_node : DAP_INIT   ← valor semántico para GPS y Supabase

    PROCESO:
        1. Handshake: Verificar que product_intent == "DAP"
        2. Reset: Limpiar dap_params.
        3. Saludo personalizado con datos de preparation_data.
        4. Actualizar semáforo: DAP_INIT / SUCCESS / PENDING.

    OUTPUT:
        - messages: Saludo de bienvenida al flujo de Depósito a Plazo.
        - session["current_node"]: "DAP_INIT".
        - collecting_data["dap_params"]: {} (limpio).
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})
    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    msg = (
        f"Excelente elección, {first_name}! Un **Depósito a Plazo** es una forma segura "
        f"de hacer crecer tu dinero. Para calcular tu proyección, necesito saber: "
        f"¿cuánto deseas invertir y en qué moneda? (CLP, UF o USD)"
    )

    # Actualizamos semáforo para notificar que el Nodo de Inicio del Flujo terminó
    application_id = session.get("application_id")
    
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="DAP_INIT", # Cambia según el nodo
            node_status="SUCCESS",       # Avisamos que el INIT terminó
            engine_status="PENDING"      # El motor de producto aún no arranca
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "DAP_INIT"},
        "collecting_data": {
            "dap_params": {},   # Reset del namespace de DAP
        },
    }

# ── DAP_COLLECT_DATA (dap_collect_data) ────────────────────────────
def dap_collect_data_node(state: FluxState) -> dict:
    """Placeholder para la recolección de datos de DAP (Fase 3)."""
    return {
        "messages": [AIMessage(content="[STUB] Iniciando recolección de datos para Depósito a Plazo...")],
        "session": {**state.get("session", {}), "current_node": "DAP_COLLECT_DATA"}
    }


def dap_investment_engine_node(state: FluxState) -> dict:
    """
    Nodo DAP_INVESTMENT_ENGINE: motor de cálculo de inversión.

    ID LangGraph : dap_investment_engine
    current_node : DAP_INVESTMENT_ENGINE   ← valor semántico para GPS y Supabase

    INPUT (State leído):
        - state["collecting_data"]["dap_params"]: monto, moneda, plazo
        - state["preparation_data"]["edad"]: edad del usuario

    PROCESO:
        1. Extracción de parámetros desde el namespace 'dap_params'.
        2. Invocación al módulo de lógica financiera (modules/dap_eng.py).
           Nota: dap_eng integra indicadores externos (UF/IPC/USD) vía eco_service.py.
        3. Persistencia atómica de resultados en evaluation_results["dap_engine"].

    OUTPUT:
        - evaluation_results["dap_engine"]: Resultado completo.
        - session["current_node"]: "DAP_INVESTMENT_ENGINE".

    NOTA ARQUITECTURA:
    Este nodo es un wrapper de flujo. La complejidad del cálculo (tasas, proyecciones
    y conversión de moneda) está delegada a módulos externos para asegurar 
    testabilidad y desacoplamiento de APIs económicas.
    """
    session = state.get("session", {})
    prep = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})

    dap_params = collecting.get("dap_params", {})
    monto = dap_params.get("monto", 0.0)
    moneda = dap_params.get("moneda", "CLP")
    plazo = dap_params.get("plazo", 0)
    edad = prep.get("edad", 0)

    # ── Lógica del motor (Orquestación) ──────────────────────────
    # TODO: En Fase 3, delegar a:
    # engine_result = dap_eng.calculate_investment_yield(monto, moneda, plazo, edad)

    # Stub para testing del patrón de escritura.
    engine_result = {
        "status_proceso": "PRE_APPROVED",
        "is_elegible": True,
        "conversion_rate_used": 1.0,
        "ipc_applied": 0.0,
        "term_premium": (plazo // 30) * 0.0005,
        "monthly_rate_total": 0.0,
        "period_rate": 0.0,
        "estimated_gain": 0.0,
        "total_return": monto,
        "motivo_rechazo": None,
    }

    # ── Sincronía ──────────────────────────────
    # Notificamos que el procesamiento del motor ha terminado con éxito
    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="DAP_INVESTMENT_ENGINE",
            node_status="SUCCESS",     # El nodo finalizó su ejecución
            engine_status="COMPLETED"  # El motor terminó su proceso
        )
        
    return {
        "evaluation_results": {
            "dap_engine": engine_result,
        },
        "session": {**session, "current_node": "DAP_INVESTMENT_ENGINE"},
    }
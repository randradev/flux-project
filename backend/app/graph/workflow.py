"""
app/graph/workflow.py
─────────────────────────────────────────────────────────────
Definición, compilación y exposición del Grafo de Estados FLUX.

PROCESO: Instancia el StateGraph, registra todos los nodos y aristas,
         y compila el grafo con el checkpointer de Supabase.
         El resultado es `compiled_graph`, el objeto que los endpoints
         de FastAPI invocan para procesar mensajes.

SALIDA:  `compiled_graph` — instancia de CompiledGraph lista para invoke/stream.

VERSIÓN: 1.5 — Motores financieros registrados (stubs) y ruta INIT → ENGINE conectada.
CAMBIOS vs v1.0:
  - Importados y registrados: loan_risk_engine_node, account_evaluation_engine_node,
    dap_investment_engine_node.
  - Ruta: loan_init → loan_risk_engine → END (idem para account y dap).
  - Eliminado: edges directos INIT → END para los 3 productos.

NOMENCLATURA (Regla de Oro de este archivo):
  Los IDs de nodo en LangGraph usan snake_case (convención del framework).
  El valor semántico de negocio (current_node en State y en Supabase)
  usa UPPER_CASE. Ambos planos están documentados en la tabla de nodos abajo.

  ┌──────────────────────────┬──────────────────────────────┐
  │ ID LangGraph (snake)     │ Valor current_node (UPPER)   │
  ├──────────────────────────┼──────────────────────────────┤
  │ welcome                  │ WELCOME_NODE                 │
  │ intent_router            │ INTENT_ROUTER                │
  │ loan_init               │ LOAN_INIT                    │
  │ loan_risk_engine         │ LOAN_RISK_ENGINE             │
  │ account_init            │ ACCOUNT_INIT                 │
  │ account_evaluation_engine│ ACCOUNT_EVALUATION_ENGINE    │
  │ dap_init                │ DAP_INIT                     │
  │ dap_investment_engine    │ DAP_INVESTMENT_ENGINE        │
  │ general_response         │ GENERAL_RESPONSE             │
  └──────────────────────────┴──────────────────────────────┘
"""

from langgraph.graph import StateGraph, END

from app.graph.state import FluxState
from app.graph.nodes.common import welcome_node, intent_router_node, general_response_node
from app.graph.nodes.credit import loan_init_node, loan_collecting_profile_node, loan_collecting_sim_node, loan_risk_engine_node
from app.graph.nodes.account import account_init_node, account_collecting_profile_node, account_evaluation_engine_node
from app.graph.nodes.deposit import dap_init_node, dap_collect_data_node, dap_investment_engine_node
from app.graph.edges import route_after_welcome, route_after_intent, route_after_loan_collecting_profile, route_after_loan_collecting_sim, route_after_account_collecting_profile
from app.infra.checkpointer import get_checkpointer


# ── Construcción del Grafo ────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Construye y retorna el StateGraph sin compilar.
    Útil para testing de la estructura del grafo.

    INPUT:  Ninguno.
    PROCESO: Crea un StateGraph con FluxState, agrega nodos y aristas.
    OUTPUT: Instancia de StateGraph sin compilar.
    """
    graph = StateGraph(FluxState)

    # ── Registro de Nodos ─────────────────────────────────────
    # Nodos comunes / transversales
    graph.add_node("welcome",                    welcome_node)
    graph.add_node("intent_router",              intent_router_node)
    graph.add_node("general_response",           general_response_node)

    # Nodos de Crédito de Consumo
    graph.add_node("loan_init",                 loan_init_node)
    graph.add_node("loan_collecting_profile",     loan_collecting_profile_node)
    graph.add_node("loan_collecting_simulation",  loan_collecting_sim_node)
    graph.add_node("loan_risk_engine",           loan_risk_engine_node)

    # Nodos de Cuenta Corriente
    graph.add_node("account_init",               account_init_node)
    graph.add_node("account_collecting_profile", account_collecting_profile_node) # placeholder
    graph.add_node("account_evaluation_engine",  account_evaluation_engine_node)

    # Nodos de Depósito a Plazo
    graph.add_node("dap_init",                   dap_init_node)
    graph.add_node("dap_collect_data",           dap_collect_data_node) # placeholder
    graph.add_node("dap_investment_engine",      dap_investment_engine_node)

    # ── Punto de Entrada ──────────────────────────────────────
    graph.set_entry_point("welcome")

    # ── Aristas Condicionales ─────────────────────────────────
    # Después de WELCOME: redirigir según intención (nueva o reanudada)
    graph.add_conditional_edges(
    "welcome",
    route_after_welcome,
    {
        # Prioridad 3 — clasificación
        "intent_router":               "intent_router",
        # Prioridad 2 — intención directa
        "loan_init":                   "loan_init",
        "account_init":                "account_init",
        "dap_init":                    "dap_init",
        # Prioridad 1 — reanudación profunda (nodos de proceso)
        "loan_collecting_profile":     "loan_collecting_profile",
        "loan_collecting_simulation":  "loan_collecting_simulation",
        "account_collecting_profile":  "account_collecting_profile",
        "dap_collect_data":            "dap_collect_data",
        }
    )

    # Después de INTENT_ROUTER: redirigir al producto correspondiente
    graph.add_conditional_edges(
        "intent_router",
        route_after_intent,
        {
            "loan_init":       "loan_init",
            "account_init":    "account_init",
            "dap_init":        "dap_init",
            "general_response": "general_response",
        }
    )

    # ── Rutas de Producto: INIT → ENGINE → END ────────────────
    # Crédito: aristas condicionales de recolección
    graph.add_edge("loan_init", END) 
    
    graph.add_conditional_edges(
        "loan_collecting_profile",
        route_after_loan_collecting_profile,
        {
            "loan_collecting_simulation": "loan_collecting_simulation",
            END: END,
        }
    )

    graph.add_conditional_edges(
        "loan_collecting_simulation",
        route_after_loan_collecting_sim,
        {
            "loan_risk_engine": "loan_risk_engine",
            END: END,
        }
    )

    graph.add_edge("loan_risk_engine", END)

    # Cuenta: arista condicional de recolección
    graph.add_edge("account_init", END)
    
    graph.add_conditional_edges(
        "account_collecting_profile",
        route_after_account_collecting_profile,
        {
            "account_evaluation_engine": "account_evaluation_engine",
            END: END,
        }
    )

    graph.add_edge("account_evaluation_engine", END)

    # Depósito a Plazo
    # DAP: dap_collect_data ya tiene edge fijo a dap_investment_engine
    # (DAP no tiene paso de perfil separado, el salto ocurre diferente)
    # graph.add_edge("dap_collect_data", "dap_investment_engine") — mantener
    graph.add_edge("dap_init",                   "dap_collect_data")
    graph.add_edge("dap_collect_data",           "dap_investment_engine")
    graph.add_edge("dap_investment_engine",      END)
    # General
    graph.add_edge("general_response",          END)

    return graph


def get_compiled_graph():
    """
    Compila el grafo con el checkpointer de Supabase.

    INPUT:  Ninguno.
    PROCESO: Llama a build_graph() y compile() con el PostgresSaver.
    OUTPUT: CompiledGraph listo para invoke/astream.

    NOTA: El checkpointer.setup() se llama dentro de get_checkpointer(),
          lo que garantiza que las tablas internas de LangGraph existen en Supabase.
    """
    graph = build_graph()
    checkpointer = get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


# ── Singleton del Grafo ────────────────────────────────────────
_compiled_graph = None

def get_active_graph():
    """
    Retorna la instancia del grafo compilado (Lazy Initialization).

    Este patrón evita que el checkpointer (que requiere un loop de asyncio activo)
    se instancie en tiempo de importación, previniendo errores en tests y scripts.
    """
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = get_compiled_graph()
    return _compiled_graph
"""
app/graph/workflow.py
─────────────────────────────────────────────────────────────
Definición, compilación y exposición del Grafo de Estados FLUX.

PROCESO: Instancia el StateGraph, registra todos los nodos y aristas,
         y compila el grafo con el checkpointer de Supabase.
         El resultado es `compiled_graph`, el objeto que los endpoints
         de FastAPI invocan para procesar mensajes.

SALIDA:  `compiled_graph` — instancia de CompiledGraph lista para invoke/stream.
"""

from langgraph.graph import StateGraph, END

from app.graph.state import FluxState
from app.graph.nodes.common import (
    welcome_node,
    intent_router_node,
    general_response_node,
)
from app.graph.nodes.credit import loan_entry_node
from app.graph.nodes.account import account_entry_node
from app.graph.nodes.deposit import deposit_entry_node
from app.graph.edges import route_after_welcome, route_after_intent
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
    graph.add_node("welcome",          welcome_node)
    graph.add_node("intent_router",    intent_router_node)
    graph.add_node("loan_entry",       loan_entry_node)
    graph.add_node("account_entry",    account_entry_node)
    graph.add_node("dap_entry",        deposit_entry_node)
    graph.add_node("general_response", general_response_node)

    # ── Punto de Entrada ──────────────────────────────────────
    graph.set_entry_point("welcome")

    # ── Aristas Condicionales ─────────────────────────────────
    # Después de WELCOME: redirigir según intención (nueva o reanudada)
    graph.add_conditional_edges(
        "welcome",
        route_after_welcome,
        {
            "intent_router":  "intent_router",
            "loan_entry":     "loan_entry",
            "account_entry":  "account_entry",
            "dap_entry":      "dap_entry",
        }
    )

    # Después de INTENT_ROUTER: redirigir al producto correspondiente
    graph.add_conditional_edges(
        "intent_router",
        route_after_intent,
        {
            "loan_entry":       "loan_entry",
            "account_entry":    "account_entry",
            "dap_entry":        "dap_entry",
            "general_response": "general_response",
        }
    )

    # ── Aristas Finales (todos los stubs terminan por ahora) ──
    graph.add_edge("loan_entry",       END)
    graph.add_edge("account_entry",    END)
    graph.add_edge("dap_entry",        END)
    graph.add_edge("general_response", END)

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
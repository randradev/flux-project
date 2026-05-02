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
from app.graph.nodes.credit import (
    loan_init_node,
    loan_collecting_profile_node,
    loan_collecting_sim_node,
    loan_risk_engine_node,
    loan_pre_approved_node,
    loan_otp_validation_node,
    loan_formalization_node,
    loan_completed_node,
    loan_rejected_policy_node,
    loan_security_block_node,
    loan_closed_by_user_node,
)
from app.graph.nodes.account import account_init_node, account_collecting_profile_node, account_evaluation_engine_node
from app.graph.nodes.deposit import dap_init_node, dap_collect_data_node, dap_investment_engine_node
from app.graph.edges import (
    route_after_welcome,
    route_after_intent,
    # Crédito de Consumo
    route_after_loan_collecting_profile,
    route_after_loan_collecting_sim,
    route_after_loan_risk_engine,
    route_after_loan_pre_approved,
    route_after_loan_otp_validation,
    # Cuenta Corriente
    route_after_account_collecting_profile,
)
from app.infra.checkpointer import get_checkpointer

# ======================================================================================================
# CONSTRUCCIÓN DEL GRAFO
# ======================================================================================================

def build_graph() -> StateGraph:
    """
    Construye y retorna el StateGraph sin compilar.

    VERSIÓN: 3.0 — Flujo de crédito completo.
    CAMBIOS vs v1.5:
      - loan_init ya NO apunta a END; ahora apunta a loan_collecting_profile.
      - Registrados: loan_pre_approved, loan_otp_validation, loan_formalization,
        loan_completed, loan_rejected_policy, loan_security_block, loan_closed_by_user.
      - Aristas condicionales: route_after_loan_risk_engine,
        route_after_loan_pre_approved, route_after_loan_otp_validation.
      - Aristas fijas: loan_formalization → loan_completed (Happy Path único post-OTP).

    NOMENCLATURA (Regla de Oro — tabla actualizada):
    ┌──────────────────────────────┬──────────────────────────────────┐
    │ ID LangGraph (snake)         │ Valor current_node (UPPER)       │
    ├──────────────────────────────┼──────────────────────────────────┤
    │ welcome                      │ WELCOME_NODE                     │
    │ intent_router                │ INTENT_ROUTER                    │
    │ loan_init                    │ LOAN_INIT                        │
    │ loan_collecting_profile      │ LOAN_COLLECTING_PROFILE          │
    │ loan_collecting_simulation   │ LOAN_COLLECTING_SIMULATION       │
    │ loan_risk_engine             │ LOAN_RISK_ENGINE                 │
    │ loan_pre_approved            │ LOAN_PRE_APPROVED                │
    │ loan_otp_validation          │ LOAN_OTP_VALIDATION              │
    │ loan_formalization           │ LOAN_FORMALIZATION               │
    │ loan_completed               │ LOAN_COMPLETED                   │
    │ loan_rejected_policy         │ LOAN_REJECTED_POLICY             │
    │ loan_security_block          │ LOAN_SECURITY_BLOCK              │
    │ loan_closed_by_user          │ LOAN_CLOSED_BY_USER              │
    │ account_init                 │ ACCOUNT_INIT                     │
    │ account_collecting_profile   │ ACCOUNT_COLLECTING_PROFILE       │
    │ account_evaluation_engine    │ ACCOUNT_EVALUATION_ENGINE        │
    │ dap_init                     │ DAP_INIT                         │
    │ dap_collect_data             │ DAP_COLLECT_DATA                 │
    │ dap_investment_engine        │ DAP_INVESTMENT_ENGINE            │
    │ general_response             │ GENERAL_RESPONSE                 │
    └──────────────────────────────┴──────────────────────────────────┘
    """
    graph = StateGraph(FluxState)

    # ──────────────────────────────────────────────────────────────────────────────────────
    # REGISTRO DE NODOS
    # ──────────────────────────────────────────────────────────────────────────────────────
    # ── Comunes / transversales ─────────────────────────────────────
    graph.add_node("welcome",                    welcome_node)
    graph.add_node("intent_router",              intent_router_node)
    graph.add_node("general_response",           general_response_node)

    # ── Crédito de Consumo ─────────────────────────────────────────────
    # Recolección
    graph.add_node("loan_init",                 loan_init_node)
    graph.add_node("loan_collecting_profile",     loan_collecting_profile_node)
    graph.add_node("loan_collecting_simulation",  loan_collecting_sim_node)
    # Evaluación y Oferta
    graph.add_node("loan_risk_engine",           loan_risk_engine_node)
    graph.add_node("loan_pre_approved",          loan_pre_approved_node)
    # Formalización y Cierre
    graph.add_node("loan_otp_validation",        loan_otp_validation_node)
    graph.add_node("loan_formalization",         loan_formalization_node)
    graph.add_node("loan_completed",             loan_completed_node)
    # Excepciones
    graph.add_node("loan_rejected_policy",       loan_rejected_policy_node)
    graph.add_node("loan_security_block",        loan_security_block_node)
    graph.add_node("loan_closed_by_user",        loan_closed_by_user_node)

    # ── Cuenta Corriente ─────────────────────────────────────────────
    graph.add_node("account_init",               account_init_node)
    graph.add_node("account_collecting_profile", account_collecting_profile_node) # placeholder
    graph.add_node("account_evaluation_engine",  account_evaluation_engine_node)

    # ── Depósito a Plazo ─────────────────────────────────────────────
    graph.add_node("dap_init",                   dap_init_node)
    graph.add_node("dap_collect_data",           dap_collect_data_node) # placeholder
    graph.add_node("dap_investment_engine",      dap_investment_engine_node)

    # ──────────────────────────────────────────────────────────────────────────────────────
    # PUNTO DE ENTRADA
    # ──────────────────────────────────────────────────────────────────────────────────────
    graph.set_entry_point("welcome")

    # ──────────────────────────────────────────────────────────────────────────────────────
    # ARISTAS CONDICIONALES
    # ──────────────────────────────────────────────────────────────────────────────────────
    # WELCOME: redirigir según intención (nueva o reanudada)
    
    graph.add_conditional_edges(
        "welcome",
        route_after_welcome,
        {
            # Clasificación
            "intent_router":               "intent_router",
            # Intención directa
            "loan_init":                   "loan_init",
            "account_init":                "account_init",
            "dap_init":                    "dap_init",
            # Reanudación de recolección
            "loan_collecting_profile":     "loan_collecting_profile",
            "loan_collecting_simulation":  "loan_collecting_simulation",
            "account_collecting_profile":  "account_collecting_profile",
            "dap_collect_data":            "dap_collect_data",
            # Reanudación de oferta/OTP
            "loan_pre_approved":           "loan_pre_approved",
            "loan_otp_validation":         "loan_otp_validation",
            # Saltos por éxito (desde _SUCCESS_MAP vía P1)
            "loan_risk_engine":            "loan_risk_engine",
            "loan_formalization":          "loan_formalization",
            "loan_rejected_policy":        "loan_rejected_policy",
            "loan_security_block":         "loan_security_block",
            "loan_closed_by_user":         "loan_closed_by_user",
            "account_evaluation_engine":   "account_evaluation_engine",
            "dap_investment_engine":       "dap_investment_engine",
            # General
            "general_response":            "general_response",
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

    # ──────────────────────────────────────────────────────────────────────────────────────
    # RUTAS DE CRÉDITO DE CONSUMO
    # ──────────────────────────────────────────────────────────────────────────────────────
    # v3.0: loan_init → loan_collecting_profile (ya NO va a END)
    # Razón: loan_init es un nodo de bienvenida automático que no espera input.
    # Transiciona directamente al primer nodo de recolección en el mismo turno.

    graph.add_edge("loan_init", "loan_collecting_profile")

    # Recolección de perfil (con salto condicional al completarse)
    graph.add_conditional_edges(
        "loan_collecting_profile",
        route_after_loan_collecting_profile,
        {
            "loan_collecting_simulation": "loan_collecting_simulation",
            END: END,
        }
    )

    # Recolección de simulación (con salto al motor al completarse)
    graph.add_conditional_edges(
        "loan_collecting_simulation",
        route_after_loan_collecting_sim,
        {
            "loan_risk_engine": "loan_risk_engine",
            END: END,
        }
    )

    # Motor de riesgo (bifurcación: aprobado / rechazado)
    graph.add_conditional_edges(
        "loan_risk_engine",
        route_after_loan_risk_engine,
        {
            "loan_pre_approved":    "loan_pre_approved",
            "loan_rejected_policy": "loan_rejected_policy",
        }
    )

    # Oferta (bifurcación: aceptada / rechazada por usuario)
    graph.add_conditional_edges(
        "loan_pre_approved",
        route_after_loan_pre_approved,
        {
            "loan_otp_validation": "loan_otp_validation",
            "loan_closed_by_user": "loan_closed_by_user",
            END: END,  # Espera turno del usuario
        }
    )

    # Validación OTP (bifurcación: éxito / bloqueo de seguridad)
    graph.add_conditional_edges(
        "loan_otp_validation",
        route_after_loan_otp_validation,
        {
            "loan_formalization": "loan_formalization",
            "loan_security_block": "loan_security_block",
            END: END,  # Espera turno del usuario (código incorrecto, reintento)
        }
    )

    # Formalización → Completado (edge fijo: nodo de servicio automático)
    # Si GENERATION_FAILED, se añadirá un edge a SERVICE_ERROR en sprint futuro.
    graph.add_edge("loan_formalization", "loan_completed")

    # Nodos terminales → END
    graph.add_edge("loan_completed",      END)
    graph.add_edge("loan_rejected_policy", END)
    graph.add_edge("loan_security_block",  END)
    graph.add_edge("loan_closed_by_user",  END)

    # ──────────────────────────────────────────────────────────────────────────────────────
    # RUTAS DE CUENTA CORRIENTE
    # ──────────────────────────────────────────────────────────────────────────────────────
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

    # ──────────────────────────────────────────────────────────────────────────────────────
    # RUTAS DE DEPÓSITO A PLAZO
    # ──────────────────────────────────────────────────────────────────────────────────────
    # DAP: dap_collect_data ya tiene edge fijo a dap_investment_engine
    # (DAP no tiene paso de perfil separado, el salto ocurre diferente)
    # graph.add_edge("dap_collect_data", "dap_investment_engine") — mantener
    graph.add_edge("dap_init",                   "dap_collect_data")
    graph.add_edge("dap_collect_data",           "dap_investment_engine")
    graph.add_edge("dap_investment_engine",      END)
    # General
    graph.add_edge("general_response",          END)

    return graph

# ======================================================================================================
# COMPILACIÓN DEL GRAFO
# ======================================================================================================

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

# ======================================================================================================
# SINGLETON DEL GRAFO
# ======================================================================================================
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
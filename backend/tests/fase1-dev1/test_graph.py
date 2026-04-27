"""Tests del Grafo LangGraph."""
import pytest
import asyncio
import sys

# Parche para compatibilidad de psycopg asíncrono en Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())



def test_flux_state_schema_has_required_fields():
    """Verifica que FluxState define todos los campos necesarios."""
    from app.graph.state import FluxState
    import typing
    
    hints = typing.get_type_hints(FluxState)
    required_fields = ["messages", "user_data", "session", "collected_data", "control_flags"]
    
    for field in required_fields:
        assert field in hints, f"Campo requerido '{field}' no encontrado en FluxState"


def test_graph_compiles_without_error():
    """Verifica que el StateGraph se compila sin lanzar excepciones."""
    from app.graph.workflow import build_graph
    graph = build_graph()
    # Si llegamos aquí, el grafo se construyó sin error
    assert graph is not None


def test_graph_has_correct_nodes():
    """Verifica que el grafo tiene registrados todos los nodos esperados para Fase 1."""
    from app.graph.workflow import build_graph
    graph = build_graph()
    
    expected_nodes = {
        "welcome", "intent_router", "loan_init",
        "account_init", "dap_init", "general_response"
    }
    actual_nodes = set(graph.nodes.keys())
    
    for node in expected_nodes:
        assert node in actual_nodes, f"Nodo '{node}' no encontrado en el grafo"

# ── PRUEBA 4.B: Test de Integración: Clasificación de Intenciones ──────────────────

def test_intent_router_classifies_loan():
    """Verifica que un mensaje de crédito se clasifica como LOAN."""
    from langchain_core.messages import HumanMessage
    from app.graph.nodes.common import intent_router_node
    from app.graph.state import FluxState

    # Estado mínimo para la prueba
    state: FluxState = {
        "messages": [HumanMessage(content="Quiero solicitar un crédito de 3 millones")],
        "user_data": {"full_name": "Juan Test", "email": "test@flux.cl"},
        "session": {"conversation_id": "test-123", "current_node": "WELCOME"},
        "collected_data": {},
        "control_flags": {},
    }
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "LOAN"


def test_intent_router_classifies_account():
    """Verifica que un mensaje de cuenta se clasifica como ACCOUNT."""
    from langchain_core.messages import HumanMessage
    from app.graph.nodes.common import intent_router_node
    from app.graph.state import FluxState

    state: FluxState = {
        "messages": [HumanMessage(content="Quiero abrir una cuenta corriente")],
        "user_data": {}, "session": {}, "collected_data": {}, "control_flags": {},
    }
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "ACCOUNT"


def test_intent_router_classifies_dap():
    """Verifica que un mensaje de inversión se clasifica como DAP."""
    from langchain_core.messages import HumanMessage
    from app.graph.nodes.common import intent_router_node
    from app.graph.state import FluxState

    state: FluxState = {
        "messages": [HumanMessage(content="Quiero hacer un depósito a plazo de 5 millones")],
        "user_data": {}, "session": {}, "collected_data": {}, "control_flags": {},
    }
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "DAP"


def test_intent_router_classifies_general():
    """Verifica que un saludo se clasifica como GENERAL."""
    from langchain_core.messages import HumanMessage
    from app.graph.nodes.common import intent_router_node
    from app.graph.state import FluxState

    state: FluxState = {
        "messages": [HumanMessage(content="Hola, ¿cómo estás?")],
        "user_data": {}, "session": {}, "collected_data": {}, "control_flags": {},
    }
    result = intent_router_node(state)
    assert result["session"]["product_intent"] == "GENERAL"

# ── PRUEBA 4.C: Test de Integración: Persistencia del Estado (Checkpointer) ──────────────────

@pytest.mark.asyncio
async def test_graph_state_persists_across_invocations():
    """
    Verifica que el grafo persiste el estado y que una segunda invocación
    con el mismo thread_id recupera el historial previo.
    ADVERTENCIA: Este test hace llamadas reales a Gemini y escribe en Supabase.
    """
    import uuid
    from langchain_core.messages import HumanMessage
    from app.graph.workflow import get_active_graph

    # Obtenemos el grafo compilado usando el inicializador perezoso
    graph = get_active_graph()

    # IMPORTANTE: Usar un UUID válido para que Supabase no falle al filtrar por ID
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}


    # Primera invocación — estado inicial
    initial_state = {
        "messages": [HumanMessage(content="Quiero un crédito")],
        "user_data": {"full_name": "Ana Test", "email": "ana@flux.cl"},
        "session": {"conversation_id": thread_id, "current_node": "START"},
        "collected_data": {},
        "control_flags": {},
    }
    
    # Usamos ainvoke ya que el checkpointer es asíncrono
    result1 = await graph.ainvoke(initial_state, config=config)
    assert result1 is not None
    assert len(result1["messages"]) > 1  # El grafo agregó mensajes

    # Segunda invocación — el estado debe ser recuperado del checkpointer
    result2 = await graph.ainvoke(
        {"messages": [HumanMessage(content="¿Cuánto me prestarían?")]},
        config=config
    )
    # El historial debe ser mayor que en la primera invocación (memoria persistida)
    assert len(result2["messages"]) > len(result1["messages"]), \
        "El checkpointer no persistió el estado correctamente"

    print(f"\nMensajes en sesión 1: {len(result1['messages'])}")
    print(f"Mensajes en sesión 2: {len(result2['messages'])}")

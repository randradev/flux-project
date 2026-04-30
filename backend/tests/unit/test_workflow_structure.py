# tests/unit/test_workflow_structure.py
from app.graph.workflow import build_graph
from app.graph.edges import _RESUME_MAP

def test_all_resume_targets_registered_in_graph():
    """Todos los destinos del _RESUME_MAP deben estar registrados en el grafo."""
    graph = build_graph()
    # En LangGraph v2, los nodos están en graph.nodes (un dict-like object)
    registered_nodes = set(graph.nodes.keys())
    for current_node_val, langgraph_id in _RESUME_MAP.items():
        assert langgraph_id in registered_nodes, (
            f"El nodo '{langgraph_id}' (reanudación de '{current_node_val}') "
            f"no está registrado en workflow.py"
        )

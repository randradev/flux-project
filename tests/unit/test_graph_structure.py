# tests/unit/test_graph_structure.py
import sys
from unittest.mock import MagicMock, patch

# Mock infra/config before any other imports
sys.modules["app.infra.gemini_client"] = MagicMock()
sys.modules["app.infra.supabase"] = MagicMock()
sys.modules["app.infra.checkpointer"] = MagicMock()
sys.modules["app.config"] = MagicMock()

from app.graph.workflow import build_graph
from langgraph.graph import END

def test_graph_structure():
    graph = build_graph()
    print("\n--- Verificación de Nodos ---")
    
    nodes_to_check = ["loan_init", "loan_risk_engine", "account_init", "account_evaluation_engine", "dap_init", "dap_investment_engine"]
    
    found_nodes = {node: False for node in nodes_to_check}
    
    # Check fixed edges
    for start, end in graph.edges:
        if start in found_nodes:
            found_nodes[start] = True
            print(f"Edge fijo encontrado: {start} -> {end}")
    
    # Check branches (conditional edges)
    # En StateGraph.branches, la llave es el nodo origen
    for start in graph.branches:
        if start in found_nodes:
            found_nodes[start] = True
            print(f"Edge condicional encontrado en: {start}")

    for node, found in found_nodes.items():
        if not found:
            print(f"ALERTA: El nodo '{node}' NO tiene aristas salientes registradas.")

if __name__ == "__main__":
    test_graph_structure()

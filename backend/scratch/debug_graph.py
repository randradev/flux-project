from app.graph.workflow import build_graph
try:
    g = build_graph()
    print("Graph built successfully")
except Exception as e:
    import traceback
    traceback.print_exc()

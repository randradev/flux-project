# backend/scratch/loan_playground.py
import os
from langchain_core.messages import HumanMessage
from app.graph.nodes.credit import loan_collecting_profile_node
from app.graph.state import FluxState

# 1. Configurar estado inicial
state = {
    "messages": [],
    "collecting_data": {"loan_profile": {}, "loan_sim": {}},
    "session": {"current_node": "WELCOME_NODE"},
    "preparation_data": {"nombre": "Tester Chileno", "edad": 30}
}

print("--- 🧪 FLUX PLAYGROUND: Nodos de Recolección ---")
print("Escribe 'salir' para terminar.\n")

# ... (tus imports)

while True:
    user_input = input("Tú: ").strip()
    if user_input.lower() in ['salir', 'exit', 'quit']: break

    # 1. IMPORTANTE: En el playground, a veces es mejor pasarle 
    # SOLO el último mensaje para probar la extracción pura.
    state["messages"] = [HumanMessage(content=user_input)] 

    # 2. Ejecutar el nodo
    result = loan_collecting_profile_node(state)
    
    # 3. Sincronizar el perfil (Merge manual en el playground)
    if "collecting_data" in result:
        state["collecting_data"]["loan_profile"].update(
            result["collecting_data"]["loan_profile"]
        )
    
    # 4. Ver qué vió el extractor realmente
    print(f"DEBUG: Datos en el cajón -> {state['collecting_data']['loan_profile']}")
    
    # 5. Reportar resultados
    print(f"\n[ESTADO] loan_profile: {state['collecting_data']['loan_profile']}")
    if "messages" in result:
        print(f"Flux: {result['messages'][-1].content}\n")
    else:
        print("Flux: (Avance silencioso - Todo capturado) ✅\n")

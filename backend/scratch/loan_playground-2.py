import os
import sys

# Ajustar path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import HumanMessage, AIMessage
from app.graph.nodes.credit import (
    loan_collecting_profile_node, 
    loan_collecting_sim_node,
    loan_risk_engine_node
)

def run_playground():
    # 1. Estado inicial
    state = {
        "messages": [],
        "preparation_data": {"nombre": "María Paz", "edad": 35}, # Datos de pre-requisito
        "collecting_data": {"loan_profile": {}, "loan_sim": {}},
        "session": {"current_node": "LOAN_COLLECTING_PROFILE", "application_id": None}
    }

    print("\n" + "="*60)
    print(" 🧪 FLUX END-TO-END SIMULATOR v2.2")
    print("="*60)

    # Mensaje inicial simulado
    bot_initial = "¡Hola María! Vamos a ver tu crédito. ¿Cuál es tu renta mensual?"
    print(f"\nFlux: {bot_initial}")
    state["messages"].append(AIMessage(content=bot_initial))

    while True:
        curr = state["session"]["current_node"]
        
        # Entrada de usuario
        user_text = input("\nTú: ").strip()
        if user_text.lower() in ["exit", "quit"]: break
        state["messages"].append(HumanMessage(content=user_text))

        # --- ORQUESTADOR DE NODOS ---
        while True:
            node_id = state["session"]["current_node"]
            
            if node_id == "LOAN_COLLECTING_PROFILE":
                res = loan_collecting_profile_node(state)
            elif node_id == "LOAN_COLLECTING_SIMULATION":
                res = loan_collecting_sim_node(state)
            elif node_id == "LOAN_RISK_ENGINE":
                res = loan_risk_engine_node(state)
            else:
                print(f"\n[ERROR] Nodo desconocido: {node_id}")
                return

            # Actualizar estado (Merge manual de seguridad)
            state.update({k: v for k, v in res.items() if k != "messages"})
            if "messages" in res:
                state["messages"].extend(res["messages"])

            # ¿Hay respuesta para el usuario?
            if "messages" in res and res["messages"]:
                print(f"\nFlux: {res['messages'][0].content}")
                break # Esperar siguiente input del usuario
            else:
                # AVANCE SILENCIOSO
                print(f"\n(⚡ {node_id} COMPLETO -> Saltando al siguiente nodo...)")
                
                # Lógica de transición manual para el playground
                if node_id == "LOAN_COLLECTING_PROFILE":
                    state["session"]["current_node"] = "LOAN_COLLECTING_SIMULATION"
                elif node_id == "LOAN_COLLECTING_SIMULATION":
                    state["session"]["current_node"] = "LOAN_RISK_ENGINE"
                elif node_id == "LOAN_RISK_ENGINE":
                    print("\n" + "="*60)
                    print(" 🎉 RESULTADO FINAL DEL MOTOR")
                    print("="*60)
                    for k, v in state["engine_result"].items():
                        print(f" • {k:25}: {v}")
                    return # Fin del flujo completo

        # DEBUG: Mostrar resumen del estado actual
        print("\n" + "-"*50)
        print(f" [DEBUG] Nodo Actual: {state['session']['current_node']}")
        print(f" [DEBUG] Perfil     : {state['collecting_data']['loan_profile']}")
        print(f" [DEBUG] Simulación : {state['collecting_data']['loan_sim']}")
        print("-"*50)

if __name__ == "__main__":
    run_playground()

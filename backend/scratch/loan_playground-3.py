import os
import sys
import uuid
import warnings
from langgraph.checkpoint.memory import MemorySaver

# Ajustar path para importar módulos de app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import HumanMessage, AIMessage
from app.graph.workflow import build_graph
from app.graph.state import FluxState

# Desactivar ruidos de consola
warnings.filterwarnings("ignore")

def run_playground():
    # 1. Configuración del Grafo
    workflow = build_graph()
    
    # 2. Compilación con INTERRUPCIONES (La clave para multi-turno)
    # Esto detiene el grafo después de cada nodo que emite un mensaje,
    # permitiendo que la sesión "espere" al usuario sin reiniciarse.
    memory = MemorySaver()
    app = workflow.compile(
        checkpointer=memory,
        interrupt_after=[
            "welcome", 
            "loan_init", 
            "loan_collecting_profile", 
            "loan_collecting_simulation",
            "loan_pre_approved"
        ]
    )
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # 3. Estado Inicial
    initial_state = {
        "preparation_data": {
            "nombre": "María Paz", 
            "edad": 35, 
            "rut": "12.345.678-9", 
            "mail": "m.paz@email.cl"
        },
        "session": {
            "product_intent": "LOAN",
            "application_id": str(uuid.uuid4())
        }
    }

    print("\n" + "="*70)
    print(" 🧪 FLUX E2E SIMULATOR v3.3 (Fase 2 - Multi-Turno)")
    print("="*70)
    print(f" Session ID : {thread_id}")
    print("="*70)

    # Iniciar flujo
    print("\n[SISTEMA] Iniciando flujo desde Welcome...")
    app.invoke(initial_state, config)

    while True:
        # 1. Obtener estado actual del checkpointer
        snapshot = app.get_state(config)
        state_vals = snapshot.values
        session = state_vals.get("session", {})
        curr_node_semantic = session.get("current_node", "START")
        messages = state_vals.get("messages", [])
        loan_profile = state_vals.get("collecting_data", {}).get("loan_profile", {})

        # 2. Mostrar último mensaje del bot
        if messages and isinstance(messages[-1], AIMessage):
            print(f"\nFlux: {messages[-1].content}")

        # 3. Renderizar Tarjeta si aplica
        offer_data = state_vals.get("offer_data", {}).get("loan", {})
        if curr_node_semantic == "LOAN_PRE_APPROVED" and offer_data.get("display_data"):
            print("\n" + "┌" + "─"*40 + "┐")
            print("│      TARJETA DE TRANSPARENCIA (UI)     │")
            print("├" + "─"*40 + "┤")
            for k, v in offer_data["display_data"].items():
                print(f"│ • {k:20}: {v:<15} │")
            print("└" + "─"*40 + "┘")

        # 4. Verificación de Cierre
        if curr_node_semantic in ["LOAN_COMPLETED", "LOAN_REJECTED_POLICY", "LOAN_CLOSED_BY_USER"]:
            print(f"\n[FIN] Flujo terminado en: {curr_node_semantic}")
            break

        # 5. Captura de Entrada
        print(f"\n[GPS] Nodo: {curr_node_semantic} | Perfil: {len(loan_profile)}/3")
        
        if curr_node_semantic == "LOAN_PRE_APPROVED":
            print("[BOTONES] (A)ceptar | (R)echazar")
            choice = input("Acción: ").strip().upper()
            if choice == "A":
                update = {"offer_data": {"loan": {"pre_approval_status": "ACCEPTED"}}}
            elif choice == "R":
                update = {"offer_data": {"loan": {"pre_approval_status": "REJECTED"}}}
            else: break
            app.update_state(config, update)
            app.invoke(None, config) # Continuar sin nuevo mensaje
        else:
            user_text = input("Tú: ").strip()
            if user_text.lower() == "exit": break
            if user_text.lower() == "state":
                print(f"\n[DUMP] {state_vals}")
                continue
            
            # Inyectar el mensaje y despertar al grafo
            app.invoke({"messages": [HumanMessage(content=user_text)]}, config)

if __name__ == "__main__":
    run_playground()
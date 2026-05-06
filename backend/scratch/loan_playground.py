"""
backend/scratch/loan_playground.py
─────────────────────────────────────────────────────────────
Playground v2.1 — Prueba manual del nodo loan_collecting_profile_node.

CAMBIOS vs v1.0:
  - Historial acumulativo: los mensajes se acumulan, no se limpian.
  - Mensaje inicial del bot inyectado para simular loan_init_node.
  - Merge manual corregido: campo por campo, no .update() completo.
  - DEBUG mejorado: muestra datos nuevos vs. datos previos por separado.
  - Indicador de "avance silencioso" claro.
"""

import os
import sys

# Ajustar path si el playground está en /scratch y no en la raíz del backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import HumanMessage, AIMessage
from app.graph.nodes.credit import loan_collecting_profile_node

# ── Estado inicial del playground ────────────────────────────
state = {
    "messages":        [],
    "collecting_data": {"loan_profile": {}, "loan_sim": {}},
    "session":         {
        "current_node":   "LOAN_INIT",
        "application_id": None,   # Sin Supabase en el playground
    },
    "preparation_data": {
        "nombre": "María González",  # Cambiar por el nombre de prueba deseado
        "edad":   32,
        "rut":    "12.345.678-9",
        "mail":   "maria@test.cl",
    },
}

# ── Simular mensaje inicial de loan_init_node ─────────────────
MENSAJE_INICIAL_BOT = (
    "¡Perfecto, María! Vamos a revisar tu solicitud de **Crédito de Consumo**. "
    "Es un proceso rápido. Primero necesito conocer un poco tu perfil financiero. "
    "¿Cuál es tu renta líquida mensual?"
)
state["messages"].append(AIMessage(content=MENSAJE_INICIAL_BOT))

print("\n" + "═" * 60)
print("  🧪 FLUX PLAYGROUND v2.1 — Nodo: loan_collecting_profile")
print("═" * 60)
print(f"\nFlux: {MENSAJE_INICIAL_BOT}\n")

# ── Loop de conversación ──────────────────────────────────────
while True:
    user_input = input("Tú: ").strip()
    if user_input.lower() in ["salir", "exit", "quit", "q"]:
        print("\n[Playground terminado]")
        break
    if not user_input:
        continue
    
    # ── Inyectar mensaje del usuario al historial (ACUMULATIVO) ──
    state["messages"].append(HumanMessage(content=user_input))
    
    # ── Snapshot del perfil antes del turno (para DEBUG) ─────────
    profile_before = dict(state["collecting_data"]["loan_profile"])
    
    # ── Ejecutar el nodo ─────────────────────────────────────────
    result = loan_collecting_profile_node(state)
    
    # ── Sincronizar el State (merge campo por campo) ─────────────
    if "collecting_data" in result:
        new_profile = result["collecting_data"].get("loan_profile", {})
        # Merge defensivo: solo actualizar campos que tienen valor en el resultado
        for field, value in new_profile.items():
            if value is not None:
                state["collecting_data"]["loan_profile"][field] = value
    
    if "session" in result:
        state["session"].update(result["session"])
    
    # ── Sincronizar mensajes del bot al historial ─────────────────
    bot_messages = result.get("messages", [])
    for msg in bot_messages:
        state["messages"].append(msg)
    
    # ── Mostrar resultado ─────────────────────────────────────────
    print()
    if bot_messages:
        print(f"Flux: {bot_messages[-1].content}")
    else:
        print("Flux: (⚡ Avance silencioso — Perfil completo, pasando al motor)")
    
    # ── DEBUG: Estado del perfil ──────────────────────────────────
    profile_after = state["collecting_data"]["loan_profile"]
    profile_diff  = {k: v for k, v in profile_after.items() if profile_before.get(k) != v}
    
    print(f"\n  {'─'*50}")
    print(f"  [DEBUG] Perfil actual  : {profile_after}")
    print(f"  [DEBUG] Cambios turno  : {profile_diff if profile_diff else '(sin cambios)'}")
    print(f"  [DEBUG] Mensajes total : {len(state['messages'])}")
    print(f"  {'─'*50}\n")
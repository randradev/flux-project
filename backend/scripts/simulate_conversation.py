#!/usr/bin/env python3
import sys
import io

# Forzar salida en UTF-8 para evitar UnicodeEncodeError en Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
"""
scripts/simulate_conversation.py
─────────────────────────────────────────────────────────────
Simulador de Orquestación FLUX — Entorno de Pruebas de Conversación.

PROPÓSITO:
  Replicar el ciclo de vida de una conversación real en consola,
  verificando que el State persiste correctamente entre turnos y
  que el ruteo no retrocede.

USO:
  python scripts/simulate_conversation.py [--scenario <nombre>]

ESCENARIOS DISPONIBLES:
  happy_path_loan       — Flujo completo de crédito (renta, antigüedad, estudios, monto, plazo)
  resume_mid_loan       — Simula renacimiento del grafo en medio de la recolección
  button_click_loan     — Simula clic de botón sin mensaje previo
  intent_change         — Usuario en crédito pregunta por cuenta corriente (a futuro)

SALIDA:
  - Cada turno imprime: input del usuario, nodo(s) ejecutados, State diff y mensaje de Flux.
  - Al final imprime: resumen de la conversación y validación de invariantes.
"""

import sys
import copy
import json
import uuid
from typing import Any
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver

# Importar el grafo SIN el checkpointer de producción
from app.graph.workflow import build_graph


# ══════════════════════════════════════════════════════════════
# UTILIDADES DE CONSOLA
# ══════════════════════════════════════════════════════════════

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
GREY   = "\033[90m"


def _print_header(text: str):
    print(f"\n{BOLD}{CYAN}{'═'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'═'*60}{RESET}")


def _print_turn(turn_num: int, user_input: str):
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}TURNO {turn_num}{RESET}")
    print(f"{GREEN}👤 Usuario:{RESET} {user_input}")


def _print_state_diff(before: dict, after: dict, path: str = ""):
    """
    Imprime recursivamente los campos del State que cambiaron entre dos snapshots.
    Ignora el campo 'messages' (tiene su propio pretty-printer).
    """
    for key in set(list(before.keys()) + list(after.keys())):
        if key == "messages":
            continue
        full_path = f"{path}.{key}" if path else key
        val_before = before.get(key)
        val_after  = after.get(key)
        if isinstance(val_before, dict) and isinstance(val_after, dict):
            _print_state_diff(val_before, val_after, full_path)
        elif val_before != val_after:
            if val_before is None and val_after is not None:
                print(f"  {YELLOW}+ {full_path}:{RESET} {GREY}None{RESET} → {GREEN}{val_after}{RESET}")
            elif val_before is not None and val_after is None:
                print(f"  {RED}- {full_path}:{RESET} {val_before} → {GREY}None{RESET}")
            else:
                print(f"  {YELLOW}~ {full_path}:{RESET} {GREY}{val_before}{RESET} → {GREEN}{val_after}{RESET}")


def _print_messages_diff(before_msgs: list, after_msgs: list):
    new_msgs = after_msgs[len(before_msgs):]
    for msg in new_msgs:
        # msg es un dict del snapshot: {"type": "AIMessage", "content": "..."}
        is_ai = msg.get("type") == "AIMessage"
        role = "🤖 Flux" if is_ai else "👤 User"
        print(f"\n{BOLD}{role}:{RESET} {msg.get('content')}")


def _extract_state_snapshot(state_values: dict) -> dict:
    """Extrae un snapshot serializable del State para diff."""
    snap = {}
    for key, val in state_values.items():
        if key == "messages":
            snap[key] = [{"type": type(m).__name__, "content": m.content} for m in val]
        elif isinstance(val, dict):
            snap[key] = copy.deepcopy(val)
        else:
            snap[key] = val
    return snap


# ══════════════════════════════════════════════════════════════
# MOTOR DE SIMULACIÓN
# ══════════════════════════════════════════════════════════════

class ConversationSimulator:
    """
    Simula turnos de conversación con el grafo FLUX usando MemorySaver.
    """

    def __init__(self, initial_user_data: dict, initial_session: dict):
        # Compilar con checkpointer en memoria (no necesita Supabase)
        self.checkpointer = MemorySaver()
        self.graph = build_graph().compile(checkpointer=self.checkpointer)
        self.thread_id = str(uuid.uuid4())
        self.config = {"configurable": {"thread_id": self.thread_id}}

        # Estado inicial que se inyecta en el primer turno
        self._initial_user_data = initial_user_data
        self._initial_session = initial_session

        self.turn_number = 0
        self.validation_log = []
        self._last_snapshot = {}

    def _get_current_state(self) -> dict:
        """Obtiene el State actual del checkpointer."""
        checkpoint = self.graph.get_state(self.config)
        return checkpoint.values if checkpoint else {}

    def send(self, user_input: str, *, inject_product_intent: str = None) -> dict:
        """
        Envía un mensaje al grafo y retorna el State resultante.
        """
        self.turn_number += 1
        
        # Guardrail: Vertex AI falla con strings vacíos. Si el input es "", usamos un espacio o None.
        effective_input = user_input if user_input.strip() else " "
        
        _print_turn(self.turn_number, user_input or "(sin mensaje — turno de inicio)")

        # Construir el input del turno
        if self.turn_number == 1:
            # Primer turno: incluir todo el estado inicial
            session = {**self._initial_session}
            if inject_product_intent:
                session["product_intent"] = inject_product_intent
            turn_input = {
                "messages": [HumanMessage(content=effective_input)] if user_input else [],
                "user_data": self._initial_user_data,
                "session": session,
                "collecting_data": {},
                "preparation_data": {},
                "evaluation_results": {},
                "offer_data": {},
                "auth_control": {},
                "flow_result": {},
            }
        else:
            # Turnos siguientes: solo el mensaje nuevo (el State persiste via checkpointer)
            session_patch = {}
            if inject_product_intent:
                session_patch["product_intent"] = inject_product_intent

            turn_input = {"messages": [HumanMessage(content=user_input)]}
            if session_patch:
                current = self._get_current_state()
                turn_input["session"] = {**current.get("session", {}), **session_patch}

        snapshot_before = _extract_state_snapshot(self._get_current_state())

        # DEBUG: Verificar qué flag se le envía al grafo
        debug_session = turn_input.get("session") or self._get_current_state().get("session", {})
        print(f"\n[SIM-DEBUG] Flag en memoria antes de enviar: {debug_session.get('just_completed_step')}")

        # Invocar el grafo
        result = self.graph.invoke(turn_input, config=self.config)

        snapshot_after = _extract_state_snapshot(result)

        # ── Imprimir diff del State ────────────────────────────
        print(f"\n{BOLD}📊 State Diff:{RESET}")
        _print_state_diff(snapshot_before, snapshot_after)

        # ── Imprimir mensajes nuevos ───────────────────────────
        msgs_before = [m for m in (self._get_current_state().get("messages", []))]
        _print_messages_diff(
            snapshot_before.get("messages", []),
            snapshot_after.get("messages", [])
        )

        # ── Validar invariantes ────────────────────────────────
        self._validate_invariants(snapshot_before, snapshot_after)

        self._last_snapshot = snapshot_after
        return result

    def _validate_invariants(self, before: dict, after: dict):
        """
        Valida que el State cumple las reglas de negocio tras cada turno.
        Registra violaciones en self.validation_log.
        """
        session_after = after.get("session", {})
        current_node = session_after.get("current_node", "")

        # Invariante 1: current_node nunca debe retroceder en el flujo de crédito
        # (simplificado: no debe volver a WELCOME_NODE si ya estaba en el flujo)
        session_before = before.get("session", {})
        current_node_before = session_before.get("current_node", "")
        loan_flow = ["LOAN_INIT", "LOAN_COLLECTING_PROFILE", "LOAN_COLLECTING_SIMULATION"]
        if current_node_before in loan_flow and current_node == "WELCOME_NODE":
            violation = f"⚠️ VIOLACIÓN T{self.turn_number}: current_node retrocedió de {current_node_before} a WELCOME_NODE"
            self.validation_log.append(violation)
            print(f"\n{RED}{violation}{RESET}")

        # Invariante 2: preparation_data debe estar poblado después del welcome
        if self.turn_number >= 1:
            prep = after.get("preparation_data", {})
            if not prep.get("nombre") and not prep.get("rut"):
                warning = f"⚠️ AVISO T{self.turn_number}: preparation_data vacío después del turno {self.turn_number}"
                self.validation_log.append(warning)
                print(f"\n{YELLOW}{warning}{RESET}")

        # Invariante 3: loan_init no debe emitir el saludo fijo hardcodeado
        messages_after = after.get("messages", [])
        if messages_after:
            last_msg_content = messages_after[-1].get("content", "")
            if "Vamos a revisar tu solicitud de **Crédito de Consumo**" in last_msg_content:
                violation = f"⚠️ VIOLACIÓN T{self.turn_number}: Saludo hardcodeado detectado en el mensaje de Flux"
                self.validation_log.append(violation)
                print(f"\n{RED}{violation}{RESET}")

    def print_summary(self):
        """Imprime un resumen al final de la simulación."""
        _print_header("RESUMEN DE LA SIMULACIÓN")
        print(f"  Turnos completados: {self.turn_number}")
        print(f"  Thread ID: {self.thread_id}")
        if not self.validation_log:
            print(f"\n  {GREEN}✅ Todos los invariantes cumplidos. Sin violaciones.{RESET}")
        else:
            print(f"\n  {RED}❌ Se detectaron {len(self.validation_log)} violaciones:{RESET}")
            for v in self.validation_log:
                print(f"    {v}")


# ══════════════════════════════════════════════════════════════
# DATOS DE PRUEBA
# ══════════════════════════════════════════════════════════════

MOCK_USER = {
    "user_id": "test-user-001",
    "full_name": "Ricardo Andrade Valderrama",
    "email": "randradev.dev@gmail.com",
    "rut": "19054114-2",
    "birth_date": "1995-03-03",
    "user_status": "ACTIVE",
    "user_category": None,
}

MOCK_SESSION_NEW = {
    "conversation_id": "conv-test-001",
    "application_id": None,
    "product_intent": None,
    "current_node": "",
    "previous_node": None,
    "is_transversal_active": False,
}


# ══════════════════════════════════════════════════════════════
# ESCENARIOS
# ══════════════════════════════════════════════════════════════

def scenario_happy_path_loan():
    """
    Escenario 1: Happy Path del Crédito de Consumo.
    Simula el flujo completo desde el saludo hasta la recolección de datos.
    """
    _print_header("ESCENARIO: Happy Path — Crédito de Consumo")

    sim = ConversationSimulator(MOCK_USER, MOCK_SESSION_NEW)

    # Turno 1: Usuario abre el chat, clic en botón "Crédito"
    sim.send("", inject_product_intent="LOAN")

    # Turno 2: Usuario entrega renta
    sim.send("gano 2 palos líquidos")

    # Turno 3: Usuario entrega antigüedad
    sim.send("llevo 3 años en mi pega actual")

    # Turno 4: Usuario entrega nivel de estudios
    sim.send("soy ingeniero comercial")

    sim.print_summary()


def scenario_resume_mid_loan():
    """
    Escenario 2: Reanudación en medio del flujo.
    Simula que el grafo "renace" (nueva invocación) después de que
    el usuario ya entregó la renta.
    """
    _print_header("ESCENARIO: Reanudación — Grafo renace en LOAN_COLLECTING_PROFILE")

    # Sesión con current_node ya en el flujo de crédito (turno anterior guardado)
    session_resumed = {
        **MOCK_SESSION_NEW,
        "current_node": "LOAN_COLLECTING_PROFILE",
        "product_intent": "LOAN",
    }
    sim = ConversationSimulator(MOCK_USER, session_resumed)

    # Turno 1: El grafo renace. El usuario envía su antigüedad laboral.
    # EXPECTATIVA: welcome es silencioso, route_after_welcome va a loan_collecting_profile.
    sim.send("llevo 5 años trabajando en la misma empresa")

    sim.print_summary()


def scenario_button_click_no_prior_history():
    """
    Escenario 3: Clic de botón en sesión completamente nueva.
    EXPECTATIVA: welcome silencioso (P2), route va a loan_init.
    """
    _print_header("ESCENARIO: Clic de Botón — Sin historial previo")

    sim = ConversationSimulator(MOCK_USER, MOCK_SESSION_NEW)
    sim.send("", inject_product_intent="LOAN")

    # Verificar que se fue a loan_init y current_node quedó en LOAN_COLLECTING_PROFILE
    state = sim._get_current_state()
    cn = state.get("session", {}).get("current_node", "")
    status = "✅ PASS" if cn == "LOAN_COLLECTING_PROFILE" else f"❌ FAIL (fue a {cn})"
    print(f"\n{BOLD}Validación Punto de Guardado:{RESET} {status}")

    sim.print_summary()

def scenario_manual_test():
    """
    Escenario interactivo para pruebas manuales en consola.
    Permite chatear con Flux en tiempo real viendo el State Diff.
    """
    _print_header("🎮 MODO PRUEBA MANUAL INTERACTIVA")
    
    # Inicializamos el simulador
    sim = ConversationSimulator(MOCK_USER, MOCK_SESSION_NEW)
    
    print("\n[Sistema] Iniciando flujo con intención de crédito (Botón LOAN)...")
    sim.send("", inject_product_intent="LOAN")
    
    # Bucle de chat
    while True:
        try:
            user_msg = input("\n[Tú]: ")
            if user_msg.lower() in ["salir", "exit", "quit", "q"]:
                print("\n[Sistema] Cerrando simulador. ¡Adiós!")
                break

            # --- MAPEADOR DE BOTONES SIMULADOS ---
            command_map = {
                "/acepto":   "ACEPTAR",
                "/si":       "ACEPTAR",
                "/no":       "RECHAZAR",
                "/rechazo":  "RECHAZAR",
                "/cancelar": "RECHAZAR"
            }
            
            if user_msg.lower() in command_map:
                user_msg = command_map[user_msg.lower()]
                print(f"{YELLOW}[Simulación] Clic en botón: {user_msg}{RESET}")
            # -------------------------------------
            
            if not user_msg.strip():
                continue
                
            sim.send(user_msg)
            
        except KeyboardInterrupt:
            print("\n\n[Sistema] Simulación interrumpida.")
            break

# ══════════════════════════════════════════════════════════════
# ENTRYPOINT
# ══════════════════════════════════════════════════════════════

SCENARIOS = {
    "happy_path_loan":            scenario_happy_path_loan,
    "resume_mid_loan":            scenario_resume_mid_loan,
    "button_click_loan":          scenario_button_click_no_prior_history,
    "manual":                     scenario_manual_test,
}

if __name__ == "__main__":
    scenario_name = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--scenario" else None

    if scenario_name:
        if scenario_name not in SCENARIOS:
            print(f"Escenario desconocido: {scenario_name}")
            print(f"Disponibles: {', '.join(SCENARIOS.keys())}")
            sys.exit(1)
        SCENARIOS[scenario_name]()
    else:
        # Si no se especifica, correr todos
        for name, fn in SCENARIOS.items():
            fn()
            print("\n")
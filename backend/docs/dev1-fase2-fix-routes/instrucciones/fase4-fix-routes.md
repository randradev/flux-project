## V. Fase 4 — Aristas Condicionales Intra-turno en `workflow.py`

**Archivo:** `app/graph/workflow.py`

Esta fase es el corazón de la solución: transforma el edge fijo `loan_collecting_profile → END` en un edge condicional que salta al siguiente nodo cuando el paso se completó.

### 5.1 Funciones de decisión de arista

Estas funciones deben vivir en `edges.py` (por consistencia arquitectónica):

```python
# En app/graph/edges.py — agregar al final del archivo

def route_after_loan_collecting_profile(state: FluxState) -> str:
    """
    Decisión de arista post-loan_collecting_profile.

    Si el perfil acaba de completarse (just_completed_step = LOAN_PROFILE),
    salta directamente a loan_collecting_simulation en el mismo turno.
    Si no, va a END para esperar el siguiente mensaje del usuario.

    NOTA: No se usa progress aquí deliberadamente; just_completed_step es
    la señal más fresca y específica del turno actual.
    """
    session = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.LOAN_PROFILE:
        return "loan_collecting_simulation"
    return END


def route_after_loan_collecting_sim(state: FluxState) -> str:
    """
    Decisión de arista post-loan_collecting_simulation.

    Si la simulación se completó (just_completed_step = LOAN_SIMULATION),
    salta al motor de riesgo en el mismo turno.
    Si no, va a END.
    """
    session = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.LOAN_SIMULATION:
        return "loan_risk_engine"
    return END


def route_after_account_collecting_profile(state: FluxState) -> str:
    """Decisión de arista post-account_collecting_profile."""
    session = state.get("session", {})
    just_completed = session.get("just_completed_step")

    if just_completed == CompletedStep.ACCOUNT_PROFILE:
        return "account_evaluation_engine"
    return END
```

**Nota:** Las funciones retornan `END` (importado de `langgraph.graph`) para el camino incompleto. LangGraph acepta `END` como valor de retorno de una función de edge condicional.

### 5.2 Actualizar `workflow.py`

**Importaciones a agregar:**

```python
from app.graph.edges import (
    route_after_welcome,
    route_after_intent,
    route_after_loan_collecting_profile,   # NUEVO
    route_after_loan_collecting_sim,        # NUEVO
    route_after_account_collecting_profile, # NUEVO
)
```

**Reemplazar edges fijos de recolección con edges condicionales:**

```python
# ── ELIMINAR estas líneas del bloque actual: ──────────────────
# graph.add_edge("loan_collecting_profile",    END)
# graph.add_edge("loan_collecting_simulation", "loan_risk_engine")
# graph.add_edge("account_collecting_profile", "account_evaluation_engine")

# ── AGREGAR en su lugar: ──────────────────────────────────────

# Crédito: aristas condicionales de recolección
graph.add_conditional_edges(
    "loan_collecting_profile",
    route_after_loan_collecting_profile,
    {
        "loan_collecting_simulation": "loan_collecting_simulation",
        END: END,
    }
)

graph.add_conditional_edges(
    "loan_collecting_simulation",
    route_after_loan_collecting_sim,
    {
        "loan_risk_engine": "loan_risk_engine",
        END: END,
    }
)

# Cuenta: arista condicional de recolección
graph.add_conditional_edges(
    "account_collecting_profile",
    route_after_account_collecting_profile,
    {
        "account_evaluation_engine": "account_evaluation_engine",
        END: END,
    }
)

# DAP: dap_collect_data ya tiene edge fijo a dap_investment_engine
# (DAP no tiene paso de perfil separado, el salto ocurre diferente)
# graph.add_edge("dap_collect_data", "dap_investment_engine") — mantener
```

**Resumen del grafo de crédito resultante:**

```
welcome (silencioso)
  ↓ route_after_welcome
loan_init
  ↓ (edge fijo)
loan_collecting_profile  ←── (P2/P3 reanudación / inicio)
  ↓ route_after_loan_collecting_profile
  ├── [perfil completo]  ──→ loan_collecting_simulation (intra-turno)
  │                              ↓ route_after_loan_collecting_sim
  │                              ├── [sim completa] ──→ loan_risk_engine
  │                              │                          ↓ route_after_loan_risk_engine [INVARIANTE]
  │                              │                          ├── PRE_APPROVED → loan_pre_approved → END
  │                              │                          └── REJECTED     → loan_rejected_policy → END
  │                              └── [sim incompleta] ──→ END (esperar usuario)
  └── [perfil incompleto] ──→ END (esperar usuario)
```

**Invariante garantizado:** ningún nodo lógico (motor de cálculo o similar) apunta a `END` directamente. Solo los nodos terminales de respuesta (`loan_pre_approved`, `loan_rejected_policy`, futuros `loan_completed`, `loan_security_block`) tienen edge a `END`.

### 5.3 Garantía de respuesta: invariante de motor

**El problema original de esta sección queda cerrado.**

La preocupación anterior era que `loan_risk_engine_node` retorna solo `evaluation_results` sin `messages`, lo que podría generar un turno silencioso si el salto intra-turno llegaba hasta él. Esa situación ya no es posible porque:

1. `loan_risk_engine` tiene una arista **condicional obligatoria** hacia `loan_pre_approved` o `loan_rejected_policy` (configurada en `workflow.py`).
2. Ambos nodos destino son **generadores de respuesta**: su primera acción es invocar la Llamada B y escribir un `AIMessage` en `state["messages"]`.
3. Esta estructura es el **invariante de motor**: cualquier nodo lógico de cálculo (actual o futuro) siempre debe conectarse a un nodo generador de respuesta, nunca a `END`.

La función `route_after_loan_collecting_sim` puede habilitarse **inmediatamente** con el salto completo a `loan_risk_engine`, sin medidas temporales ni postergación. No hay prerequisito pendiente.

---

### ✅ Tests Fase 4

#### TEST 4.A — Funciones de edge condicional

```python
# tests/unit/test_edges_intra_turn.py
from langgraph.graph import END
from app.graph.edges import (
    route_after_loan_collecting_profile,
    route_after_loan_collecting_sim,
)
from app.graph.constants import CompletedStep


def test_loan_profile_edge_jumps_when_complete():
    state = {"session": {"just_completed_step": CompletedStep.LOAN_PROFILE}}
    assert route_after_loan_collecting_profile(state) == "loan_collecting_simulation"


def test_loan_profile_edge_goes_to_end_when_incomplete():
    state = {"session": {"just_completed_step": None}}
    assert route_after_loan_collecting_profile(state) == END


def test_loan_sim_edge_jumps_when_complete():
    state = {"session": {"just_completed_step": CompletedStep.LOAN_SIMULATION}}
    assert route_after_loan_collecting_sim(state) == "loan_risk_engine"


def test_loan_sim_edge_goes_to_end_when_incomplete():
    state = {"session": {"just_completed_step": None}}
    assert route_after_loan_collecting_sim(state) == END


def test_loan_profile_edge_ignores_other_steps():
    """Pasos de otros productos no deben causar salto en el edge de perfil."""
    state = {"session": {"just_completed_step": CompletedStep.ACCOUNT_PROFILE}}
    assert route_after_loan_collecting_profile(state) == END
```

#### TEST 4.B — Integración: flujo completo de un turno con salto intra-turno

```python
# tests/integration/test_intra_turn_jump.py
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from app.graph.workflow import build_graph
from app.graph.constants import CompletedStep


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_intra_turn_jump_profile_to_sim(mock_conv, mock_sem, mock_profile_ext, mock_gen):
    """
    CASO CRÍTICO: El turno en que se completa el perfil debe:
    1. Ejecutar loan_collecting_profile (avance silencioso).
    2. Saltar a loan_collecting_sim EN EL MISMO TURNO (sin input adicional).
    3. Generar un mensaje de celebración + pregunta de monto.
    4. Estado final: current_node = LOAN_COLLECTING_SIMULATION, just_completed_step = None.
    """
    from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction, LoanSimExtraction

    # Perfil completo al dar el último dato (nivel_estudios)
    mock_profile_ext.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        razonamiento="Nivel estudios detectado",
        nivel_estudios="UNIVERSITARIO",
    )
    mock_gen.invoke.return_value = MagicMock(
        content="¡Listo tu perfil, {nombre}! Ahora, ¿cuánto necesitas?"
    )

    graph = build_graph().compile(checkpointer=MemorySaver())
    thread_cfg = {"configurable": {"thread_id": "test-intra-01"}}

    state_input = {
        "messages": [HumanMessage(content="Soy ingeniero civil")],
        "user_data": {"full_name": "Luis Morales", "birth_date": "1988-03-10", "rut": "", "email": ""},
        "session": {
            "product_intent": "LOAN",
            "current_node": "LOAN_COLLECTING_PROFILE",
            "progress": {},
            "application_id": None,
        },
        "preparation_data": {"nombre": "Luis Morales", "edad": 36, "rut": "", "mail": ""},
        "collecting_data": {
            "loan_profile": {"renta": 2500000, "antiguedad_laboral": 48},  # Solo falta nivel_estudios
            "loan_sim": {}
        },
        "evaluation_results": {}, "offer_data": {}, "auth_control": {}, "flow_result": {},
    }

    result = graph.invoke(state_input, config=thread_cfg)

    # Verificar que se generó un mensaje (Llamada B de simulación)
    messages = result.get("messages", [])
    ai_messages = [m for m in messages if hasattr(m, "type") and m.type == "ai"]
    assert len(ai_messages) >= 1, "Debe haber al menos un mensaje de Flux"

    # Verificar estado final
    final_session = result.get("session", {})
    assert final_session.get("current_node") == "LOAN_COLLECTING_SIMULATION"
    assert final_session.get("just_completed_step") is None, \
        "just_completed_step debe limpiarse tras la Llamada B"
    assert final_session.get("progress", {}).get("loan", {}).get("profile_completed") is True
```

#### TEST 4.C — Protocolo de "un solo turno" (criterio de aceptación de negocio)

```python
@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_no_double_celebration_in_subsequent_turn(
    mock_conv, mock_sem, mock_profile_ext, mock_gen
):
    """
    INVARIANTE: La celebración del perfil completado ocurre exactamente una vez.
    En el turno siguiente (usuario responde el monto), Flux NO debe celebrar de nuevo.
    """
    from app.graph.nodes.schemas.loan_schemas import LoanSimExtraction

    celebration_count = {"n": 0}
    original_gen = mock_gen.invoke.side_effect

    def gen_side_effect(messages):
        system_prompt = messages[0]["content"]
        if "acaba de completar su perfil" in system_prompt or "LOAN_PROFILE" in str(messages[1]["content"]):
            celebration_count["n"] += 1
        return MagicMock(content="¿Cuántas cuotas?")

    mock_gen.invoke.side_effect = gen_side_effect
    mock_profile_ext.invoke.return_value = MagicMock(
        intencion="DATO_FINANCIERO", razonamiento="", monto_solicitado=5000000, plazo_solicitado=None
    )

    # Simular turno donde ya se saltó a simulación (just_completed_step ya limpio)
    from app.graph.nodes.credit import loan_collecting_sim_node
    from app.graph.nodes.schemas.loan_schemas import LoanSimExtraction

    mock_profile_ext.invoke.return_value = LoanSimExtraction(
        intencion="DATO_FINANCIERO", razonamiento="Monto detectado", monto_solicitado=5000000
    )

    state = {
        "preparation_data": {"nombre": "Rosa Fuentes", "edad": 32, "rut": "", "mail": ""},
        "session": {
            "current_node": "LOAN_COLLECTING_SIMULATION",
            "just_completed_step": None,  # Ya fue limpiada en el turno anterior
            "progress": {"loan": {"profile_completed": True}},
            "application_id": None,
        },
        "collecting_data": {
            "loan_profile": {"renta": 1800000, "antiguedad_laboral": 18, "nivel_estudios": "TECNICO"},
            "loan_sim": {},
        },
        "messages": [HumanMessage(content="quiero 5 millones")],
    }

    loan_collecting_sim_node(state)
    # La llamada B NO debe recibir instrucción de celebración del perfil
    call_args = mock_gen.invoke.call_args[0][0]
    user_context = call_args[1]["content"]
    assert "acaba de completar su perfil" not in user_context
```

---

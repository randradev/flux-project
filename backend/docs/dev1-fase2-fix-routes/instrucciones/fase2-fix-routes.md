## III. Fase 2 — Refactorización de Nodos y Helpers en `credit.py`

**Archivo:** `app/graph/nodes/credit.py`

### 3.1 Actualizar `loan_collecting_profile_node`

**Cambio:** Reemplazar la flag local `profile_just_completed` por la escritura dual (histórica + volátil).

Sección a modificar (paso 7, bloque `if not missing`):

```python
# ANTES (código actual)
if not missing:
    if application_id:
        update_application_semaphores(...)
    output["session"]["profile_just_completed"] = True
    return output

# DESPUÉS (v2.2)
if not missing:
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_COLLECTING_PROFILE",
            node_status="SUCCESS",
            engine_status="PENDING",
        )
    # ── ESCRITURA DUAL de flags ───────────────────────────────
    # 1. Histórica (persistente): el ruteador sabrá que el perfil está completo
    current_progress = session.get("progress", {})
    loan_progress = current_progress.get("loan", {})
    updated_progress = {
        **current_progress,
        "loan": {**loan_progress, "profile_completed": True},
    }
    # 2. Volátil (1 turno): señal para el nodo destino del salto intra-turno
    output["session"] = {
        **output["session"],
        "progress":           updated_progress,
        "just_completed_step": CompletedStep.LOAN_PROFILE,
        # current_node ya está en "LOAN_COLLECTING_PROFILE" desde output base
    }
    return output  # Sin mensajes: la arista condicional saltará a loan_collecting_sim
```

**Importante:** agregar el import al inicio del archivo:
```python
from app.graph.constants import CompletedStep
```

### 3.2 Actualizar `loan_collecting_sim_node`

Este nodo tiene tres responsabilidades nuevas:
1. **Detectar salto intra-turno** vía `just_completed_step`.
2. **Omitir Llamada A** si viene de salto (no hay dato nuevo para extraer).
3. **Limpiar** `just_completed_step` en su propio return, **después** de invocar Llamada B.
4. **Escribir** su propia escritura dual cuando la simulación se completa.

```python
def loan_collecting_sim_node(state: FluxState) -> dict:
    """
    VERSIÓN 2.2 — Nodo LOAN_COLLECTING_SIMULATION con Ruteo Consciente.

    CAMBIOS vs 2.1:
      - Detecta salto intra-turno via just_completed_step == LOAN_PROFILE.
      - Omite Llamada A en caso de salto (no hay mensaje nuevo del usuario).
      - Lee just_completed_step en lugar de profile_just_completed (deprecated).
      - Limpia just_completed_step en el return post-Llamada B.
      - Escribe escritura dual al completar la simulación.
    """
    session    = state.get("session", {})
    collecting = state.get("collecting_data", {})
    prep       = state.get("preparation_data", {})
    messages   = state.get("messages", [])

    just_completed = session.get("just_completed_step")   # ← v2.2
    is_intra_turn_jump = (just_completed == CompletedStep.LOAN_PROFILE)

    current_sim = collecting.get("loan_sim", {})
    first_name  = prep.get("nombre", "").split()[0] if prep.get("nombre") else "amig@"

    last_user_msg = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )

    # ── LLAMADA A: solo si NO es salto intra-turno ────────────
    # Si venimos de un salto, el last_user_msg ya fue procesado por el nodo de perfil.
    # Ejecutar Llamada A sobre él generaría extracciones incorrectas o vacías.
    newly_extracted = {}
    updated_sim = {**current_sim}

    if not is_intra_turn_jump and last_user_msg:
        extracted: LoanSimExtraction = _sim_extractor.invoke([
            {"role": "system", "content": SYSTEM_PROMPT_EXTRACTION_SIM},
            {"role": "user",   "content": last_user_msg},
        ]) or LoanSimExtraction(intencion="OTRO", razonamiento="Error")

        if extracted.intencion == "DATO_FINANCIERO":
            if extracted.monto_solicitado is not None:
                updated_sim["monto_solicitado"] = extracted.monto_solicitado
                newly_extracted["monto_solicitado"] = extracted.monto_solicitado
            if extracted.plazo_solicitado is not None:
                updated_sim["plazo_solicitado"] = extracted.plazo_solicitado
                newly_extracted["plazo_solicitado"] = extracted.plazo_solicitado

        intencion_for_b = extracted.intencion
        razonamiento_for_b = extracted.razonamiento
    else:
        # Salto intra-turno: no hay extracción; el contexto es solo la transición
        intencion_for_b = "DATO_FINANCIERO"   # Neutro: el generador se guiará por just_completed
        razonamiento_for_b = "Salto intra-turno desde perfil completo."

    # ── EVALUACIÓN DE COMPLETITUD ─────────────────────────────
    missing = _get_missing_sim_fields(updated_sim)

    # ── OUTPUT BASE ───────────────────────────────────────────
    output = {
        "collecting_data": {**collecting, "loan_sim": updated_sim},
        "session": {
            **session,
            "current_node": "LOAN_COLLECTING_SIMULATION",
            "just_completed_step": None,   # ← Limpieza anticipada (se sobreescribirá si sim completa)
        },
    }

    # ── AVANCE SILENCIOSO (simulación completa) ───────────────
    if not missing:
        current_progress = session.get("progress", {})
        loan_progress = current_progress.get("loan", {})
        output["session"] = {
            **output["session"],
            "progress": {
                **current_progress,
                "loan": {**loan_progress, "simulation_completed": True},
            },
            "just_completed_step": CompletedStep.LOAN_SIMULATION,
            # La arista condicional saltará a loan_risk_engine
        }
        return output

    # ── LLAMADA B ─────────────────────────────────────────────
    context = _build_sim_generation_context(
        nombre=first_name,
        intencion=intencion_for_b,
        known_sim=updated_sim,
        missing=missing,
        newly_extracted=newly_extracted,
        just_completed_step=just_completed,   # ← v2.2: reemplaza profile_just_completed
        last_msg=last_user_msg,
        razonamiento=razonamiento_for_b,
    )

    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_GENERATION_SIM},
        {"role": "user",   "content": context},
    ])

    clean_content = normalize_llm_response(flux_response.content)
    output["messages"] = [AIMessage(content=clean_content)]
    # just_completed_step ya se limpió en output base (= None): no reasignar aquí.
    # La Llamada B ya lo consumió; la flag no debe sobrevivir al siguiente turno.

    return output
```

### 3.3 Actualizar `_build_sim_generation_context`

Reemplazar el parámetro `profile_just_completed: bool` por `just_completed_step: str | None`:

```python
def _build_sim_generation_context(
    nombre: str,
    intencion: str,
    known_sim: dict,
    missing: list[str],
    newly_extracted: dict,
    just_completed_step: str | None = None,   # ← v2.2: reemplaza profile_just_completed
    last_msg: str = "",
    razonamiento: str = "",
) -> str:
    """
    CAMBIOS v2.2:
      - Parámetro just_completed_step reemplaza profile_just_completed (bool).
      - Genera instrucciones de transición para cualquier paso completado, no solo perfil.
    """
    from app.graph.constants import CompletedStep

    field_labels = {
        "monto_solicitado": "monto del crédito",
        "plazo_solicitado": "plazo en cuotas mensuales",
    }

    # ... (construcción de known_lines, new_lines, missing_labels sin cambios) ...

    # ── Mensaje de transición basado en qué se acaba de completar ──
    transicion_msg = ""
    if just_completed_step == CompletedStep.LOAN_PROFILE:
        transicion_msg = (
            "AVISO: El usuario acaba de completar su perfil financiero exitosamente. "
            "NO saludes de nuevo; celebra brevemente ese hito y pide el MONTO del crédito."
        )
    elif just_completed_step == CompletedStep.LOAN_SIMULATION:
        transicion_msg = (
            "AVISO: El usuario acaba de completar los datos de simulación. "
            "Indícale que calcularás su crédito de inmediato."
        )
    # Extensible: agregar elif para otros pasos futuros

    context = f"""
    {transicion_msg}
    ÚLTIMO MENSAJE DEL USUARIO: "{last_msg}"
    ANÁLISIS DEL EXTRACTOR: {razonamiento}
    ...
    """
    return context
```

### 3.4 Limpiar la flag deprecada `profile_just_completed`

Buscar y eliminar **todas** las referencias a `profile_just_completed` en `credit.py`:
- Línea 385: `output["session"]["profile_just_completed"] = True` → eliminada (reemplazada en 3.1).
- Línea 422: `just_finished_profile = session.get("profile_just_completed", False)` → eliminada (reemplazada por `just_completed_step`).
- Línea 493: `output["session"]["profile_just_completed"] = False` → eliminada (la limpieza ahora ocurre en el output base de `loan_collecting_sim_node`).

---

### ✅ Tests Fase 2

#### TEST 2.A — Escritura dual al completar el perfil

```python
# tests/unit/test_credit_nodes_v22.py
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage
from app.graph.constants import CompletedStep
from app.graph.nodes.credit import loan_collecting_profile_node


def _profile_state_complete():
    """State donde el perfil se completa en este turno."""
    return {
        "preparation_data": {"nombre": "Ana López", "edad": 30, "rut": "", "mail": ""},
        "session": {
            "product_intent": "LOAN",
            "current_node": "LOAN_COLLECTING_PROFILE",
            "application_id": None,
            "progress": {},
        },
        "collecting_data": {"loan_profile": {"renta": 1500000, "antiguedad_laboral": 24}},
        "messages": [HumanMessage(content="Tengo estudios universitarios")],
    }


@patch("app.graph.nodes.credit._profile_extractor")
def test_dual_flag_written_when_profile_completes(mock_extractor):
    from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        razonamiento="Nivel universitario detectado",
        nivel_estudios="UNIVERSITARIO",
    )
    result = loan_collecting_profile_node(_profile_state_complete())

    # Flag histórica
    assert result["session"]["progress"]["loan"]["profile_completed"] is True
    # Flag volátil
    assert result["session"]["just_completed_step"] == CompletedStep.LOAN_PROFILE
    # Sin mensajes (avance silencioso)
    assert "messages" not in result or result.get("messages") == []


@patch("app.graph.nodes.credit._profile_extractor")
def test_no_flags_written_when_profile_incomplete(mock_extractor):
    from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        razonamiento="Solo renta",
        renta=1500000,
    )
    state = _profile_state_complete()
    state["collecting_data"] = {"loan_profile": {}}  # Perfil vacío: solo se añade renta
    result = loan_collecting_profile_node(state)

    progress = result.get("session", {}).get("progress", {})
    jcs = result.get("session", {}).get("just_completed_step")
    assert not progress.get("loan", {}).get("profile_completed")
    assert jcs is None
```

#### TEST 2.B — `loan_collecting_sim_node`: omite Llamada A en salto intra-turno

```python
@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._sim_extractor")
def test_sim_node_skips_extractor_on_intra_turn_jump(mock_extractor, mock_gen):
    from app.graph.nodes.credit import loan_collecting_sim_node

    mock_gen.invoke.return_value = MagicMock(
        content="¡Perfecto, perfil listo! ¿Cuánto necesitas?"
    )

    state = {
        "preparation_data": {"nombre": "Carlos Vera", "edad": 35, "rut": "", "mail": ""},
        "session": {
            "current_node": "LOAN_COLLECTING_PROFILE",
            "just_completed_step": CompletedStep.LOAN_PROFILE,
            "progress": {"loan": {"profile_completed": True}},
            "application_id": None,
        },
        "collecting_data": {"loan_profile": {"renta": 2000000, "antiguedad_laboral": 36, "nivel_estudios": "UNIVERSITARIO"}, "loan_sim": {}},
        "messages": [HumanMessage(content="Tengo estudios universitarios")],
    }

    result = loan_collecting_sim_node(state)

    # Extractor NO debe llamarse (mensaje ya fue procesado por nodo anterior)
    mock_extractor.invoke.assert_not_called()
    # Generador SÍ debe llamarse (debe pedir el monto)
    mock_gen.invoke.assert_called_once()
    # just_completed_step debe limpiarse
    assert result["session"]["just_completed_step"] is None


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._sim_extractor")
def test_sim_node_cleans_flag_after_generation(mock_extractor, mock_gen):
    """La flag just_completed_step debe ser None en el return tras Llamada B."""
    from app.graph.nodes.credit import loan_collecting_sim_node
    from app.graph.nodes.schemas.loan_schemas import LoanSimExtraction

    mock_gen.invoke.return_value = MagicMock(content="¿Cuánto necesitas?")
    mock_extractor.invoke.return_value = LoanSimExtraction(
        intencion="OTRO", razonamiento="Saludo"
    )

    state = {
        "preparation_data": {"nombre": "María Torres", "edad": 28, "rut": "", "mail": ""},
        "session": {
            "current_node": "LOAN_COLLECTING_SIMULATION",
            "just_completed_step": None,
            "progress": {"loan": {"profile_completed": True}},
            "application_id": None,
        },
        "collecting_data": {"loan_profile": {"renta": 1000000, "antiguedad_laboral": 12, "nivel_estudios": "TECNICO"}, "loan_sim": {}},
        "messages": [HumanMessage(content="hola")],
    }

    result = loan_collecting_sim_node(state)
    assert result["session"]["just_completed_step"] is None


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._sim_extractor")
def test_sim_completion_sets_dual_flags(mock_extractor, mock_gen):
    """Cuando la simulación se completa, debe escribir ambas flags."""
    from app.graph.nodes.credit import loan_collecting_sim_node
    from app.graph.nodes.schemas.loan_schemas import LoanSimExtraction

    mock_extractor.invoke.return_value = LoanSimExtraction(
        intencion="DATO_FINANCIERO",
        razonamiento="Monto y plazo detectados",
        monto_solicitado=5000000,
        plazo_solicitado=24,
    )

    state = {
        "preparation_data": {"nombre": "Pedro Soto", "edad": 40, "rut": "", "mail": ""},
        "session": {
            "current_node": "LOAN_COLLECTING_SIMULATION",
            "just_completed_step": None,
            "progress": {"loan": {"profile_completed": True}},
            "application_id": None,
        },
        "collecting_data": {"loan_profile": {"renta": 3000000, "antiguedad_laboral": 60, "nivel_estudios": "POSTGRADO"}, "loan_sim": {}},
        "messages": [HumanMessage(content="quiero 5 palos en 24 cuotas")],
    }

    result = loan_collecting_sim_node(state)

    assert result["session"]["progress"]["loan"]["simulation_completed"] is True
    assert result["session"]["just_completed_step"] == CompletedStep.LOAN_SIMULATION
    assert "messages" not in result or not result.get("messages")
    mock_gen.invoke.assert_not_called()  # Avance silencioso: no se genera mensaje
```

---
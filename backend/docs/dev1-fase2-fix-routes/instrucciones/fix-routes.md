# Plan de Implementación: Ruteo Consciente de Progreso
**Proyecto:** FLUX — Asistente Financiero  
**Versión objetivo:** 2.2  
**Archivos afectados:** `state.py`, `credit.py`, `edges.py`, `workflow.py`, `common.py`  
**Problema raíz:** `loan_collecting_profile` retorna sin mensajes al completarse, el grafo termina en `END`, y el siguiente turno reanuda en el mismo nodo → bucle infinito de recolección.

---

## I. Validación Técnica de Viabilidad

### 1.1 Diagnóstico del Bucle Infinito

El ciclo se reproduce así con el código actual:

```
Turno N (usuario completa perfil):
  welcome (silencioso)
  → route_after_welcome: current_node="LOAN_COLLECTING_PROFILE" → P1 → loan_collecting_profile
  → loan_collecting_profile: profile completo → sets profile_just_completed=True, sin mensajes
  → Edge: loan_collecting_profile → END  ← aquí nace el problema
  → State persiste: current_node="LOAN_COLLECTING_PROFILE", profile_just_completed=True

Turno N+1 (usuario escribe cualquier cosa):
  welcome (silencioso)
  → route_after_welcome: current_node="LOAN_COLLECTING_PROFILE" → P1 → loan_collecting_profile
  → loan_collecting_profile: profile sigue completo → sin mensajes → END
  → ∞ (bucle)
```

La causa raíz es que `current_node` no avanza cuando el nodo hace "avance silencioso", porque termina en `END` en vez de avanzar al nodo siguiente. La solución tiene dos capas complementarias que el requerimiento describe correctamente:

- **Capa intra-turno (Fase 4):** arista condicional que, cuando el perfil se completa, salta a `loan_collecting_simulation` en el **mismo** turno, actualizando `current_node` antes de terminar.
- **Capa inter-turno de seguridad (Fase 3):** `_SUCCESS_MAP` en `route_after_welcome` que, si de algún modo el estado quedó con `progress.loan.profile_completed = True` y `current_node` todavía apunta al nodo de perfil, salta al siguiente nodo en vez de repetirlo.

### 1.2 Viabilidad por Fase

| Fase | Viabilidad | Observaciones |
|---|---|---|
| 1 — Esquema de State | ✅ Viable | `state.py` admite extensión de `SessionData` sin romper sesiones existentes si se usan `total=False`. |
| 2 — Refactorización de flags | ✅ Viable | `profile_just_completed` está en pocos puntos; la migración es quirúrgica. |
| 3 — `_SUCCESS_MAP` + P0/P1 | ✅ Viable | Se integra sobre `_RESUME_MAP` existente como capa superior. |
| 4 — Aristas condicionales intra-turno | ✅ Viable sin restricciones | LangGraph actualiza el state entre nodos dentro del mismo `invoke()`. Las funciones de edge leen el state post-nodo. La preocupación de "silencio de grafo" al saltar a `loan_risk_engine` queda eliminada por el invariante: el motor siempre enruta a un nodo generador de respuesta. |

### 1.3 ~~Hallazgo Crítico: Lectura de `just_completed_step` en Salto Intra-turno~~ → Resuelto por Invariante de Motor

~~Cuando `loan_collecting_profile` salta a `loan_collecting_simulation` en el mismo turno, el nodo de simulación **no tiene un mensaje nuevo del usuario** para su propia Llamada A.~~

**Este apartado queda resuelto por la siguiente decisión de arquitectura:**

> **Invariante de Motor:** `loan_risk_engine` (y cualquier nodo lógico futuro) **nunca apunta a `END`**. Su salida está mapeada obligatoriamente a nodos generadores de respuesta: `loan_pre_approved`, `loan_rejected_policy`, o `loan_service_error`. Esto garantiza que todo ciclo de ejecución termina con al menos un `AIMessage` en `state["messages"]`, eliminando el riesgo de "silencio de grafo" en cualquier escenario de salto intra-turno.

La regla de diseño sobre **omitir la Llamada A en salto intra-turno** se mantiene intacta y sigue siendo necesaria (el mensaje del usuario ya fue procesado por el nodo anterior), pero ya no es una precaución de seguridad ante posibles silencios: es simplemente eficiencia de procesamiento.

### 1.4 Orden de Limpieza de `just_completed_step`

La flag debe sobrevivir exactamente hasta que el generador (Llamada B) la consuma. El punto de limpieza correcto es **dentro del mismo `return` dict del nodo que invoca la Llamada B**. Así:

```
loan_collecting_profile retorna: just_completed_step = "LOAN_PROFILE"
  ↓ (salto intra-turno)
loan_collecting_sim_node lee: just_completed_step == "LOAN_PROFILE" → omite Llamada A
loan_collecting_sim_node invoca Llamada B con contexto de celebración
loan_collecting_sim_node retorna: just_completed_step = None  ← limpieza en el mismo return
```

Si la simulación también se completa en el mismo turno (el usuario dio monto y plazo junto con el último dato del perfil), la misma lógica aplica en cascada: `loan_collecting_sim_node` setea `just_completed_step = "LOAN_SIMULATION"`, y el salto intra-turno continúa hacia `loan_risk_engine`. Gracias al **invariante de motor** (§1.3), `loan_risk_engine` siempre enruta a `loan_pre_approved` o `loan_rejected_policy`, garantizando que la cascada completa termina con un mensaje visible para el usuario sin excepciones.

---

## II. Fase 1 — Esquema de State: Namespaces de Progreso y Flag de Evento

**Archivos:** `app/graph/state.py`

> `state.py` es inmutable por regla del proyecto. Esta fase requiere autorización explícita del Dev 1 (Orchestrator). Los cambios propuestos son **aditivos** (campos nuevos con `total=False`), lo que garantiza compatibilidad con sesiones existentes.

### 2.1 Nuevos TypedDicts de Progreso

Agregar antes de `SessionData`:

```python
# ══════════════════════════════════════════════════════════════
# NAMESPACE B.1: ProgressData  [NUEVO en v2.2]
# Historial de pasos completados por producto.
# Escritura: nodos COLLECTING de cada producto (al completar un paso).
# Lectura: edges.py → _SUCCESS_MAP para ruteo inter-turno.
# Inmutable retroactivamente: una vez marcado True, nunca vuelve a False.
# ══════════════════════════════════════════════════════════════

class LoanProgress(TypedDict, total=False):
    """Registro histórico de completitud del flujo de crédito."""
    profile_completed:    bool   # True cuando loan_profile tiene todos los campos
    simulation_completed: bool   # True cuando loan_sim tiene monto y plazo


class AccountProgress(TypedDict, total=False):
    """Registro histórico de completitud del flujo de cuenta corriente."""
    profile_completed: bool


class DapProgress(TypedDict, total=False):
    """Registro histórico de completitud del flujo de depósito a plazo."""
    data_completed: bool


class ProgressData(TypedDict, total=False):
    """
    Contenedor raíz de progreso histórico por producto.
    Cada sub-cajón es independiente; un producto NUNCA toca el cajón de otro.
    """
    loan:    LoanProgress
    account: AccountProgress
    dap:     DapProgress
```

### 2.2 Actualizar `SessionData`

Agregar dos campos al final de `SessionData`:

```python
class SessionData(TypedDict, total=False):
    conversation_id: str
    application_id: str | None
    product_intent: str | None
    current_node: str
    previous_node: str | None
    is_transversal_active: bool
    # ── NUEVO en v2.2 ──────────────────────────────────────────
    progress: ProgressData          # Historial persistente de pasos completados
    just_completed_step: str | None # Flag volátil (1 turno): qué hito acaba de ocurrir
```

### 2.3 Constantes de `CompletedStep`

Crear archivo nuevo `app/graph/constants.py`:

```python
"""
app/graph/constants.py
─────────────────────────────────────────────────────────────
Constantes de negocio compartidas por nodos y edges.

REGLA: Cualquier string que viaje en session["just_completed_step"]
       DEBE estar definido aquí. Nunca usar strings literales sueltos.
"""


class CompletedStep:
    """
    Valores válidos para session["just_completed_step"].
    Flag volátil: vive exactamente un turno.
    Se setea al completar un paso; se limpia en el return del nodo generador.
    """
    LOAN_PROFILE    = "LOAN_PROFILE"
    LOAN_SIMULATION = "LOAN_SIMULATION"
    ACCOUNT_PROFILE = "ACCOUNT_PROFILE"
    DAP_DATA        = "DAP_DATA"


class ProductPrefix:
    """
    Prefijos de producto para inferir el producto desde current_node.
    Usados en route_after_welcome para detectar cambio de intención (P0).
    """
    LOAN    = "LOAN"
    ACCOUNT = "ACCOUNT"
    DAP     = "DAP"

    # Mapa: prefijo del current_node (UPPER) → código de producto
    NODE_TO_PRODUCT: dict[str, str] = {
        "LOAN":    LOAN,
        "ACCOUNT": ACCOUNT,
        "DAP":     DAP,
    }

    @classmethod
    def from_node(cls, current_node: str) -> str | None:
        """Infiere el producto desde el current_node. Ej: 'LOAN_COLLECTING_PROFILE' → 'LOAN'."""
        for prefix, product in cls.NODE_TO_PRODUCT.items():
            if current_node.startswith(prefix):
                return product
        return None
```

### 2.4 Informe de Impacto sobre Sesiones Existentes

Dado que todos los campos nuevos usan `total=False`:
- Sesiones antiguas (sin `progress` ni `just_completed_step`) cargarán correctamente: `session.get("progress", {})` retornará `{}` y `session.get("just_completed_step")` retornará `None`.
- No se requiere migración de datos en Supabase.
- El único riesgo es código que acceda a `session["progress"]` sin `.get()`. Por eso todos los accesos deben usar `session.get("progress", {})`.

---

### ✅ Tests Fase 1

#### TEST 1.A — Schema: compatibilidad con sesiones antiguas

```python
# tests/unit/test_state_v22.py
from app.graph.state import SessionData, FluxState
from app.graph.constants import CompletedStep, ProductPrefix


def test_session_data_accepts_progress():
    """SessionData acepta los nuevos campos sin error de TypedDict."""
    session: SessionData = {
        "current_node": "LOAN_COLLECTING_PROFILE",
        "progress": {"loan": {"profile_completed": True}},
        "just_completed_step": CompletedStep.LOAN_PROFILE,
    }
    assert session["progress"]["loan"]["profile_completed"] is True
    assert session["just_completed_step"] == "LOAN_PROFILE"


def test_old_session_missing_progress_handled_gracefully():
    """Sesión antigua sin 'progress' ni 'just_completed_step' no falla."""
    old_session: SessionData = {
        "conversation_id": "abc",
        "current_node": "LOAN_COLLECTING_PROFILE",
        "product_intent": "LOAN",
    }
    progress = old_session.get("progress", {})
    jcs = old_session.get("just_completed_step")
    assert progress == {}
    assert jcs is None


def test_completed_step_constants_are_strings():
    assert isinstance(CompletedStep.LOAN_PROFILE, str)
    assert isinstance(CompletedStep.LOAN_SIMULATION, str)


def test_product_prefix_from_node():
    assert ProductPrefix.from_node("LOAN_COLLECTING_PROFILE") == "LOAN"
    assert ProductPrefix.from_node("ACCOUNT_INIT") == "ACCOUNT"
    assert ProductPrefix.from_node("DAP_COLLECT_DATA") == "DAP"
    assert ProductPrefix.from_node("WELCOME_NODE") is None
    assert ProductPrefix.from_node("GENERAL_RESPONSE") is None
```

---

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

## IV. Fase 3 — `_SUCCESS_MAP` y Nueva Jerarquía de Prioridades en `edges.py`

**Archivo:** `app/graph/edges.py`

### 4.1 Definición del `_SUCCESS_MAP`

```python
# Mapa de éxito: producto → {CompletedStep → ID LangGraph destino}
# Propósito: dado un paso completado en el historial, indica el siguiente nodo lógico.
# Es la capa de seguridad inter-turno que evita el bucle infinito.
_SUCCESS_MAP: dict[str, dict[str, str]] = {
    "LOAN": {
        CompletedStep.LOAN_PROFILE:    "loan_collecting_simulation",
        CompletedStep.LOAN_SIMULATION: "loan_risk_engine",
    },
    "ACCOUNT": {
        CompletedStep.ACCOUNT_PROFILE: "account_evaluation_engine",
    },
    "DAP": {
        CompletedStep.DAP_DATA: "dap_investment_engine",
    },
}
```

### 4.2 Helpers de ruteo

```python
import logging

_routing_logger = logging.getLogger("flux.routing")


def _infer_product_from_node(current_node: str) -> str | None:
    """Infiere el producto desde el current_node para detectar cambio de intención."""
    from app.graph.constants import ProductPrefix
    return ProductPrefix.from_node(current_node)


def _get_completed_steps_for_product(progress: dict, product: str) -> list[str]:
    """
    Retorna lista de pasos completados para un producto, en orden cronológico.
    Usado por P1 para verificar si hay un salto de éxito pendiente.
    """
    product_progress = progress.get(product.lower(), {})
    completed = []
    if product == "LOAN":
        if product_progress.get("profile_completed"):
            completed.append(CompletedStep.LOAN_PROFILE)
        if product_progress.get("simulation_completed"):
            completed.append(CompletedStep.LOAN_SIMULATION)
    elif product == "ACCOUNT":
        if product_progress.get("profile_completed"):
            completed.append(CompletedStep.ACCOUNT_PROFILE)
    elif product == "DAP":
        if product_progress.get("data_completed"):
            completed.append(CompletedStep.DAP_DATA)
    return completed
```

### 4.3 Función `route_after_welcome` refactorizada

```python
def route_after_welcome(state: FluxState) -> str:
    """
    VERSIÓN 2.2 — Jerarquía de 4 prioridades.

    P0 — Cambio de producto: el usuario (o frontend) señaló un producto
         distinto al que está en proceso → ir al INIT del nuevo producto.
    P1 — Salto por éxito: el progreso histórico indica que el paso actual
         ya se completó → consultar _SUCCESS_MAP y saltar al siguiente.
    P2 — Reanudación estándar: current_node activo → ir ahí.
    P3 — Intención directa: product_intent declarado → ir al INIT.
    P4 — Sin señales: intent_router.
    """
    session      = state.get("session", {})
    current_node = session.get("current_node", "")
    product_intent = session.get("product_intent")
    progress     = session.get("progress", {})

    # ── P0: Cambio de producto ────────────────────────────────
    # Si hay un current_node de un producto activo Y product_intent apunta
    # a un producto DIFERENTE, el usuario está cambiando de flujo.
    if current_node in _RESUME_MAP and product_intent in _INTENT_MAP:
        node_product   = _infer_product_from_node(current_node)
        intent_product = product_intent  # LOAN | ACCOUNT | DAP
        if node_product and node_product != intent_product:
            _routing_logger.info(
                f"P0 — Cambio de producto: {node_product} → {intent_product}. "
                f"Redirigiendo a {_INTENT_MAP[intent_product]}."
            )
            return _INTENT_MAP[intent_product]

    # ── P1: Salto por éxito (seguridad inter-turno) ───────────
    # Si current_node indica que estamos en un flujo de producto,
    # verificar si el paso actual ya fue completado en el historial.
    # Esto evita el bucle cuando el intra-turno no completó el salto.
    if current_node in _RESUME_MAP:
        node_product = _infer_product_from_node(current_node)
        if node_product and node_product in _SUCCESS_MAP:
            completed_steps = _get_completed_steps_for_product(progress, node_product)
            product_success_map = _SUCCESS_MAP[node_product]
            for step in reversed(completed_steps):  # El más reciente primero
                if step in product_success_map:
                    next_node = product_success_map[step]
                    # Validación de existencia: el nodo debe estar en _RESUME_MAP o ser conocido
                    if next_node in _VALID_DESTINATION_NODES:
                        _routing_logger.info(
                            f"P1 — Salto por éxito: '{step}' completado. "
                            f"Redirigiendo a '{next_node}'."
                        )
                        return next_node
                    else:
                        _routing_logger.error(
                            f"P1 — Nodo destino '{next_node}' no existe en el grafo. "
                            f"Fallback a END."
                        )
                        return "end_fallback"  # Nodo de error genérico

    # ── P2: Reanudación estándar ──────────────────────────────
    if current_node in _RESUME_MAP:
        return _RESUME_MAP[current_node]

    # ── P3: Intención directa (clic de botón) ─────────────────
    if product_intent in _INTENT_MAP:
        return _INTENT_MAP[product_intent]

    # ── P4: Sin señales → clasificar ──────────────────────────
    return "intent_router"
```

### 4.4 Set de nodos destino válidos

```python
# Nodos válidos como destino del _SUCCESS_MAP.
# Debe actualizarse al registrar nuevos nodos en workflow.py.
_VALID_DESTINATION_NODES: frozenset[str] = frozenset({
    "loan_collecting_profile",
    "loan_collecting_simulation",
    "loan_risk_engine",
    "account_collecting_profile",
    "account_evaluation_engine",
    "dap_collect_data",
    "dap_investment_engine",
    "intent_router",
    "general_response",
})
```

### 4.5 Nota sobre `P1` vs Fase 4

Con la Fase 4 correctamente implementada (aristas condicionales intra-turno), el `P1` de `edges.py` debería **raramente activarse** en condiciones normales. Su rol es de **cortafuegos inter-turno**: si por alguna razón (error de red, timeout, estado corrupto) el salto intra-turno no se completó y el `current_node` quedó desincronizado con el `progress`, P1 lo corrige en el siguiente turno.

---

### ✅ Tests Fase 3

#### TEST 3.A — Prioridades en `route_after_welcome`

```python
# tests/unit/test_edges_v22.py
from app.graph.edges import route_after_welcome
from app.graph.constants import CompletedStep


def _state(current_node="", product_intent=None, progress=None):
    return {
        "session": {
            "current_node": current_node,
            "product_intent": product_intent,
            "progress": progress or {},
        }
    }


# P0: Cambio de producto
def test_p0_product_switch_loan_to_account():
    """Usuario estaba en crédito y ahora quiere cuenta corriente."""
    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="ACCOUNT"
    )
    assert route_after_welcome(state) == "account_init"


def test_p0_same_product_does_not_trigger():
    """Mismo producto: no es cambio, P0 no activa."""
    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="LOAN",
        progress={}
    )
    # Debe ir a P2 (reanudación) porque product matches
    assert route_after_welcome(state) == "loan_collecting_profile"


# P1: Salto por éxito (seguridad inter-turno)
def test_p1_success_jump_profile_completed():
    """Perfil completado: P1 salta a simulación aunque current_node sea profile."""
    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="LOAN",
        progress={"loan": {"profile_completed": True}},
    )
    assert route_after_welcome(state) == "loan_collecting_simulation"


def test_p1_success_jump_simulation_completed():
    state = _state(
        current_node="LOAN_COLLECTING_SIMULATION",
        product_intent="LOAN",
        progress={"loan": {"profile_completed": True, "simulation_completed": True}},
    )
    assert route_after_welcome(state) == "loan_risk_engine"


def test_p1_not_triggered_when_progress_empty():
    """Sin progreso registrado, P1 no activa; se va a P2."""
    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="LOAN",
        progress={}
    )
    assert route_after_welcome(state) == "loan_collecting_profile"


# P2: Reanudación estándar (sin progreso que dispare P1)
def test_p2_resume_without_progress():
    state = _state(current_node="LOAN_COLLECTING_SIMULATION")
    assert route_after_welcome(state) == "loan_collecting_simulation"


# P3 y P4: sin cambios respecto a tests anteriores
def test_p3_product_intent_no_current_node():
    state = _state(current_node="WELCOME_NODE", product_intent="DAP")
    assert route_after_welcome(state) == "dap_init"


def test_p4_no_signals_intent_router():
    state = _state()
    assert route_after_welcome(state) == "intent_router"
```

#### TEST 3.B — Fallback ante nodo destino inválido en `_SUCCESS_MAP`

```python
from unittest.mock import patch
from app.graph import edges as edges_module


def test_p1_fallback_if_destination_not_valid():
    """Si el nodo destino del _SUCCESS_MAP no está en _VALID_DESTINATION_NODES,
    el router no debe fallar; debe ir al fallback de error."""
    original_valid = edges_module._VALID_DESTINATION_NODES
    edges_module._VALID_DESTINATION_NODES = frozenset()  # Vaciar para simular nodo faltante

    state = _state(
        current_node="LOAN_COLLECTING_PROFILE",
        product_intent="LOAN",
        progress={"loan": {"profile_completed": True}},
    )
    result = route_after_welcome(state)
    assert result == "end_fallback"

    edges_module._VALID_DESTINATION_NODES = original_valid  # Restaurar
```

---

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

## VI. Actualización de `common.py`: Inicialización de `progress`

**Archivo:** `app/graph/nodes/common.py`

El `welcome_node` en modo Bienvenida (sesión nueva) debe inicializar `progress: {}` en `session` para evitar que los nodos de recolección tengan que manejar la ausencia del campo.

**Cambio en el bloque `else` de `welcome_node`:**

```python
else:
    # MODO BIENVENIDA: sesión nueva, sin intención, sin historial
    welcome_text = (...)
    # ...
    return {
        "messages": [AIMessage(content=welcome_text)],
        "session": {
            **session,
            "current_node": "WELCOME_NODE",
            "progress": session.get("progress", {}),          # ← Inicializar si no existe
            "just_completed_step": None,                       # ← Siempre limpio al inicio
        },
        "preparation_data": preparation_data,
    }
```

En modo silencioso, `session` no se modifica, por lo que `progress` y `just_completed_step` del turno anterior se preservan correctamente.

---

### ✅ Tests de `common.py`

```python
# tests/unit/test_common_v22.py
from unittest.mock import patch
from app.graph.nodes.common import welcome_node


@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_welcome_initializes_progress_on_new_session(mock_conv, mock_sem):
    state = {
        "user_data": {"full_name": "Test User", "birth_date": "1990-01-01", "rut": "", "email": ""},
        "session": {"product_intent": None, "current_node": "", "conversation_id": None, "application_id": None},
        "messages": [],
    }
    result = welcome_node(state)
    assert "progress" in result["session"]
    assert result["session"]["just_completed_step"] is None


@patch("app.graph.nodes.common.update_application_semaphores")
@patch("app.graph.nodes.common.update_conversation_node")
def test_welcome_silent_preserves_progress(mock_conv, mock_sem):
    """En modo silencioso, el progreso existente no debe borrarse."""
    from langchain_core.messages import HumanMessage
    state = {
        "user_data": {"full_name": "Test User", "birth_date": "1990-01-01", "rut": "", "email": ""},
        "session": {
            "product_intent": "LOAN",
            "current_node": "LOAN_COLLECTING_PROFILE",
            "progress": {"loan": {"profile_completed": True}},
            "just_completed_step": None,
        },
        "messages": [HumanMessage(content="hola")],
    }
    result = welcome_node(state)
    # En silencio, session NO se modifica
    assert "session" not in result
```

---

## VII. Orden de Implementación y Dependencias

| # | Paso | Archivos | Depende de |
|---|---|---|---|
| 1 | Crear `constants.py` | Nuevo | — |
| 2 | Actualizar `state.py` | `state.py` | Paso 1 |
| 3 | Actualizar `_build_sim_generation_context` en `credit.py` | `credit.py` | Pasos 1, 2 |
| 4 | Actualizar `loan_collecting_profile_node` | `credit.py` | Pasos 1, 2, 3 |
| 5 | Actualizar `loan_collecting_sim_node` | `credit.py` | Paso 4 |
| 6 | Actualizar `common.py` (init progress) | `common.py` | Paso 2 |
| 7 | Agregar `_SUCCESS_MAP` y helpers a `edges.py` | `edges.py` | Pasos 1, 2 |
| 8 | Refactorizar `route_after_welcome` en `edges.py` | `edges.py` | Paso 7 |
| 9 | Agregar funciones de edge intra-turno a `edges.py` | `edges.py` | Paso 1 |
| 10 | Actualizar `workflow.py` con edges condicionales | `workflow.py` | Pasos 8, 9 |
| 11 | Suite de tests unitarios | `tests/unit/` | Cada paso |
| 12 | Test de integración intra-turno | `tests/integration/` | Todos los anteriores |

---

## VIII. Checklist de Aceptación Final

```bash
# Todos los tests
pytest tests/unit/ tests/integration/ -v

# Escenario crítico en consola
python scripts/simulate_conversation.py --scenario happy_path_loan
```

- [ ] `loan_collecting_profile` escribe `just_completed_step = "LOAN_PROFILE"` y `progress.loan.profile_completed = True` al completarse.
- [ ] `loan_collecting_sim_node` omite la Llamada A cuando `just_completed_step == "LOAN_PROFILE"`.
- [ ] `loan_collecting_sim_node` retorna `just_completed_step = None` tras invocar Llamada B.
- [ ] `route_after_loan_collecting_profile` retorna `"loan_collecting_simulation"` cuando `just_completed_step == "LOAN_PROFILE"`.
- [ ] `route_after_loan_collecting_sim` retorna `"loan_risk_engine"` cuando `just_completed_step == "LOAN_SIMULATION"` (habilitado sin restricciones por el invariante de motor).
- [ ] **[INVARIANTE]** `loan_risk_engine` nunca tiene edge a `END`. Su arista condicional solo puede resolver a `loan_pre_approved` o `loan_rejected_policy`.
- [ ] **[INVARIANTE]** `loan_pre_approved` y `loan_rejected_policy` generan al menos un `AIMessage` antes de retornar. Todo ciclo de ejecución termina con un mensaje visible.
- [ ] El turno donde se completa el perfil genera exactamente **un mensaje** de Flux (celebración + pregunta de monto), no cero ni dos.
- [ ] El turno siguiente (usuario da el monto) no incluye instrucción de celebración de perfil en el contexto de Llamada B.
- [ ] `route_after_welcome` con `progress.loan.profile_completed = True` y `current_node = "LOAN_COLLECTING_PROFILE"` devuelve `"loan_collecting_simulation"` (P1 activo como red de seguridad).
- [ ] `route_after_welcome` con `product_intent = "ACCOUNT"` estando en flujo `LOAN_*` devuelve `"account_init"` (P0 activo).
- [ ] No hay referencias a `profile_just_completed` en ningún archivo.
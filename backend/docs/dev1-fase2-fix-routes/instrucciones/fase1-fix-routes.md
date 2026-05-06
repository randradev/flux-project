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
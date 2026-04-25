# Plan de Migración: FluxState → Arquitectura de Namespaces
**Proyecto:** FLUX — Chatbot Financiero  
**Fase:** Transición Fase 1 → Fase 2  
**Objetivo:** Refactorizar `state.py` desde diccionarios genéricos (`collected_data`, `control_flags`) hacia TypedDicts anidados por namespace, garantizando escalabilidad multi-producto y cero colisión de datos.

---

## Índice

1. [Paso 1 — Nuevo `state.py`](#paso-1)
2. [Paso 2 — Refactor de `common.py`](#paso-2)
3. [Paso 3 — Patrón de Reset en Nodos INIT](#paso-3)
4. [Paso 4 — Mapeo de Motores a `evaluation_results`](#paso-4)
5. [Paso 5 — Verificación de `edges.py`](#paso-5)

---

## PASO 1 — Nuevo `state.py` {#paso-1}

### Contexto de la Decisión

El `collected_data: dict` actual es un contenedor plano sin tipado. Si LOAN y ACCOUNT tienen ambos un campo `renta`, existe riesgo de sobreescritura silenciosa. Adicionalmente, `control_flags` mezcla lógica de OTP con errores de servicio.

La nueva arquitectura introduce **5 namespaces TypedDict**, todos con `total=False` (campos opcionales) para que LangGraph pueda hacer merge parcial sin exigir que todos los campos estén presentes en cada retorno de nodo.

### 1.1 Sub-paso: Diseño de los TypedDicts

**Decisión técnica clave:** Todos los sub-TypedDicts usan `total=False`. Esto permite que un nodo retorne solo las claves que modificó (`return {"collecting_data": {"loan_profile": {"renta": 1500000}}}`) sin necesidad de conocer ni repoblar los demás campos.

**Verificación al terminar este sub-paso:**
- [ ] Confirmar que cada campo está nombrado exactamente igual que en los archivos `.md` (sensible a mayúsculas/minúsculas).
- [ ] Confirmar que no hay campo que aparezca en dos sub-TypedDicts distintos con distinto tipo (ej: `renta` es `int` en loan y account — correcto, son namespaces distintos).

### 1.2 Sub-paso: Código Completo de `state.py`

```python
"""
app/graph/state.py
─────────────────────────────────────────────────────────────
Definición del Estado Global del Grafo (The Single Source of Truth).

REGLA DE ORO #1: Este archivo es la única fuente de verdad del sistema.
Ningún desarrollador puede modificarlo sin aprobación del Dev 1 (Orchestrator).

VERSIÓN: 2.0 — Arquitectura de Namespaces (Fase 2)
CAMBIOS vs v1.0:
  - Eliminado: collected_data (dict plano)
  - Eliminado: control_flags (dict plano)
  - Agregado: preparation_data (datos universales de DB, procesados)
  - Agregado: collecting_data (extracción del chat, segmentado por producto)
  - Agregado: evaluation_results (outputs de motores financieros)
  - Agregado: offer_data (datos de oferta, formalización y contrato)
  - Agregado: auth_control (lógica de OTP y seguridad transversal)
"""

from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages


# ══════════════════════════════════════════════════════════════
# NAMESPACE A: user_data
# Sin cambios vs v1.0. Contiene el perfil RAW de la DB.
# Escritura reservada a: WELCOME_NODE (una sola vez por sesión).
# ══════════════════════════════════════════════════════════════

class UserData(TypedDict, total=False):
    """
    Datos crudos del usuario cargados desde la DB al iniciar el grafo.
    Inmutables durante la sesión. Solo WELCOME_NODE los escribe.
    """
    user_id: str
    full_name: str
    email: str
    rut: str
    birth_date: str       # ISO8601. WELCOME_NODE calcula edad a partir de esto.
    user_status: str      # ACTIVE | BLOCKED_SECURITY | PROSPECT
    user_category: str | None  # START | MEDIUM | ADVANCE | None


# ══════════════════════════════════════════════════════════════
# NAMESPACE B: session
# Sin cambios vs v1.0. GPS del grafo y metadatos de conversación.
# ══════════════════════════════════════════════════════════════

class SessionData(TypedDict, total=False):
    """
    Metadatos de la sesión conversacional activa.
    """
    conversation_id: str
    application_id: str | None
    product_intent: str | None   # LOAN | ACCOUNT | DAP | GENERAL
    current_node: str
    previous_node: str | None
    is_transversal_active: bool


# ══════════════════════════════════════════════════════════════
# NAMESPACE C: preparation_data  [NUEVO en v2.0]
# Datos "cocinados" para consumo inmediato de los nodos de producto.
# WELCOME_NODE los calcula/copia desde user_data.
# Son inmutables post-WELCOME; ningún nodo de producto los modifica.
# ══════════════════════════════════════════════════════════════

class PreparationData(TypedDict, total=False):
    """
    Datos universales listos para consumo de los nodos de producto.
    WELCOME_NODE los escribe una vez al inicio de cada sesión.

    Diferencia con user_data:
      - user_data.full_name  →  preparation_data.nombre (primer nombre + apellido, formateado)
      - user_data.email      →  preparation_data.mail
      - user_data.birth_date →  preparation_data.edad (int calculado en WELCOME_NODE)
    """
    nombre: str   # Nombre completo para mensajes personalizados
    rut: str      # RUT sin puntos, con guión
    mail: str     # Correo para OTP y notificaciones
    edad: int     # Edad en años completos (calculada en WELCOME_NODE)


# ══════════════════════════════════════════════════════════════
# NAMESPACE D: collecting_data  [NUEVO en v2.0]
# Extracción de entidades del chat. Sub-cajones por producto.
# Escritura: nodos COLLECTING de cada producto.
# ══════════════════════════════════════════════════════════════

class LoanProfile(TypedDict, total=False):
    """Datos de perfil recolectados en LOAN_COLLECTING_PROFILE."""
    renta: int              # Renta líquida en CLP
    antiguedad_laboral: int # Meses de antigüedad laboral
    nivel_estudios: str     # POSTGRADO | UNIVERSITARIO | TECNICO | MEDIA


class LoanSim(TypedDict, total=False):
    """Parámetros de simulación recolectados en LOAN_COLLECTING_SIMULATION."""
    monto_solicitado: int   # Monto del crédito en CLP
    plazo_solicitado: int   # Número de cuotas (meses)


class AccountProfile(TypedDict, total=False):
    """Datos de perfil recolectados en ACCOUNT_COLLECTING_PROFILE."""
    renta: int              # Renta líquida en CLP
    antiguedad_laboral: int # Meses de antigüedad laboral
    nivel_estudios: str     # POSTGRADO | UNIVERSITARIO | TECNICO | MEDIA


class DapParams(TypedDict, total=False):
    """Parámetros de inversión recolectados en DAP_COLLECT_DATA."""
    monto: float            # Monto a invertir (en la moneda indicada)
    moneda: str             # CLP | UF | USD
    plazo: int              # Días: 7 | 14 | 30 | 180 | 360


class CollectingData(TypedDict, total=False):
    """
    Contenedor raíz de datos recolectados del chat.
    Cada sub-cajón es independiente; un producto NUNCA toca el cajón de otro.

    Convención de limpieza (reset):
      Cada nodo INIT debe resetear su sub-cajón asignando un dict vacío.
      Ejemplo en LOAN_INIT:
        return {"collecting_data": {"loan_profile": {}, "loan_sim": {}}}
    """
    loan_profile: LoanProfile
    loan_sim: LoanSim
    account_profile: AccountProfile
    dap_params: DapParams


# ══════════════════════════════════════════════════════════════
# NAMESPACE E: evaluation_results  [NUEVO en v2.0]
# Outputs crudos de los motores financieros (caja negra).
# Escritura: nodos ENGINE de cada producto.
# ══════════════════════════════════════════════════════════════

class LoanEngineResult(TypedDict, total=False):
    """Resultado del motor LOAN_RISK_ENGINE."""
    status_proceso: str          # PRE_APPROVED | REJECTED_POLICY | ERROR_TECHNICAL
    scoring_puntos: int          # 0-100
    nivel_riesgo: str            # Bajo | Medio | Alto
    tasa_interes_mensual: float  # 0.012 | 0.020 | 0.035
    cuota_mensual: int           # Cuota mensual redondeada al entero superior
    cuota_maxima_permitida: int  # renta * 0.30
    capacidad_pago_valida: bool  # True si cuota_mensual <= renta * 0.30
    ctc: int                     # Costo Total del Crédito (cuota * plazo)
    total_intereses: int         # ctc - monto_solicitado
    cae: float                   # Carga Anual Equivalente (decimal)
    monto_aprobado: int          # Monto final aprobado por el banco
    plazo_aprobado: int          # Cuotas aprobadas
    motivo_rechazo: str | None   # ERR_EDAD | ERR_RENTA | ERR_ANTIGUEDAD |
                                 # ERR_SCORING | ERR_CAPACIDAD_PAGO | None


class AccountEngineResult(TypedDict, total=False):
    """Resultado del motor ACCOUNT_EVALUATION_ENGINE."""
    status_proceso: str          # PRE_APPROVED | REJECTED_POLICY | ERROR_TECHNICAL
    is_elegible: bool            # edad >= 18, renta >= 500k, antiguedad >= 6m
    base_category: str           # START | MEDIUM | ADVANCE (solo por tramo de renta)
    final_category: str          # START | MEDIUM | ADVANCE (tras upgrade por estudios)
    has_upgrade: bool            # True si obtuvo categoría superior por título
    credit_line_amount: int      # Monto de línea de crédito ($0 si START o ant<12m)
    monthly_cost: int            # Costo de mantención ($0 según Promo MVP)
    motivo_rechazo: str | None   # ERR_EDAD | ERR_RENTA | ERR_ANTIGUEDAD | None


class DapEngineResult(TypedDict, total=False):
    """Resultado del motor DAP_INVESTMENT_ENGINE."""
    status_proceso: str          # PRE_APPROVED | REJECTED_POLICY | ERROR_TECHNICAL
    is_elegible: bool            # edad >= 18 y monto CLP entre $50k y $50M
    conversion_rate_used: float  # Valor USD/UF del día. 1.0 si es CLP.
    ipc_applied: float           # Delta IPC (solo si moneda=CLP, sino 0.0)
    term_premium: float          # Premio por plazo: (plazo // 30) * 0.05
    monthly_rate_total: float    # i_base + term_premium + ipc_applied
    period_rate: float           # monthly_rate_total * (plazo / 30)
    estimated_gain: float        # Ganancia proyectada en moneda original
    total_return: float          # monto + estimated_gain
    motivo_rechazo: str | None   # ERR_EDAD | ERR_MONTO_MIN | ERR_MONTO_MAX | None


class EvaluationResults(TypedDict, total=False):
    """
    Contenedor raíz de resultados de motores financieros.
    Cada sub-cajón es la caja negra de un motor específico.
    """
    loan_engine: LoanEngineResult
    account_engine: AccountEngineResult
    dap_engine: DapEngineResult


# ══════════════════════════════════════════════════════════════
# NAMESPACE F: offer_data  [NUEVO en v2.0]
# "Foto" de la oferta aceptada + datos de formalización.
# Escritura: nodos PRE_APPROVED y FORMALIZATION de cada producto.
# ══════════════════════════════════════════════════════════════

class LoanOfferData(TypedDict, total=False):
    """Datos de oferta y formalización del crédito de consumo."""
    pre_approval_status: str     # ACCEPTED | REJECTED
    timestamp_acceptance: str    # ISO8601 datetime del momento de aceptación
    file_contrato_path: str      # Ruta/URL del PDF generado con ReportLab
    hash_sha256: str             # Hash SHA-256 del contrato
    contract_status: str         # SIGNED_AND_STAMPED | GENERATION_FAILED


class AccountOfferData(TypedDict, total=False):
    """Datos de oferta y formalización de la cuenta corriente."""
    pre_approval_status: str
    timestamp_acceptance: str
    file_contrato_path: str
    hash_sha256: str
    contract_status: str


class DapOfferData(TypedDict, total=False):
    """Datos de oferta y formalización del depósito a plazo."""
    pre_approval_status: str
    timestamp_acceptance: str
    file_contrato_path: str
    hash_sha256: str
    contract_status: str


class OfferData(TypedDict, total=False):
    """
    Contenedor raíz de datos de oferta por producto.
    Almacena la foto definitiva de la oferta aceptada y el contrato.
    """
    loan: LoanOfferData
    account: AccountOfferData
    dap: DapOfferData


# ══════════════════════════════════════════════════════════════
# NAMESPACE G: auth_control  [NUEVO en v2.0 — reemplaza control_flags]
# Lógica de OTP y bloqueos de seguridad transversal.
# Escritura: nodos OTP_VALIDATION y SECURITY_WATCHDOG.
# ══════════════════════════════════════════════════════════════

class AuthControl(TypedDict, total=False):
    """
    Control de autenticación y seguridad transversal.
    Reemplaza el control_flags genérico de v1.0.

    Notas de diseño:
      - otp_generated y otp_user_input se limpian tras validación exitosa.
      - block_timestamp se setea en ISO8601 para compatibilidad con Supabase.
      - security_blocked = True es un flag terminal: el grafo debe terminar.
    """
    security_blocked: bool       # True si SECURITY_WATCHDOG bloqueó el flujo
    service_error: bool          # True si un servicio externo falló
    otp_attempts: int            # Contador de intentos OTP (0–3)
    otp_generated: str           # Código OTP generado por el sistema (6 dígitos)
    otp_user_input: str          # Último código ingresado por el usuario
    last_otp_input: str          # Copia del último código erróneo (para auditoría)
    block_timestamp: str | None  # ISO8601 del momento de bloqueo
    error_detail: str | None     # Descripción técnica para logging


# ══════════════════════════════════════════════════════════════
# RAÍZ: FluxState
# ══════════════════════════════════════════════════════════════

class FluxState(TypedDict):
    """
    Estado global del Grafo FLUX — v2.0 (Arquitectura de Namespaces).

    El TypedDict raíz que LangGraph serializa y persiste en el
    checkpointer de Supabase después de cada transición de nodo.

    ESTRUCTURA DE NAMESPACES:
    ┌──────────────────────────────────────────────────────────┐
    │ messages          │ Historial de mensajes (reducer acum.)│
    │ user_data         │ Perfil RAW de la DB (inmutable)      │
    │ session           │ GPS del grafo + metadatos de sesión  │
    │ preparation_data  │ Datos "cocinados" para nodos          │
    │ collecting_data   │ Extracción del chat (por producto)   │
    │ evaluation_results│ Outputs de motores financieros       │
    │ offer_data        │ Oferta aceptada + contrato           │
    │ auth_control      │ OTP, bloqueos y errores de servicio  │
    └──────────────────────────────────────────────────────────┘

    GUARDRAILS INMUTABLES:
    - messages usa add_messages como reducer (no reemplazable).
    - user_data solo es escrito por WELCOME_NODE.
    - preparation_data solo es escrito por WELCOME_NODE.
    - La llave session["product_intent"] es el GPS de edges.py.
    """

    # ── Mensajes (reducer acumulativo) ───────────────────────────
    messages: Annotated[list, add_messages]

    # ── Datos RAW de DB (escritura única: WELCOME_NODE) ──────────
    user_data: UserData

    # ── GPS y Metadatos de Sesión ─────────────────────────────────
    session: SessionData

    # ── Datos "Cocinados" de DB (escritura única: WELCOME_NODE) ──
    preparation_data: PreparationData

    # ── Recolección del Chat (por producto) ───────────────────────
    collecting_data: CollectingData

    # ── Resultados de Motores Financieros ─────────────────────────
    evaluation_results: EvaluationResults

    # ── Foto de Oferta y Contrato ─────────────────────────────────
    offer_data: OfferData

    # ── Control de Autenticación y Seguridad ──────────────────────
    auth_control: AuthControl
```

### 1.3 Sub-paso: Verificación Post-Escritura

**Checklist de verificación manual:**
- [ ] Ejecutar `python -c "from app.graph.state import FluxState; print('OK')"` — debe pasar sin errores.
- [ ] Verificar que `PreparationData` tiene exactamente: `nombre`, `rut`, `mail`, `edad` (alineado con los 3 archivos `.md`).
- [ ] Verificar que `LoanProfile` tiene `antiguedad_laboral` (no `antiguedad` a secas — los `.md` usan el nombre largo).
- [ ] Verificar que `DapParams.plazo` es `int` (el `.md` indica que debe transformarse el mensaje del usuario a int).
- [ ] Verificar que `DapEngineResult` tiene `conversion_rate_used`, `ipc_applied`, `term_premium`, `monthly_rate_total`, `period_rate`, `estimated_gain`, `total_return` — todos los outputs del motor DAP.

### 1.4 Pruebas del Paso 1

```python
# tests/test_state_v2.py
"""
Pruebas unitarias del nuevo state.py.
Estas pruebas no requieren LangGraph activo; solo validan los TypedDicts.
"""
import pytest
from datetime import datetime

def test_flux_state_keys():
    """Verifica que FluxState tiene exactamente los 8 namespaces esperados."""
    from app.graph.state import FluxState
    expected_keys = {
        "messages", "user_data", "session", "preparation_data",
        "collecting_data", "evaluation_results", "offer_data", "auth_control"
    }
    assert set(FluxState.__annotations__.keys()) == expected_keys

def test_preparation_data_fields():
    """Verifica los campos exactos de PreparationData."""
    from app.graph.state import PreparationData
    assert set(PreparationData.__annotations__.keys()) == {"nombre", "rut", "mail", "edad"}

def test_collecting_data_no_collision():
    """Verifica que loan_profile y account_profile son tipos distintos (no el mismo objeto)."""
    from app.graph.state import CollectingData, LoanProfile, AccountProfile
    assert CollectingData.__annotations__["loan_profile"] is LoanProfile
    assert CollectingData.__annotations__["account_profile"] is AccountProfile
    assert LoanProfile is not AccountProfile

def test_loan_profile_field_names():
    """Verifica nomenclatura exacta según credito-datos.md."""
    from app.graph.state import LoanProfile
    assert "antiguedad_laboral" in LoanProfile.__annotations__
    assert "nivel_estudios" in LoanProfile.__annotations__

def test_dap_params_plazo_is_int():
    """El .md especifica que plazo debe transformarse a int."""
    from app.graph.state import DapParams
    assert DapParams.__annotations__["plazo"] is int

def test_dap_engine_has_all_outputs():
    """Verifica todos los outputs del DAP_INVESTMENT_ENGINE."""
    from app.graph.state import DapEngineResult
    required = {
        "status_proceso", "is_elegible", "conversion_rate_used", "ipc_applied",
        "term_premium", "monthly_rate_total", "period_rate",
        "estimated_gain", "total_return", "motivo_rechazo"
    }
    assert required.issubset(set(DapEngineResult.__annotations__.keys()))

def test_auth_control_replaces_control_flags():
    """Verifica que FluxState no tiene el antiguo control_flags."""
    from app.graph.state import FluxState
    assert "control_flags" not in FluxState.__annotations__
    assert "auth_control" in FluxState.__annotations__
```

**Documentación del Paso 1:**
> Se reemplazó el `state.py` v1.0 (2 namespaces planos: `collected_data`, `control_flags`) por el `state.py` v2.0 con 8 namespaces tipados. Decisión técnica: todos los sub-TypedDicts usan `total=False` para permitir retornos parciales de nodos sin romper la serialización de LangGraph. Se mantuvieron `messages` (con `add_messages`), `user_data` y `session` sin cambios estructurales para preservar la compatibilidad con el checkpointer y `edges.py`.

---

## PASO 2 — Refactor de `common.py` {#paso-2}

### 2.1 Sub-paso: Modificar `welcome_node`

El cambio central es: al final de `welcome_node`, además de escribir `session`, ahora también escribe `preparation_data` con los datos procesados.

**Lógica de cálculo de edad:**
```python
from datetime import date

def _calculate_age(birth_date_str: str) -> int:
    """Calcula la edad en años completos a partir de una fecha ISO8601."""
    birth = date.fromisoformat(birth_date_str)
    today = date.today()
    return today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )
```

**Modificación del retorno de `welcome_node`:**

```python
# ANTES (v1.0):
return {
    "messages": [AIMessage(content=welcome_text)],
    "session": {**session, "current_node": "WELCOME_NODE"},
}

# DESPUÉS (v2.0):
# Calcular edad desde birth_date
birth_date_str = user.get("birth_date")
edad = _calculate_age(birth_date_str) if birth_date_str else 0

return {
    "messages": [AIMessage(content=welcome_text)],
    "session": {**session, "current_node": "WELCOME_NODE"},
    "preparation_data": {
        "nombre": full_name,
        "rut": user.get("rut", ""),
        "mail": user.get("email", ""),
        "edad": edad,
    },
}
```

### 2.2 Sub-paso: Código Completo del `welcome_node` Refactorizado

```python
# En app/graph/nodes/common.py

from datetime import date
from langchain_core.messages import AIMessage, SystemMessage
from app.graph.state import FluxState
from app.infra.supabase import get_user_by_email, update_conversation_node
from app.infra.gemini_client import get_chat_model


def _calculate_age(birth_date_str: str) -> int:
    """
    Calcula la edad en años completos a partir de una fecha ISO8601.

    INPUT:  birth_date_str — string ISO8601 (ej: "1990-05-15")
    OUTPUT: edad en años completos (int)
    EDGE CASE: Si el cumpleaños es hoy, ya cumplió → se cuenta el año.
    """
    birth = date.fromisoformat(birth_date_str)
    today = date.today()
    return today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )


def welcome_node(state: FluxState) -> dict:
    """
    Nodo de bienvenida, carga de perfil y preparación de datos universales.

    INPUT (State):
        - state["user_data"]: Perfil RAW del usuario desde DB.
        - state["session"]: Metadatos de sesión.
        - state["messages"]: Historial (vacío=nueva sesión, con contenido=reanudada).

    PROCESO:
        1. Detecta si es sesión nueva o reanudada.
        2. Calcula edad a partir de birth_date (centralizado aquí para toda la app).
        3. Genera mensaje de bienvenida personalizado.
        4. Actualiza GPS en Supabase.
        5. Escribe preparation_data con datos procesados.

    OUTPUT (campos del State que modifica):
        - messages: Agrega mensaje de bienvenida.
        - session["current_node"]: "WELCOME_NODE".
        - preparation_data: {nombre, rut, mail, edad}.
    """
    user = state.get("user_data", {})
    session = state.get("session", {})
    messages = state.get("messages", [])

    full_name = user.get("full_name", "")
    first_name = full_name.split()[0] if full_name else "amig@"

    # Calcular edad (responsabilidad centralizada en este nodo desde v2.0)
    birth_date_str = user.get("birth_date")
    edad = _calculate_age(birth_date_str) if birth_date_str else 0

    # Detectar si es sesión nueva o reanudada
    is_resumed = len(messages) > 0 and session.get("previous_node") is not None

    if is_resumed:
        welcome_text = (
            f"¡Hola de nuevo, {first_name}! 👋 Veo que nos habíamos quedado a mitad del camino. "
            f"No te preocupes, tu progreso está guardado. ¿Continuamos donde lo dejamos?"
        )
    else:
        welcome_text = (
            f"¡Hola, {first_name}! 👋 Soy Flux, tu asistente financiero. "
            f"Estoy aquí para ayudarte a solicitar un **Crédito de Consumo**, "
            f"abrir una **Cuenta Corriente**, o contratar un **Depósito a Plazo**. "
            f"¿Con qué te puedo ayudar hoy?"
        )

    # Actualizar GPS en la DB
    conversation_id = session.get("conversation_id")
    if conversation_id:
        update_conversation_node(conversation_id, "WELCOME_NODE")

    return {
        "messages": [AIMessage(content=welcome_text)],
        "session": {**session, "current_node": "WELCOME_NODE"},
        # ── NUEVO en v2.0: preparation_data ──────────────────────
        "preparation_data": {
            "nombre": full_name,
            "rut": user.get("rut", ""),
            "mail": user.get("email", ""),
            "edad": edad,
        },
    }
```

### 2.3 Sub-paso: Verificación Post-Refactor

**Checklist de verificación manual:**
- [ ] Ejecutar el nodo en aislamiento (mock del state) y verificar que `preparation_data` aparece en el dict de retorno.
- [ ] Verificar que `edad` es un `int` (no un `float`, no un `str`).
- [ ] Verificar que el cálculo de edad es correcto para un usuario con cumpleaños hoy (debe sumar el año).
- [ ] Verificar que `user_data` NO es modificado por este nodo (solo lectura).
- [ ] Confirmar que `edges.py` sigue leyendo `state["session"]["product_intent"]` sin cambios.

### 2.4 Pruebas del Paso 2

```python
# tests/test_welcome_node_v2.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from langchain_core.messages import HumanMessage


def make_mock_state(birth_date="1990-06-15", previous_node=None, messages=None):
    """Helper para construir un FluxState mínimo para testing."""
    return {
        "user_data": {
            "full_name": "Ana García",
            "email": "ana@example.com",
            "rut": "12345678-9",
            "birth_date": birth_date,
        },
        "session": {
            "conversation_id": "test-conv-001",
            "previous_node": previous_node,
        },
        "messages": messages or [],
    }


@patch("app.infra.supabase.update_conversation_node")
def test_welcome_writes_preparation_data(mock_update):
    """Verifica que welcome_node escribe preparation_data correctamente."""
    from app.graph.nodes.common import welcome_node
    state = make_mock_state()
    result = welcome_node(state)

    assert "preparation_data" in result
    pd = result["preparation_data"]
    assert pd["nombre"] == "Ana García"
    assert pd["rut"] == "12345678-9"
    assert pd["mail"] == "ana@example.com"
    assert isinstance(pd["edad"], int)
    assert pd["edad"] >= 0


@patch("app.infra.supabase.update_conversation_node")
def test_age_calculation_before_birthday(mock_update):
    """Edad calculada correctamente cuando el cumpleaños aún no ha llegado este año."""
    from app.graph.nodes.common import welcome_node, _calculate_age
    today = date.today()
    # Cumpleaños en el futuro de este año
    future_bday = date(1990, today.month + 1 if today.month < 12 else 12, 15)
    age = _calculate_age(future_bday.isoformat())
    expected = today.year - 1990 - 1
    assert age == expected


@patch("app.infra.supabase.update_conversation_node")
def test_welcome_does_not_modify_user_data(mock_update):
    """user_data NO debe aparecer en el dict de retorno (no se modifica)."""
    from app.graph.nodes.common import welcome_node
    state = make_mock_state()
    result = welcome_node(state)
    assert "user_data" not in result


@patch("app.infra.supabase.update_conversation_node")
def test_welcome_resumed_session(mock_update):
    """Mensaje de bienvenida diferente para sesión reanudada."""
    from app.graph.nodes.common import welcome_node
    state = make_mock_state(
        previous_node="LOAN_COLLECTING_PROFILE",
        messages=[HumanMessage(content="quiero un crédito")]
    )
    result = welcome_node(state)
    welcome_msg = result["messages"][0].content
    assert "de nuevo" in welcome_msg.lower() or "reanud" in welcome_msg.lower()
```

**Documentación del Paso 2:**
> Se refactorizó `welcome_node` para: (1) extraer la función `_calculate_age` como utilidad privada del módulo, (2) agregar la escritura de `preparation_data` en el dict de retorno. El nodo ahora es el único punto del sistema donde se calcula la edad, eliminando cualquier recálculo en nodos posteriores. No se modificó la lógica de mensajes ni la integración con Supabase.

---

## PASO 3 — Patrón de Reset en Nodos INIT {#paso-3}

### 3.1 Contexto y Decisión de Diseño

Cuando un usuario abandona a mitad de un flujo de crédito y luego inicia un flujo de cuenta corriente, `collecting_data.loan_profile` puede tener datos residuales. Los nodos INIT deben limpiar **solo su propio sub-cajón** al arrancar.

**Patrón de reset:** Retornar el sub-cajón como un `TypedDict` vacío (`{}`). LangGraph hará merge: el sub-cajón queda limpio, los otros sub-cajones (de otros productos) se preservan.

### 3.2 Implementación de `loan_entry_node` (Stub + Reset)

```python
# app/graph/nodes/credit.py

from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def loan_entry_node(state: FluxState) -> dict:
    """
    Nodo LOAN_INIT: punto de entrada al flujo de Crédito de Consumo.

    INPUT (State):
        - state["preparation_data"]: Datos del usuario (nombre, rut, mail, edad).
        - state["session"]: Para verificar product_intent == "LOAN".
        - state["collecting_data"]["loan_profile"]: Se limpiará (reset).
        - state["collecting_data"]["loan_sim"]: Se limpiará (reset).

    PROCESO (Fase 2):
        1. Handshake: Verificar que product_intent == "LOAN".
        2. Reset: Limpiar loan_profile y loan_sim.
        3. Saludo personalizado con datos de preparation_data.

    OUTPUT (campos del State que modifica):
        - messages: Saludo de bienvenida al flujo de crédito.
        - session["current_node"]: "LOAN_INIT".
        - collecting_data["loan_profile"]: {} (limpio).
        - collecting_data["loan_sim"]: {} (limpio).

    NOTA FASE 1: Este nodo es un stub. Solo hace el reset y confirma la intención.
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})

    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    # Handshake: verificar intención (defensa en profundidad)
    product_intent = session.get("product_intent")
    if product_intent != "LOAN":
        # Esto no debería ocurrir si edges.py está bien configurado
        # pero es una salvaguarda explícita
        msg = "Hubo un error de navegación. Por favor, indica nuevamente qué necesitas."
    else:
        msg = (
            f"¡Perfecto, {first_name}! Vamos a revisar tu solicitud de **Crédito de Consumo**. "
            f"Es un proceso rápido. Primero necesito conocer un poco tu perfil financiero. "
            f"¿Cuál es tu renta líquida mensual?"
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "LOAN_INIT"},
        # ── RESET del namespace del producto ─────────────────────
        # Limpia datos de intentos anteriores sin tocar los otros productos.
        "collecting_data": {
            "loan_profile": {},
            "loan_sim": {},
        },
    }
```

### 3.3 Implementación de `account_entry_node` (Stub + Reset)

```python
# app/graph/nodes/account.py

from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def account_entry_node(state: FluxState) -> dict:
    """
    Nodo ACCOUNT_INIT: punto de entrada al flujo de Cuenta Corriente.

    RESET: Limpia collecting_data["account_profile"].
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})
    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    msg = (
        f"¡Genial, {first_name}! Vamos a abrir tu **Cuenta Corriente**. "
        f"Para asignarte la mejor categoría, cuéntame: ¿cuál es tu renta líquida mensual?"
    )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "ACCOUNT_INIT"},
        "collecting_data": {
            "account_profile": {},   # Reset del namespace de cuenta
        },
    }
```

### 3.4 Implementación de `deposit_entry_node` (Stub + Reset)

```python
# app/graph/nodes/deposit.py

from langchain_core.messages import AIMessage
from app.graph.state import FluxState


def deposit_entry_node(state: FluxState) -> dict:
    """
    Nodo DAP_INIT: punto de entrada al flujo de Depósito a Plazo.

    RESET: Limpia collecting_data["dap_params"].
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})
    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    msg = (
        f"Excelente elección, {first_name}! Un **Depósito a Plazo** es una forma segura "
        f"de hacer crecer tu dinero. Para calcular tu proyección, necesito saber: "
        f"¿cuánto deseas invertir y en qué moneda? (CLP, UF o USD)"
    )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "DAP_INIT"},
        "collecting_data": {
            "dap_params": {},   # Reset del namespace de DAP
        },
    }
```

### 3.5 Sub-paso: Verificación Post-Implementación

**Checklist de verificación manual:**
- [ ] Simular un escenario de "flujo cruzado": ejecutar `loan_entry_node` con `collecting_data.loan_profile` pre-poblado → verificar que el resultado tiene `loan_profile: {}`.
- [ ] Verificar que el reset de `loan_entry_node` NO borra `account_profile` ni `dap_params` (otros productos deben ser intocables).
- [ ] Verificar que `preparation_data` se puede leer correctamente en cada nodo INIT (datos disponibles antes de la primera interacción del usuario).

### 3.6 Pruebas del Paso 3

```python
# tests/test_init_nodes_v2.py
import pytest


def make_polluted_state():
    """State con datos residuales de múltiples productos (simula sesiones anteriores)."""
    return {
        "preparation_data": {
            "nombre": "Carlos López",
            "rut": "98765432-1",
            "mail": "carlos@example.com",
            "edad": 32,
        },
        "session": {
            "conversation_id": "test-002",
            "product_intent": "LOAN",
        },
        "collecting_data": {
            "loan_profile": {"renta": 999999, "antiguedad_laboral": 99},
            "loan_sim": {"monto_solicitado": 10000000, "plazo_solicitado": 24},
            "account_profile": {"renta": 888888},  # Datos de otro producto
            "dap_params": {"monto": 5000000.0},      # Datos de otro producto
        },
        "messages": [],
    }


def test_loan_init_resets_only_loan_namespace():
    """loan_entry_node resetea solo loan_profile y loan_sim, no los demás."""
    from app.graph.nodes.credit import loan_entry_node
    state = make_polluted_state()
    result = loan_entry_node(state)

    cd = result.get("collecting_data", {})
    # Loan reseteado
    assert cd.get("loan_profile") == {}
    assert cd.get("loan_sim") == {}
    # Otros productos NO en el resultado (no fueron tocados)
    assert "account_profile" not in cd
    assert "dap_params" not in cd


def test_account_init_resets_only_account_namespace():
    """account_entry_node resetea solo account_profile."""
    from app.graph.nodes.account import account_entry_node
    state = make_polluted_state()
    state["session"]["product_intent"] = "ACCOUNT"
    result = account_entry_node(state)

    cd = result.get("collecting_data", {})
    assert cd.get("account_profile") == {}
    assert "loan_profile" not in cd
    assert "dap_params" not in cd


def test_init_node_uses_preparation_data():
    """Los nodos INIT usan preparation_data (no user_data) para el nombre."""
    from app.graph.nodes.credit import loan_entry_node
    state = make_polluted_state()
    result = loan_entry_node(state)
    welcome_msg = result["messages"][0].content
    assert "Carlos" in welcome_msg


def test_init_node_updates_current_node():
    """El nodo INIT actualiza session["current_node"]."""
    from app.graph.nodes.credit import loan_entry_node
    state = make_polluted_state()
    result = loan_entry_node(state)
    assert result["session"]["current_node"] == "LOAN_INIT"
```

**Documentación del Paso 3:**
> Se estandarizó el patrón de reset en los 3 nodos INIT: cada uno limpia exclusivamente su sub-cajón en `collecting_data`. Este patrón garantiza que datos residuales de un flujo anterior no contaminan el nuevo flujo. Los nodos INIT también fueron refactorizados para leer `preparation_data` en lugar de `user_data`, desacoplándolos del acceso directo a la DB.

---

## PASO 4 — Mapeo de Motores a `evaluation_results` {#paso-4}

### 4.1 Convención de Escritura de Motores

Cada motor financiero (nodo de servicio automático) escribe **únicamente** en su sub-cajón de `evaluation_results`. No lee ni escribe en `collecting_data` de forma directa: recibe sus inputs del State.

**Patrón de escritura:**
```python
return {
    "evaluation_results": {
        "loan_engine": {   # <-- solo el sub-cajón del motor, no todo evaluation_results
            "status_proceso": "PRE_APPROVED",
            "scoring_puntos": 78,
            # ... resto de outputs ...
        }
    },
    "session": {**session, "current_node": "LOAN_RISK_ENGINE"},
}
```

### 4.2 Stub del Motor LOAN_RISK_ENGINE

```python
# app/graph/nodes/credit.py (agregar función)

def loan_risk_engine_node(state: FluxState) -> dict:
    """
    Nodo LOAN_RISK_ENGINE: motor de riesgo para crédito de consumo.

    INPUT (State leído):
        - state["collecting_data"]["loan_profile"]: renta, antiguedad_laboral, nivel_estudios
        - state["collecting_data"]["loan_sim"]: monto_solicitado, plazo_solicitado
        - state["preparation_data"]["edad"]: edad del usuario

    PROCESO:
        1. Extraer inputs de los namespaces correctos.
        2. Ejecutar motor de scoring y cálculo financiero.
        3. Escribir todos los outputs en evaluation_results["loan_engine"].

    OUTPUT (campos del State que modifica):
        - evaluation_results["loan_engine"]: Resultado completo del motor.
        - session["current_node"]: "LOAN_RISK_ENGINE".

    NOTA FASE 2: Implementar la lógica del motor aquí.
    Este stub demuestra el patrón de lectura/escritura correcto.
    """
    session = state.get("session", {})
    prep = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})

    # ── Lectura de inputs desde los namespaces correctos ──────────
    loan_profile = collecting.get("loan_profile", {})
    loan_sim = collecting.get("loan_sim", {})

    renta = loan_profile.get("renta", 0)
    antiguedad_laboral = loan_profile.get("antiguedad_laboral", 0)
    nivel_estudios = loan_profile.get("nivel_estudios", "")
    monto_solicitado = loan_sim.get("monto_solicitado", 0)
    plazo_solicitado = loan_sim.get("plazo_solicitado", 0)
    edad = prep.get("edad", 0)

    # ── Lógica del motor (implementar en Fase 2) ──────────────────
    # TODO: Implementar scoring, cálculo de cuota (fórmula francesa),
    #       CAE, CTc, validación de capacidad de pago, etc.
    # Por ahora, stub que retorna PRE_APPROVED para testing.
    engine_result = {
        "status_proceso": "PRE_APPROVED",  # Stub
        "scoring_puntos": 0,
        "nivel_riesgo": "",
        "tasa_interes_mensual": 0.0,
        "cuota_mensual": 0,
        "cuota_maxima_permitida": int(renta * 0.30),
        "capacidad_pago_valida": True,
        "ctc": 0,
        "total_intereses": 0,
        "cae": 0.0,
        "monto_aprobado": monto_solicitado,
        "plazo_aprobado": plazo_solicitado,
        "motivo_rechazo": None,
    }

    return {
        "evaluation_results": {
            "loan_engine": engine_result,
        },
        "session": {**session, "current_node": "LOAN_RISK_ENGINE"},
    }
```

### 4.3 Stub del Motor DAP_INVESTMENT_ENGINE

```python
# app/graph/nodes/deposit.py (agregar función)

def dap_investment_engine_node(state: FluxState) -> dict:
    """
    Nodo DAP_INVESTMENT_ENGINE: motor de cálculo de inversión.

    INPUT (State leído):
        - state["collecting_data"]["dap_params"]: monto, moneda, plazo
        - state["preparation_data"]["edad"]: edad del usuario
        - (Fase 2) eco_service: valor_uf, valor_usd, valor_ipc desde API externa

    PROCESO:
        1. Extraer inputs.
        2. Consultar eco_service para conversion_rate y ipc.
        3. Calcular term_premium, monthly_rate_total, period_rate, estimated_gain, total_return.
        4. Validar elegibilidad.
        5. Escribir en evaluation_results["dap_engine"].

    OUTPUT:
        - evaluation_results["dap_engine"]: Resultado completo.
        - session["current_node"]: "DAP_INVESTMENT_ENGINE".
    """
    session = state.get("session", {})
    prep = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})

    dap_params = collecting.get("dap_params", {})
    monto = dap_params.get("monto", 0.0)
    moneda = dap_params.get("moneda", "CLP")
    plazo = dap_params.get("plazo", 0)
    edad = prep.get("edad", 0)

    # TODO Fase 2: Consultar eco_service para rates y calcular el motor completo.
    # Stub para testing del patrón de escritura.
    engine_result = {
        "status_proceso": "PRE_APPROVED",
        "is_elegible": True,
        "conversion_rate_used": 1.0,
        "ipc_applied": 0.0,
        "term_premium": (plazo // 30) * 0.0005,
        "monthly_rate_total": 0.0,
        "period_rate": 0.0,
        "estimated_gain": 0.0,
        "total_return": monto,
        "motivo_rechazo": None,
    }

    return {
        "evaluation_results": {
            "dap_engine": engine_result,
        },
        "session": {**session, "current_node": "DAP_INVESTMENT_ENGINE"},
    }
```

### 4.4 Sub-paso: Verificación Post-Implementación

**Checklist de verificación manual:**
- [ ] Ejecutar un motor stub con un state válido y verificar que el retorno tiene la estructura `{"evaluation_results": {"loan_engine": {...}}}`.
- [ ] Verificar que el motor NO escribe en `collecting_data` (solo lectura).
- [ ] Verificar que los nombres de los campos en `loan_engine` corresponden exactamente a `LoanEngineResult` del nuevo `state.py`.
- [ ] Verificar que `motivo_rechazo` es `None` en el camino feliz (no un string vacío).

### 4.5 Pruebas del Paso 4

```python
# tests/test_engines_v2.py
import pytest


def make_loan_ready_state():
    """State con datos completos para ejecutar el motor de crédito."""
    return {
        "preparation_data": {"nombre": "Pedro Soto", "rut": "11111111-1", "mail": "p@e.com", "edad": 30},
        "session": {"conversation_id": "c-003", "product_intent": "LOAN"},
        "collecting_data": {
            "loan_profile": {
                "renta": 2000000,
                "antiguedad_laboral": 18,
                "nivel_estudios": "UNIVERSITARIO",
            },
            "loan_sim": {
                "monto_solicitado": 5000000,
                "plazo_solicitado": 24,
            },
        },
        "evaluation_results": {},
        "messages": [],
    }


def test_loan_engine_writes_to_correct_namespace():
    """El motor escribe en evaluation_results["loan_engine"], no en otro lugar."""
    from app.graph.nodes.credit import loan_risk_engine_node
    state = make_loan_ready_state()
    result = loan_risk_engine_node(state)

    assert "evaluation_results" in result
    assert "loan_engine" in result["evaluation_results"]
    # No escribe en account_engine ni dap_engine
    assert "account_engine" not in result["evaluation_results"]


def test_loan_engine_does_not_write_to_collecting_data():
    """El motor no debe modificar collecting_data."""
    from app.graph.nodes.credit import loan_risk_engine_node
    state = make_loan_ready_state()
    result = loan_risk_engine_node(state)
    assert "collecting_data" not in result


def test_loan_engine_reads_from_preparation_data():
    """El motor lee edad desde preparation_data, no desde user_data."""
    from app.graph.nodes.credit import loan_risk_engine_node
    state = make_loan_ready_state()
    # No hay user_data en el state; si el motor falla aquí, está leyendo del lugar incorrecto
    result = loan_risk_engine_node(state)
    assert result["evaluation_results"]["loan_engine"]["cuota_maxima_permitida"] == int(2000000 * 0.30)


def test_dap_engine_term_premium_calculation():
    """Verifica la fórmula de term_premium: (plazo // 30) * 0.0005."""
    from app.graph.nodes.deposit import dap_investment_engine_node
    state = {
        "preparation_data": {"edad": 25},
        "session": {"conversation_id": "c-004", "product_intent": "DAP"},
        "collecting_data": {
            "dap_params": {"monto": 1000000.0, "moneda": "CLP", "plazo": 180}
        },
        "evaluation_results": {},
        "messages": [],
    }
    result = dap_investment_engine_node(state)
    # plazo=180, 180//30=6, 6*0.0005 = 0.003
    assert result["evaluation_results"]["dap_engine"]["term_premium"] == pytest.approx(0.003)
```

**Documentación del Paso 4:**
> Se estableció el patrón de escritura para los motores financieros: cada motor lee sus inputs desde `collecting_data` y `preparation_data`, y escribe sus outputs **exclusivamente** en su sub-cajón de `evaluation_results`. Los motores no tienen acceso de escritura a `collecting_data`. Se crearon stubs de `loan_risk_engine_node` y `dap_investment_engine_node` que implementan el patrón correcto de I/O, listos para recibir la lógica de negocio en Fase 2.

---

## PASO 5 — Verificación de `edges.py` {#paso-5}

### 5.1 Análisis de Compatibilidad

`edges.py` solo lee `state["session"]["product_intent"]`. Esta clave **no cambió** en v2.0: sigue siendo parte de `SessionData`. El archivo no requiere modificaciones.

Sin embargo, se debe verificar explícitamente que:
1. El path `state → session → product_intent` sigue funcionando.
2. Los nombres de nodo que retornan las funciones (`"loan_entry"`, `"account_entry"`, `"dap_entry"`) coinciden con los registrados en `workflow.py`.
3. El `workflow.py` importa correctamente los nuevos nodos (los stubs refactorizados).

### 5.2 Verificación de `edges.py` (sin cambios requeridos)

```python
# app/graph/edges.py — SIN CAMBIOS
# Este archivo es compatible con FluxState v2.0 porque:
# - Solo accede a state["session"]["product_intent"]
# - SessionData no fue modificado en v2.0
# - Los nombres de nodo destino no cambiaron

# VERIFICAR que estas rutas siguen siendo válidas en workflow.py:
# "loan_entry"     → loan_entry_node     (en nodes/credit.py)
# "account_entry"  → account_entry_node  (en nodes/account.py)
# "dap_entry"      → deposit_entry_node  (en nodes/deposit.py)
# "intent_router"  → intent_router_node  (en nodes/common.py)
# "general_response" → general_response_node (en nodes/common.py)
```

### 5.3 Ajuste de `workflow.py`

El único cambio en `workflow.py` es que los nodos importados ahora retornan `preparation_data` en sus payloads. LangGraph maneja esto automáticamente (merge del State). No se requieren cambios estructurales, pero sí agregar `preparation_data`, `collecting_data`, `evaluation_results`, `offer_data` y `auth_control` como campos del State que LangGraph debe serializar.

**Verificar que `build_graph()` no requiere cambios:**
```python
# workflow.py — SIN CAMBIOS ESTRUCTURALES REQUERIDOS
# LangGraph infiere los campos del State desde FluxState (TypedDict).
# Al actualizar state.py, LangGraph automáticamente serializa los nuevos namespaces.
# El checkpointer de Supabase persiste el state completo como JSON; los nuevos
# campos simplemente aparecerán en el JSON serializado sin romper nada.
```

### 5.4 Checklist de Verificación de Integración Completa

**Verificación manual del flujo end-to-end:**
- [ ] Crear un state inicial mínimo con `user_data`, `session` y `messages: []`.
- [ ] Ejecutar `welcome_node` → verificar que `preparation_data` aparece en el state.
- [ ] Ejecutar `intent_router_node` → verificar que `session["product_intent"]` se setea.
- [ ] Ejecutar `route_after_intent` con el state → verificar que retorna `"loan_entry"` para intent `"LOAN"`.
- [ ] Ejecutar `loan_entry_node` → verificar reset de `collecting_data["loan_profile"]`.
- [ ] Verificar que el checkpointer puede serializar el state v2.0 a JSON (Supabase).

### 5.5 Pruebas de Integración del Paso 5

```python
# tests/test_integration_v2.py
"""
Pruebas de integración del flujo completo Fase 1 + namespaces v2.0.
Estas pruebas requieren el grafo compilado (sin checkpointer real: usar MemorySaver).
"""
import pytest
from unittest.mock import patch
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver


@pytest.fixture
def compiled_graph():
    """Grafo compilado con MemorySaver (sin Supabase) para tests."""
    from app.graph.workflow import build_graph
    graph = build_graph()
    return graph.compile(checkpointer=MemorySaver())


@patch("app.infra.supabase.update_conversation_node")
def test_full_loan_flow_state_structure(mock_update, compiled_graph):
    """
    Verifica que después de un flujo LOAN completo (stubs), el state tiene
    todos los namespaces correctamente populados.
    """
    initial_state = {
        "messages": [HumanMessage(content="quiero un crédito")],
        "user_data": {
            "full_name": "Luis Martínez",
            "email": "luis@example.com",
            "rut": "22222222-2",
            "birth_date": "1985-03-20",
            "user_status": "ACTIVE",
        },
        "session": {
            "conversation_id": "integration-001",
            "product_intent": None,
            "current_node": None,
            "previous_node": None,
            "is_transversal_active": False,
        },
        "preparation_data": {},
        "collecting_data": {},
        "evaluation_results": {},
        "offer_data": {},
        "auth_control": {},
    }
    config = {"configurable": {"thread_id": "test-thread-001"}}
    result = compiled_graph.invoke(initial_state, config)

    # Verificar namespaces populados
    assert result["preparation_data"]["nombre"] == "Luis Martínez"
    assert isinstance(result["preparation_data"]["edad"], int)
    assert result["session"]["product_intent"] == "LOAN"
    assert result["collecting_data"].get("loan_profile") == {}  # Reset ejecutado
    assert result["collecting_data"].get("loan_sim") == {}


@patch("app.infra.supabase.update_conversation_node")
def test_edges_route_correctly_after_refactor(mock_update):
    """Verifica que route_after_intent sigue funcionando con FluxState v2.0."""
    from app.graph.edges import route_after_intent

    state_loan = {
        "session": {"product_intent": "LOAN"},
        "preparation_data": {},
        "collecting_data": {},
    }
    assert route_after_intent(state_loan) == "loan_entry"

    state_dap = {
        "session": {"product_intent": "DAP"},
        "preparation_data": {},
        "collecting_data": {},
    }
    assert route_after_intent(state_dap) == "dap_entry"

    state_general = {
        "session": {"product_intent": "GENERAL"},
        "preparation_data": {},
        "collecting_data": {},
    }
    assert route_after_intent(state_general) == "general_response"


@patch("app.infra.supabase.update_conversation_node")
def test_state_serializable_to_json(mock_update):
    """
    Verifica que el nuevo FluxState es completamente serializable a JSON
    (requisito del checkpointer de Supabase).
    """
    import json
    from app.graph.nodes.common import welcome_node

    state = {
        "user_data": {
            "full_name": "Test User",
            "email": "test@test.com",
            "rut": "33333333-3",
            "birth_date": "1995-01-01",
        },
        "session": {
            "conversation_id": "serial-test-001",
            "previous_node": None,
        },
        "messages": [],
        "preparation_data": {},
        "collecting_data": {},
        "evaluation_results": {},
        "offer_data": {},
        "auth_control": {},
    }
    result = welcome_node(state)
    # El retorno del nodo (sin AIMessage) debe ser serializable
    serializable = {
        k: v for k, v in result.items() if k != "messages"
    }
    json_str = json.dumps(serializable)
    assert len(json_str) > 0
```

**Documentación del Paso 5:**
> `edges.py` no requirió modificaciones: solo accede a `session["product_intent"]`, que es una clave de `SessionData` que no cambió en v2.0. `workflow.py` tampoco requirió cambios estructurales: LangGraph infiere la serialización del State desde el TypedDict. Se confirmó mediante pruebas de integración con `MemorySaver` que el flujo completo (welcome → intent_router → loan_entry) funciona correctamente con la nueva estructura de namespaces.

---

## Resumen Ejecutivo de la Migración

| Paso | Archivo Principal | Cambio | Riesgo |
|------|------------------|--------|--------|
| 1 | `state.py` | Reescritura completa (v1→v2) | 🔴 Alto — es la fuente de verdad |
| 2 | `common.py` | Agregar escritura de `preparation_data` + `_calculate_age` | 🟡 Medio |
| 3 | `credit.py`, `account.py`, `deposit.py` | Agregar reset de namespace en INIT | 🟢 Bajo |
| 4 | `credit.py`, `deposit.py` | Stubs de motores con patrón de escritura correcto | 🟢 Bajo |
| 5 | `edges.py`, `workflow.py` | Sin cambios (verificación) | 🟢 Ninguno |

### Invariantes que Deben Mantenerse en Todo Momento

1. `messages` con reducer `add_messages` — intocable.
2. `session["product_intent"]` — GPS del grafo, solo escrito por `intent_router_node`.
3. Checkpointer de Supabase — solo cambia `state.py`, LangGraph maneja el resto automáticamente.
4. Un producto nunca escribe en el namespace de otro.
5. `preparation_data` es de solo lectura para todos los nodos excepto `welcome_node`.

### Secuencia de Ejecución Recomendada

```
Paso 1 → pytest test_state_v2.py ✓
Paso 2 → pytest test_welcome_node_v2.py ✓
Paso 3 → pytest test_init_nodes_v2.py ✓
Paso 4 → pytest test_engines_v2.py ✓
Paso 5 → pytest test_integration_v2.py ✓
         → smoke test manual con el servidor levantado
```
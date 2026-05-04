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
  - Agregado: flow_result (estado de cierre del flujo para auditoría)
  - Agregado: FinalDisplay (datos tipados para renderizado del Frontend)
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
    progress: ProgressData          # Historial persistente de pasos completados
    just_completed_step: str | None # Flag volátil (1 turno): qué hito acaba de ocurrir


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
# NAMESPACE H: FinalDisplay  [NUEVO en v2.0 — dentro de OfferData]
# Datos de cierre para mostrar al usuario (pantalla final).
# Escritura: nodos COMPLETED y REJECTED de cada producto.
# ══════════════════════════════════════════════════════════════
class FinalDisplay(TypedDict, total=False):
    """
    Datos que el Frontend renderiza en la pantalla de cierre.
    Escritura: nodos COMPLETED y REJECTED de cada producto.
    """
    download_url: str | None
    main_detail: str | None      # Ej: "Monto: $5.000.000"
    security_hash: str | None
    reason: str | None           # Solo para rechazos

# ══════════════════════════════════════════════════════════════
# NAMESPACE I: FlowResult [NUEVO en v2.0 — fuera de OfferData]
# Estado de cierre del flujo para auditoría y analytics.
# Escritura: tras nodos COMPLETED, REJECTED y SERVICE_ERROR.
# ══════════════════════════════════════════════════════════════
class FlowResult(TypedDict, total=False):
    """
    Estado de cierre del flujo. Captura el fin de la sesión.
    """
    status_code: str        # SUCCESS | REJECTED | CLOSED_BY_USER | SECURITY_BLOCKED
    close_reason: str | None 
    product_name: str       
    closed_at: str          # ISO8601 timestamp

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
    display_data: FinalDisplay   # [NUEVO] Datos limpios para mostrar en frontend

class AccountOfferData(TypedDict, total=False):
    """Datos de oferta y formalización de la cuenta corriente."""
    pre_approval_status: str
    timestamp_acceptance: str
    file_contrato_path: str
    hash_sha256: str
    contract_status: str
    display_data: FinalDisplay   # [NUEVO] Datos limpios para mostrar en frontend


class DapOfferData(TypedDict, total=False):
    """Datos de oferta y formalización del depósito a plazo."""
    pre_approval_status: str
    timestamp_acceptance: str
    file_contrato_path: str
    hash_sha256: str
    contract_status: str
    display_data: FinalDisplay   # [NUEVO] Datos limpios para mostrar en frontend


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
# NAMESPACE J: transparency_data  [NUEVO en v2.1]
# Datos curados para la "Tarjeta de Transparencia" de cada producto.
# Escritura: Nodos PRE_APPROVED de cada producto.
# ══════════════════════════════════════════════════════════════

class LoanTransparency(TypedDict, total=False):
    """Atributos de visualización para Crédito de Consumo."""
    monto_aprobado: str
    plazo_aprobado: str
    tasa_interes_mensual: str
    cuota_mensual: str
    ctc: str
    total_intereses: str
    cae: str
    nivel_riesgo: str

class AccountTransparency(TypedDict, total=False):
    """Atributos de visualización para Cuenta Corriente."""
    final_category: str
    has_upgrade: str
    credit_line_amount: str
    monthly_cost: str

class DapTransparency(TypedDict, total=False):
    """Atributos de visualización para Depósito a Plazo."""
    monto: str
    moneda: str
    estimated_gain: str
    total_return: str
    period_rate: str
    conversion_rate_used: str
    ipc_applied: str

class TransparencyData(TypedDict, total=False):
    """
    Contenedor raíz para la visualización intermedia de ofertas.
    """
    loan: LoanTransparency
    account: AccountTransparency
    dap: DapTransparency


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
    │ flow_result       │ Estado de cierre del flujo           │
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

    # ── Datos para Tarjeta de Transparencia ───────────────────────
    transparency_data: TransparencyData

    # ── Resultado final del flujo (solo usado al terminar) ─────────
    flow_result: FlowResult
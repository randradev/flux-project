"""
app/graph/state.py
─────────────────────────────────────────────────────────────
Definición del Estado Global del Grafo (The Single Source of Truth).

REGLA DE ORO #1: Este archivo es la única fuente de verdad del sistema.
Ningún desarrollador puede modificarlo sin aprobación del Dev 1 (Orchestrator).

PROCESO: Define el TypedDict FluxState que LangGraph usa como contenedor
         de información entre nodos. Cada clave tiene un propósito específico
         y su escritura está reservada a los nodos indicados en los comentarios.

SALIDA:  Clase FluxState importada por workflow.py y todos los nodos.
"""

from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages


class UserData(TypedDict, total=False):
    """
    Datos del usuario cargados desde la DB al iniciar el grafo.
    Estos campos son inmutables durante la sesión; solo WELCOME_NODE los escribe.
    """
    user_id: str           # UUID del usuario en la tabla `users`
    full_name: str         # Nombre completo para personalización de mensajes
    email: str             # Correo para envío de OTP
    rut: str               # RUT (sin puntos, con guión)
    birth_date: str        # Fecha de nacimiento ISO8601 (para cálculo de edad)
    user_status: str       # Código de estado: ACTIVE, BLOCKED_SECURITY, PROSPECT
    user_category: str | None  # START, MEDIUM, ADVANCE o None


class SessionData(TypedDict, total=False):
    """
    Datos de la sesión conversacional activa.
    Estos campos los escriben los nodos de orquestación.
    """
    conversation_id: str       # UUID de la conversación = thread_id de LangGraph
    application_id: str | None # UUID de la solicitud en financial_applications
    product_intent: str | None # Intención detectada: LOAN, ACCOUNT, DAP, GENERAL
    current_node: str          # Nombre del nodo activo (para el GPS visual del FE)
    previous_node: str | None  # Nodo previo (para retorno desde transversales)
    is_transversal_active: bool  # True si el flujo está en un nodo transversal


class FluxState(TypedDict):
    """
    Estado global del Grafo FLUX.
    
    Es el TypedDict raíz que LangGraph serializa y persiste en el
    checkpointer de Supabase después de cada transición de nodo.

    CAMPOS:
    - messages: Historial de mensajes LangChain (acumulativo, no reemplazable).
                Usa `add_messages` como reducer para que cada nodo agregue
                mensajes sin sobreescribir el historial anterior.
    - user_data: Perfil del usuario cargado desde la DB.
    - session:   Metadatos de la sesión activa (IDs, intención, nodo GPS).
    - collected_data: Datos recolectados por los nodos de extracción.
                      Es un dict flexible para acomodar los distintos productos.
    - control_flags: Flags de control del flujo del grafo.
    """

    # ── Mensajes (reducer acumulativo) ───────────────────────
    messages: Annotated[list, add_messages]

    # ── Datos del Usuario (escritura única: WELCOME_NODE) ────
    user_data: UserData

    # ── Sesión Activa ─────────────────────────────────────────
    session: SessionData

    # ── Datos Recolectados (escritura: nodos de extracción) ──
    # Estructura flexible: cada producto agrega sus llaves sin conflicto.
    # Ejemplo LOAN: {"renta": 1500000, "antiguedad": 12, "nivel_estudios": "UNIVERSITARIO"}
    # Ejemplo DAP:  {"monto_inversion": 5000000, "moneda": "CLP", "plazo_dias": 180}
    collected_data: dict

    # ── Flags de Control del Flujo ────────────────────────────
    # Escritura reservada a nodos de seguridad y manejo de errores.
    control_flags: dict
    # Estructura esperada de control_flags:
    # {
    #   "security_blocked": bool,    # True si SECURITY_WATCHDOG bloqueó el flujo
    #   "service_error": bool,       # True si un servicio externo falló
    #   "otp_attempts": int,         # Contador de intentos de OTP (0-3)
    #   "error_detail": str | None,  # Descripción técnica del error para logging
    # }
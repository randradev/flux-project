"""
app/infra/supabase.py
─────────────────────────────────────────────────────────────
Cliente centralizado para interacción con Supabase.

PROCESO: Inicializa el cliente de Supabase usando las variables de
         entorno. Expone funciones helper para las operaciones de DB
         más frecuentes del sistema.

SALIDA:  Instancias `supabase_client` (para operaciones CRUD) y
         `supabase_admin` (para operaciones que requieren service_role).
         Funciones de acceso a datos para conversations y messages.
"""

from supabase import create_client, Client
from app.config import settings


# ── Clientes ─────────────────────────────────────────────────

# Cliente estándar (service role) — para operaciones del sistema
supabase_client: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key
)

# Cliente admin (service role) — para operaciones privilegiadas (Auth, etc.)
supabase_admin: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key
)


# ── Helpers de Usuario ────────────────────────────────────────

def get_user_by_email(email: str) -> dict | None:
    """
    Recupera los datos de un usuario desde la tabla `users` por email.

    INPUT:  email (str) — correo del usuario autenticado via Supabase Auth.
    PROCESO: Consulta la tabla `users` con JOIN a `user_statuses`.
    OUTPUT: Diccionario con los campos del usuario, o None si no existe.
    """
    response = (
        supabase_client
        .table("users")
        .select("*, user_statuses(code)")
        .eq("email", email)
        .maybe_single()
        .execute()
    )
    return response.data


def get_user_by_id(user_id: str) -> dict | None:
    """
    Recupera los datos de un usuario desde la tabla `users` por UUID.

    INPUT:  user_id (str) — UUID del usuario.
    OUTPUT: Diccionario con los campos del usuario, o None si no existe.
    """
    response = (
        supabase_client
        .table("users")
        .select("*, user_statuses(code)")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return response.data


# ── Helpers de Conversación ───────────────────────────────────

def create_conversation(user_id: str, product_type_code: str | None = None) -> dict:
    """
    Crea un nuevo hilo de conversación en la tabla `conversations`.

    INPUT:  user_id (str) — UUID del usuario.
            product_type_code (str | None) — Código del producto si ya se conoce.
    PROCESO: Si se provee product_type_code, resuelve su ID desde `product_types`.
             Crea el registro en `conversations`.
    OUTPUT: Diccionario con los datos de la conversación creada (incluye el `id` = thread_id).
    """
    data = {"user_id": user_id, "is_active": True}

    if product_type_code:
        pt = (
            supabase_client
            .table("product_types")
            .select("id")
            .eq("code", product_type_code)
            .single()
            .execute()
        )
        if pt.data:
            data["product_type_id"] = pt.data["id"]

    response = supabase_client.table("conversations").insert(data).execute()
    return response.data[0]


def save_message(conversation_id: str, role: str, content: str,
                 node_at_time: str | None = None,
                 extracted_data: dict | None = None) -> dict:
    """
    Persiste un mensaje en la tabla `messages`.

    INPUT:  conversation_id (str) — UUID de la conversación.
            role (str) — 'user', 'assistant' o 'system'.
            content (str) — Texto del mensaje.
            node_at_time (str | None) — Nodo de LangGraph activo al generarse el mensaje.
            extracted_data (dict | None) — Entidades extraídas por el LLM (si aplica).
    OUTPUT: Diccionario con el registro del mensaje creado.
    """
    data = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
    }
    if node_at_time:
        data["node_at_time"] = node_at_time
    if extracted_data:
        data["extracted_data"] = extracted_data

    response = supabase_client.table("messages").insert(data).execute()
    return response.data[0]


def get_conversation_messages(conversation_id: str) -> list[dict]:
    """
    Recupera todos los mensajes de una conversación en orden cronológico.

    INPUT:  conversation_id (str) — UUID de la conversación.
    PROCESO: Consulta la tabla `messages` ordenada por `created_at ASC`.
    OUTPUT: Lista de diccionarios con los mensajes.
    """
    response = (
        supabase_client
        .table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []


def update_conversation_node(conversation_id: str, current_node: str,
                              state_snapshot: dict | None = None) -> None:
    """
    Actualiza el nodo activo y el snapshot de estado de una conversación.

    INPUT:  conversation_id (str) — UUID de la conversación.
            current_node (str) — Nombre del nodo LangGraph activo.
            state_snapshot (dict | None) — Estado serializado del grafo.
    PROCESO: UPDATE en la tabla `conversations`. El trigger updated_at se dispara automáticamente.
    OUTPUT: None. Lanza excepción si falla.
    """
    data = {"current_node": current_node}
    if state_snapshot:
        data["state_snapshot"] = state_snapshot

    supabase_client.table("conversations").update(data).eq("id", conversation_id).execute()

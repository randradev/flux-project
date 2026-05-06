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
    # Se cambió supabase_client por supabase_admin para evitar error RLS
    response = supabase_admin.table("conversations").insert(data).execute()
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
    # Se cambió supabase_client por supabase_admin para evitar error RLS
    response = supabase_admin.table("messages").insert(data).execute()
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
    # Se cambió supabase_client por supabase_admin para evitar error RLS
    supabase_admin.table("conversations").update(data).eq("id", conversation_id).execute()


# ── Helpers de Solicitudes (Aplicaciones Financieras) ───────────

def update_application_semaphores(
    application_id: str,
    current_node_id: str | None = None,
    node_status: str | None = None,      # IN_PROGRESS | SUCCESS | FAILED
    engine_status: str | None = None,    # PENDING | COMPLETED | FAILED | NOT_APPLICABLE
    document_status: str | None = None,  # PENDING | GENERATED
) -> None:
    """
    Actualiza los semáforos de sincronía en financial_applications.
    Esta es la única función autorizada para escribir en estos campos.

    Los nodos de producto la llaman explícitamente; no es automática.
    Esto es intencional: cada nodo sabe qué semáforo le corresponde actualizar.
    """
    # 1. Construir el diccionario de actualización dinámicamente
    update_data = {}
    if current_node_id is not None: update_data["current_node_id"] = current_node_id
    if node_status is not None: update_data["node_status"] = node_status
    if engine_status is not None: update_data["engine_status"] = engine_status
    if document_status is not None: update_data["document_status"] = document_status

    # 2. Si no hay datos, no hacemos nada
    if not update_data:
        return

    try:
        # 3. Ejecutar el update en la tabla correspondiente
        # Reemplaza 'supabase' por tu instancia del cliente si tiene otro nombre
        supabase_admin.table("financial_applications") \
            .update(update_data) \
            .eq("id", application_id) \
            .execute()
            
        print(f"DEBUG: Semáforos actualizados para {application_id}: {update_data}")
    except Exception as e:
        # Logueamos el error pero no rompemos el flujo del bot
        # Es preferible que el bot siga aunque el semáforo de la DB falle
        print(f"ERROR: No se pudieron actualizar los semáforos en DB: {e}")

# ── Helpers de Storage (Archivos) ─────────────────────────────

def upload_contract_to_storage(file_path: str, bucket_name: str = "contracts") -> str | None:
    """
    Sube un archivo PDF al storage de Supabase con un sufijo único para evitar errores de duplicidad.
    """
    import os
    import time
    try:
        if not os.path.exists(file_path):
            print(f"ERROR: Archivo no encontrado para subir: {file_path}")
            return None

        # 1. Generar nombre único usando el nombre base + timestamp
        base_name = os.path.basename(file_path)
        name, ext = os.path.splitext(base_name)
        unique_name = f"{name}_{int(time.time())}{ext}" # Ejemplo: contrato_190541142_1714950000.pdf
        
        # 2. Subida en binario
        with open(file_path, "rb") as f:
            supabase_admin.storage.from_(bucket_name).upload(
                path=unique_name,
                file=f,
                file_options={"content-type": "application/pdf"}
            )
            
        # 3. Obtener URL pública
        public_url = supabase_admin.storage.from_(bucket_name).get_public_url(unique_name)
        print(f"✅ Archivo subido exitosamente a Supabase: {public_url}")
        return public_url
        
    except Exception as e:
        print(f"❌ Error subiendo archivo a Supabase Storage: {e}")
        return None

def block_user_security(user_id: str) -> bool:
    """
    Bloquea a un usuario en la DB por razones de seguridad (ej. 3 intentos fallidos de OTP).
    """
    try:
        supabase_admin.table("users").update({"user_status": "BLOCKED_SECURITY"}).eq("id", user_id).execute()
        print(f"🔒 Usuario {user_id} marcado como BLOCKED_SECURITY en DB.")
        return True
    except Exception as e:
        print(f"❌ Error intentando bloquear al usuario {user_id}: {e}")
        return False


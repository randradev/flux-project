"""
app/api/v1/docs.py
─────────────────────────────────────────────────────────────
Endpoints para recuperación de historial y gestión de documentos.

En Fase 1: Solo el endpoint /history para el historial de conversaciones.
En Fase 2+: Se agregan endpoints para descarga de contratos PDF y verificación de hash.
"""

from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_verified_user
from app.infra.supabase import supabase_client, get_conversation_messages

router = APIRouter()


@router.get("/history")
async def get_conversation_history(
    user_profile: dict = Depends(get_verified_user),
):
    """
    Recupera todas las conversaciones del usuario con sus últimos mensajes.

    INPUT:  JWT en Authorization header (usuario autenticado).
    PROCESO:
        1. Consulta la tabla `conversations` del usuario, ordenadas por created_at DESC.
        2. Para cada conversación, incluye el último mensaje como preview.
    OUTPUT: Lista de conversaciones con metadatos para el Sidebar del FE.
    """
    user_id = str(user_profile.get("id"))

    response = (
        supabase_client
        .table("conversations")
        .select("id, product_type_id, current_node, is_active, created_at, updated_at, product_types(name)")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(20)
        .execute()
    )

    return {"conversations": response.data or []}


@router.get("/history/{conversation_id}")
async def get_messages_by_conversation(
    conversation_id: str,
    user_profile: dict = Depends(get_verified_user),
):
    """
    Recupera todos los mensajes de una conversación específica.

    INPUT:  conversation_id (str) — UUID de la conversación.
            JWT en Authorization header.
    PROCESO:
        1. Verifica que la conversación pertenece al usuario autenticado.
        2. Recupera todos los mensajes ordenados cronológicamente.
    OUTPUT: Lista de mensajes para reconstruir el hilo en el chat.
    """
    user_id = str(user_profile.get("id"))

    # Verificar propiedad
    conv = (
        supabase_client
        .table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    if not conv.data:
        raise HTTPException(
            status_code=404,
            detail="Conversación no encontrada o no tienes acceso a ella."
        )

    messages = get_conversation_messages(conversation_id)
    return {"conversation_id": conversation_id, "messages": messages}

# ── Pendiente ────────────────────────────────────────
# =========================== BORRAR CONVERSACIÓN =====
# ── Pendiente ────────────────────────────────────────
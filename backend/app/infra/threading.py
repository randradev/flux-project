"""
app/infra/threading.py
─────────────────────────────────────────────────────────────
Gestión del thread_id de LangGraph y su vinculación con el usuario.

PROCESO: En LangGraph, el `thread_id` es la clave que el checkpointer
         usa para almacenar y recuperar el estado del grafo.
         En FLUX, el thread_id equivale al UUID de la conversación,
         que a su vez pertenece a un usuario específico.
         Esta vinculación es lo que garantiza que un usuario solo
         pueda acceder a sus propias conversaciones.

SALIDA:  Funciones para crear o recuperar el thread_id de una sesión.
"""

from app.infra.supabase import supabase_client, create_conversation


def get_or_create_thread(user_id: str, conversation_id: str | None = None) -> str:
    """
    Retorna un thread_id válido para la sesión del usuario.

    INPUT:  user_id (str) — UUID del usuario autenticado.
            conversation_id (str | None) — UUID de conversación existente
              para reanudar, o None para crear una nueva.
    PROCESO:
        1. Si conversation_id es None: crea una nueva conversación en la DB
           y retorna su UUID como thread_id.
        2. Si conversation_id es provisto: verifica que la conversación
           pertenece al user_id (seguridad). Si la verificación pasa,
           retorna el conversation_id como thread_id.
    OUTPUT: thread_id (str) — UUID de la conversación = thread_id de LangGraph.

    RAISES: ValueError si el conversation_id no pertenece al user_id.
    """
    if conversation_id is None:
        # Crear nueva conversación
        new_conv = create_conversation(user_id=user_id)
        return new_conv["id"]
    else:
        # Verificar propiedad de la conversación (CRÍTICO para seguridad)
        response = (
            supabase_client
            .table("conversations")
            .select("id, user_id, is_active")
            .eq("id", conversation_id)
            .eq("user_id", user_id)  # Doble filtro: id Y user_id deben coincidir
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise ValueError(
                f"La conversación {conversation_id} no existe o no pertenece al usuario {user_id}."
            )
        return conversation_id


def get_langgraph_config(thread_id: str) -> dict:
    """
    Retorna el dict de configuración que LangGraph requiere para el checkpointer.

    INPUT:  thread_id (str) — UUID de la conversación.
    OUTPUT: dict {"configurable": {"thread_id": thread_id}}
            Listo para pasar como `config=` en compiled_graph.invoke() / astream().
    """
    return {"configurable": {"thread_id": thread_id}}
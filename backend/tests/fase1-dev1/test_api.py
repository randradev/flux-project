import json
import pytest
import asyncio
import sys
from fastapi.testclient import TestClient
from main import app
from app.api.deps import get_verified_user

# Parche para compatibilidad de psycopg asíncrono en Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

client = TestClient(app, raise_server_exceptions=False)

# ── Mock de Usuario para Pruebas ─────────────────────────────
TEST_USER_ID = "0643145f-4557-4408-9d73-1ae9f224daa1"

async def override_get_verified_user():
    """Simula un usuario verificado para evitar validación de JWT real."""
    return {
        "id": TEST_USER_ID,
        "full_name": "Usuario de Prueba",
        "email": "test@example.com",
        "rut": "12345678-9",
        "birth_date": "1990-01-01",
        "user_statuses": {"code": "ACTIVE"},
        "user_categories": {"code": "PREMIUM"}
    }

# ── Prueba 6.A ────────────────────────────────────────────────

def test_chat_endpoint_requires_auth():
    """POST /chat sin token debe retornar 401/403."""
    response = client.post("/api/v1/chat", json={"message": "Hola"})
    assert response.status_code in [401, 403]


def test_history_endpoint_requires_auth():
    """GET /history sin token debe retornar 401/403."""
    response = client.get("/api/v1/history")
    assert response.status_code in [401, 403]


# ── Prueba 6.B ────────────────────────────────────────────────

def test_e2e_chat_flow():
    """
    Test end-to-end: POST /chat → grafo LangGraph → respuesta streamed → DB.
    Usa dependency_overrides para simular autenticación.
    """
    # Aplicar override
    app.dependency_overrides[get_verified_user] = override_get_verified_user

    try:
        # Hacer request al endpoint usando el TestClient de FastAPI
        with client.stream(
            "POST",
            "/api/v1/chat",
            json={"message": "Hola, quiero un crédito"},
            headers={"Authorization": "Bearer fake-token"},
            timeout=60.0,
        ) as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers.get("content-type", "")

                events = []
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        event_data = json.loads(line[6:])
                        events.append(event_data)
                        if event_data.get("type") == "done":
                            break

        # Verificar que se recibieron eventos
        assert len(events) > 0, "No se recibieron eventos SSE"

        # Verificar que hay al menos un evento de mensaje
        message_events = [e for e in events if e.get("type") == "message"]
        assert len(message_events) > 0, "No se recibió ningún mensaje del asistente"

        # Verificar que hay un evento de finalización
        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1, "No se recibió el evento 'done'"

        conversation_id = done_events[0].get("conversation_id")
        assert conversation_id is not None

        print(f"\n[6.B] Conversation ID creado: {conversation_id}")
        print(f"[6.B] Total de eventos recibidos: {len(events)}")
        print(f"[6.B] Respuesta del asistente: {''.join([e['content'] for e in message_events])}")

    finally:
        # Limpiar overrides para no afectar otros tests
        app.dependency_overrides.clear()


# ── Prueba 6.C ────────────────────────────────────────────────

def test_messages_persist_after_chat():
    """
    Verifica que tras un turno de chat, los mensajes se guardan en la DB.
    Simula la lógica del stream_graph_response directamente (sin HTTP).
    """
    import uuid
    from app.infra.supabase import supabase_client, save_message, get_conversation_messages, create_conversation

    # Verificar si hay usuario de prueba
    users = supabase_client.table("users").select("id").limit(1).execute()
    if not users.data:
        pytest.skip("No hay usuarios de prueba en la DB.")

    user_id = users.data[0]["id"]

    # Crear conversación de prueba
    conv = create_conversation(user_id=user_id)
    conv_id = conv["id"]

    # Simular guardado de mensajes
    save_message(conv_id, "user", "Quiero abrir una cuenta")
    save_message(conv_id, "assistant", "¡Claro! Te ayudo con tu Cuenta Corriente.", node_at_time="WELCOME_NODE")

    # Verificar persistencia
    messages = get_conversation_messages(conv_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["node_at_time"] == "WELCOME_NODE"

    # Limpieza
    supabase_client.table("messages").delete().eq("conversation_id", conv_id).execute()
    supabase_client.table("conversations").delete().eq("id", conv_id).execute()

    print(f"\nMensajes persistidos y verificados correctamente.")

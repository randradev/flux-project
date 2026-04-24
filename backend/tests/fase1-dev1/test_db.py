"""Tests de integración para la capa de persistencia."""
import pytest


def test_supabase_client_initializes():
    """Verifica que el cliente Supabase se crea sin errores."""
    from app.infra.supabase import supabase_client
    assert supabase_client is not None


def test_supabase_can_read_catalog():
    """Verifica conectividad real consultando la tabla de catálogo user_statuses."""
    from app.infra.supabase import supabase_client

    response = supabase_client.table("user_statuses").select("code").execute()
    assert response.data is not None
    codes = [row["code"] for row in response.data]
    assert "ACTIVE" in codes
    assert "BLOCKED_SECURITY" in codes
    assert "PROSPECT" in codes


def test_seed_data_completeness():
    """Verifica que todos los catálogos tienen los registros del seed."""
    from app.infra.supabase import supabase_client

    catalogs = {
        "user_statuses": 3,
        "user_categories": 3,
        "product_types": 3,
        "application_statuses": 5,
        "education_levels": 4,
        "risk_levels": 3,
        "rejection_reason_codes": 6,
        "currencies": 3,
        "dap_terms": 5,
        "document_types": 3,
        "economic_indicators": 3,
    }

    for table, expected_count in catalogs.items():
        response = supabase_client.table(table).select("id", count="exact").execute()
        actual_count = response.count
        assert actual_count == expected_count, \
            f"Tabla '{table}': esperaba {expected_count} filas, encontré {actual_count}"


def test_conversation_lifecycle():
    """
    Prueba el ciclo completo: crear conversación, guardar mensajes, recuperarlos.
    NOTA: Este test crea datos reales en Supabase. Requiere un user_id válido.
          Si no existe un usuario de prueba, el test se saltará con una advertencia.
    """
    from app.infra.supabase import supabase_client, create_conversation, save_message, get_conversation_messages

    # Verificar si hay al least un usuario de prueba disponible
    users = supabase_client.table("users").select("id").limit(1).execute()
    if not users.data:
        pytest.skip("No hay usuarios en la DB. Insertar un usuario de prueba para ejecutar este test.")

    test_user_id = users.data[0]["id"]

    # Crear conversación
    conv = create_conversation(user_id=test_user_id)
    assert conv is not None
    assert "id" in conv
    conversation_id = conv["id"]

    # Guardar mensajes
    msg1 = save_message(conversation_id, "user", "Hola, quiero un crédito", node_at_time="INTENT_ROUTER")
    msg2 = save_message(conversation_id, "assistant", "¡Perfecto! Te ayudaré con eso.", node_at_time="WELCOME_NODE")

    assert msg1["role"] == "user"
    assert msg2["role"] == "assistant"

    # Recuperar mensajes
    messages = get_conversation_messages(conversation_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

    # Limpieza (opcional, pero recomendable para no contaminar la DB)
    supabase_client.table("messages").delete().eq("conversation_id", conversation_id).execute()
    supabase_client.table("conversations").delete().eq("id", conversation_id).execute()


@pytest.mark.asyncio
async def test_checkpointer_setup():
    """
    Verifica que el AsyncPostgresSaver se inicializa y ejecuta setup() sin errores.
    """
    from app.infra.checkpointer import get_checkpointer
    checkpointer = get_checkpointer()
    assert checkpointer is not None
    
    # Setup es asíncrono
    await checkpointer.setup()
    # Si llegamos aquí sin excepción, la conexión y el setup fueron exitosos

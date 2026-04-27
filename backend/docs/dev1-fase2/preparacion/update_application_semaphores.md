```python
# /backend/app/infra/supabase.py

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
```
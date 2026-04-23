from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from app.config import settings


def get_checkpointer() -> AsyncPostgresSaver:
    """
    Retorna una instancia del AsyncPostgresSaver configurada con la conexión a Supabase.

    INPUT:  Ninguno (lee DATABASE_URL desde settings).
    PROCESO: Ajusta la URL para desactivar prepared statements (PgBouncer compatibility)
             y crea un pool de conexiones asíncrono.
    OUTPUT: Instancia de AsyncPostgresSaver lista para compilación del grafo.
    """
    pool = AsyncConnectionPool(
        settings.database_url,
        max_size=10,
        kwargs={
            "prepare_threshold": None,
            "options": "-c prepare_threshold=0"
        }
    )

    saver = AsyncPostgresSaver(pool)
    return saver


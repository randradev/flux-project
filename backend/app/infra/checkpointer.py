from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from app.config import settings


def get_checkpointer() -> AsyncPostgresSaver:
    """
    Retorna una instancia del AsyncPostgresSaver configurada con la conexión a Supabase.

    INPUT:  Ninguno (lee DATABASE_URL desde settings).
    PROCESO: Crea un pool de conexiones asíncrono y el saver.
    OUTPUT: Instancia de AsyncPostgresSaver lista para compilación del grafo.
    """
    pool = AsyncConnectionPool(settings.database_url, max_size=10)
    saver = AsyncPostgresSaver(pool)
    
    # NOTA: setup() es asíncrono y debe llamarse antes de usar el saver.
    # En este diseño, el grafo lo llamará o se llamará en la inicialización de la app.
    
    return saver

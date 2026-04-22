"""
app/infra/embeddings.py
─────────────────────────────────────────────────────────────
Cliente para búsqueda semántica en el Vector Store (pgvector en Supabase).

FASE 1: Stub funcional. Provee la interfaz que los nodos del grafo
        usarán, pero con implementación básica que devuelve resultados
        vacíos hasta que el RAG sea implementado en Fase 3.

SALIDA:  Función `similarity_search()` que el nodo KNOWLEDGE_BASE_RAG
         invocará para buscar fragmentos relevantes de políticas.
"""

from app.infra.gemini_client import get_embeddings_model


def similarity_search(query: str, top_k: int = 3) -> list[dict]:
    """
    Busca fragmentos de documentos similares a la consulta en el vector store.

    INPUT:  query (str) — Texto de la consulta del usuario.
            top_k (int) — Número de fragmentos a retornar.
    PROCESO: [FASE 1 - STUB] Genera el embedding de la consulta pero devuelve
             lista vacía hasta que el vector store esté poblado (Fase 3).
    OUTPUT: Lista de dicts con campos 'content' y 'similarity_score'.
            Vacía en Fase 1.
    """
    # En Fase 3, aquí se hará la búsqueda real en pgvector:
    # embedding = get_embeddings_model().embed_query(query)
    # ... consulta a Supabase con el embedding ...

    # FASE 1: Retornar stub vacío
    return []
"""
ingest.py
─────────────────────────────────────────────────────────────
Script de ingesta de reglas de negocio FLUX hacia el Vector Store.

PROCESO:
  1. Lee la estrategia de chunking (estrategia-chunking.md).
  2. Parsea cada chunk extrayendo: ID, producto, sección y contenido.
  3. Genera el embedding de cada chunk usando Gemini text-embedding-004.
  4. Hace upsert en la tabla `knowledge_base` de Supabase (pgvector).

USO:
  python ingest.py                          → Ingesta todos los productos
  python ingest.py --product LOAN           → Solo chunks de crédito
  python ingest.py --dry-run               → Parsea sin escribir en DB
  python ingest.py --file otro-doc.md      → Ingesta un archivo específico

NOTA: Diseñado para ser idempotente. Re-ejecutar no duplica datos.
"""

import re
import json
import time
import argparse
import logging
from pathlib import Path
from typing import Iterator

from app.infra.gemini_client import get_embeddings_model
from app.infra.supabase import supabase_admin


# ── Configuración de Logging ──────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("flux.ingest")


# ── Constantes ────────────────────────────────────────────────

# Ruta por defecto al archivo de chunking (relativa al proyecto)
DEFAULT_CHUNKING_FILE = Path("estrategia-chunking.md")

# Mapa de prefijos de Chunk ID → código de producto en metadata
# Debe mantenerse sincronizado con los IDs definidos en estrategia-chunking.md
PRODUCT_MAP: dict[str, str] = {
    "LOAN": "LOAN",
    "ACC":  "ACCOUNT",
    "DAP":  "DAP",
    "GEN":  "GENERAL",
}

# Umbral de pausa entre llamadas a la API de embeddings (segundos)
# Evita rate-limit en lotes grandes. Ajustar según cuota del proyecto.
API_RATE_DELAY = 0.3

# Tabla destino en Supabase
TABLE_NAME = "knowledge_base"


# ══════════════════════════════════════════════════════════════
# PARSING
# ══════════════════════════════════════════════════════════════

def _extract_product_from_chunk_id(chunk_id: str) -> str:
    """
    Infiere el código de producto a partir del prefijo del Chunk ID.

    INPUT:  chunk_id (str) — Ej: "LOAN_001", "ACC_003", "DAP_007", "GEN_001"
    OUTPUT: Código de producto — "LOAN" | "ACCOUNT" | "DAP" | "GENERAL"
    RAISES: ValueError si el prefijo no está en PRODUCT_MAP.
    """
    prefix = chunk_id.split("_")[0].upper()
    if prefix not in PRODUCT_MAP:
        raise ValueError(
            f"Prefijo desconocido '{prefix}' en chunk_id '{chunk_id}'. "
            f"Prefijos válidos: {list(PRODUCT_MAP.keys())}"
        )
    return PRODUCT_MAP[prefix]


def _parse_section_from_content(content_line: str) -> str:
    """
    Extrae el nombre de la sección desde la línea CONTENIDO del chunk.

    INPUT:  content_line — Ej: "PRODUCTO: CRÉDITO | SECCIÓN: SCORING | CONTENIDO: ..."
    OUTPUT: Nombre de sección o "GENERAL" si no se encuentra.
    """
    match = re.search(r"SECCIÓN:\s*([^|]+)", content_line)
    return match.group(1).strip() if match else "GENERAL"


def parse_chunks(markdown_text: str) -> Iterator[dict]:
    """
    Parsea el archivo de estrategia de chunking y genera dicts de chunks.

    ESTRATEGIA DE PARSING:
      - Detecta headers de chunk por el patrón "### ID: " o "### Chunk ID: "
      - Extrae el bloque de contenido completo hasta el siguiente header o fin de archivo
      - Construye metadata enriquecida por chunk

    INPUT:  markdown_text (str) — Contenido completo del archivo .md
    OUTPUT: Iterator[dict] con campos:
              - chunk_id  (str)   Ej: "LOAN_001"
              - content   (str)   Texto del chunk listo para embeddear
              - metadata  (dict)  Producto, sección, chunk_id, source
    """
    # Patrón que captura el ID de cualquier variante: "### ID:" o "### Chunk ID:"
    chunk_pattern = re.compile(
        r"###\s+(?:Chunk\s+)?ID:\s*(\w+)\s*\n(.*?)(?=\n###\s+(?:Chunk\s+)?ID:|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    matches = list(chunk_pattern.finditer(markdown_text))
    if not matches:
        log.warning("No se encontraron chunks en el archivo. Verifica el formato.")
        return

    for match in matches:
        chunk_id = match.group(1).strip()
        raw_content = match.group(2).strip()

        # Limpiar líneas vacías extra y normalizar whitespace
        content = re.sub(r"\n{3,}", "\n\n", raw_content).strip()

        # Ignorar chunks vacíos (puede ocurrir con headers de sección sin contenido)
        if not content:
            log.debug(f"Chunk {chunk_id} vacío, omitido.")
            continue

        # Inferir producto desde el prefijo del ID
        try:
            product = _extract_product_from_chunk_id(chunk_id)
        except ValueError as e:
            log.warning(f"Chunk omitido: {e}")
            continue

        # Extraer nombre de sección desde la primera línea de contenido
        section = _parse_section_from_content(content)

        metadata = {
            "chunk_id": chunk_id,
            "product":  product,
            "section":  section,
            "source":   DEFAULT_CHUNKING_FILE.name,
        }

        yield {
            "chunk_id": chunk_id,
            "content":  content,
            "metadata": metadata,
        }


# ══════════════════════════════════════════════════════════════
# EMBEDDINGS
# ══════════════════════════════════════════════════════════════

def generate_embedding(model, text: str) -> list[float]:
    """
    Genera el vector de embedding para un texto dado.

    INPUT:  model — Instancia de VertexAIEmbeddings (get_embeddings_model())
            text  — Texto a embeddear
    OUTPUT: list[float] de 768 dimensiones
    RAISES: Exception si la API de Vertex AI falla (propagada al caller)
    """
    # embed_query() es el método de LangChain para embeddings de consulta/documento
    return model.embed_query(text)


# ══════════════════════════════════════════════════════════════
# UPSERT EN SUPABASE
# ══════════════════════════════════════════════════════════════

def upsert_chunk(chunk_id: str, content: str, metadata: dict, embedding: list[float]) -> bool:
    """
    Hace upsert de un chunk en la tabla knowledge_base de Supabase.

    IDEMPOTENCIA: Usa chunk_id como clave lógica en metadata.
      Si el chunk ya existe (mismo chunk_id), actualiza content y embedding.
      Si no existe, lo inserta.

    INPUT:  chunk_id  — Identificador lógico del chunk (Ej: "LOAN_001")
            content   — Texto del chunk
            metadata  — Dict con product, section, chunk_id, source
            embedding — Vector de 768 floats
    OUTPUT: True si exitoso, False si falló.
    """
    # Estrategia de upsert: DELETE + INSERT por chunk_id en metadata
    # (Supabase no soporta upsert por campos JSONB nativamente sin índice único)
    try:
        # 1. Borrar versión anterior si existe (por chunk_id en metadata)
        supabase_admin.table(TABLE_NAME) \
            .delete() \
            .eq("metadata->>chunk_id", chunk_id) \
            .execute()

        # 2. Insertar versión actualizada
        supabase_admin.table(TABLE_NAME).insert({
            "content":   content,
            "metadata":  metadata,
            "embedding": embedding,
        }).execute()

        return True

    except Exception as e:
        log.error(f"Error en upsert de chunk {chunk_id}: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════════

def run_ingestion(
    source_file: Path,
    product_filter: str | None = None,
    dry_run: bool = False,
) -> None:
    """
    Ejecuta el pipeline completo de ingesta.

    INPUT:  source_file    — Path al archivo .md de chunking
            product_filter — Si se indica, solo procesa ese producto (Ej: 'LOAN')
            dry_run        — Si True, parsea y loguea sin escribir en DB
    """
    log.info("═" * 55)
    log.info("FLUX RAG — Pipeline de Ingesta")
    log.info(f"Archivo:  {source_file}")
    log.info(f"Producto: {product_filter or 'TODOS'}")
    log.info(f"Modo:     {'DRY RUN (sin escritura)' if dry_run else 'PRODUCCIÓN'}")
    log.info("═" * 55)

    # 1. Leer el archivo fuente
    if not source_file.exists():
        log.error(f"Archivo no encontrado: {source_file}")
        raise FileNotFoundError(f"No se encontró el archivo: {source_file}")

    markdown_text = source_file.read_text(encoding="utf-8")
    log.info(f"Archivo leído: {len(markdown_text):,} caracteres")

    # 2. Parsear chunks
    all_chunks = list(parse_chunks(markdown_text))
    log.info(f"Chunks parseados: {len(all_chunks)}")

    # 3. Aplicar filtro de producto si se indicó
    if product_filter:
        all_chunks = [
            c for c in all_chunks
            if c["metadata"]["product"] == product_filter.upper()
        ]
        log.info(f"Chunks tras filtro '{product_filter}': {len(all_chunks)}")

    if not all_chunks:
        log.warning("No hay chunks para procesar. Verifica el filtro y el archivo.")
        return

    # 4. Inicializar modelo de embeddings (una sola vez)
    if not dry_run:
        log.info("Inicializando modelo de embeddings (Gemini text-embedding-004)...")
        embeddings_model = get_embeddings_model()
        log.info("Modelo listo.")

    # 5. Procesar cada chunk
    success_count = 0
    error_count = 0

    for i, chunk in enumerate(all_chunks, 1):
        chunk_id = chunk["chunk_id"]
        content  = chunk["content"]
        metadata = chunk["metadata"]

        log.info(
            f"[{i:>2}/{len(all_chunks)}] Procesando {chunk_id} "
            f"({metadata['product']} | {metadata['section'][:40]}...)"
        )

        if dry_run:
            log.info(f"  → DRY RUN: contenido ({len(content)} chars), metadata: {json.dumps(metadata)}")
            success_count += 1
            continue

        # Generar embedding
        try:
            embedding = generate_embedding(embeddings_model, content)
            log.debug(f"  → Embedding generado: {len(embedding)} dimensiones")
        except Exception as e:
            log.error(f"  → ERROR generando embedding para {chunk_id}: {e}")
            error_count += 1
            continue

        # Hacer upsert en Supabase
        ok = upsert_chunk(chunk_id, content, metadata, embedding)
        if ok:
            log.info(f"  → ✓ Upsert exitoso")
            success_count += 1
        else:
            log.error(f"  → ✗ Fallo en upsert")
            error_count += 1

        # Pausa entre llamadas para respetar rate limits de Vertex AI
        if i < len(all_chunks):
            time.sleep(API_RATE_DELAY)

    # 6. Resumen final
    log.info("═" * 55)
    log.info(f"RESUMEN INGESTA:")
    log.info(f"  ✓ Exitosos: {success_count}")
    log.info(f"  ✗ Errores:  {error_count}")
    log.info(f"  Total:      {len(all_chunks)}")
    log.info("═" * 55)

    if error_count > 0:
        log.warning(f"{error_count} chunk(s) fallaron. Revisar logs para detalles.")


# ══════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingesta de reglas de negocio FLUX al Vector Store (Supabase + pgvector)"
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_CHUNKING_FILE,
        help=f"Ruta al archivo .md de chunking (default: {DEFAULT_CHUNKING_FILE})",
    )
    parser.add_argument(
        "--product",
        type=str,
        default=None,
        choices=["LOAN", "ACCOUNT", "DAP", "GENERAL"],
        help="Filtrar ingesta por producto específico",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parsea y muestra los chunks sin escribir en la base de datos",
    )

    args = parser.parse_args()

    run_ingestion(
        source_file=args.file,
        product_filter=args.product,
        dry_run=args.dry_run,
    )
"""
app/modules/consultant.py
─────────────────────────────────────────────────────────────
Módulo RAG Consultor de FLUX.

Responsabilidad ÚNICA: Responder preguntas sobre reglas de negocio
usando el Vector Store (knowledge_base en Supabase + pgvector).

FLUJO INTERNO:
  1. Extrae contexto del usuario desde el estado de LangGraph.
  2. Genera el embedding de la pregunta del usuario.
  3. Ejecuta búsqueda por similitud de coseno en Supabase.
  4. Construye un prompt enriquecido (Identidad + Contexto + Fragmentos).
  5. Genera la respuesta final con personalidad Flux chilena.
  6. Aplica fallback si la similitud es baja o el LLM no encuentra info.

PUNTO DE ENTRADA PÚBLICO:
  get_consultant_response(user_msg: str, state: FluxState) -> str

DEPENDENCIAS:
  - app.infra.gemini_client  → get_embeddings_model(), get_generation_model()
  - app.infra.supabase       → supabase_client (no crea nueva conexión)
  - app.graph.state          → FluxState (solo lectura)
"""

import logging
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage

from app.infra.gemini_client import get_embeddings_model, get_generation_model
from app.infra.supabase import supabase_client
from app.graph.state import FluxState

# ── Logging ───────────────────────────────────────────────────
log = logging.getLogger("flux.consultant")


# ══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

# Tabla y función RPC del Vector Store
KB_TABLE       = "knowledge_base"
KB_RPC         = "match_knowledge_base"

# Parámetros de retrieval
DEFAULT_TOP_K           = 5     # Fragmentos a recuperar
SIMILARITY_THRESHOLD    = 0.55  # Umbral mínimo de similitud (coseno)
FALLBACK_THRESHOLD      = 0.60  # Si el mejor resultado está bajo esto → fallback

# Singletons de modelos (se instancian una vez al importar el módulo)
_embeddings_model = get_embeddings_model()
_generation_model = get_generation_model()


# ══════════════════════════════════════════════════════════════
# PROMPTS
# ══════════════════════════════════════════════════════════════

# Identidad core de Flux (reutilizable)
FLUX_IDENTITY = (
    "Eres Flux, el genio amigable de las finanzas en Chile. "
    "Hablas de tú, eres cercano, ágil y traduces la burocracia a lenguaje humano. "
    "Entiendes perfectamente el contexto chileno y usas modismos locales con moderación."
)

SYSTEM_PROMPT_CONSULTANT = """
{identity}

ROL ACTUAL: Consultor experto en reglas de negocio de FLUX.
Tu misión es responder la pregunta del usuario usando EXCLUSIVAMENTE
los fragmentos de documentación oficial que te entrego más abajo.

PERSONALIDAD:
- Cercano, empático y ágil. Hablas de tú.
- Traduces el lenguaje técnico bancario a palabras simples.
- No das rodeos: responde directo, pero con calidez chilena.

RESTRICCIONES CRÍTICAS:
- NO inventes información. Si no está en los fragmentos, activa el fallback.
- NO menciones que tienes "fragmentos" o "documentos". Habla naturalmente.
- Si la pregunta es sobre el proceso en curso del usuario, usa el contexto de sesión.
- Máximo 4 oraciones en tu respuesta, a menos que la pregunta requiera detalles.

CONTEXTO DE SESIÓN DEL USUARIO:
{context_snapshot}

FRAGMENTOS DE REGLAS DE NEGOCIO RECUPERADOS:
{retrieved_chunks}

INSTRUCCIÓN FINAL:
Responde la pregunta del usuario usando la información de los fragmentos.
Si detectas que la información no está cubierta, aplica el protocolo de fallback.
"""

FALLBACK_RESPONSE_TEMPLATE = (
    "¡Hola {nombre}! Esa es una buena pregunta, pero la verdad es que "
    "no tengo esa información disponible en este momento. 😅\n\n"
    "Para resolverla al tiro, puedes escribirle a nuestro equipo a "
    "**ayuda@flux.cl** y te damos una respuesta en menos de 24 horas "
    "(lunes a viernes de 9 a 18 hrs).\n\n"
    "{process_redirect}"
)

PROCESS_REDIRECT_MAP = {
    "LOAN":    "Mientras tanto, ¿seguimos con tu simulación de crédito? ¡Ya casi terminamos! 💪",
    "ACCOUNT": "Mientras tanto, ¿seguimos abriendo tu cuenta corriente? ¡Va a quedar lista en minutos! 🚀",
    "DAP":     "Mientras tanto, ¿seguimos con tu depósito a plazo? Tu inversión te está esperando 📈",
    "GENERAL": "Si quieres, puedo ayudarte a explorar nuestros productos: crédito de consumo, cuenta corriente o depósito a plazo.",
}


# ══════════════════════════════════════════════════════════════
# EXTRACCIÓN DE CONTEXTO DESDE EL ESTADO
# ══════════════════════════════════════════════════════════════

def _get_nombre(state: FluxState) -> str:
    """Extrae el primer nombre del usuario desde preparation_data."""
    nombre = state.get("preparation_data", {}).get("nombre", "")
    return nombre.split()[0].capitalize() if nombre else "amigo/a"


def _get_current_node(state: FluxState) -> str:
    """Extrae el nodo actual del grafo desde session."""
    return state.get("session", {}).get("current_node", "UNKNOWN")


def _get_product_intent(state: FluxState) -> str:
    """
    Infiere el producto activo desde el nodo actual o product_intent.
    Retorna: 'LOAN' | 'ACCOUNT' | 'DAP' | 'GENERAL'
    """
    node = _get_current_node(state)

    if node.startswith("LOAN_"):
        return "LOAN"
    elif node.startswith("ACC_"):
        return "ACCOUNT"
    elif node.startswith("DAP_"):
        return "DAP"

    # Fallback a product_intent del estado
    intent = state.get("session", {}).get("product_intent", "GENERAL")
    return intent or "GENERAL"


def _build_context_snapshot(state: FluxState) -> str:
    """
    Genera un resumen de los datos que el usuario ha entregado en la sesión actual.
    El snapshot varía según el nodo activo para mostrar solo datos relevantes.

    INPUT:  state — Estado completo de LangGraph
    OUTPUT: String con el resumen formateado para el prompt del LLM
    """
    nombre  = _get_nombre(state)
    node    = _get_current_node(state)
    product = _get_product_intent(state)

    prep    = state.get("preparation_data", {})
    collect = state.get("collecting_data", {})

    lines = [f"- Nombre: {nombre}"]
    lines.append(f"- Nodo actual: {node}")

    # ── Datos según producto activo ───────────────────────────

    if product == "LOAN":
        profile = collect.get("loan_profile", {})
        sim     = collect.get("loan_sim", {})
        edad    = prep.get("edad")

        if edad:
            lines.append(f"- Edad: {edad} años")
        if profile.get("renta"):
            lines.append(f"- Renta líquida: ${profile['renta']:,} CLP")
        if profile.get("antiguedad_laboral"):
            lines.append(f"- Antigüedad laboral: {profile['antiguedad_laboral']} meses")
        if profile.get("nivel_estudios") and profile["nivel_estudios"] != "DESCONOCIDO":
            lines.append(f"- Nivel de estudios: {profile['nivel_estudios'].capitalize()}")
        if sim.get("monto_solicitado"):
            lines.append(f"- Monto solicitado: ${sim['monto_solicitado']:,} CLP")
        if sim.get("plazo_solicitado"):
            lines.append(f"- Plazo deseado: {sim['plazo_solicitado']} cuotas")

    elif product == "ACCOUNT":
        profile = collect.get("account_profile", {})
        edad    = prep.get("edad")

        if edad:
            lines.append(f"- Edad: {edad} años")
        if profile.get("renta"):
            lines.append(f"- Renta líquida: ${profile['renta']:,} CLP")
        if profile.get("antiguedad_laboral"):
            lines.append(f"- Antigüedad laboral: {profile['antiguedad_laboral']} meses")
        if profile.get("nivel_estudios") and profile["nivel_estudios"] != "DESCONOCIDO":
            lines.append(f"- Nivel de estudios: {profile['nivel_estudios'].capitalize()}")

    elif product == "DAP":
        params = collect.get("dap_params", {})
        edad   = prep.get("edad")

        if edad:
            lines.append(f"- Edad: {edad} años")
        if params.get("monto"):
            lines.append(f"- Monto a invertir: {params['monto']:,} {params.get('moneda', 'CLP')}")
        if params.get("plazo"):
            lines.append(f"- Plazo de inversión: {params['plazo']} días")
        if params.get("moneda"):
            lines.append(f"- Moneda seleccionada: {params['moneda']}")

    else:
        # Producto GENERAL: solo datos básicos de preparation_data
        if prep.get("edad"):
            lines.append(f"- Edad: {prep['edad']} años")

    # Si no se recopiló nada (inicio de flujo), indicarlo explícitamente
    if len(lines) <= 2:
        lines.append("- (Sin datos recolectados aún en esta sesión)")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# RETRIEVAL (BÚSQUEDA VECTORIAL)
# ══════════════════════════════════════════════════════════════

def _retrieve_chunks(
    query: str,
    product: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """
    Busca los fragmentos más relevantes en el Vector Store.

    ESTRATEGIA DE FILTRADO:
      - Primera búsqueda: filtrada por producto activo (más precisa).
      - Si no hay resultados suficientes: búsqueda global sin filtro.

    INPUT:  query   — Pregunta del usuario (texto natural)
            product — Código de producto activo: 'LOAN' | 'ACCOUNT' | 'DAP' | 'GENERAL'
            top_k   — Número máximo de chunks a retornar
    OUTPUT: Lista de dicts con 'content', 'metadata', 'similarity'
    """
    # 1. Generar embedding de la query
    try:
        query_embedding = _embeddings_model.embed_query(query)
    except Exception as e:
        log.error(f"Error generando embedding de query: {e}")
        return []

    # 2. Búsqueda filtrada por producto (si no es GENERAL)
    filter_product = product if product != "GENERAL" else None

    try:
        result = supabase_client.rpc(KB_RPC, {
            "query_embedding":    query_embedding,
            "match_count":        top_k,
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "filter_product":     filter_product,
        }).execute()

        chunks = result.data or []

    except Exception as e:
        log.error(f"Error en búsqueda vectorial: {e}")
        return []

    # 3. Si la búsqueda filtrada no retorna resultados, intentar sin filtro
    if not chunks and filter_product is not None:
        log.info(f"Sin resultados para producto '{product}'. Intentando búsqueda global...")
        try:
            result = supabase_client.rpc(KB_RPC, {
                "query_embedding":    query_embedding,
                "match_count":        top_k,
                "similarity_threshold": SIMILARITY_THRESHOLD,
                "filter_product":     None,
            }).execute()
            chunks = result.data or []
        except Exception as e:
            log.error(f"Error en búsqueda global de fallback: {e}")
            return []

    log.info(f"Chunks recuperados: {len(chunks)} (producto: {product})")
    return chunks


def _format_retrieved_chunks(chunks: list[dict]) -> str:
    """
    Formatea los chunks recuperados para incluirlos en el prompt del LLM.

    INPUT:  chunks — Lista de dicts con 'content', 'metadata', 'similarity'
    OUTPUT: String formateado listo para el prompt
    """
    if not chunks:
        return "(Sin fragmentos recuperados)"

    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta      = chunk.get("metadata", {})
        chunk_id  = meta.get("chunk_id", f"CHUNK_{i}")
        section   = meta.get("section", "General")
        product   = meta.get("product", "")
        similarity = chunk.get("similarity", 0.0)
        content   = chunk.get("content", "")

        parts.append(
            f"[{chunk_id} | {product} | {section} | similitud: {similarity:.2f}]\n"
            f"{content}"
        )

    return "\n\n---\n\n".join(parts)


def _get_best_similarity(chunks: list[dict]) -> float:
    """Retorna la similitud más alta de los chunks recuperados."""
    if not chunks:
        return 0.0
    return max(c.get("similarity", 0.0) for c in chunks)


# ══════════════════════════════════════════════════════════════
# GENERACIÓN DE RESPUESTA
# ══════════════════════════════════════════════════════════════

def _generate_response(system_prompt: str, user_msg: str) -> str:
    """
    Genera la respuesta conversacional de Flux usando el modelo generador.

    INPUT:  system_prompt — Prompt construido con identidad + contexto + chunks
            user_msg      — Pregunta original del usuario
    OUTPUT: String con la respuesta generada
    """
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ]
    try:
        response = _generation_model.invoke(messages)
        # Extraer el contenido de texto de la respuesta
        if hasattr(response, "content"):
            return str(response.content).strip()
        return str(response).strip()
    except Exception as e:
        log.error(f"Error en generación de respuesta: {e}")
        return None


def _build_fallback(nombre: str, product: str) -> str:
    """Construye el mensaje de fallback estandarizado."""
    redirect = PROCESS_REDIRECT_MAP.get(product, PROCESS_REDIRECT_MAP["GENERAL"])
    return FALLBACK_RESPONSE_TEMPLATE.format(
        nombre=nombre,
        process_redirect=redirect,
    )


# ══════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA PÚBLICO
# ══════════════════════════════════════════════════════════════

def get_consultant_response(user_msg: str, state: FluxState) -> str:
    """
    Función principal del módulo RAG Consultor.

    Orquesta el pipeline completo: extracción de contexto → retrieval →
    augmentation → generation → fallback si corresponde.

    INPUT:
        user_msg (str)       — Pregunta o consulta del usuario en texto natural.
        state (FluxState)    — Estado completo del grafo LangGraph (solo lectura).

    OUTPUT:
        str — Respuesta final lista para mostrar al usuario.
              Garantiza que siempre retorna un string (nunca None ni excepción).

    NOTAS:
        - No modifica el estado del grafo.
        - No persiste mensajes (eso es responsabilidad del nodo que lo llame).
        - Usa supabase_client existente (no crea nuevas conexiones).
    """
    # ── 1. Extraer contexto del estado ────────────────────────
    nombre          = _get_nombre(state)
    product         = _get_product_intent(state)
    context_snapshot = _build_context_snapshot(state)

    log.info(f"Consultor RAG activado | Usuario: {nombre} | Producto: {product}")
    log.info(f"Query: '{user_msg[:80]}...'")

    # ── 2. Retrieval: búsqueda vectorial ──────────────────────
    chunks = _retrieve_chunks(query=user_msg, product=product)

    # ── 3. Evaluar calidad de resultados ──────────────────────
    best_similarity = _get_best_similarity(chunks)
    log.info(f"Mejor similitud encontrada: {best_similarity:.3f} (umbral fallback: {FALLBACK_THRESHOLD})")

    if best_similarity < FALLBACK_THRESHOLD and not chunks:
        # Sin resultados relevantes → fallback inmediato
        log.warning("Sin chunks relevantes. Activando fallback.")
        return _build_fallback(nombre, product)

    # ── 4. Augmentation: construir prompt enriquecido ─────────
    formatted_chunks = _format_retrieved_chunks(chunks)

    system_prompt = SYSTEM_PROMPT_CONSULTANT.format(
        identity=FLUX_IDENTITY,
        context_snapshot=context_snapshot,
        retrieved_chunks=formatted_chunks,
    )

    # ── 5. Generation: respuesta con personalidad Flux ────────
    response = _generate_response(system_prompt, user_msg)

    # ── 6. Fallback si la generación falló o la similitud es baja ──
    if not response:
        log.warning("Generación fallida. Activando fallback.")
        return _build_fallback(nombre, product)

    # Detectar si el LLM mismo indicó que no tiene la información
    # (el prompt le instruye implícitamente usar el fallback protocol)
    NO_INFO_MARKERS = [
        "no tengo esa información",
        "no cuento con esa información",
        "no está en mis documentos",
        "no puedo responder",
        "no encontré información",
    ]
    response_lower = response.lower()
    if any(marker in response_lower for marker in NO_INFO_MARKERS):
        log.info("LLM indicó falta de información. Reemplazando con fallback estandarizado.")
        return _build_fallback(nombre, product)

    log.info("Respuesta generada exitosamente.")
    return response
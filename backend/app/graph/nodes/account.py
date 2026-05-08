"""
app/graph/nodes/account.py
─────────────────────────────────────────────────────────────
Nodos del flujo de Cuenta Corriente.

Ruta del grafo: account_init → account_evaluation_engine → END
  - account_init              (ID LangGraph) → current_node = "ACCOUNT_INIT"
  - account_evaluation_engine  (ID LangGraph) → current_node = "ACCOUNT_EVALUATION_ENGINE"
"""

from langchain_core.messages import AIMessage, HumanMessage
from app.graph.state import FluxState
from app.infra.supabase import update_application_semaphores, upload_contract_to_storage
from app.infra.gemini_client import get_structured_model, get_generation_model
from app.graph.nodes.schemas.account_schemas import AccountProfileExtraction, AccountSimExtraction, AccountDecisionExtraction, AccountOTPExtraction
# from app.modules.credit_eng import CreditEngine, PolicyRejectionError, PaymentCapacityError
from app.utils.llm_utils import normalize_llm_response
from app.graph.constants import CompletedStep
from langchain_core.outputs import LLMResult
from app.modules.consultant import get_consultant_response
from app.modules import security
from app.infra.supabase import update_application_semaphores, upload_contract_to_storage, block_user_security
from app.modules.pdf_factory import PDFFactory

# ======================================================================================================
# LLM Y PROMPTS
# ======================================================================================================

# ── CONFIGURACIÓN DE INTELIGENCIA (SINGLETONS) ──────────────
# Singletons de modelos (se instancian una vez al importar el módulo)
_profile_extractor = get_structured_model(AccountProfileExtraction)
_flux_generator    = get_generation_model()  # NUEVO — Llamada B
_pdf_factory = PDFFactory()

# ───────────────────────────────────────────────────
# ── SYSTEM PROMPTS (IDENTIDAD FLUX) ────────────────
# ───────────────────────────────────────────────────

# ── 1. IDENTIDAD CORE (Reutilizable en todo el bot)
FLUX_IDENTITY = (
    "Eres Flux, el genio amigable de las finanzas en Chile. "
    "Hablas de tú, eres cercano, ágil y traduces la burocracia a lenguaje humano. "
    "Entiendes perfectamente el contexto chileno y modismos locales."
)

# ─────────────────────────────────────────────────────────────────────────────────────────
# ── PROMPT DE BIENVENIDA AL PRODUCTO (account_init_node) ────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────────────────

# ── PROMPT LLAMADA B: GENERACIÓN ────────────────────────────────────────────
# Recibe contexto estructurado e inyecta personalidad Flux.
# La temperatura 0.7 lo hace variado y natural entre sesiones.

SYSTEM_PROMPT_INIT_ACCOUNT = """
Eres Flux, el genio amigable de las finanzas en Chile.

PERSONALIDAD:
- Hablas de tú, eres cercano y usas modismos chilenos con moderación.
- Eres ágil y empático: no das rodeos, pero sí transmites calidez.

TAREA ACTUAL: Dar la bienvenida al usuario al proceso de Cuenta Corriente.
Esta es la PRIMERA vez que el usuario entra al flujo de Cuenta Corriente.

RESTRICCIONES CRÍTICAS:
- Máximo 2 oraciones.
- Tu respuesta DEBE terminar pidiendo la renta líquida mensual.
- NO menciones tasas, CAE ni otros detalles técnicos en este paso.
- NO repitas el saludo de bienvenida general (ya fue hecho antes).
- Varía el tono: no siempre uses "¡Perfecto!" al inicio.
"""

# ─────────────────────────────────────────────────────────────────────────────────────────
# ── PROMPTS DE EXTRACCIÓN EN NODOS COLLECTING ────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────────────────

# ── PROMPT LLAMADA A: EXTRACCIÓN ────────────────────────────────────────────
# Directivo y sin ambigüedad. Temperatura 0.0 hace el trabajo pesado;
# el prompt solo establece el contrato de qué retornar.

SYSTEM_PROMPT_EXTRACTION_PROFILE = """
Eres un motor de extracción de datos financieros. Tu ÚNICA misión es analizar el mensaje del usuario y retornar un JSON estructurado VÁLIDO.

REGLAS DE FORMATO:
- NO uses bloques de código Markdown (prohibido usar ```json).
- El campo 'razonamiento' debe ser una sola frase corta sin comillas internas.
- Los números deben ser enteros puros (sin puntos ni comas).

REGLAS DE RAZONAMIENTO:
1. 'razonamiento': Escribe máximo 5 palabras. PROHIBIDO usar comillas " o saltos de línea.
2. 'renta': Solo números.
3. 'nivel_estudios': Solo usa los valores del Literal.

Si el usuario dice "2 millones", tu razonamiento debe ser: "Monto detectado en lenguaje natural". NADA MÁS.

INSTRUCCIONES:
1. Clasifica la `intencion` (DATO_FINANCIERO, PREGUNTA, SALUDO, OTRO).
    - PRIORIDAD ABSOLUTA: Si el usuario hace una pregunta, duda o pide una explicación (¿por qué?, ¿qué tiene que ver?, ¿cómo?), la intención DEBE ser 'PREGUNTA', incluso si también entrega datos.
2. Usa el campo `razonamiento` para explicar qué datos ves.
3. REGLAS DE CONVERSIÓN:
   - DINERO: "palo" = 1.000.000 | "luca" = 1.000.
   - ANTIGÜEDAD: Convierte siempre años a meses (ej: "1 año" = 12, "5 años" = 60).
   - ESTUDIOS (Instrucción de Inferencia):
     * Eres un experto en el mercado laboral chileno. 
     * Si el usuario menciona una profesión titulada (Ingeniero, Abogado, Médico, Psicólogo, etc.) o dice "soy titulado/graduado", clasifica automáticamente como UNIVERSITARIO.
     * No seas excesivamente conservador: una profesión implica estudios superiores.
     * Si el usuario menciona técnicos o centros de formación, clasifica automáticamente como TECNICO.
     * Si el usuario dice "Cuarto medio", "Escuela", "Licenciatura de enseñanza media" o "Terminé el colegio" -> Usa MEDIA.
     * Solo usa 'DESCONOCIDO' si el mensaje es un saludo o no tiene relación alguna con educación.
4. REGLA DE ORO: Si un dato numérico no está explícito, el valor DEBE ser 0.
5. Si el nivel de estudios no está, usa estrictamente 'DESCONOCIDO'.

EJEMPLO DORADO (es un ejemplo, las respuestas del usuario podrían ser parceladas y no incluir todos los datos de una vez, tienes que ser capaz de identificar los datos presentes y retornar un JSON con ellos, los que no estén presentes deben ser 0 o DESCONOCIDO según la regla de oro):
Usuario: "Gano 1.5 palos, soy contador y llevo 4 años en mi pega"
-> {
    "intencion": "DATO_FINANCIERO",
    "razonamiento": "Extraigo renta de 1.5M (1.5 palos), estudios universitarios (contador) y antigüedad de 48 meses (4 años).",
    "renta": 1500000,
    "antiguedad_laboral": 48,
    "nivel_estudios": "UNIVERSITARIO"
}
"""

# ── PROMPT LLAMADA B: GENERACIÓN ────────────────────────────────────────────
# Recibe contexto estructurado e inyecta personalidad Flux.
# La temperatura 0.7 lo hace variado y natural entre sesiones.

SYSTEM_PROMPT_GENERATION_PROFILE = """
Eres Flux, el genio amigable de las finanzas en Chile. 

PERSONALIDAD:
- Hablas de tú, eres cercano y usas modismos chilenos con moderación.
- Eres ágil: no das rodeos innecesarios, pero sí eres empático.
- Celebras cuando el usuario entrega datos (¡Buenazo!, ¡Perfecto!, ¡Anotado!).
- Si el usuario da información fuera de contexto, lo rediriges con gracia, sin regañar.

TAREA ACTUAL: Recolección de perfil financiero para una Cuenta Corriente.

RESTRICCIONES:
- NO inventes datos. Trabaja solo con lo que el contexto te provee.
- NO menciones números técnicos ni tasas en este paso (eso viene después).
- NO hagas más de UNA pregunta a la vez. Pide un dato, no tres.
- Máximo 3 oraciones en tu respuesta.

INSTRUCCIÓN PARA SOLICITAR NIVEL DE ESTUDIOS:
- Cuando falte el nivel de estudios, pídelo de forma casual sugiriendo opciones para ayudar al sistema.
- Ejemplo: "Oye, y para tu ficha, ¿cuál es tu nivel de estudios? (¿Universitario, técnico, tienes algún postgrado o media?). ¡Con eso ya estamos!"
- Si el ANÁLISIS TÉCNICO indica 'Error' en estudios, di: "¡Te escuché lo de [título/carrera]! Pero para que mi sistema no se maree, ¿me confirmas si eso es universitario o técnico?

MANEJO DE ERRORES Y AMBIGÜEDAD (CRÍTICO):
- Tu prioridad es que el usuario se sienta ESCUCHADO. 
- Si en el 'ANÁLISIS TÉCNICO' ves que hubo un problema (Error, duda, confusión), pero en el 'ÚLTIMO MENSAJE' ves que el usuario sí respondió, usa esa información.
- NUNCA digas "mi sistema falló" o "hubo un error técnico". 
- Usa frases como: 
    * "¡Buenísimo lo de [profesión]! Para que no se me escape nada, ¿me confirmas si eso cuenta como [categoría]?"
    * "Pucha, te entendí la idea pero me falta el detalle exacto: ¿cuánto sería tu renta líquida?"
    * "¡Te escuché clarito!, pero me perdí en la parte de [campo], ¿me lo repites?"

Si el usuario se ve frustrado o escribe en mayúsculas, mantén la calma, dale la razón ("¡Toda la razón, me traspapelé!") y pide el dato de la forma más sencilla posible.
"""

# ── ACCOUNT_INIT (account_init) ────────────────────────────

def account_init_node(state: FluxState) -> dict:
    """
    Nodo ACCOUNT_INIT: punto de entrada al flujo de Cuenta Corriente.

    ID LangGraph : account_init
    current_node : ACCOUNT_INIT   ← valor semántico para GPS y Supabase

    PROCESO:
        1. Handshake: Verificar que product_intent == "ACCOUNT".
        2. Reset: Limpiar account_profile.
        3. Saludo personalizado con datos de preparation_data.
        4. Actualizar semáforo: ACCOUNT_INIT / SUCCESS / PENDING.

    OUTPUT:
        - messages: Saludo de bienvenida al flujo de cuenta.
        - session["current_node"]: "ACCOUNT_INIT".
        - collecting_data["account_profile"]: {} (limpio).
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})

    nombre = prep.get("nombre", "")
    edad = prep.get("edad", 0)
    first_name = nombre.split()[0] if nombre else "amig@"

    product_intent = session.get("product_intent")
    application_id = session.get("application_id")

    if product_intent != "ACCOUNT":
        msg = "Hubo un error de navegación. Por favor, indica nuevamente qué necesitas."
        return {
            "messages": [AIMessage(content=msg)],
            "session": {**session, "current_node": "ACCOUNT_INIT"},
        }

    # ── Llamada Tipo B: Bienvenida dinámica al crédito ────────
    init_context = (
        f"Usuario: {first_name}, {edad} años.\n"
        f"Genera la bienvenida al proceso de Cuenta Corriente."
    )
    
    from langchain_core.messages import SystemMessage, HumanMessage
    flux_response = _flux_generator.invoke([
        SystemMessage(content=SYSTEM_PROMPT_INIT_ACCOUNT),
        HumanMessage(content=init_context),
    ])
    msg = normalize_llm_response(flux_response.content)

    # ── Semáforo ──────────────────────────────────────────────
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="ACCOUNT_INIT",
            node_status="SUCCESS",
            engine_status="PENDING",
        )

    # ── PUNTO DE GUARDADO: current_node → ACCOUNT_COLLECTING_PROFILE ──
    return {
        "messages": [],
        "session": {**session, "current_node": "ACCOUNT_COLLECTING_PROFILE"},
        "collecting_data": {
            "account_profile": {},
        },
    }

# ── 2. NODO DE RECOLECCION PERFIL (account_collecting_profile) ───────────────────────────────────

def account_collecting_profile_node(state: FluxState) -> dict:
    """
    Nodo ACCOUNT_COLLECTING_PROFILE: recolección del perfil financiero del usuario.
    
    ID LangGraph : account_collecting_profile
    current_node : account_collecting_profile
    
    ARQUITECTURA INTERNA — DOBLE LLAMADA:
    
      Llamada A (Extractor):
        - Modelo   : gemini-3-flash-preview, temperature=0.0, function_calling
        - Input    : Último mensaje del usuario
        - Output   : AccountProfileExtraction (JSON validado por Pydantic)
        - Objetivo : Extraer datos financieros. Clasificar intención.
                     Jamás genera texto conversacional.
    
      Llamada B (Generador) — Solo si se necesita emitir un mensaje:
        - Modelo   : gemini-3-flash-preview, temperature=0.7, texto libre
        - Input    : Contexto estructurado de _build_generation_context()
        - Output   : String con la respuesta de Flux
        - Objetivo : Generar respuesta con personalidad. No extrae datos.
    
    ATOMICIDAD:
        El nodo realiza un único return al final con todos los campos del State
        que modifica. No hay returns intermedios para garantizar consistencia
        con el checkpointer de LangGraph.
    
    AVANCE SILENCIOSO:
        Si el perfil está completo (missing == []), la Llamada B NO se invoca.
        El nodo retorna sin mensaje. El grafo avanza automáticamente al siguiente nodo.
    """
    # ------ 1. EXTRACCIÓN DE VARIABLES DEL STATE ------
    session = state.get("session", {})
    collecting = state.get("collecting_data", {})
    prep = state.get("preparation_data", {})
    messages = state.get("messages", [])
    
    current_profile = collecting.get("account_profile", {}) # datos previos
    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"
    application_id = session.get("application_id")

    extracted = None
    newly_extracted = {}

    # ------ 2. CAPTURA DEL ÚLTIMO MENSAJE DEL USUARIO ------
    last_user_msg = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
        ""
    )

    # Guardrail: si no hay mensaje del usuario, re-preguntar desde el estado actual
    if not last_user_msg.strip():
        missing = _get_missing_profile_fields(current_profile)
        context = _build_profile_generation_context(
            nombre=first_name,
            intencion="OTRO",
            known_profile=current_profile,
            missing=missing,
            newly_extracted={},
        )
        flux_response = _flux_generator.invoke([
            {"role": "system", "content": SYSTEM_PROMPT_GENERATION_PROFILE},
            {"role": "user",   "content": context},
        ])
        return {
            "messages":       [AIMessage(content=flux_response.content)],
            "collecting_data": {**collecting, "account_profile": current_profile},
            "session":        {**session, "current_node": "ACCOUNT_COLLECTING_PROFILE"},
        }

    # 3. ------ LLAMADA A - EXTRACCIÓN ------ 
    print(f"\n[DEBUG-PROFILE] Mensaje Usuario: '{last_user_msg}'")
    
    raw_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_EXTRACTION_PROFILE},
        {"role": "user",   "content": last_user_msg},
    ])

    # 1. Normalizamos el contenido
    content_str = normalize_llm_response(raw_response.content)
    
    # 2. Intentamos parsear el JSON manualmente para tener control
    import json
    import re

    match = re.search(r"\{.*\}", content_str, re.DOTALL)
    
    if match:
        try:
            json_str = match.group()
            data = json.loads(json_str)
            extracted = AccountProfileExtraction(**data)
        except Exception as e:
            print(f"[!!!] Error parseando JSON (Pydantic o JSON inválido): {e}")
            extracted = AccountProfileExtraction(
                intencion="OTRO",
                razonamiento=f"Error de validación, pero el LLM dijo: {content_str[:100]}",
                renta=0, antiguedad_laboral=0, nivel_estudios="DESCONOCIDO"
            )
    else:
        print(f"[!!!] No se encontró JSON en la respuesta. Contenido crudo: {content_str}")
        extracted = AccountProfileExtraction(
            intencion="OTRO",
            razonamiento="No se detectó formato JSON",
            renta=0, antiguedad_laboral=0, nivel_estudios="DESCONOCIDO"
        )

    # Ahora los prints son seguros porque 'extracted' nunca será None
    print(f"[DEBUG-PROFILE] LLM razonamiento: {extracted.razonamiento}")
    print(f"[DEBUG-PROFILE] LLM extraccion: renta={extracted.renta}, antiguedad={extracted.antiguedad_laboral}, estudios={extracted.nivel_estudios}")

    # ------ 4.  MERGE DEFENSIVO (Versión Elástica CP-08) ------
    newly_extracted = {}
    updated_profile = {**current_profile} # o updated_sim para el otro nodo

    if extracted.razonamiento != "Error":
        # Definimos qué valores NO son progreso (Centinelas)
        SENTINELS = [0, "0", "DESCONOCIDO", None, "null"]
        
        # Lista de campos a procesar (ajustar según el nodo)
        fields_to_process = ["renta", "antiguedad_laboral", "nivel_estudios"]

        for field in fields_to_process:
            val = getattr(extracted, field, None)
            
            # REGLA DE ORO: Solo actualizamos si el valor NO es un centinela
            # Esto evita que un "DESCONOCIDO" borre un dato que ya teníamos.
            if val not in SENTINELS:
                updated_profile[field] = val
                newly_extracted[field] = val


    # 5. ------ EVALUACIÓN DE COMPLETITUD ------
    missing = _get_missing_profile_fields(updated_profile)

    # 6. ------ PREPARAR OUTPUT BASE (siempre presente) ------ 
    output = {
        "collecting_data": {**collecting, "account_profile": updated_profile},
        "session":         {**session, "current_node": "ACCOUNT_COLLECTING_PROFILE"},
    }

    if last_user_msg and extracted and extracted.intencion == "PREGUNTA":
        # 1. Preparamos un estado temporal que ya incluya los datos recién extraídos
        # para que el Consultor los vea en su snapshot.
        temp_state = {**state, "collecting_data": {**collecting, "account_profile": updated_profile}}
        
        # 2. Obtenemos la respuesta del experto
        rag_response = get_consultant_response(last_user_msg, temp_state)
        
        # 3. Retornamos y esperamos la siguiente interacción del usuario
        output["messages"] = [AIMessage(content=rag_response)]
        return output

    # 7. ------ DECISIÓN: ¿Avance silencioso o Llamada B? ------
    if not missing:
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="ACCOUNT_COLLECTING_PROFILE",
                node_status="SUCCESS",
                engine_status="PENDING",
            )
        # ── ESCRITURA DUAL de flags ───────────────────────────────
        # 1. Histórica (persistente): el ruteador sabrá que el perfil está completo
        current_progress = session.get("progress", {})
        account_progress = current_progress.get("account", {})
        updated_progress = {
            **current_progress,
            "account": {**account_progress, "profile_completed": True},
        }
        # 2. Volátil (1 turno): señal para el nodo destino del salto intra-turno
        output["session"] = {
            **output["session"],
            "progress":           updated_progress,
            "just_completed_step": CompletedStep.ACCOUNT_PROFILE,
            # current_node ya está en "ACCOUNT_COLLECTING_PROFILE" desde output base
        }
        return output  # Sin mensajes: la arista condicional saltará a account_evaluation_engine
    
    # 8. ------ LLAMADA B - GENERACIÓN ------
    context = _build_profile_generation_context(
        nombre=first_name,
        intencion=extracted.intencion,
        known_profile=updated_profile,
        missing=missing,
        newly_extracted=newly_extracted,last_msg=last_user_msg,          # <--- Nuevo
        razonamiento=extracted.razonamiento # <--- Nuevo
    )

    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_GENERATION_PROFILE},
        {"role": "user",   "content": context},
    ])

    # Normalizar ANTES de guardar en el State
    clean_content = normalize_llm_response(flux_response.content)

    # Si después de todo sigue vacío, aplicamos el fallback de seguridad
    if not clean_content:
        clean_content = f"¡Oye {first_name}! Me perdí un poquito. ¿Podrías repetirme esa parte sobre tu {missing[0]}?"

    # 9. ------ RETURN TRANSACCIONAL ------
    # Un único return con todos los cambios al State.
    output["messages"] = [AIMessage(content=clean_content)]
    return output

# ── ACCOUNT_EVALUATION_ENGINE (account_evaluation_engine) ────

def account_evaluation_engine_node(state: FluxState) -> dict:
    """
    Nodo ACCOUNT_EVALUATION_ENGINE: motor de evaluación para cuenta corriente.

    ID LangGraph : account_evaluation_engine
    current_node : ACCOUNT_EVALUATION_ENGINE   ← valor semántico para GPS y Supabase

    INPUT (State leído):
        - state["collecting_data"]["account_profile"]: renta, antiguedad_laboral, nivel_estudios
        - state["preparation_data"]["edad"]: edad del usuario

    PROCESO:
        1. Extraer inputs de los namespaces correctos.
        2. Invocar al motor de evaluación comercial (modules/account_eng.py).
        3. Escribir todos los outputs en evaluation_results["account_engine"].
        4. Actualizar semáforo: ACCOUNT_EVALUATION_ENGINE / SUCCESS / COMPLETED.

    OUTPUT:
        - evaluation_results["account_engine"]: Resultado completo del motor.
        - session["current_node"]: "ACCOUNT_EVALUATION_ENGINE".

    NOTA ARQUITECTURA:
        Wrapper de flujo. La lógica de categorización está delegada a
        modules/account_eng.py para asegurar testabilidad.
    """
    session = state.get("session", {})
    prep = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})

    account_profile = collecting.get("account_profile", {})
    renta = account_profile.get("renta", 0)
    antiguedad_laboral = account_profile.get("antiguedad_laboral", 0)
    nivel_estudios = account_profile.get("nivel_estudios", "")
    edad = prep.get("edad", 0)

    # TODO Fase 3: engine_result = account_eng.calculate_account_category(...)
    engine_result = {
        "status_proceso": "PRE_APPROVED",
        "is_elegible": True,
        "base_category": "ADVANCE",
        "final_category": "ADVANCE",
        "has_upgrade": False,
        "credit_line_amount": 500000,
        "monthly_cost": 0,
        "motivo_rechazo": None,
    }

    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="ACCOUNT_EVALUATION_ENGINE",
            node_status="SUCCESS",
            engine_status="COMPLETED",
        )

    return {
        "evaluation_results": {
            "account_engine": engine_result,
        },
        "session": {**session, "current_node": "ACCOUNT_EVALUATION_ENGINE"},
    }

# ======================================================================================================
# HELPERS DEL FLUJO DE ACCOUNT
# ======================================================================================================

# ── Obtener campos faltantes del perfil | v2.1 — añade validación de valores centinela del LLM
def _get_missing_profile_fields(profile: dict) -> list[str]:
    """
    Retorna lista de campos del perfil que faltan o tienen valores inválidos.
    
    REGLAS:
      - None siempre es faltante.
      - renta <= 0: imposible semánticamente (0 y negativos son centinela del LLM).
      - antiguedad_laboral < 0: -1 es valor centinela clásico del LLM para int ausente.
      - nivel_estudios fuera del Literal: valor no reconocido.
    
    NOTA: Esta función NO aplica reglas de negocio (renta mínima $500k, etc.).
    Eso es responsabilidad exclusiva del EvaluationEngine. Aquí solo se filtran
    datos técnicamente imposibles.
    
    v2.1 — Añadida validación de valores centinela (0, -1) del LLM.
    """
    missing = []
    
    renta = profile.get("renta")
    if renta is None or renta <= 0:
        missing.append("renta")
    
    ant = profile.get("antiguedad_laboral")
    if ant is None or ant < 0:
        missing.append("antiguedad_laboral")
    
    estudios = profile.get("nivel_estudios")
    valid_estudios = {"POSTGRADO", "UNIVERSITARIO", "TECNICO", "MEDIA"}
    if estudios is None or estudios not in valid_estudios:
        missing.append("nivel_estudios")
    
    return missing

# ── Construir el contexto para la Llamada B (generador) para nodo ACCOUNT_COLLECTING_PROFILE ──────────────
def _build_profile_generation_context(
    nombre: str,
    intencion: str,
    known_profile: dict,
    missing: list[str],
    newly_extracted: dict,
    last_msg: str = "",
    razonamiento: str = ""
) -> str:
    """
    Construye el bloque de contexto estructurado para la Llamada B (generador).
    
    El generador NO recibe el historial de mensajes crudos ni el resultado
    del extractor directamente. Recibe este resumen pre-digerido para que
    pueda enfocarse en generar la respuesta correcta sin reinterpretar datos.
    
    INPUT:
        nombre          : Primer nombre del usuario (desde preparation_data).
        intencion       : Resultado de la Llamada A ("SALUDO", "PREGUNTA", etc.)
        known_profile   : Datos ya en el State ANTES de este turno.
        missing         : Lista de campos que faltan (resultado de _get_missing_profile_fields).
        newly_extracted : Campos que se extrajeron en ESTE turno (para que Flux los comente).
    
    OUTPUT: String formateado listo para inyectar como HumanMessage al generador.
    """
    # Etiquetas amigables para mostrar al generador
    field_labels = {
        "renta":              "renta líquida mensual",
        "antiguedad_laboral": "antigüedad laboral",
        "nivel_estudios":     "nivel de estudios",
    }
    
    # Construir sección de datos conocidos (para que Flux no los repida)
    known_lines = []
    for field, label in field_labels.items():
        value = known_profile.get(field)
        if value is not None:
            if field == "renta":
                known_lines.append(f"  - {label}: ${value:,} CLP")
            elif field == "antiguedad_laboral":
                known_lines.append(f"  - {label}: {value} meses")
            else:
                known_lines.append(f"  - {label}: {value.capitalize()}")
    
    # Construir sección de datos nuevos (para que Flux los celebre)
    new_lines = []
    for field, value in newly_extracted.items():
        if value is not None and field in field_labels:
            label = field_labels[field]
            if field == "renta":
                new_lines.append(f"  - {label}: ${value:,} CLP")
            elif field == "antiguedad_laboral":
                new_lines.append(f"  - {label}: {value} meses")
            else:
                new_lines.append(f"  - {label}: {value.capitalize()}")
    
    # Construir sección de datos faltantes
    missing_labels = [field_labels[f] for f in missing]
    
    context = f"""
    --- ENTRADA ACTUAL ---
    ÚLTIMO MENSAJE DEL USUARIO: "{last_msg}"
    ANÁLISIS DEL EXTRACTOR: {razonamiento}

    CONTEXTO PARA TU RESPUESTA:
    --- ENTRADA ACTUAL ---
    Usuario: {nombre}
    Intención detectada en su último mensaje: {intencion}

    DATOS RECIÉN EXTRAÍDOS (Confírmalos si aparecen aquí):
    {chr(10).join(new_lines) if new_lines else "  - (ninguno nuevo detectado)"}

    DATOS QUE YA TENÍAMOS:
    {chr(10).join(known_lines) if known_lines else "  - (ninguno aún)"}

    DATOS QUE FALTAN (Prioridad):
    {chr(10).join(f"  - {l}" for l in missing_labels) if missing_labels else "  - (perfil completo)"}

    INSTRUCCIÓN DE FLUJO: Genera la respuesta de Flux según este contexto. 
    1. Si el ANÁLISIS TÉCNICO indica que el usuario entregó un dato pero hay dudas (ej: "Error", "No estoy seguro", "Formato inválido"), NO digas que te mareaste. Di algo como: "Oye, te escuché lo de [dato], pero para dejarlo impecable en tu ficha, ¿me confirmas si es [valor]?" o pídelo de nuevo amablemente.
    2. Si hay datos en 'DATOS RECIÉN EXTRAÍDOS', celébralos brevemente.
    3. Pide solo el primer dato de la lista 'DATOS QUE FALTAN'.
    4. Si la intención es SALUDO u OTRO, responde con empatía y redirige amablemente a pedir el primer dato faltante.
    5. Si la intención es PREGUNTA, reconoce la duda brevemente y redirige al proceso.
    """
    return context
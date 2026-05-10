"""
app/graph/nodes/deposit.py
─────────────────────────────────────────────────────────────
Nodos del flujo de Depósito a Plazo.

Ruta del grafo: dap_init → dap_investment_engine → END
  - dap_init              (ID LangGraph) → current_node = "DAP_INIT"
  - dap_investment_engine  (ID LangGraph) → current_node = "DAP_INVESTMENT_ENGINE"
"""

from langchain_core.messages import AIMessage, HumanMessage
from app.graph.state import FluxState
from app.infra.gemini_client import get_structured_model, get_generation_model
from app.graph.nodes.schemas.deposit_schemas import DapDataExtraction, DapDecisionExtraction, DapOTPExtraction
from app.modules.dap_eng import DapEngine, PolicyRejectionError
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
_params_extractor = get_structured_model(DapDataExtraction)
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
# ── PROMPT DE BIENVENIDA AL PRODUCTO (dap_init_node) ────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────────────────

# ── PROMPT LLAMADA B: GENERACIÓN ────────────────────────────────────────────
# Recibe contexto estructurado e inyecta personalidad Flux.
# La temperatura 0.7 lo hace variado y natural entre sesiones.

SYSTEM_PROMPT_INIT_DAP = """
Eres Flux, el genio amigable de las finanzas en Chile.

PERSONALIDAD:
- Hablas de tú, eres cercano y usas modismos chilenos con moderación.
- Eres ágil y empático: no das rodeos, pero sí transmites calidez.

TAREA ACTUAL: Dar la bienvenida al usuario al proceso de Depósito a Plazo.
Esta es la PRIMERA vez que el usuario entra al flujo de Depósito a Plazo.

RESTRICCIONES CRÍTICAS:
- Máximo 2 oraciones.
- Tu respuesta DEBE terminar pidiendo el monto a invertir y la moneda.
- NO menciones tasas, CAE ni otros detalles técnicos en este paso.
- NO repitas el saludo de bienvenida general (ya fue hecho antes).
- Varía 
"""

# ─────────────────────────────────────────────────────────────────────────────────────────
# ── PROMPTS DE EXTRACCIÓN EN NODOS COLLECTING ────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────────────────

# ── PROMPT LLAMADA A: EXTRACCIÓN ────────────────────────────────────────────
# Directivo y sin ambigüedad. Temperatura 0.0 hace el trabajo pesado;
# el prompt solo establece el contrato de qué retornar.

SYSTEM_PROMPT_EXTRACTION_PARAMS = """
Eres un motor de extracción de datos financieros. Tu ÚNICA misión es analizar el mensaje del usuario y retornar un JSON estructurado VÁLIDO.

REGLAS DE FORMATO:
- NO uses bloques de código Markdown (prohibido usar ```json).
- El campo 'razonamiento' debe ser una sola frase corta sin comillas internas.
- Los números deben ser enteros puros (sin puntos ni comas).

REGLAS DE RAZONAMIENTO:
1. 'razonamiento': Escribe máximo 5 palabras. PROHIBIDO usar comillas " o saltos de línea.
2. 'monto': Solo números.
3. 'plazo': Solo números en días.
4. 'moneda': Solo usa los valores del Literal.

Si el usuario dice "2 millones", tu razonamiento debe ser: "Monto detectado en lenguaje natural". NADA MÁS.

INSTRUCCIONES:
1. Clasifica la `intencion` (DATO_FINANCIERO, PREGUNTA, SALUDO, OTRO).
    - PRIORIDAD ABSOLUTA: Si el usuario hace una pregunta, duda o pide una explicación (¿por qué?, ¿qué tiene que ver?, ¿cómo?), la intención DEBE ser 'PREGUNTA', incluso si también entrega datos.
2. Usa el campo `razonamiento` para explicar qué datos ves.
3. REGLAS DE CONVERSIÓN:
   - DINERO: "palo" = 1.000.000 | "luca" = 1.000.
   - PLAZO: Convierte siempre, "años", "meses" y/o "semanas" a días (ej: "1 mes" = 30, "6 meses" = 180, "2 años" = 730, "3 semanas" = 21).
   - MONEDA (Instrucción de Inferencia):
     * Analiza símbolos y palabras clave para determinar la divisa exacta.
     * "pesos", "$", "CLP", "palos", "lucas", "gambas" -> CLP.
     * "dólares", "USD", "US$", "U$D", "verdes" -> USD.
     * "UF", "unidades de fomento", "fomento" -> UF.
     * Si el usuario solo dice un número (ej: "quiero invertir 500.000") sin mencionar moneda, usa 'DESCONOCIDO' (esto obligará al sistema a preguntar para estar seguros).
4. REGLA DE ORO: Si un dato numérico (monto o plazo) no está explícito, el valor DEBE ser 0.
5. Si la moneda no está definida o es ambigua, usa estrictamente 'DESCONOCIDO'.

EJEMPLO DORADO (es un ejemplo, las respuestas del usuario podrían ser parceladas y no incluir todos los datos de una vez, tienes que ser capaz de identificar los datos presentes y retornar un JSON con ellos, los que no estén presentes deben ser 0 o DESCONOCIDO según la regla de oro):
Usuario: "Quiero meter 1,5 millones de pesos a 1 mes plazo"
-> {
    "intencion": "DATO_FINANCIERO",
    "razonamiento": "Extraigo monto de 1.5M (1,5 millones), moneda indicada CLP (pesos) y plazo de 30 días (1 mes).",
    "monto": 1500000,
    "plazo": 30,
    "moneda": "CLP"
}
"""

# ── PROMPT LLAMADA B: GENERACIÓN ────────────────────────────────────────────
# Recibe contexto estructurado e inyecta personalidad Flux.
# La temperatura 0.7 lo hace variado y natural entre sesiones.

SYSTEM_PROMPT_GENERATION_PARAMS = """
Eres Flux, el genio amigable de las finanzas en Chile. 

PERSONALIDAD:
- Hablas de tú, eres cercano y usas modismos chilenos con moderación.
- Eres ágil: no das rodeos innecesarios, pero sí eres empático.
- Celebras cuando el usuario entrega datos (¡Buenazo!, ¡Perfecto!, ¡Anotado!).
- Si el usuario da información fuera de contexto, lo rediriges con gracia, sin regañar.

TAREA ACTUAL: Recolección de parámetros de inversión para un Depósito a Plazo.

RESTRICCIONES:
- NO inventes datos. Trabaja solo con lo que el contexto te provee.
- NO menciones números técnicos ni tasas en este paso (eso viene después).
- NO hagas más de UNA pregunta a la vez. Pide un dato, no tres.
- Máximo 3 oraciones en tu respuesta.

INSTRUCCIÓN PARA SOLICITAR MONEDA:
- Cuando falte la moneda, pídelo de forma casual sugiriendo opciones para ayudar al sistema.
- Ejemplo: "Oye, y para que tu inversión quede tiqui taca, ¿en qué moneda quieres hacer el depósito? (¿pesos, dólares, UF?). ¡Con eso ya estamos!"
- Si el ANÁLISIS TÉCNICO indica 'Error' en moneda, di: "¡Te escuché lo de [moneda]! Pero para que mi sistema no se maree, ¿me confirmas si te refieres a CLP, USD o UF?"

MANEJO DE ERRORES Y AMBIGÜEDAD (CRÍTICO):
- Tu prioridad es que el usuario se sienta ESCUCHADO. 
- Si en el 'ANÁLISIS TÉCNICO' ves que hubo un problema (Error, duda, confusión), pero en el 'ÚLTIMO MENSAJE' ves que el usuario sí respondió, usa esa información.
- NUNCA digas "mi sistema falló" o "hubo un error técnico". 
- Usa frases como: 
    * "¡Buenísimo lo de [divisa]! Para que no se me escape nada, ¿me confirmas si eso cuenta como [moneda]?"
    * "Pucha, te entendí la idea pero me falta el detalle exacto: ¿cuánto sería el monto que quieres invertir entonces?"
    * "¡Te escuché clarito!, pero me perdí en la parte de [plazo], ¿me lo repites?"

Si el usuario se ve frustrado o escribe en mayúsculas, mantén la calma, dale la razón ("¡Toda la razón, me traspapelé!") y pide el dato de la forma más sencilla posible.
"""

# ── DAP_INIT (dap_init) ────────────────────────────

def dap_init_node(state: FluxState) -> dict:
    """
    Nodo DAP_INIT: punto de entrada al flujo de Depósito a Plazo.

    ID LangGraph : dap_init
    current_node : DAP_INIT   ← valor semántico para GPS y Supabase

    PROCESO:
        1. Handshake: Verificar que product_intent == "DAP".
        2. Reset: Limpiar dap_params.
        3. Saludo personalizado con datos de preparation_data.
        4. Actualizar semáforo: DAP_INIT / SUCCESS / PENDING.

    OUTPUT:
        - messages: Saludo de bienvenida al flujo de depósito a plazo.
        - session["current_node"]: "DAP_INIT".
        - collecting_data["dap_params"]: {} (limpio).
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})

    nombre = prep.get("nombre", "")
    edad = prep.get("edad", 0)
    first_name = nombre.split()[0] if nombre else "amig@"

    product_intent = session.get("product_intent")
    application_id = session.get("application_id")

    if product_intent != "DAP":
        msg = "Hubo un error de navegación. Por favor, indica nuevamente qué necesitas."
        return {
            "messages": [AIMessage(content=msg)],
            "session": {**session, "current_node": "DAP_INIT"},
        }

    # ── Llamada Tipo B: Bienvenida dinámica al Depósito a Plazo ────────
    init_context = (
        f"Usuario: {first_name}, {edad} años.\n"
        f"Genera la bienvenida al proceso de Depósito a Plazo."
    )
    
    from langchain_core.messages import SystemMessage, HumanMessage
    flux_response = _flux_generator.invoke([
        SystemMessage(content=SYSTEM_PROMPT_INIT_DAP),
        HumanMessage(content=init_context),
    ])
    msg = normalize_llm_response(flux_response.content)

    # ── Semáforo ──────────────────────────────────────────────
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="DAP_INIT",
            node_status="SUCCESS",
            engine_status="PENDING",
        )

    # ── PUNTO DE GUARDADO: current_node → DAP_COLLECTING_DATA ──
    return {
        "messages": [],
        "session": {**session, "current_node": "DAP_COLLECTING_DATA"},
        "collecting_data": {
            "dap_params": {},
        },
    }

# ── 2. DAP_COLLECT_DATA (dap_collect_data) ────────────────────────────
def dap_collect_data_node(state: FluxState) -> dict:
    """
    Nodo DAP_COLLECT_DATA: recolección de los parámetros de inversión (monto, plazo, moneda).
    
    ID LangGraph : dap_collect_data
    current_node : DAP_COLLECTING_DATA
    
    ARQUITECTURA INTERNA — DOBLE LLAMADA:
    
      Llamada A (Extractor):
        - Modelo   : gemini-3-flash-preview, temperature=0.0, function_calling
        - Input    : Último mensaje del usuario
        - Output   : DapDataExtraction (JSON validado por Pydantic)
        - Objetivo : Extraer monto, plazo y moneda. Clasificar intención.
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
        Si los datos están completos (missing == []), la Llamada B NO se invoca.
        El nodo retorna sin mensaje. El grafo avanza automáticamente al siguiente nodo.
    """
    # ------ 1. EXTRACCIÓN DE VARIABLES DEL STATE ------
    session = state.get("session", {})
    collecting = state.get("collecting_data", {})
    prep = state.get("preparation_data", {})
    messages = state.get("messages", [])
    
    current_params = collecting.get("dap_params", {}) # datos previos
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
        missing = _get_missing_params_fields(current_params)
        context = _build_params_generation_context(
            nombre=first_name,
            intencion="OTRO",
            known_params=current_params,
            missing=missing,
            newly_extracted={},
        )
        flux_response = _flux_generator.invoke([
            {"role": "system", "content": SYSTEM_PROMPT_GENERATION_PARAMS},
            {"role": "user",   "content": context},
        ])
        return {
            "messages":       [AIMessage(content=flux_response.content)],
            "collecting_data": {**collecting, "dap_params": current_params},
            "session":        {**session, "current_node": "DAP_COLLECTING_DATA"},
        }

    # 3. ------ LLAMADA A - EXTRACCIÓN ------ 
    print(f"\n[DEBUG-PROFILE] Mensaje Usuario: '{last_user_msg}'")
    
    raw_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_EXTRACTION_PARAMS},
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
            extracted = DapDataExtraction(**data)
        except Exception as e:
            print(f"[!!!] Error parseando JSON (Pydantic o JSON inválido): {e}")
            extracted = DapDataExtraction(
                intencion="OTRO",
                razonamiento=f"Error de validación, pero el LLM dijo: {content_str[:100]}",
                monto=0.0, plazo=0, moneda="DESCONOCIDO"
            )
    else:
        print(f"[!!!] No se encontró JSON en la respuesta. Contenido crudo: {content_str}")
        extracted = DapDataExtraction(
            intencion="OTRO",
            razonamiento="No se detectó formato JSON",
            monto=0.0, plazo=0, moneda="DESCONOCIDO"
        )

    # Ahora los prints son seguros porque 'extracted' nunca será None
    print(f"[DEBUG-PARAMS] LLM razonamiento: {extracted.razonamiento}")
    print(f"[DEBUG-PARAMS] LLM extraccion: monto={extracted.monto}, plazo={extracted.plazo}, moneda={extracted.moneda}")

    # ------ 4.  MERGE DEFENSIVO (Versión Elástica CP-08) ------
    newly_extracted = {}
    updated_params = {**current_params} # o updated_sim para el otro nodo

    if extracted.razonamiento != "Error":
        # Definimos qué valores NO son progreso (Centinelas)
        SENTINELS = [0, 0.0, "0", "DESCONOCIDO", None, "null"]
        
        # Lista de campos a procesar
        fields_to_process = ["monto", "plazo", "moneda"]

        for field in fields_to_process:
            val = getattr(extracted, field, None)
            
            # REGLA DE ORO: Solo actualizamos si el valor NO es un centinela
            # Esto evita que un "DESCONOCIDO" borre un dato que ya teníamos.
            if val not in SENTINELS:
                updated_params[field] = val
                newly_extracted[field] = val


    # 5. ------ EVALUACIÓN DE COMPLETITUD ------
    missing = _get_missing_params_fields(updated_params)

    # 6. ------ PREPARAR OUTPUT BASE (siempre presente) ------ 
    output = {
        "collecting_data": {**collecting, "dap_params": updated_params},
        "session":         {**session, "current_node": "DAP_COLLECTING_DATA"},
    }

    if last_user_msg and extracted and extracted.intencion == "PREGUNTA":
        # 1. Preparamos un estado temporal que ya incluya los datos recién extraídos
        # para que el Consultor los vea en su snapshot.
        temp_state = {**state, "collecting_data": {**collecting, "dap_params": updated_params}}
        
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
                current_node_id="DAP_COLLECTING_DATA",
                node_status="SUCCESS",
                engine_status="PENDING",
            )
        # ── ESCRITURA DUAL de flags ───────────────────────────────
        # 1. Histórica (persistente): el ruteador sabrá que el perfil está completo
        current_progress = session.get("progress", {})
        dap_progress = current_progress.get("dap", {})
        updated_progress = {
            **current_progress,
            "dap": {**dap_progress, "data_completed": True},
        }
        # 2. Volátil (1 turno): señal para el nodo destino del salto intra-turno
        output["session"] = {
            **output["session"],
            "progress":           updated_progress,
            "just_completed_step": CompletedStep.DAP_DATA,
            # current_node ya está en "DAP_COLLECTING_DATA" desde output base
        }
        return output  # Sin mensajes: la arista condicional saltará a dap_investment_engine
    
    # 8. ------ LLAMADA B - GENERACIÓN ------
    context = _build_params_generation_context(
        nombre=first_name,
        intencion=extracted.intencion,
        known_params=updated_params,
        missing=missing,
        newly_extracted=newly_extracted,last_msg=last_user_msg,
        razonamiento=extracted.razonamiento
    )

    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_GENERATION_PARAMS},
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


def dap_investment_engine_node(state: FluxState) -> dict:
    """
    Nodo DAP_INVESTMENT_ENGINE: motor de cálculo de inversión.

    ID LangGraph : dap_investment_engine
    current_node : DAP_INVESTMENT_ENGINE   ← valor semántico para GPS y Supabase

    INPUT (State leído):
        - state["collecting_data"]["dap_params"]: monto, moneda, plazo
        - state["preparation_data"]["edad"]: edad del usuario

    PROCESO:
        1. Extracción de parámetros desde el namespace 'dap_params'.
        2. Invocación al módulo de lógica financiera (modules/dap_eng.py).
           Nota: dap_eng integra indicadores externos (UF/IPC/USD) vía eco_service.py.
        3. Persistencia atómica de resultados en evaluation_results["dap_engine"].

    OUTPUT:
        - evaluation_results["dap_engine"]: Resultado completo.
        - session["current_node"]: "DAP_INVESTMENT_ENGINE".

    NOTA ARQUITECTURA:
    Este nodo es un wrapper de flujo. La complejidad del cálculo (tasas, proyecciones
    y conversión de moneda) está delegada a módulos externos para asegurar 
    testabilidad y desacoplamiento de APIs económicas.
    """
    # 1. ------ PREPARACIÓN DE DATOS ------
    session    = state.get("session", {})
    prep       = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})
    evaluation_results = state.get("evaluation_results", {})
    dap_params = collecting.get("dap_params", {})

    try:
        # 2. ------ LLAMADA AL MOTOR REAL ------
        engine = DapEngine(
            preparation_data=prep,
            dap_params=dap_params,
        )
        engine_result = engine.run()

    except PolicyRejectionError as e:
        # Caso: Rechazo por Edad, Renta o Antigüedad
        engine_result = {
            "status_proceso":       "REJECTED",
            "is_elegible":          False,
            "conversion_rate_used": engine.conversion_rate_used,
            "ipc_applied":          engine.ipc_applied,
            "term_premium":         engine.term_premium,
            "monthly_rate_total":   0.0,
            "period_rate":          0.0,
            "estimated_gain":       0.0,
            "total_return":         0.0,
            "motivo_rechazo":       e.motivo
        }

    except Exception as e:
        # Error técnico inesperado
        print(f"[ERROR-ENGINE] Fallo crítico: {str(e)}")
        engine_result = {
            "status_proceso": "ERROR",
            "motivo_rechazo": "ERR_INTERNAL",
        }

    # 3. ------ PERSISTENCIA Y SEMÁFOROS ------
    application_id = session.get("application_id")
    if application_id:
        engine_status = "SUCCESS" if engine_result["status_proceso"] != "ERROR" else "FAILED"
        update_application_semaphores(
            application_id=application_id,
            current_node_id="DAP_INVESTMENT_ENGINE",
            node_status="SUCCESS",
            engine_status=engine_status,
        )

    # 4. ------ SELECCIÓN DE FLAG DE SALIDA ------
    status = engine_result.get("status_proceso")
    if status == "PRE_APPROVED":
        completion_flag = CompletedStep.DAP_INVESTMENT_SUCCESS
        # Actualizar Progreso Histórico (Persistencia para ruteo P1)
        current_progress = session.get("progress", {})
        dap_progress = current_progress.get("dap", {})
        session["progress"] = {
            **current_progress,
            "dap": {**dap_progress, "investment_engine_completed": True}
        }
    else:
        # Cubre REJECTED y ERROR
        completion_flag = CompletedStep.DAP_INVESTMENT_REJECTED

    return {
        "evaluation_results": {
            **evaluation_results,
            "dap_engine": engine_result # <-- Namespace DAP
        },
        "session": {
            **session,
            "just_completed_step": completion_flag,
        }
    }

    return {
        "evaluation_results": {
            **evaluation_results,
            "dap_engine": engine_result
        },
        "session": {
            **session,
            "just_completed_step": CompletedStep.DAP_INVESTMENT_SUCCESS,
        }
    }

import datetime as _dt  # Alias para evitar colisión con nombres de variables locales

# ======================================================================================================
# HELPERS DEL FLUJO DE DAP
# ======================================================================================================

# ── Obtener campos faltantes de parámetros del DAP | v2.1 — añade validación de valores centinela del LLM
def _get_missing_params_fields(params: dict) -> list[str]:
    """
    Retorna lista de campos de parámetro del DAP que faltan o tienen valores inválidos.
    
    REGLAS:
      - None siempre es faltante.
      - monto <= 0: centinela del LLM para monto ausente.
      - plazo <= 0: centinela del LLM para plazo ausente.
      - moneda fuera del Literal: valor no reconocido.
    
    NOTA: Esta función NO aplica reglas de negocio.
    Eso es responsabilidad exclusiva del InvestmentEngine. Aquí solo se filtran
    datos técnicamente imposibles.
    
    v2.1 — Añadida validación de valores centinela (0, -1) del LLM.
    """
    missing = []
    
    monto = params.get("monto")
    if monto is None or monto <= 0:
        missing.append("monto")
    
    plazo = params.get("plazo")
    if plazo is None or plazo <= 0:
        missing.append("plazo")
    
    moneda = params.get("moneda")
    valid_moneda = {"CLP", "UF", "USD"}
    if moneda is None or moneda not in valid_moneda:
        missing.append("moneda")
    
    return missing

# ── Construir el contexto para la Llamada B (generador) para nodo DAP_COLLECTING_DATA ──────────────
def _build_params_generation_context(
    nombre: str,
    intencion: str,
    known_params: dict,
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
        known_params    : Datos ya en el State ANTES de este turno.
        missing         : Lista de campos que faltan (resultado de _get_missing_params_fields).
        newly_extracted : Campos que se extrajeron en ESTE turno (para que Flux los comente).
    
    OUTPUT: String formateado listo para inyectar como HumanMessage al generador.
    """
    # Etiquetas amigables para mostrar al generador
    field_labels = {
        "monto":              "monto del deposito",
        "plazo":              "plazo del deposito",
        "moneda":             "moneda del deposito",
    }
    
    # Construir sección de datos conocidos (para que Flux no los repida)
    known_lines = []
    
    # 1. Obtener moneda una sola vez para todo el contexto
    # Priorizamos la recién extraída, si no, la que ya teníamos, si no, CLP.
    moneda_contexto = newly_extracted.get("moneda") or known_params.get("moneda") or "CLP"

    for field, label in field_labels.items():
        value = known_params.get(field)
        if value is not None:
            if field == "monto":
                known_lines.append(f"  - {label}: ${value:,} {moneda_contexto}")
            elif field == "plazo":
                known_lines.append(f"  - {label}: {value} días")
            else:
                known_lines.append(f"  - {label}: {value.capitalize()}")
    
    # Construir sección de datos nuevos (para que Flux los celebre)
    new_lines = []
    for field, value in newly_extracted.items():
        if value is not None and field in field_labels:
            label = field_labels[field]
            if field == "monto":
                new_lines.append(f"  - {label}: ${value:,} {moneda_contexto}")
            elif field == "plazo":
                new_lines.append(f"  - {label}: {value} días")
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
    {chr(10).join(f"  - {l}" for l in missing_labels) if missing_labels else "  - (todos los parámetros listos)"}

    INSTRUCCIÓN DE FLUJO: Genera la respuesta de Flux según este contexto. 
    1. Si el ANÁLISIS TÉCNICO indica que el usuario entregó un dato pero hay dudas (ej: "Error", "No estoy seguro", "Formato inválido"), NO digas que te mareaste. Di algo como: "Oye, te escuché lo de [dato], pero para dejarlo impecable en tu ficha, ¿me confirmas si es [valor]?" o pídelo de nuevo amablemente.
    2. Si hay datos en 'DATOS RECIÉN EXTRAÍDOS', celébralos brevemente.
    3. Pide solo el primer dato de la lista 'DATOS QUE FALTAN'.
    4. Si la intención es SALUDO u OTRO, responde con empatía y redirige amablemente a pedir el primer dato faltante.
    5. Si la intención es PREGUNTA, reconoce la duda brevemente y redirige al proceso.
    """
    return context
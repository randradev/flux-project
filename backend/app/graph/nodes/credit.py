"""
app/graph/nodes/credit.py
─────────────────────────────────────────────────────────────
Nodos del flujo de Crédito de Consumo.

Ruta del grafo: loan_init → loan_risk_engine → END
  - loan_init        (ID LangGraph) → current_node = "LOAN_INIT"
  - loan_risk_engine  (ID LangGraph) → current_node = "LOAN_RISK_ENGINE"
"""

from langchain_core.messages import AIMessage, HumanMessage
from app.infra.gemini_client import get_structured_model, get_generation_model
from app.graph.state import FluxState
from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction, LoanSimExtraction
from app.infra.supabase import update_application_semaphores
from app.modules.credit_eng import CreditEngine, PolicyRejectionError, PaymentCapacityError
from app.utils.llm_utils import normalize_llm_response
from app.graph.constants import CompletedStep
from langchain_core.outputs import LLMResult
from app.modules.consultant import get_consultant_response

# ======================================================================================================
# LLM Y PROMPTS
# ======================================================================================================

# ── CONFIGURACIÓN DE INTELIGENCIA (SINGLETONS) ──────────────
# Singletons de modelos (se instancian una vez al importar el módulo)
_profile_extractor = get_structured_model(LoanProfileExtraction)
_sim_extractor     = get_structured_model(LoanSimExtraction)
_flux_generator    = get_generation_model()  # NUEVO — Llamada B

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
# ── PROMPT DE BIENVENIDA AL PRODUCTO (loan_init_node) ────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────────────────

# ── PROMPT LLAMADA B: GENERACIÓN ────────────────────────────────────────────
# Recibe contexto estructurado e inyecta personalidad Flux.
# La temperatura 0.7 lo hace variado y natural entre sesiones.

SYSTEM_PROMPT_INIT_LOAN = """
Eres Flux, el genio amigable de las finanzas en Chile.

PERSONALIDAD:
- Hablas de tú, eres cercano y usas modismos chilenos con moderación.
- Eres ágil y empático: no das rodeos, pero sí transmites calidez.

TAREA ACTUAL: Dar la bienvenida al usuario al proceso de Crédito de Consumo.
Esta es la PRIMERA vez que el usuario entra al flujo de crédito.

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

SYSTEM_PROMPT_EXTRACTION_SIM = """
Eres un motor de extracción de datos financieros. Tu función es analizar el mensaje del usuario y retornar un JSON estructurado.

INSTRUCCIONES:
1. Clasifica la `intencion` (DATO_FINANCIERO, PREGUNTA, SALUDO, OTRO).
    - PRIORIDAD ABSOLUTA: Si hay una consulta, duda o pregunta sobre plazos, montos o límites (ej: "¿hay límite?", "¿puedo pedir más?"), marca 'PREGUNTA' aunque también indique el monto o cuotas.
2. Usa el campo `razonamiento` para explicar qué datos ves en el mensaje. Si un dato no está, decláralo ahí (ej: "No se menciona monto").
3. Basándote en ese razonamiento, llena los campos `monto_solicitado` y `plazo_solicitado`. 
4. REGLA DE ORO: Si el dato no está explícito, el valor DEBE ser 0. 
   Prohibido inventar o inferir montos. 
   RECUERDA: Si no lo dice -> 0.
EJEMPLO:
Usuario: "En 12 cuotas"
-> {
    "intencion": "DATO_FINANCIERO",
    "razonamiento": "El usuario indica 12 cuotas pero no menciona monto.",
    "monto_solicitado": 0,
    "plazo_solicitado": 12
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

TAREA ACTUAL: Recolección de perfil financiero para un Crédito de Consumo.

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

SYSTEM_PROMPT_GENERATION_SIM = """
Eres Flux, el genio amigable de las finanzas en Chile.

PERSONALIDAD:
- Hablas de tú, eres cercano y usas modismos chilenos con moderación.
- Eres ágil: no das rodeos innecesarios, pero sí eres empático.
- Celebras cuando el usuario entrega datos (¡Buenazo!, ¡Perfecto!, ¡Anotado!).
- Si el usuario da información fuera de contexto, lo rediriges con gracia, sin regañar.
- Si el contexto indica que el perfil se completó, evita saludos de inicio ("Hola", "Qué gusto") y usa frases de transición ("¡Excelente!, con eso listo...", "¡Perfecto!, ya tenemos tu perfil...").

TAREA ACTUAL: Recolección de monto y plazo del crédito.

RESTRICCIONES:
- NO inventes datos. Trabaja solo con lo que el contexto te provee.
- NO menciones números técnicos ni tasas en este paso (eso viene después).
- NO hagas más de UNA pregunta a la vez. Pide un dato, no tres.
- Máximo 3 oraciones en tu respuesta.

MANEJO DE ERRORES Y AMBIGÜEDAD (CRÍTICO):
- Tu prioridad es que el usuario se sienta ESCUCHADO. 
- Si en el 'ANÁLISIS TÉCNICO' ves que hubo un problema (Error, duda, confusión), pero en el 'ÚLTIMO MENSAJE' ves que el usuario sí respondió, usa esa información.
- NUNCA digas "mi sistema falló" o "hubo un error técnico". 
- Usa frases como: 
    * "¡Te escuché lo de las lucas, pero me perdí la cifra exacta! Para estar seguros, ¿cuánta plata necesitas pedir exactamente?"
    * "Pucha, te entendí la idea pero me falta el detalle exacto: ¿en cuántos meses quieres pagarlo?"
    * "¡Te escuché clarito!, pero me perdí en la parte de [campo], ¿me lo repites?"

Si el usuario se ve frustrado o escribe en mayúsculas, mantén la calma, dale la razón ("¡Toda la razón, me traspapelé!") y pide el dato de la forma más sencilla posible.
"""

SYSTEM_PROMPT_GENERATION_PRE_APPROVED = """
Eres Flux, el genio amigable de las finanzas en Chile. 

PERSONALIDAD:
- Hablas de tú, eres cercano y usas modismos chilenos con moderación.
- Eres ágil: no das rodeos innecesarios, pero sí eres empático.
- Si el contexto indica que el crédito se aprobó justo ahora (AVISO), usa frases de celebración y éxito ("¡Lo logramos!", "¡Noticias espectaculares!").
- Si el contexto no indica un aviso nuevo (RE-PREGUNTA), evita celebrar de nuevo o saludar; asume que el usuario ya conoce su oferta y responde directo a su duda.

TAREA ACTUAL: Gestión de la oferta de crédito pre-aprobada.

RESTRICCIONES:
- Máximo 3 oraciones en tu respuesta.
- No repitas los números técnicos en el texto (ya están en la tarjeta).
- Refuerza SIEMPRE que la decisión (Aceptar/Rechazar) se toma exclusivamente con los botones de la tarjeta de transparencia. No aceptamos texto para formalizar.

MANEJO DE DUDAS:
- Si el usuario pregunta cómo proceder o qué hacer, indícale con mucha gracia que debe usar los botones de la tarjeta de abajo para que la aceptación sea oficial.
"""

# ======================================================================================================
# NODOS DEL FLUJO DE CREDITO DE CONSUMO
# ======================================================================================================

# ── 1. NODO INICIAL (loan_init) ───────────────────────────────────

def loan_init_node(state: FluxState) -> dict:
    """
    Nodo LOAN_INIT: punto de entrada al flujo de Crédito de Consumo.

    ID LangGraph : loan_init
    current_node : LOAN_INIT   ← valor semántico para GPS y Supabase

    INPUT (State):
        - state["preparation_data"]: Datos del usuario (nombre, rut, mail, edad).
        - state["session"]: Para verificar product_intent == "LOAN".
        - state["collecting_data"]["loan_profile"]: Se limpiará (reset).
        - state["collecting_data"]["loan_sim"]: Se limpiará (reset).

    PROCESO:
        1. Handshake: Verificar que product_intent == "LOAN".
        2. Reset: Limpiar loan_profile y loan_sim.
        3. Saludo personalizado con datos de preparation_data.
        4. Actualizar semáforo: LOAN_COLLECTING_INIT / SUCCESS / PENDING.

    OUTPUT (campos del State que modifica):
        - messages: Saludo de bienvenida al flujo de crédito.
        - session["current_node"]: "LOAN_COLLECTING_PROFILE".
        - collecting_data["loan_profile"]: {} (limpio).
        - collecting_data["loan_sim"]: {} (limpio).

    CAMBIOS vs 2.0:
      - Eliminado: string fijo de bienvenida.
      - Agregado: Llamada Tipo B al LLM para generar bienvenida dinámica.
      - Agregado: current_node se actualiza a LOAN_COLLECTING_PROFILE
        inmediatamente (sincronización del "Punto de Guardado").

    PUNTO DE GUARDADO:
      Este nodo actualiza current_node a "LOAN_COLLECTING_PROFILE" (no "LOAN_INIT")
      antes de retornar, para que en el siguiente renacimiento del grafo,
      route_after_welcome dirija al nodo de recolección directamente.
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})

    nombre = prep.get("nombre", "")
    edad = prep.get("edad", 0)
    first_name = nombre.split()[0] if nombre else "amig@"

    product_intent = session.get("product_intent")
    application_id = session.get("application_id")

    if product_intent != "LOAN":
        msg = "Hubo un error de navegación. Por favor, indica nuevamente qué necesitas."
        return {
            "messages": [AIMessage(content=msg)],
            "session": {**session, "current_node": "LOAN_INIT"},
        }

    # ── Llamada Tipo B: Bienvenida dinámica al crédito ────────
    init_context = (
        f"Usuario: {first_name}, {edad} años.\n"
        f"Genera la bienvenida al proceso de Crédito de Consumo y pide la renta líquida mensual."
    )
    
    from langchain_core.messages import SystemMessage, HumanMessage
    flux_response = _flux_generator.invoke([
        SystemMessage(content=SYSTEM_PROMPT_INIT_LOAN),
        HumanMessage(content=init_context),
    ])
    msg = normalize_llm_response(flux_response.content)

    # ── Semáforo ──────────────────────────────────────────────
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_INIT",
            node_status="SUCCESS",
            engine_status="PENDING",
        )

    # ── PUNTO DE GUARDADO: current_node → LOAN_COLLECTING_PROFILE ──
    # Registramos el destino del SIGUIENTE turno, no el nodo actual.
    # Esto garantiza que tras el renacimiento del grafo, route_after_welcome
    # dirija directamente a loan_collecting_profile sin pasar por loan_init de nuevo.
    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "LOAN_COLLECTING_PROFILE"},
        "collecting_data": {
            "loan_profile": {},
            "loan_sim": {},
        },
    }


# ── 2. NODO DE RECOLECCION PERFIL (loan_collecting_profile) ───────────────────────────────────

def loan_collecting_profile_node(state: FluxState) -> dict:
    """
    Nodo LOAN_COLLECTING_PROFILE: recolección del perfil financiero del usuario.
    
    ID LangGraph : loan_collecting_profile
    current_node : LOAN_COLLECTING_PROFILE
    
    ARQUITECTURA INTERNA — DOBLE LLAMADA:
    
      Llamada A (Extractor):
        - Modelo   : gemini-3-flash-preview, temperature=0.0, function_calling
        - Input    : Último mensaje del usuario
        - Output   : LoanProfileExtraction (JSON validado por Pydantic)
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
    
    current_profile = collecting.get("loan_profile", {}) # datos previos
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
            "collecting_data": {**collecting, "loan_profile": current_profile},
            "session":        {**session, "current_node": "LOAN_COLLECTING_PROFILE"},
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
            extracted = LoanProfileExtraction(**data)
        except Exception as e:
            print(f"[!!!] Error parseando JSON (Pydantic o JSON inválido): {e}")
            extracted = LoanProfileExtraction(
                intencion="OTRO",
                razonamiento=f"Error de validación, pero el LLM dijo: {content_str[:100]}",
                renta=0, antiguedad_laboral=0, nivel_estudios="DESCONOCIDO"
            )
    else:
        print(f"[!!!] No se encontró JSON en la respuesta. Contenido crudo: {content_str}")
        extracted = LoanProfileExtraction(
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
        "collecting_data": {**collecting, "loan_profile": updated_profile},
        "session":         {**session, "current_node": "LOAN_COLLECTING_PROFILE"},
    }

    if last_user_msg and extracted and extracted.intencion == "PREGUNTA":
        # 1. Preparamos un estado temporal que ya incluya los datos recién extraídos
        # para que el Consultor los vea en su snapshot.
        temp_state = {**state, "collecting_data": {**collecting, "loan_profile": updated_profile}}
        
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
                current_node_id="LOAN_COLLECTING_PROFILE",
                node_status="SUCCESS",
                engine_status="PENDING",
            )
        # ── ESCRITURA DUAL de flags ───────────────────────────────
        # 1. Histórica (persistente): el ruteador sabrá que el perfil está completo
        current_progress = session.get("progress", {})
        loan_progress = current_progress.get("loan", {})
        updated_progress = {
            **current_progress,
            "loan": {**loan_progress, "profile_completed": True},
        }
        # 2. Volátil (1 turno): señal para el nodo destino del salto intra-turno
        output["session"] = {
            **output["session"],
            "progress":           updated_progress,
            "just_completed_step": CompletedStep.LOAN_PROFILE,
            # current_node ya está en "LOAN_COLLECTING_PROFILE" desde output base
        }
        return output  # Sin mensajes: la arista condicional saltará a loan_collecting_sim
    
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
            
# ── 3. NODO DE RECOLECCION MONTO Y PLAZO (loan_collecting_simulation) ───────────────────────────────────

def loan_collecting_sim_node(state: FluxState) -> dict:
    """
    VERSIÓN 2.2 — Nodo LOAN_COLLECTING_SIMULATION con Ruteo Consciente.

    CAMBIOS vs 2.1:
      - Detecta salto intra-turno via just_completed_step == LOAN_PROFILE.
      - Omite Llamada A en caso de salto (no hay mensaje nuevo del usuario).
      - Lee just_completed_step en lugar de profile_just_completed (deprecated).
      - Limpia just_completed_step en el return post-Llamada B.
      - Escribe escritura dual al completar la simulación.
    """
    session    = state.get("session", {})
    collecting = state.get("collecting_data", {})
    prep       = state.get("preparation_data", {})
    messages   = state.get("messages", [])

    just_completed = session.get("just_completed_step")   # ← v2.2
    is_intra_turn_jump = (just_completed == CompletedStep.LOAN_PROFILE)

    current_sim = collecting.get("loan_sim", {})
    first_name  = prep.get("nombre", "").split()[0] if prep.get("nombre") else "amig@"

    newly_extracted = {}
    updated_sim = {**current_sim}
    extracted = None

    last_user_msg = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), ""
    )

    # ── LLAMADA A: solo si NO es salto intra-turno ────────────
    # Si venimos de un salto, el last_user_msg ya fue procesado por el nodo de perfil.
    
    newly_extracted = {}
    updated_sim = {**current_sim}
    
    if not is_intra_turn_jump and last_user_msg:
        # ------ 3. LLAMADA A - EXTRACCIÓN ROBUSTA ------
        print(f"\n[DEBUG-SIM] Mensaje Usuario: '{last_user_msg}'")
        
        raw_response = _flux_generator.invoke([
            {"role": "system", "content": SYSTEM_PROMPT_EXTRACTION_SIM},
            {"role": "user",   "content": last_user_msg},
        ])

        content_str = normalize_llm_response(raw_response.content)
        
        import json
        import re

        # Intento de parseo manual con Regex
        match = re.search(r"\{.*\}", content_str, re.DOTALL)
        
        if match:
            try:
                json_str = match.group()
                data = json.loads(json_str)
                extracted = LoanSimExtraction(**data)
            except Exception as e:
                print(f"[!!!] Error parseando JSON en SIM: {e}")
                extracted = LoanSimExtraction(intencion="OTRO", razonamiento="Error")
        else:
            print(f"[!!!] No se encontró JSON en SIM.")
            extracted = LoanSimExtraction(intencion="OTRO", razonamiento="Error")

        print(f"[DEBUG-SIM] Intención: {extracted.intencion}")
        print(f"[DEBUG-SIM] Razonamiento: {extracted.razonamiento}")

        # ------ 4. MERGE DEFENSIVO ------
        if extracted.razonamiento != "Error":
            # Definimos qué valores NO son progreso (Centinelas)
            SENTINELS = [0, "0", "DESCONOCIDO", None, "null"]
            fields_to_process = ["monto_solicitado", "plazo_solicitado"]

            for field in fields_to_process:
                val = getattr(extracted, field, None)
                # Solo actualizamos si el valor NO es un centinela
                if val not in SENTINELS:
                    updated_sim[field] = val
                    newly_extracted[field] = val

            intencion_for_b = extracted.intencion
            razonamiento_for_b = extracted.razonamiento
        else:
            intencion_for_b = "OTRO"
            razonamiento_for_b = f"Error de formato, LLM dijo: {content_str[:50]}"

    else:
        # Salto intra-turno o mensaje vacío
        intencion_for_b = "DATO_FINANCIERO"
        razonamiento_for_b = "Salto intra-turno desde perfil completo o inicio."

    # ── EVALUACIÓN DE COMPLETITUD ─────────────────────────────
    missing = _get_missing_sim_fields(updated_sim)

    # ── OUTPUT BASE ───────────────────────────────────────────
    output = {
        "collecting_data": {**collecting, "loan_sim": updated_sim},
        "session": {
            **session,
            "current_node": "LOAN_COLLECTING_SIMULATION",
            "just_completed_step": None,   # ← Limpieza anticipada (se sobreescribirá si sim completa)
        },
    }

    if last_user_msg and extracted and extracted.intencion == "PREGUNTA":
        # 1. Preparamos el estado temporal con los datos de simulación (monto/plazo)
        # que el usuario pudo haber entregado en el mismo mensaje.
        temp_state = {**state, "collecting_data": {**collecting, "loan_sim": updated_sim}}
        
        # 2. Obtenemos la respuesta del Consultor
        rag_response = get_consultant_response(last_user_msg, temp_state)
        
        # 3. Retornamos y detenemos el flujo para esperar al usuario
        output = {
            "collecting_data": {**collecting, "loan_sim": updated_sim},
            "session":         {**session, "current_node": "LOAN_COLLECTING_SIMULATION"},
            "messages":        [AIMessage(content=rag_response)]
        }
        return output

    # ── AVANCE SILENCIOSO (simulación completa) ───────────────
    if not missing:
        application_id = session.get("application_id")
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="LOAN_COLLECTING_SIMULATION",
                node_status="SUCCESS",
                engine_status="PENDING", # Sigue PENDING porque aún no corre el motor
            )

        current_progress = session.get("progress", {})
        loan_progress = current_progress.get("loan", {})
        output["session"] = {
            **output["session"],
            "progress": {
                **current_progress,
                "loan": {**loan_progress, "simulation_completed": True},
            },
            "just_completed_step": CompletedStep.LOAN_SIMULATION,
        }
        return output

    # ── LLAMADA B ─────────────────────────────────────────────
    context = _build_sim_generation_context(
        nombre=first_name,
        intencion=intencion_for_b,
        known_sim=updated_sim,
        missing=missing,
        newly_extracted=newly_extracted,
        just_completed_step=just_completed,   # ← v2.2: reemplaza profile_just_completed
        last_msg=last_user_msg,
        razonamiento=razonamiento_for_b,
    )

    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_GENERATION_SIM},
        {"role": "user",   "content": context},
    ])

    clean_content = normalize_llm_response(flux_response.content)

    # Si después de todo sigue vacío, aplicamos el fallback de seguridad
    if not clean_content:
        clean_content = f"¡Oye {first_name}! Me perdí un poquito. ¿Podrías repetirme esa parte sobre tu {missing[0]}?"

    output["messages"] = [AIMessage(content=clean_content)]
    # just_completed_step ya se limpió en output base (= None): no reasignar aquí.
    # La Llamada B ya lo consumió; la flag no debe sobrevivir al siguiente turno.

    return output


# ── 4. NODO DE CÁLCULO DE RIESGO (loan_risk_engine) ───────────────────────

def loan_risk_engine_node(state: FluxState) -> dict:
    """
    Nodo LOAN_RISK_ENGINE: motor de riesgo para crédito de consumo.

    ID LangGraph : loan_risk_engine
    current_node : LOAN_RISK_ENGINE   ← valor semántico para GPS y Supabase

    INPUT (State leído):
        - state["collecting_data"]["loan_profile"]: renta, antiguedad_laboral, nivel_estudios
        - state["collecting_data"]["loan_sim"]: monto_solicitado, plazo_solicitado
        - state["preparation_data"]["edad"]: edad del usuario

    PROCESO:
        1. Extraer inputs de los namespaces correctos.
        2. Invocar al motor de scoring y cálculo financiero (modules/credit_eng.py).
        3. Escribir todos los outputs en evaluation_results["loan_engine"].
        4. Actualizar semáforo: LOAN_RISK_ENGINE / SUCCESS / COMPLETED.

    OUTPUT (campos del State que modifica):
        - evaluation_results["loan_engine"]: Resultado completo del motor.
        - session["current_node"]: "LOAN_RISK_ENGINE".

    NOTA ARQUITECTURA:
        Este nodo es un wrapper de flujo. La lógica de cálculo pesada debe residir
        en módulos independientes (modules/credit_eng.py) para facilitar tests unitarios.
    """
    # 1. ------ PREPARACIÓN DE DATOS ------
    session    = state.get("session", {})
    prep       = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})
    evaluation_results = state.get("evaluation_results", {})
    loan_profile = collecting.get("loan_profile", {})
    loan_sim     = collecting.get("loan_sim", {})

    try:
        # 2. ------ LLAMADA AL MOTOR REAL ------
        engine = CreditEngine(
            preparation_data=prep,
            loan_profile=loan_profile,
            loan_sim=loan_sim
        )
        engine_result = engine.run()

    except PolicyRejectionError as e:
        # Caso: Rechazo por Edad, Renta o Antigüedad
        engine_result = {
            "status_proceso": "REJECTED",
            "motivo_rechazo": e.motivo,
            "capacidad_pago_valida": True, 
            "monto_aprobado": 0,
            "plazo_aprobado": 0
        }

    except PaymentCapacityError as e:
        # Caso: La cuota supera el 30% de la renta
        engine_result = {
            "status_proceso": "REJECTED",
            "motivo_rechazo": "ERR_CAPACIDAD_PAGO",
            "capacidad_pago_valida": False,
            "cuota_mensual": e.cuota_calculada,
            "cuota_maxima_permitida": e.cuota_maxima,
            "monto_aprobado": 0,
            "plazo_aprobado": 0
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
            current_node_id="LOAN_RISK_ENGINE",
            node_status="SUCCESS",
            engine_status=engine_status,
        )

    # 4. ------ SELECCIÓN DE FLAG DE SALIDA ------
    status = engine_result.get("status_proceso")
    if status == "PRE_APPROVED":
        completion_flag = CompletedStep.LOAN_RISK_SUCCESS
        # Actualizar Progreso Histórico (Persistencia para ruteo P1)
        current_progress = session.get("progress", {})
        loan_progress = current_progress.get("loan", {})
        session["progress"] = {
            **current_progress,
            "loan": {**loan_progress, "risk_engine_completed": True}
        }
    else:
        # Cubre REJECTED y ERROR
        completion_flag = CompletedStep.LOAN_RISK_REJECTED

    return {
        "evaluation_results": {
            **evaluation_results,
            "loan_engine": engine_result
        },
        "session": {
            **session,
            "just_completed_step": completion_flag,
        }
    }

    return {
        "evaluation_results": {
            **evaluation_results,
            "loan_engine": engine_result
        },
        "session": {
            **session,
            "just_completed_step": CompletedStep.LOAN_RISK_ENGINE,
        }
    }

import datetime as _dt  # Alias para evitar colisión con nombres de variables locales


# ──────────────────────────────────────────────────────────────────────────────────────
# LOAN_PRE_APPROVED — Muestra la Tarjeta de Transparencia al usuario
# ──────────────────────────────────────────────────────────────────────────────────────

def loan_pre_approved_node(state: FluxState) -> dict:
    """
    Stub: LOAN_PRE_APPROVED.

    Responsabilidades finales:
      - Leer evaluation_results["loan_engine"] y formatear la oferta.
      - Mostrar la Tarjeta de Transparencia (monto, plazo, cuota, CAE, CTC).
      - Esperar la decisión del usuario (ACCEPTED / REJECTED).
      - Si ACCEPTED: setear just_completed_step = LOAN_PRE_APPROVED
                     y escribir offer_data["loan"]["pre_approval_status"] = "ACCEPTED".
      - Si REJECTED: setear just_completed_step = LOAN_CLOSED_BY_USER.
    """
    # 1. ------ Recolectar Datos Iniciales ------
    raw_session = state.get("session", {})
    just_completed = raw_session.get("just_completed_step")
    session = {**raw_session, "just_completed_step": None}

    prep       = state.get("preparation_data", {})
    messages   = state.get("messages", [])
    nombre     = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    # 2. ------ Detección de Salto Intra-turno (Viene de loan_risk_engine) ------
    is_intra_turn_jump = (just_completed == CompletedStep.LOAN_RISK_SUCCESS)
    
    # 3. ------ Leer resultados del motor
    engine_result = state.get("evaluation_results", {}).get("loan_engine", {})
    
    # Datos para cálculos y visualización
    monto   = engine_result.get("monto_aprobado", 0)
    cuota   = engine_result.get("cuota_mensual", 0)
    plazo   = engine_result.get("plazo_aprobado", 0)
    cae     = engine_result.get("cae", 0.0)
    ctc     = engine_result.get("ctc", 0)
    tasa    = engine_result.get("tasa_interes_mensual", 0.0)
    riesgo  = engine_result.get("nivel_riesgo", "Bajo")
    interes = engine_result.get("total_intereses", 0)


    # 4. ------ LLAMADA A: PROCESAMIENTO DE DECISIÓN ------
    user_decision = "PENDING"  # Por defecto
    last_user_msg = ""

    if not is_intra_turn_jump:
        # Capturamos el último mensaje del usuario
        last_user_msg = next(
            (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), 
            ""
        ).strip().upper()

        # Lógica de detección (puede robustecerse con el Extractor si se desea, 
        # pero para botones/comandos simples basta con keywords)
        if last_user_msg in ["ACEPTAR", "ACEPTO", "SI", "ACEPTA"]:
            user_decision = "ACCEPTED"
        elif last_user_msg in ["RECHAZAR", "RECHAZO", "NO", "RECHAZA"]:
            user_decision = "REJECTED"
        else:
            # El usuario dijo algo que no es una decisión clara
            user_decision = "PENDING"


    # 5. ------ EVALUACIÓN DE ESTADO DE OFERTA (Paso 2.4) ------
    application_id = session.get("application_id")

    # Inicializamos el output base con los metadatos de sesión
    output = {
        "session": {
            **session,
            "current_node": "LOAN_PRE_APPROVED",
            "just_completed_step": None, # Limpieza por defecto
        }
    }
    
    if user_decision == "ACCEPTED":
        # A. Actualizar Progreso Histórico
        current_progress = session.get("progress", {})
        loan_progress = current_progress.get("loan", {})
        updated_progress = {
            **current_progress,
            "loan": {**loan_progress, "pre_approval_accepted": True},
        }

        # B. Actualizar Semáforo en DB
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="LOAN_PRE_APPROVED",
                node_status="SUCCESS",
                engine_status="SUCCESS",
            )

        # C. Output de Éxito con "Foto" congelada de la oferta
        output["session"] = {
            **output["session"],
            "progress": updated_progress,
            "just_completed_step": CompletedStep.LOAN_PRE_APPROVED
        }
        
        # Guardamos la data exacta que el usuario aceptó
        output["offer_data"] = {
            "loan": {
                "pre_approval_status": "ACCEPTED",
                "timestamp_acceptance": _dt.datetime.utcnow().isoformat(),
                "monto_aprobado":       monto,
                "plazo_aprobado":       plazo,
                "cuota_mensual":        cuota,
                "cae":                  cae,
                "ctc":                  ctc,
                "tasa_interes_mensual": tasa,
            }
        }
        return output

    elif user_decision == "REJECTED":
        # Al rechazar, también informamos al semáforo (pero con estado final o similar)
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="LOAN_PRE_APPROVED",
                node_status="SUCCESS",
                engine_status="SUCCESS", # El motor ya hizo su parte
            )
        output["session"]["just_completed_step"] = CompletedStep.LOAN_CLOSED_BY_USER
        return output

    # Si estamos en PENDING (mostrando la tarjeta por primera vez o re-preguntando), 
    # opcionalmente puedes actualizar el semáforo para decir que el nodo está "IN_PROGRESS"

    # 6. ------ LLAMADA B: GENERACIÓN (Paso 2.5) ------
    # Si llegamos aquí, user_decision es "PENDING"
    
    # A. Construir contexto usando el helper desacoplado (Paso 3)
    context = _build_pre_approved_generation_context(
        nombre=first_name,
        just_completed_step=just_completed,
        engine_result=engine_result,
        last_msg=last_user_msg
    )

    print(f"\n[DEBUG-LOGIC] just_completed: {just_completed}")

    # B. Llamada al LLM usando el prompt constante (Paso 4)
    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_GENERATION_PRE_APPROVED},
        {"role": "user",   "content": context},
    ])

    clean_content = normalize_llm_response(flux_response.content)

    # C. Preparar data para la Tarjeta de Transparencia (Namespace J)
    # Formateamos los datos para que la UI los muestre bonitos
    transparency_card = {
        "loan": {
            "monto_aprobado":       f"${monto:,} CLP",
            "plazo_aprobado":       f"{plazo} meses",
            "tasa_interes_mensual": f"{tasa:.2%}",
            "cuota_mensual":        f"${cuota:,} CLP",
            "ctc":                 f"${ctc:,} CLP",
            "total_intereses":      f"${interes:,} CLP",
            "cae":                 f"{cae:.2%}",
            "nivel_riesgo":         riesgo
        }
    }

    # 7. ------ SALIDA CONSISTENTE (Paso 2.6) ------
    
    # Preparamos el mensaje de Flux
    output["messages"] = [AIMessage(content=clean_content)]
    
    # Sincronizamos el Namespace J (Transparency)
    # Importante: Mantenemos la estructura de segmentación por producto
    current_transparency = state.get("transparency_data", {})
    output["transparency_data"] = {
        **current_transparency,
        "loan": transparency_card["loan"] 
    }
    
    # Actualizamos metadatos de visualización en la sesión
    output["session"] = {
        **output["session"],
        "display_control": {
            "active_component": "LOAN_TRANSPARENCY_CARD",
            "show_full_details": True
        }
    }

    # MARTILLAZO DE LIMPIEZA FINAL:
    output["session"]["just_completed_step"] = None 

    return output

# ======================================================================================================
# STUBS (v3.0)
# ======================================================================================================
# Cada stub cumple el contrato mínimo:
#   1. Actualizar session["current_node"] con el valor UPPER correspondiente.
#   2. Limpiar session["just_completed_step"] (flag volátil de turno anterior).
#   3. Retornar el estado con los campos modificados.
#
# La lógica de negocio completa se implementará en sprints posteriores.
# ======================================================================================================

# ──────────────────────────────────────────────────────────────────────────────────────
# LOAN_OTP_VALIDATION — Validación del código enviado por email
# ──────────────────────────────────────────────────────────────────────────────────────

def loan_otp_validation_node(state: FluxState) -> dict:
    """
    Stub: LOAN_OTP_VALIDATION.

    Responsabilidades finales:
      - Al entrar por primera vez: generar el OTP (6 dígitos) y enviarlo por email.
      - Leer auth_control["otp_user_input"] del turno actual.
      - Comparar con auth_control["otp_generated"].
      - Si coincide: setear just_completed_step = LOAN_OTP_SUCCESS.
      - Si falla y intentos < 3: incrementar otp_attempts, pedir reintento.
      - Si falla y intentos == 3: setear just_completed_step = LOAN_SECURITY_BLOCK.
    """
    session      = state.get("session", {})
    auth_control = state.get("auth_control", {})
    nombre       = state.get("preparation_data", {}).get("nombre", "")
    mail         = state.get("preparation_data", {}).get("mail", "")

    # STUB: Simula validación exitosa para pruebas de ruteo.
    # ─── REEMPLAZAR por lógica real en Sprint correspondiente ───
    just_completed = CompletedStep.LOAN_OTP_SUCCESS  # stub: siempre válido
    mensaje = (
        f"✅ ¡Código verificado, {nombre}! "
        "Estamos generando tu contrato..."
    )
    # ────────────────────────────────────────────────────────────

    from langchain_core.messages import AIMessage
    return {
        "session": {
            **session,
            "current_node":      "LOAN_OTP_VALIDATION",
            "previous_node":     session.get("current_node"),
            "just_completed_step": just_completed,
        },
        "auth_control": {
            **auth_control,
            "otp_attempts": auth_control.get("otp_attempts", 0),
        },
        "messages": [AIMessage(content=mensaje)],
    }


# ──────────────────────────────────────────────────────────────────────────────────────
# LOAN_FORMALIZATION — Generación y Sellado del Contrato PDF
# ──────────────────────────────────────────────────────────────────────────────────────

def loan_formalization_node(state: FluxState) -> dict:
    """
    Stub: LOAN_FORMALIZATION.

    Responsabilidades finales:
      - Recopilar datos del motor (monto, plazo, cuota, tasa) y del usuario (nombre, rut).
      - Generar el PDF del contrato con ReportLab.
      - Calcular hash SHA-256 del PDF generado.
      - Escribir en offer_data["loan"]: file_contrato_path, hash_sha256, contract_status.
      - Si SIGNED_AND_STAMPED: continuar a loan_completed (via edge fijo).
      - Si GENERATION_FAILED: redirigir a SERVICE_ERROR (futuro).
    """
    session = state.get("session", {})

    # STUB: Simula contrato generado exitosamente.
    # ─── REEMPLAZAR por lógica real (ReportLab + hashlib) ───────
    fake_path   = "/tmp/contrato_stub.pdf"
    fake_hash   = "a" * 64  # SHA-256 de 64 hex chars
    contract_ok = True
    # ────────────────────────────────────────────────────────────

    from langchain_core.messages import AIMessage
    return {
        "session": {
            **session,
            "current_node":      "LOAN_FORMALIZATION",
            "previous_node":     session.get("current_node"),
            "just_completed_step": None,  # Nodo de servicio: no emite CompletedStep propio
        },
        "offer_data": {
            "loan": {
                **state.get("offer_data", {}).get("loan", {}),
                "file_contrato_path": fake_path,
                "hash_sha256":        fake_hash,
                "contract_status":    "SIGNED_AND_STAMPED" if contract_ok else "GENERATION_FAILED",
            }
        },
        "messages": [AIMessage(content="📄 Contrato generado. Procesando cierre...")],
    }


# ──────────────────────────────────────────────────────────────────────────────────────
# LOAN_COMPLETED — Estado Final Exitoso
# ──────────────────────────────────────────────────────────────────────────────────────

def loan_completed_node(state: FluxState) -> dict:
    """
    Stub: LOAN_COMPLETED.

    Responsabilidades finales:
      - Leer offer_data["loan"] y construir el mensaje de felicitaciones.
      - Escribir flow_result con status_code = "SUCCESS".
      - Poblar offer_data["loan"]["display_data"] para el Frontend.
      - Limpiar current_node (flujo terminado).
    """
    session    = state.get("session", {})
    nombre     = state.get("preparation_data", {}).get("nombre", "")
    offer      = state.get("offer_data", {}).get("loan", {})
    file_url   = offer.get("file_contrato_path", "")
    sha256     = offer.get("hash_sha256", "")
    engine     = state.get("evaluation_results", {}).get("loan_engine", {})
    monto      = engine.get("monto_aprobado", 0)

    mensaje = (
        f"🥳 ¡Felicitaciones, {nombre}! Tu **Crédito de Consumo** de "
        f"**${monto:,} CLP** está formalizado.\n\n"
        f"📥 [Descarga tu contrato]({file_url})\n"
        f"🔐 Hash de seguridad: `{sha256[:16]}...`"
    )

    from langchain_core.messages import AIMessage
    return {
        "session": {
            **session,
            "current_node":      "LOAN_COMPLETED",
            "previous_node":     session.get("current_node"),
            "just_completed_step": None,
        },
        "flow_result": {
            "status_code":  "SUCCESS",
            "close_reason": None,
            "product_name": "Crédito de Consumo",
            "closed_at":    _dt.datetime.utcnow().isoformat(),
        },
        "offer_data": {
            "loan": {
                **offer,
                "display_data": {
                    "download_url":  file_url,
                    "main_detail":   f"Monto: ${monto:,} CLP",
                    "security_hash": sha256,
                    "reason":        None,
                }
            }
        },
        "messages": [AIMessage(content=mensaje)],
    }

# ======================================================================================================
# STUBS — NODOS MANEJO DE ERRORES Y EXCEPCIONES (v3.0)
# ======================================================================================================

# ──────────────────────────────────────────────────────────────────────────────────────
# LOAN_REJECTED_POLICY — Rechazo por Política de Crédito
# ──────────────────────────────────────────────────────────────────────────────────────

_REJECTION_MESSAGES = {
    "ERR_EDAD":           "lamentablemente necesitas ser mayor de 18 años para solicitar un crédito con nosotros",
    "ERR_RENTA":          "tu renta declarada está por debajo del mínimo que requerimos para este producto",
    "ERR_ANTIGUEDAD":     "necesitas al menos 6 meses de antigüedad laboral para calificar",
    "ERR_SCORING":        "tu perfil de riesgo actual no cumple los requisitos de nuestra política de crédito",
    "ERR_CAPACIDAD_PAGO": "la cuota mensual supera el 30% de tu renta, por lo que no podemos aprobar esta solicitud",
}

def loan_rejected_policy_node(state: FluxState) -> dict:
    """
    Stub: LOAN_REJECTED_POLICY.

    Responsabilidades finales:
      - Leer evaluation_results["loan_engine"]["motivo_rechazo"].
      - Generar un mensaje de rechazo empático y personalizado.
      - Escribir flow_result con status_code = "REJECTED".
      - Poblar offer_data["loan"]["display_data"]["reason"].
    """
    session = state.get("session", {})
    nombre  = state.get("preparation_data", {}).get("nombre", "")
    engine  = state.get("evaluation_results", {}).get("loan_engine", {})
    motivo  = engine.get("motivo_rechazo", "ERR_SCORING")

    razon_legible = _REJECTION_MESSAGES.get(
        motivo,
        "tu solicitud no pudo ser aprobada en este momento"
    )
    mensaje = (
        f"😔 {nombre}, revisamos tu información con cuidado y, "
        f"{razon_legible}.\n\n"
        "No te desanimes: puedes volver a intentarlo cuando tu situación cambie. "
        "¡Acá vamos a estar!"
    )

    from langchain_core.messages import AIMessage
    return {
        "session": {
            **session,
            "current_node":      "LOAN_REJECTED_POLICY",
            "previous_node":     session.get("current_node"),
            "just_completed_step": None,
        },
        "flow_result": {
            "status_code":  "REJECTED",
            "close_reason": motivo,
            "product_name": "Crédito de Consumo",
            "closed_at":    _dt.datetime.utcnow().isoformat(),
        },
        "offer_data": {
            "loan": {
                "display_data": {
                    "download_url":  None,
                    "main_detail":   None,
                    "security_hash": None,
                    "reason":        motivo,
                }
            }
        },
        "messages": [AIMessage(content=mensaje)],
    }


# ──────────────────────────────────────────────────────────────────────────────────────
# LOAN_SECURITY_BLOCK — Bloqueo por Múltiples Intentos OTP Fallidos
# ──────────────────────────────────────────────────────────────────────────────────────

def loan_security_block_node(state: FluxState) -> dict:
    """
    Stub: LOAN_SECURITY_BLOCK.

    Responsabilidades finales:
      - Registrar el bloqueo en auth_control con block_timestamp.
      - Actualizar user_status en DB a "BLOCKED_SECURITY" (vía Supabase).
      - Escribir flow_result con status_code = "SECURITY_BLOCKED".
      - Este nodo es TERMINAL: no hay retorno al flujo de crédito.
    """
    session      = state.get("session", {})
    auth_control = state.get("auth_control", {})
    nombre       = state.get("preparation_data", {}).get("nombre", "")
    now_iso      = _dt.datetime.utcnow().isoformat()

    mensaje = (
        f"🔒 {nombre}, hemos detectado múltiples intentos fallidos de validación. "
        "Por tu seguridad, esta solicitud ha sido bloqueada temporalmente.\n\n"
        "Recibirás un correo con instrucciones para desbloquear tu cuenta. "
        "Si crees que esto es un error, contáctanos."
    )

    from langchain_core.messages import AIMessage
    return {
        "session": {
            **session,
            "current_node":      "LOAN_SECURITY_BLOCK",
            "previous_node":     session.get("current_node"),
            "just_completed_step": None,
        },
        "auth_control": {
            **auth_control,
            "security_blocked": True,
            "block_timestamp":  now_iso,
        },
        "flow_result": {
            "status_code":  "SECURITY_BLOCKED",
            "close_reason": "MAX_OTP_ATTEMPTS",
            "product_name": "Crédito de Consumo",
            "closed_at":    now_iso,
        },
        "messages": [AIMessage(content=mensaje)],
    }


# ──────────────────────────────────────────────────────────────────────────────────────
# LOAN_CLOSED_BY_USER — Cierre Voluntario (Usuario rechazó la oferta)
# ──────────────────────────────────────────────────────────────────────────────────────

def loan_closed_by_user_node(state: FluxState) -> dict:
    """
    Stub: LOAN_CLOSED_BY_USER.

    Responsabilidades finales:
      - Leer el último estado alcanzado (previous_node) para analytics.
      - Leer evaluation_results["loan_engine"] para capturar monto y cuota rechazados.
      - Escribir flow_result con status_code = "CLOSED_BY_USER".
      - Mensaje empático de despedida.
    """
    session = state.get("session", {})
    nombre  = state.get("preparation_data", {}).get("nombre", "")
    engine  = state.get("evaluation_results", {}).get("loan_engine", {})
    monto   = engine.get("monto_aprobado", 0)
    cuota   = engine.get("cuota_mensual", 0)
    now_iso = _dt.datetime.utcnow().isoformat()

    mensaje = (
        f"Entendido, {nombre}. Si en algún momento cambias de opinión, "
        "¡acá vamos a estar para ayudarte! 👋"
    )

    from langchain_core.messages import AIMessage
    return {
        "session": {
            **session,
            "current_node":      "LOAN_CLOSED_BY_USER",
            "previous_node":     session.get("current_node"),
            "just_completed_step": None,
        },
        "flow_result": {
            "status_code":  "CLOSED_BY_USER",
            "close_reason": "USER_REJECTED_OFFER",
            "product_name": "Crédito de Consumo",
            "closed_at":    now_iso,
        },
        "offer_data": {
            "loan": {
                "display_data": {
                    "download_url":  None,
                    "main_detail":   f"Monto rechazado: ${monto:,} CLP",
                    "security_hash": None,
                    "reason":        "USER_REJECTED_OFFER",
                }
            }
        },
        "messages": [AIMessage(content=mensaje)],
    }

# ======================================================================================================
# HELPERS DEL FLUJO DE CREDITO DE CONSUMO
# ======================================================================================================

# ── HELPERS DE RECOLECCIÓN (UTILITIES) ──────────────────────

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
    Eso es responsabilidad exclusiva del CreditEngine. Aquí solo se filtran
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

# ── Obtener campos faltantes de simulación| v2.1 — añade validación de valores centinela del LLM
def _get_missing_sim_fields(sim_data: dict) -> list[str]:
    """
    Retorna lista de campos de simulación que faltan o tienen valores inválidos.
    
    REGLAS:
      - None siempre es faltante.
      - monto_solicitado <= 0: centinela del LLM para monto ausente.
      - plazo_solicitado <= 0: centinela del LLM para plazo ausente.
    """
    missing = []
    
    monto = sim_data.get("monto_solicitado")
    if monto is None or monto <= 0:
        missing.append("monto_solicitado")
    
    plazo = sim_data.get("plazo_solicitado")
    if plazo is None or plazo <= 0:
        missing.append("plazo_solicitado")
    
    return missing

# ── Construir el contexto para la Llamada B (generador) para nodo LOAN_COLLECTING_PROFILE ──────────────
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

# ── Construir el contexto para la Llamada B (generador) para nodo LOAN_COLLECTING_SIMULATION ──────────────
def _build_sim_generation_context(
    nombre: str,
    intencion: str,
    known_sim: dict,
    missing: list[str],
    newly_extracted: dict,
    just_completed_step: str | None = None,
    last_msg: str = "",          # <--- Nuevo
    razonamiento: str = ""       # <--- Nuevo
) -> str:
    """
    Versión especializada para la recolección de monto y plazo.
    CAMBIOS v2.2:
      - Parámetro just_completed_step reemplaza profile_just_completed (bool).
      - Genera instrucciones de transición para cualquier paso completado, no solo perfil.
    """
    from app.graph.constants import CompletedStep

    field_labels = {
        "monto_solicitado": "monto del crédito",
        "plazo_solicitado": "plazo en cuotas mensuales",
    }
    
    known_lines = []
    for field, label in field_labels.items():
        value = known_sim.get(field)
        if value is not None:
            if field == "monto_solicitado":
                known_lines.append(f"  - {label}: ${value:,} CLP")
            else:
                known_lines.append(f"  - {label}: {value} meses")
    
    new_lines = []
    for field, value in newly_extracted.items():
        if value is not None and field in field_labels:
            label = field_labels[field]
            if field == "monto_solicitado":
                new_lines.append(f"  - {label}: ${value:,} CLP")
            else:
                new_lines.append(f"  - {label}: {value} meses")
    
    missing_labels = [field_labels[f] for f in missing]
    
    # ── Mensaje de transición basado en qué se acaba de completar ──
    transicion_msg = ""
    if just_completed_step == CompletedStep.LOAN_PROFILE:
        transicion_msg = (
            "AVISO: El usuario acaba de completar su perfil financiero exitosamente. "
            "NO saludes de nuevo; celebra brevemente ese hito y pide el MONTO del crédito."
        )
    elif just_completed_step == CompletedStep.LOAN_SIMULATION:
        transicion_msg = (
            "AVISO: El usuario acaba de completar los datos de simulación. "
            "Indícale que calcularás su crédito de inmediato."
        )
    # Extensible: agregar elif para otros pasos futuros

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

# ── Construir el contexto para la Llamada B (generador) para nodo LOAN_PRE_APPROVED ──────────────
def _build_pre_approved_generation_context(
    nombre: str,
    just_completed_step: str,
    engine_result: dict,
    last_msg: str = ""
) -> str:
    
    # ── Extracción de datos del motor ──
    monto   = engine_result.get("monto_aprobado", 0)
    cuota   = engine_result.get("cuota_mensual", 0)
    plazo   = engine_result.get("plazo_aprobado", 0)
    cae     = engine_result.get("cae", 0.0)
    ctc     = engine_result.get("ctc", 0)

    # 1. ── AVISO DE TRANSICIÓN (Igual que en SIM) ──
    # Este bloque solo existe en el momento del "salto"
    transicion_msg = ""
    if just_completed_step == CompletedStep.LOAN_RISK_SUCCESS:
        transicion_msg = (
            "AVISO: El crédito acaba de ser aprobado exitosamente. "
            "Esta es la primera vez que el usuario ve la oferta: ¡CELEBRA EL ÉXITO!"
        )

    # 2. ── INSTRUCCIÓN DE COMPORTAMIENTO (El "Else" lógico) ──
    # Esta instrucción siempre está, pero su foco cambia según el contexto
    if not transicion_msg and last_msg:
        # Este es el caso de "Turno 4" (Re-pregunta)
        comportamiento = (
            f"RE-PREGUNTA: El usuario ya tiene su oferta y ahora comenta: '{last_msg}'. "
            "NO celebres de nuevo. Responde su duda brevemente y dile que para avanzar "
            "DEBE usar los botones de la tarjeta de transparencia. Sé firme pero amable."
        )
    else:
        # Este es el caso de "Turno 3" (Celebración)
        comportamiento = (
            "PRESENTACIÓN: Invita al usuario a revisar los detalles en la tarjeta de "
            "transparencia y a decidir usando los botones."
        )

    context = f"""
    {transicion_msg}

    --- CONTEXTO DE LA OFERTA ---
    Usuario: {nombre}
    Monto: ${monto:,} | Cuota: ${cuota:,} | Plazo: {plazo} meses
    CAE: {cae:.2%} | CTC: ${ctc:,}

    --- INSTRUCCIÓN ACTUAL ---
    {comportamiento}
    """
    return context



# ── Gestionar re-preguntas con contexto
def _build_flux_reprompt(missing: list[str], known: dict, context: str) -> str:
    """
    Helper Unificado de Tono Flux.
    Reconoce lo que ya sabemos y pide lo que falta con cercanía chilena.
    """
    # 1. Etiquetas amigables para los datos
    labels = {
        "renta": "tu renta líquida",
        "antiguedad_laboral": "hace cuánto trabajas ahí",
        "nivel_estudios": "tu nivel de estudios",
        "monto_solicitado": "cuánta plata necesitas",
        "plazo_solicitado": "en cuántas cuotas quieres pagar"
    }

    # 2. Construcción del reconocimiento (Lo que ya tenemos)
    known_parts = []
    if known.get("renta"):
        known_parts.append(f"tu renta de ${known['renta']:,}")
    if known.get("antiguedad_laboral"):
        known_parts.append(f"tus {known['antiguedad_laboral']} meses en la pega")
    if known.get("nivel_estudios"):
        known_parts.append(f"tus estudios ({known['nivel_estudios'].capitalize()})")
    if known.get("monto_solicitado"):
        known_parts.append(f"los ${known['monto_solicitado']:,} que pides")
    if known.get("plazo_solicitado"):
        known_parts.append(f"el plazo de {known['plazo_solicitado']} meses")

    # 3. Construcción de la frase
    missing_labels = [labels[f] for f in missing]
    missing_str = " y ".join(missing_labels)

    if not known_parts:
        # Caso cuando no ha entregado nada aún en este contexto
        return f"¡Ya! Para seguir con tu {context}, cuéntame: ¿Cuál es {missing_str}?"
    
    known_str = " y ".join(known_parts)
    return f"¡Buenísimo! Ya anoté {known_str}. Solo me falta saber {missing_str} para tener todo listo."
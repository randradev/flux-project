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

    # --- INICIO REEMPLAZO EXACTO ---
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
    # --- FIN REEMPLAZO EXACTO ---

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

    # ── AVANCE SILENCIOSO (simulación completa) ───────────────
    if not missing:
        current_progress = session.get("progress", {})
        loan_progress = current_progress.get("loan", {})
        output["session"] = {
            **output["session"],
            "progress": {
                **current_progress,
                "loan": {**loan_progress, "simulation_completed": True},
            },
            "just_completed_step": CompletedStep.LOAN_SIMULATION,
            # La arista condicional saltará a loan_risk_engine
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

    return {
        "evaluation_results": {
            "loan_engine": engine_result,
        },
        "session": {**session, "current_node": "LOAN_RISK_ENGINE"},
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
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
from app.modules.account_eng import AccountEngine, PolicyRejectionError, PaymentCapacityError
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
# ─────────────────────────────────────────────────────────────────────────────────────────
# ── PROMPTS EN NODO PRE_APPROVED ─────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_EXTRACTION_DECISION = """
Eres un motor de extracción de datos. Tu ÚNICA misión es analizar el mensaje del usuario y retornar un JSON estructurado VÁLIDO.

REGLAS DE FORMATO:
- NO uses bloques de código Markdown (prohibido usar ```json).
- Retorna estrictamente un objeto JSON con los campos 'decision' y 'razonamiento'.

INTENCIONES POSIBLES ('decision'):
- ACCEPTED: El usuario acepta o quiere avanzar.
- REJECTED: El usuario rechaza o quiere cancelar.
- PREGUNTA: El usuario tiene una duda técnica (En qué consiste el Upgrade, cómo se calcula la categoría del plan. etc).
- OTRO: Saludos o irrelevante.

REGLA DE ORO: Si hay una PREGUNTA, la decisión DEBE ser 'PREGUNTA', aunque también parezca aceptar.

EJEMPLO:
Usuario: "Bacán, pero ¿qué es el upgrade?"
-> {
    "decision": "PREGUNTA",
    "razonamiento": "Usuario acepta pero pregunta por el upgrade."
}
"""

SYSTEM_PROMPT_GENERATION_PRE_APPROVED = """
Eres Flux, el genio amigable de las finanzas en Chile. 

PERSONALIDAD:
- Hablas de tú, eres cercano y usas modismos chilenos con moderación.
- Eres ágil: no das rodeos innecesarios, pero sí eres empático.
- Si el contexto indica que la cuenta corriente se aprobó justo ahora (AVISO), usa frases de celebración y éxito ("¡Lo logramos!", "¡Noticias espectaculares!").
- Si el contexto no indica un aviso nuevo (RE-PREGUNTA), evita celebrar de nuevo o saludar; asume que el usuario ya conoce su oferta y responde directo a su duda.

TAREA ACTUAL: Gestión de la oferta de cuenta corriente pre-aprobada.

RESTRICCIONES:
- Máximo 3 oraciones en tu respuesta.
- No repitas los números técnicos en el texto (ya están en la tarjeta).

MANEJO DE DUDAS:
- Si el usuario pregunta cómo proceder o qué hacer, indícale con mucha gracia que debe revisar los datos de la tarjeta de transparencia y responder para decidir si acepta o rechaza la oferta.
"""

# ─────────────────────────────────────────────────────────────────────────────────────────
# ── PROMPTS EN NODO ACCOUNT_OTP_VALIDATION ──────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_EXTRACTION_OTP = """
Eres un motor de extracción de datos. Tu ÚNICA misión es analizar el mensaje del usuario y retornar un JSON estructurado VÁLIDO.

REGLAS DE FORMATO:
- NO uses bloques de código Markdown (prohibido usar ```json).
- Retorna estrictamente un objeto JSON con los campos 'intent' y 'razonamiento'.

INTENCIONES POSIBLES ('intent'):
- OTP_CODE: El usuario intenta ingresar el código que recibió en su mail.
- PREGUNTA: El usuario tiene una duda técnica (Cantidad de intentos, nuevo envío, etc.).
- OTRO: Saludos o irrelevante.

REGLA DE ORO: Si hay una PREGUNTA, la decisión DEBE ser 'PREGUNTA', aunque también parezca ingresar un código.

EJEMPLO:
Usuario: "Bacán, pero ¿cuántos intentos tengo?"
-> {
    "intent": "PREGUNTA",
    "razonamiento": "Usuario pregunta por la cantidad de intentos que le quedan."
}
"""

SYSTEM_PROMPT_GENERATION_OTP = """
Eres Flux, el genio amigable de las finanzas en Chile. 

PERSONALIDAD:
- Hablas de tú, eres cercano y usas modismos chilenos con moderación.
- Eres ágil: no das rodeos innecesarios, pero sí eres empático.
- Si el contexto indica que es la primera vez que le envían un código OTP en esta sesión, usa frases de información y motivación para ingresar el código ("¡Listo! Te enviamos un código de 6 dígitos a tu correo registrado." "¡Ahora solo queda este paso de seguridad! Ingresa el código que te enviamos al correo y quedamos listos", "¡Estamos a punto de lograrlo!, Solo falta que ingreses el código que te enviamos al correo, ¡y listo!").
- Si el contexto no indica un aviso nuevo (RE-PREGUNTA), evita informar de nuevo; asume que el usuario ya sabe y recuérdale la cantidad de intentos restantes.

TAREA ACTUAL: Estás en la fase de validación de identidad mediante OTP. Tu tono es profesional, seguro y servicial.

REGLAS:
1. Si es el primer envío (AVISO NUEVO): Explica que enviaste un código al correo registrado y motiva al usuario a ingresarlo.
2. Si el ESTADO es RE-PREGUNTA (ERROR): No saludes ni des instrucciones de nuevo. Indica que el código no coincide y menciona cuántos intentos le quedan.
3. Si el ESTADO es RE-PREGUNTA (CONTINUACIÓN): No saludes ni des instrucciones de nuevo. Responde a lo que el usuario diga (si aplica) y recuérdale amablemente que sigues esperando el código en la tarjeta para finalizar.

RESTRICCIONES:
- Máximo 3 oraciones en tu respuesta.
- NUNCA menciones el código real en el chat.
- Refuerza SIEMPRE que el ingreso del código, por la seguridad del propio cliente, se realiza mediante la interfaz.

MANEJO DE DUDAS:
- Si el usuario pregunta cómo proceder o qué hacer, indícale con mucha gracia que debe usar los botones de la tarjeta de abajo para que la aceptación sea oficial. 
"""

# ─────────────────────────────────────────────────────────────────────────────────────────
# ── PROMPTS EN NODO ACCOUNT_COMPLETED_NODE ──────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_GENERATION_COMPLETED = """
Eres Flux, el genio de las finanzas. El usuario acaba de completar exitosamente la contratación de su Cuenta Corriente en Flux.
Tu tarea es felicitarlo con mucha energía y calidez chilena. 
Dile que su contrato ya está listo para descarga (el link aparecerá abajo).
Sé breve (máximo 2-3 oraciones).
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
    Nodo ACCOUNT_EVALUATION_ENGINE: motor de riesgo para cuenta corriente.

    ID LangGraph : account_evaluation_engine
    current_node : ACCOUNT_EVALUATION_ENGINE   ← valor semántico para GPS y Supabase

    NOTA ARQUITECTURA:
        Este nodo es un wrapper de flujo. La lógica de cálculo pesada debe residir
        en módulos independientes (modules/account_eng.py) para facilitar tests unitarios.
    """
    # 1. ------ PREPARACIÓN DE DATOS ------
    session    = state.get("session", {})
    prep       = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})
    evaluation_results = state.get("evaluation_results", {})
    account_profile = collecting.get("account_profile", {})

    try:
        # 2. ------ LLAMADA AL MOTOR REAL ------
        engine = AccountEngine(
            preparation_data=prep,
            account_profile=account_profile,
        )
        engine_result = engine.run()

    except PolicyRejectionError as e:
        # Caso: Rechazo por Edad, Renta o Antigüedad
        engine_result = {
            "status_proceso": "REJECTED",
            "is_elegible": False,
            "base_category": engine.base_category,
            "final_category": engine.final_category,
            "has_upgrade": engine.has_upgrade,
            "credit_line_amount": engine.credit_line,
            "monthly_cost": engine.monthly_cost,
            "motivo_rechazo": e.motivo
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
            current_node_id="ACCOUNT_EVALUATION_ENGINE",
            node_status="SUCCESS",
            engine_status=engine_status,
        )

    # 4. ------ SELECCIÓN DE FLAG DE SALIDA ------
    status = engine_result.get("status_proceso")
    if status == "PRE_APPROVED":
        completion_flag = CompletedStep.ACCOUNT_EVALUATION_SUCCESS
        # Actualizar Progreso Histórico (Persistencia para ruteo P1)
        current_progress = session.get("progress", {})
        account_progress = current_progress.get("account", {})
        session["progress"] = {
            **current_progress,
            "account": {**account_progress, "evaluation_engine_completed": True}
        }
    else:
        # Cubre REJECTED y ERROR
        completion_flag = CompletedStep.ACCOUNT_EVALUATION_REJECTED

    return {
        "evaluation_results": {
            **evaluation_results,
            "account_engine": engine_result
        },
        "session": {
            **session,
            "just_completed_step": completion_flag,
        }
    }

    return {
        "evaluation_results": {
            **evaluation_results,
            "account_engine": engine_result
        },
        "session": {
            **session,
            "just_completed_step": CompletedStep.ACCOUNT_EVALUATION_ENGINE,
        }
    }

import datetime as _dt  # Alias para evitar colisión con nombres de variables locales

# ──────────────────────────────────────────────────────────────────────────────────────
# ACCOUNT_PRE_APPROVED — Muestra la Tarjeta de Transparencia al usuario
# ──────────────────────────────────────────────────────────────────────────────────────

def account_pre_approved_node(state: FluxState) -> dict:
    """
    Stub: ACCOUNT_PRE_APPROVED.

    Responsabilidades finales:
      - Leer evaluation_results["account_engine"] y formatear la oferta.
      - Mostrar la Tarjeta de Transparencia (monto, plazo, cuota, CAE, CTC).
      - Esperar la decisión del usuario (ACCEPTED / REJECTED).
      - Si ACCEPTED: setear just_completed_step = ACCOUNT_PRE_APPROVED
                     y escribir offer_data["account"]["pre_approval_status"] = "ACCEPTED".
      - Si REJECTED: setear just_completed_step = ACCOUNT_CLOSED_BY_USER.
    """
    # 1. ------ Recolectar Datos Iniciales ------
    raw_session = state.get("session", {})
    just_completed = raw_session.get("just_completed_step")
    session = {**raw_session, "just_completed_step": None}

    prep       = state.get("preparation_data", {})
    messages   = state.get("messages", [])
    nombre     = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    # 2. ------ Detección de Salto Intra-turno (Viene de account_evaluation_engine) ------
    is_intra_turn_jump = (just_completed == CompletedStep.ACCOUNT_EVALUATION_SUCCESS)
    
    # 3. ------ Leer resultados del motor
    engine_result = state.get("evaluation_results", {}).get("account_engine", {})
    
    # Datos para cálculos y visualización
    final_category = engine_result.get("final_category", "Medium")
    has_upgrade = engine_result.get("has_upgrade", False)
    credit_line_amount = engine_result.get("credit_line_amount", 0)
    monthly_cost = engine_result.get("monthly_cost", 0)

    extracted = None

    # Inicializamos el output base con los metadatos de sesión
    output = {
        "session": {
            **session,
            "current_node": "ACCOUNT_PRE_APPROVED",
            "just_completed_step": None, # Limpieza por defecto
        }
    }

    # 4. ------ LLAMADA A: PROCESAMIENTO DE DECISIÓN ------
    user_decision = "PENDING"  # Por defecto
    last_user_msg = ""

    if not is_intra_turn_jump:
        # 1. Capturamos el mensaje
        last_user_msg = next(
            (m.content for m in reversed(messages) if isinstance(m, HumanMessage)), 
            ""
        ).strip()
        
        if last_user_msg:
            # 2. LLAMADA A - Extracción de Decisión/Pregunta
            # (Usamos el schema de account_schemas.py)
            raw_extraction = _flux_generator.invoke([
                {"role": "system", "content": SYSTEM_PROMPT_EXTRACTION_DECISION},
                {"role": "user", "content": last_user_msg}
            ])

            # --- PARSEO MANUAL ---
            content_str = normalize_llm_response(raw_extraction.content)
            import json, re
            match = re.search(r"\{.*\}", content_str, re.DOTALL)
            
            if match:
                try:
                    data = json.loads(match.group())
                    extracted = AccountDecisionExtraction(**data)
                except Exception as e:
                    print(f"[!!!] Error parseando decisión: {e}")
                    extracted = AccountDecisionExtraction(decision="OTRO", razonamiento="Error")
            else:
                extracted = AccountDecisionExtraction(decision="OTRO", razonamiento="No JSON")
            # ---------------------

            # AÑADIMOS ESTO PARA DEBUG:
            if extracted:
                print(f"[DEBUG-OFFER] Decisión detectada: {extracted.decision}")
                print(f"[DEBUG-OFFER] Razonamiento: {extracted.razonamiento}")

            # 3. HOOK DE RAG: Si es pregunta, interrumpimos y respondemos
            if extracted and extracted.decision == "PREGUNTA":
                print(f"[DEBUG-RAG-OFFER] Pregunta detectada: {last_user_msg}")
                rag_response = get_consultant_response(last_user_msg, state)
                
                output["messages"] = [AIMessage(content=rag_response)]
                # IMPORTANTE: No cambiamos de nodo, nos quedamos en PRE_APPROVED
                return output
            # 4. Lógica de Decisión (Máxima inteligencia y seguridad)
            msg_upper = last_user_msg.upper()
            
            # A. Prioridad 1: Confiar en el LLM (Lenguaje natural)
            if extracted and extracted.decision == "ACCEPTED":
                user_decision = "ACCEPTED"
            elif extracted and extracted.decision == "REJECTED":
                user_decision = "REJECTED"
                
            # B. Prioridad 2: El Botón o las Keywords (Seguridad extra)
            elif "[ACCION_DIRECTA:ACCEPT_OFFER]" in msg_upper or msg_upper in ["ACEPTAR", "ACEPTO", "SI", "ACEPTA"]:
                user_decision = "ACCEPTED"
            elif "[ACCION_DIRECTA:REJECT_OFFER]" in msg_upper or msg_upper in ["RECHAZAR", "RECHAZO", "NO", "RECHAZA"]:
                user_decision = "REJECTED"


    # 5. ------ EVALUACIÓN DE ESTADO DE OFERTA (Paso 2.4) ------
    application_id = session.get("application_id")
    
    if user_decision == "ACCEPTED":
        # A. Actualizar Progreso Histórico
        current_progress = session.get("progress", {})
        account_progress = current_progress.get("account", {})
        updated_progress = {
            **current_progress,
            "account": {**account_progress, "pre_approval_accepted": True},
        }

        # B. Actualizar Semáforo en DB
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="ACCOUNT_PRE_APPROVED",
                node_status="SUCCESS",
                engine_status="SUCCESS",
            )

        # C. Output de Éxito con "Foto" congelada de la oferta
        output["session"] = {
            **output["session"],
            "progress": updated_progress,
            "just_completed_step": CompletedStep.ACCOUNT_PRE_APPROVED
        }
        
        # Guardamos la data exacta que el usuario aceptó
        output["offer_data"] = {
            **state.get("offer_data", {}),
            "account": {
                "pre_approval_status": "ACCEPTED",
                "timestamp_acceptance": _dt.datetime.utcnow().isoformat(),
                "final_category": final_category,
                "has_upgrade": has_upgrade,
                "credit_line_amount": credit_line_amount,
                "monthly_cost": monthly_cost
            }
        }
        return output

    elif user_decision == "REJECTED":
        # Al rechazar, también informamos al semáforo (pero con estado final o similar)
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="ACCOUNT_PRE_APPROVED",
                node_status="SUCCESS",
                engine_status="SUCCESS", # El motor ya hizo su parte
            )
        output["session"]["just_completed_step"] = CompletedStep.ACCOUNT_CLOSED_BY_USER
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
        "account": {
            "final_category": f"{final_category}",
            "has_upgrade": "Upgrade por nivel de estudios" if has_upgrade else "Categoría base según perfil",
            "credit_line_amount": f"${credit_line_amount:,} CLP",
            "monthly_cost": f"${monthly_cost:,} CLP"
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
        "account": transparency_card["account"] 
    }
    
    # Actualizamos metadatos de visualización en la sesión
    output["session"] = {
        **output["session"],
        "display_control": {
            "active_component": "ACCOUNT_TRANSPARENCY_CARD",
            "show_full_details": True
        }
    }

    # MARTILLAZO DE LIMPIEZA FINAL:
    output["session"]["just_completed_step"] = None 

    return output

# ──────────────────────────────────────────────────────────────────────────────────────
# ACCOUNT_OTP_VALIDATION — Validación del código enviado por email
# ──────────────────────────────────────────────────────────────────────────────────────

def account_otp_validation_node(state: FluxState):
    """
    Nodo de validación de identidad mediante OTP.
    Maneja el envío inicial, la validación de intentos y el bloqueo de seguridad.
    """
    print("--- NODO: ACCOUNT_OTP_VALIDATION ---")
    
    # 1. ------ PREPARACIÓN DE DATOS (Handshake) ------
    messages     = state.get("messages", [])
    session      = state.get("session", {})
    auth_control = state.get("auth_control", {})
    prep_data    = state.get("preparation_data", {})
    initial_attempts = auth_control.get("otp_attempts", 0)
    
    # Metadatos para ruteo intra-turno
    just_completed     = session.get("just_completed_step")
    is_intra_turn_jump = just_completed == CompletedStep.ACCOUNT_PRE_APPROVED
    
    # Datos del usuario
    first_name = prep_data.get("nombre", "Usuario").split()[0]
    mail       = prep_data.get("mail")
    
    # Inicializamos el output base
    output = {
        "session": {
            **session,
            "current_node": "ACCOUNT_OTP_VALIDATION",
            "just_completed_step": None, # Por defecto no avanzamos
        },
        "auth_control": {**auth_control}
    }

    # 2. ------ LÓGICA DE DISPARO INICIAL (Envío de Mail) ------
    # Si venimos saltando del nodo anterior y no hemos generado código aún
    if is_intra_turn_jump and not auth_control.get("otp_generated"):
        print(f"[OTP] Generando y enviando código a {mail}...")
        
        new_code = security.generate_otp()
        success  = security.send_otp_email(mail, new_code)
        
        if success:
            output["auth_control"]["otp_generated"] = new_code
            output["auth_control"]["otp_attempts"]  = 0
            # Continuamos a la fase de generación de respuesta para informar al usuario
        else:
            # Error de servicio (Resend falló)
            output["auth_control"]["service_error"] = True
            # Aquí podrías decidir si mandas a SERVICE_ERROR o reintentas

    # 3. ------ LÓGICA DE PROCESAMIENTO (Si NO es salto inicial) ------
    #user_msg = ""

    user_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "").strip()

    import re

    extracted = None

    if not is_intra_turn_jump:
        # --- A. VALIDACIÓN PRIORITARIA (Desde Interfaz/Botón) ---
        # Si el frontend envió algo, esto manda sobre cualquier texto del chat
        user_input_code = auth_control.get("otp_user_input")

        if not user_input_code:
            match = re.search(r"\b\d{6}\b", user_msg)
            user_input_code = match.group(0) if match else None
            
        actual_code     = auth_control.get("otp_generated")
        if user_input_code is not None and user_input_code != "":
            # Limpiamos el input para que no se procese dos veces si el usuario escribe luego en chat
            output["auth_control"]["otp_user_input"] = None
            
            is_valid = security.validate_otp(user_input_code, actual_code)
            
            if is_valid:
                print("🏆 OTP Validado con éxito.")
                
                # ── ACTUALIZACIÓN DE PROGRESO HISTÓRICO (Cableado de Seguridad) ──
                current_progress = session.get("progress", {})
                account_progress = current_progress.get("account", {})
                updated_progress = {
                    **current_progress,
                    "account": {**account_progress, "otp_validated": True}
                }
                
                output["auth_control"]["otp_generated"] = ""
                output["session"] = {
                    **output["session"],
                    "progress": updated_progress,
                    "just_completed_step": CompletedStep.ACCOUNT_OTP_SUCCESS
                }
                return output

            else:
                # ERROR: El código no coincide
                current_attempts = auth_control.get("otp_attempts", 0) + 1
                output["auth_control"]["otp_attempts"] = current_attempts
                
                if current_attempts >= 3:
                    print("🚫 Bloqueo por seguridad: Máximos intentos alcanzados.")
                    output["auth_control"]["security_blocked"] = True
                    # Asegúrate de que _dt esté disponible o usa datetime directamente
                    output["auth_control"]["block_timestamp"]  = _dt.datetime.utcnow().isoformat()
                    output["auth_control"]["last_otp_input"]   = user_input_code
                    output["session"]["just_completed_step"] = CompletedStep.ACCOUNT_SECURITY_BLOCK
                    return output
                
                # Al no haber nada aquí, el flujo sigue hacia la generación de respuesta del LLM
                # avisándole al usuario que se equivocó, pero manteniendo el mismo código.

                
        # Si falló pero hay intentos, NO retornamos; seguimos para que el LLM responda el error.
        # --- B. EXTRACCIÓN Y RAG (Desde Chat) ---
        # Solo procesamos texto si realmente hay un mensaje del usuario (evita falsos positivos de comandos)
        
        if user_msg:
            raw_extraction = _flux_generator.invoke([
                {"role": "system", "content": SYSTEM_PROMPT_EXTRACTION_OTP},
                {"role": "user",   "content": user_msg}
            ])
            
            extracted = None
            content_str = normalize_llm_response(raw_extraction.content)
            import json, re
            match = re.search(r"\{.*\}", content_str, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                    extracted = AccountOTPExtraction(**data)
                except: pass
            # Hook de RAG: Solo si detectamos una pregunta clara
            if extracted and extracted.intent == "PREGUNTA":
                rag_response = get_consultant_response(user_msg, state)
                output["messages"] = [AIMessage(content=rag_response)]
                # IMPORTANTE: No limpiamos just_completed_step aquí para no romper el ruteo
                return output

    # 4. ------ GENERACIÓN DE RESPUESTA (LLM) ------
    
    current_attempts = output["auth_control"].get("otp_attempts", 0)

    hubo_error_en_este_turno = (current_attempts > initial_attempts)
    
    # Pasar variables para crear contexto para la respuesta
    context = _build_otp_generation_context(
        nombre=first_name,
        attempts=current_attempts,
        last_msg=user_msg,
        error=hubo_error_en_este_turno, # <--- Lógica dinámica
        just_completed=just_completed,
        blocked=output["auth_control"].get("security_blocked", False)
    )

    # Agregamos la intención al contexto para que Flux sepa QUÉ hizo el usuario
    if extracted:
        context += f"\nINTENCIÓN DETECTADA EN CHAT: {extracted.intent}"

    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_GENERATION_OTP},
        {"role": "user",   "content": context},
    ])
    
    clean_content = normalize_llm_response(flux_response.content)
    output["messages"] = [AIMessage(content=clean_content)]

    # 5. ------ MARTILLAZO DE LIMPIEZA ------
    output["session"]["just_completed_step"] = None
    
    return output

# ──────────────────────────────────────────────────────────────────────────────────────
# ACCOUNT_FORMALIZATION — Generación y Sellado del Contrato PDF
# ──────────────────────────────────────────────────────────────────────────────────────

def account_formalization_node(state: FluxState) -> dict:
    """
    Stub: ACCOUNT_FORMALIZATION.

    Responsabilidades finales:
      - Recopilar datos del motor y del usuario (nombre, rut).
      - Generar el PDF del contrato con ReportLab.
      - Calcular hash SHA-256 del PDF generado.
      - Escribir en offer_data["account"]: file_contrato_path, hash_sha256, contract_status.
      - Si SIGNED_AND_STAMPED: continuar a account_completed (via edge fijo).
      - Si GENERATION_FAILED: redirigir a SERVICE_ERROR (futuro).
    """
    print("--- NODO: ACCOUNT_FORMALIZATION ---")
    
    # 1. ------ RECOLECCIÓN (The Handshake) ------
    prep_data    = state.get("preparation_data", {})
    account_engine  = state.get("evaluation_results", {}).get("account_engine", {})
    session      = state.get("session", {})
    offer_account  = state.get("offer_data", {}).get("account", {})
    
    # 2. ------ EJECUCIÓN (The Worker) ------
    try:
        factory = PDFFactory()
        
        # Construimos el payload alineado con los requerimientos de branding
        payload = {
            "nombre":               prep_data.get("nombre"),
            "rut":                  prep_data.get("rut"),
            "final_category":       account_engine.get("final_category"),
            "has_upgrade":          account_engine.get("has_upgrade"),
            "credit_line_amount":   account_engine.get("credit_line_amount"),
            "monthly_cost":         account_engine.get("monthly_cost"),
        }
        
        # A. Generación Local
        local_path, security_hash = _pdf_factory.create_pdf("CUENTA_CORRIENTE", payload)
        
        # B. Subida a la Nube (Supabase Storage)
        cloud_url = upload_contract_to_storage(local_path)
        
        if cloud_url:
            final_path = cloud_url
            contract_status = "SIGNED_AND_STAMPED"
            completion_flag = CompletedStep.ACCOUNT_FORMALIZATION_SUCCESS
        else:
            raise Exception("No se pudo obtener la URL del storage")
        
    except Exception as e:
        print(f"❌ ERROR CRÍTICO EN FORMALIZACIÓN: {e}")
        final_path = None
        security_hash = None
        contract_status = "GENERATION_FAILED"
        completion_flag = None # El ruteador se detendrá para intervención
        
    # 3. ------ PERSISTENCIA Y SEMÁFOROS (The Auditor) ------
    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="ACCOUNT_FORMALIZATION",
            node_status="SUCCESS" if contract_status == "SIGNED_AND_STAMPED" else "FAILED",
            engine_status="SUCCESS",
            document_status="GENERATED" if cloud_url else "PENDING"
        )
        
    # 4. ------ ACTUALIZACIÓN DE ESTADO (The State Manager) ------
    # A. Progreso Histórico (Consistencia inter-turno)
    current_progress = session.get("progress", {})
    account_progress = current_progress.get("account", {})
    updated_progress = {
        **current_progress,
        "account": {**account_progress, "contract_signed": True}
    }
    
    # B. Consolidación de Oferta y Display para el Usuario
    updated_offer_account = {
        **offer_account,
        "file_contrato_path": final_path,
        "hash_sha256":        security_hash,
        "contract_status":    contract_status,
        "display_data": {
            **offer_account.get("display_data", {}),
            "download_url":  final_path,
            "security_hash": security_hash,
            "main_detail": f"Plan: {account_engine.get('final_category', 'Standard')}"
        }
    }
    
    # 5. ------ SALIDA SILENCIOSA (The Jump) ------
    return {
        "session": {
            **session,
            "current_node":        "ACCOUNT_FORMALIZATION",
            "progress":           updated_progress,
            "just_completed_step": completion_flag
        },
        "offer_data": {
            **state.get("offer_data", {}),
            "account": updated_offer_account
        }
        # Sin "messages": El nodo es invisible para el usuario
    }

# ──────────────────────────────────────────────────────────────────────────────────────
# ACCOUNT_COMPLETED — Estado Final Exitoso
# ──────────────────────────────────────────────────────────────────────────────────────

def account_completed_node(state: FluxState) -> dict:
    """
    Nodo de Cierre Exitoso: El final del camino para la Cuenta Corriente.
    
    Responsabilidades:
      - Consolidar la vista final para el usuario.
      - Notificar éxito total en los semáforos de la DB.
      - Registrar el resultado del flujo para analítica.
    """
    print("--- NODO: ACCOUNT_COMPLETED ---")
    import datetime as _dt
    
    # 1. ------ RECOLECCIÓN (The Handshake) ------
    session    = state.get("session", {})
    prep_data  = state.get("preparation_data", {})
    offer_account = state.get("offer_data", {}).get("account", {})
    engine     = state.get("evaluation_results", {}).get("account_engine", {})
    
    nombre   = prep_data.get("nombre", "Cliente").split()[0]
    categoria   = engine.get("final_category", "Medium")
    file_url = offer_account.get("file_contrato_path", "")
    sha256   = offer_account.get("hash_sha256")
    
    # --- LLAMADA B: GENERACIÓN DINÁMICA ---
    context = f"Usuario: {nombre}. Plan Cuenta Corriente: {categoria}. El contrato fue generado exitosamente."
    
    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_GENERATION_COMPLETED},
        {"role": "user",   "content": context},
    ])
    
    mensaje = normalize_llm_response(flux_response.content)

    # 3. ------ AUDITORÍA (The Auditor) ------
    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="ACCOUNT_COMPLETED",
            node_status="SUCCESS",
            engine_status="SUCCESS",
            document_status="GENERATED"
        )

    # 4. ------ ACTUALIZACIÓN DE ESTADO (The State Manager) ------
    # A. Resultado del Flujo (Analítica)
    flow_result = {
        "status_code":  "SUCCESS",
        "close_reason": None,
        "product_name": "Cuenta Corriente",
        "closed_at":    _dt.datetime.utcnow().isoformat(),
    }
    
    # B. Datos de Visualización Final (Frontend)
    updated_display = {
        "download_url":  file_url,
        "main_detail":   f"Plan: {categoria}",
        "security_hash": sha256,
        "reason":        None
    }
    
    # C. Consolidación de la Oferta
    updated_offer_account = {
        **offer_account,
        "display_data": updated_display
    }

    # 5. ------ SALIDA (The Final Jump) ------
    return {
        "session": {
            **session,
            "current_node":      "ACCOUNT_COMPLETED",
            "previous_node":     session.get("current_node"),
            "just_completed_step": None, # Nodo terminal
        },
        "flow_result": flow_result,
        "offer_data": {
            **state.get("offer_data", {}),
            "account": updated_offer_account
        },
        "messages": [AIMessage(content=mensaje)]
    }

# ======================================================================================================
# NODOS MANEJO DE ERRORES Y EXCEPCIONES
# ======================================================================================================

# ──────────────────────────────────────────────────────────────────────────────────────
# ACCOUNT_REJECTED_POLICY — Rechazo por Política de Cuenta Corriente
# ──────────────────────────────────────────────────────────────────────────────────────

_REJECTION_MESSAGES = {
    "ERR_EDAD":           "lamentablemente necesitas ser mayor de 18 años para solicitar una cuenta corriente con nosotros",
    "ERR_RENTA":          "tu renta declarada está por debajo del mínimo que requerimos para este producto",
    "ERR_ANTIGUEDAD":     "necesitas al menos 6 meses de antigüedad laboral para acceder a este producto",
}

def account_rejected_policy_node(state: FluxState) -> dict:
    """
    Nodo de Rechazo por Política: Entrega la noticia con empatía vía LLM.
    """
    print("--- NODO: ACCOUNT_REJECTED_POLICY ---")
    import datetime as _dt
    
    # 1. ------ RECOLECCIÓN ------
    session   = state.get("session", {})
    prep_data = state.get("preparation_data", {})
    engine    = state.get("evaluation_results", {}).get("account_engine", {})
    
    nombre    = prep_data.get("nombre", "Cliente").split()[0]
    motivo    = engine.get("motivo_rechazo", "ERR_RENTA")
    
    # 2. ------ GENERACIÓN DE MENSAJE EMPÁTICO ------
    razon_tecnica = _REJECTION_MESSAGES.get(motivo, "no cumplimos con los filtros mínimos de riesgo")
    
    # Identidad de marca mucho más definida
    system_identity = (
        "Eres Flux, un asistente bancario joven, optimista y directo. "
        "Tu estilo es chileno coloquial pero profesional (usas palabras como 'pucha', 'fome', 'dale', 'buenazo'). "
        "Eres breve, vas al grano y evitas sonar condescendiente o melancólico."
    )
    
    instruction = (
        f"Hola Flux. Cuéntale a {nombre} que su solicitud de cuenta corriente NO pasó esta vez. "
        f"La razón es: {razon_tecnica}. "
        f"Sé súper breve (máximo 2 párrafos cortos). No pidas perdón ni suenes triste, "
        f"dilo de forma optimista, como una pausa y no un rechazo eterno. "
        f"¡Mantén la energía arriba!"
    )
    
    response = _flux_generator.invoke([
        {"role": "system", "content": system_identity},
        {"role": "user",   "content": instruction}
    ])
    mensaje_final = normalize_llm_response(response.content)


    # 3. ------ PERSISTENCIA Y SEMÁFOROS ------
    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="ACCOUNT_REJECTED_POLICY",
            node_status="SUCCESS", # El proceso de rechazo se ejecutó bien
            engine_status="COMPLETED"
        )

    # 4. ------ SALIDA ------
    return {
        "session": {
            **session,
            "current_node": "ACCOUNT_REJECTED_POLICY",
            "just_completed_step": None # Nodo terminal
        },
        "flow_result": {
            "status_code":  "REJECTED",
            "close_reason": motivo,
            "product_name": "Cuenta Corriente",
            "closed_at":    _dt.datetime.utcnow().isoformat(),
        },
        "offer_data": {
            **state.get("offer_data", {}),
            "account": {
                **state.get("offer_data", {}).get("account", {}),
                "display_data": {
                    "reason": razon_tecnica,
                    "download_url": None
                }
            }
        },
        "messages": [AIMessage(content=mensaje_final)]
    }

# ──────────────────────────────────────────────────────────────────────────────────────
# ACCOUNT_SECURITY_BLOCK — Bloqueo por Múltiples Intentos OTP Fallidos
# ──────────────────────────────────────────────────────────────────────────────────────

def account_security_block_node(state: FluxState) -> dict:
    """
    Nodo Terminal: Bloqueo de seguridad tras 3 intentos fallidos de OTP.
    """
    print("--- NODO: ACCOUNT_SECURITY_BLOCK ---")
    import datetime as _dt
    
    # 1. ------ RECOLECCIÓN (The Handshake) ------
    session      = state.get("session", {})
    user_data    = state.get("user_data", {})
    auth_control = state.get("auth_control", {})
    nombre       = state.get("preparation_data", {}).get("nombre", "Cliente").split()[0]
    user_id      = user_data.get("user_id")
    now_iso      = _dt.datetime.utcnow().isoformat()
    
    # 2. ------ EJECUCIÓN (The Warden) ------
    # Bloqueo persistente en la DB (usando el nuevo helper)
    if user_id:
        block_user_security(user_id)
        
    mensaje = (
        f"🔒 **{nombre}, lo sentimos mucho.**\n\n"
        f"Hemos detectado múltiples intentos fallidos de validación de identidad. "
        f"Por tu seguridad, **esta solicitud y tu acceso a Flux han sido bloqueados temporalmente**.\n\n"
        f"Recibirás un correo electrónico en breve con los pasos necesarios para verificar tu cuenta "
        f"y recuperar el acceso. Si crees que esto es un error, por favor contáctanos de inmediato."
    )

    # 3. ------ AUDITORÍA (The Auditor) ------
    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="ACCOUNT_SECURITY_BLOCK",
            node_status="BLOCKED", # <--- Estado de semáforo específico
            engine_status="FAILED"
        )

    # 4. ------ SALIDA TERMINAL (The End) ------
    return {
        "session": {
            **session,
            "current_node": "ACCOUNT_SECURITY_BLOCK",
            "just_completed_step": None # Flag terminal
        },
        "auth_control": {
            **auth_control,
            "security_blocked": True,
            "block_timestamp":  now_iso,
            "error_detail": "Máximo de intentos OTP superado."
        },
        "flow_result": {
            "status_code":  "SECURITY_BLOCKED",
            "close_reason": "OTP_LIMIT_EXCEEDED",
            "product_name": "Cuenta Corriente",
            "closed_at":    now_iso,
        },
        "messages": [AIMessage(content=mensaje)]
    }

# ──────────────────────────────────────────────────────────────────────────────────────
# ACCOUNT_CLOSED_BY_USER — Cierre Voluntario (Usuario rechazó la oferta)
# ──────────────────────────────────────────────────────────────────────────────────────

def account_closed_by_user_node(state: FluxState) -> dict:
    """
    Nodo Terminal: El usuario rechaza formalmente la oferta de cuenta corriente.
    """
    print("--- NODO: ACCOUNT_CLOSED_BY_USER ---")
    import datetime as _dt
    
    # 1. ------ RECOLECCIÓN (The Handshake) ------
    session      = state.get("session", {})
    prep_data    = state.get("preparation_data", {})
    engine       = state.get("evaluation_results", {}).get("account_engine", {})
    offer_account   = state.get("offer_data", {}).get("account", {})
    
    nombre       = prep_data.get("nombre", "Cliente").split()[0]
    final_category       = engine.get("final_category", "Medium")
    now_iso      = _dt.datetime.utcnow().isoformat()

    # 2. ------ GENERACIÓN DE MENSAJE (The Farewell) ------
    # Usamos LLM para una despedida personalizada y cálida (Toque Flux)
    system_identity = (
        "Eres Flux, un asistente bancario joven, optimista y directo. "
        "Tu estilo es chileno coloquial pero profesional ('dale', 'buenazo', 'no te preocupes')."
    )
    
    instruction = (
        f"Hola Flux. El usuario {nombre} acaba de rechazar nuestra oferta de cuenta corriente para el Plan {final_category}. "
        f"Despídete de forma muy breve (máximo 2 líneas), dile que no hay drama "
        f"y que aquí estarás cuando lo necesite. Sé buena onda y relajado."
    )
    
    response = _flux_generator.invoke([
        {"role": "system", "content": system_identity},
        {"role": "user",   "content": instruction}
    ])
    mensaje_final = normalize_llm_response(response.content)

    # 3. ------ PERSISTENCIA HISTÓRICA (The Progress Tracker) ------
    current_progress = session.get("progress", {})
    account_progress = current_progress.get("account", {})
    updated_progress = {
        **current_progress,
        "account": {**account_progress, "user_rejected_offer": True}
    }

    # 4. ------ AUDITORÍA (The Auditor) ------
    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="ACCOUNT_CLOSED_BY_USER",
            node_status="REJECTED_BY_USER",
            engine_status="SUCCESS"
        )

    # 5. ------ SALIDA (The Final State) ------
    return {
        "session": {
            **session,
            "current_node": "ACCOUNT_CLOSED_BY_USER",
            "previous_node": session.get("current_node"),
            "progress": updated_progress,
            "just_completed_step": None # Flag terminal
        },
        "flow_result": {
            "status_code":  "CLOSED_BY_USER",
            "close_reason": "USER_REJECTED_OFFER",
            "product_name": "Cuenta Corriente",
            "closed_at":    now_iso,
        },
        "offer_data": {
            **state.get("offer_data", {}),
            "account": {
                **offer_account,
                "display_data": {
                    **offer_account.get("display_data", {}),
                    "reason": "USER_REJECTED_OFFER",
                    "main_detail": f"Plan rechazado: {final_category}",
                    "download_url": None
                }
            }
        },
        "messages": [AIMessage(content=mensaje_final)]
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

# ── Construir el contexto para la Llamada B (generador) para nodo ACCOUNT_PRE_APPROVED ──────────────
def _build_pre_approved_generation_context(
    nombre: str,
    just_completed_step: str,
    engine_result: dict,
    last_msg: str = ""
) -> str:
    
    # ── Extracción de datos del motor ──
    final_category = engine_result.get("final_category", "Medium")
    has_upgrade = engine_result.get("has_upgrade", False)
    credit_line_amount = engine_result.get("credit_line_amount", 0)
    monthly_cost = engine_result.get("monthly_cost", 0)

    # 1. ── AVISO DE TRANSICIÓN (Igual que en SIM) ──
    # Este bloque solo existe en el momento del "salto"
    transicion_msg = ""
    if just_completed_step == CompletedStep.ACCOUNT_EVALUATION_SUCCESS:
        transicion_msg = (
            "AVISO: La cuenta corriente acaba de ser aprobada exitosamente. "
            "Esta es la primera vez que el usuario ve la oferta: ¡CELEBRA EL ÉXITO!"
        )

    # 2. ── INSTRUCCIÓN DE COMPORTAMIENTO (El "Else" lógico) ──
    # Esta instrucción siempre está, pero su foco cambia según el contexto
    if not transicion_msg and last_msg:
        # Este es el caso de "Turno 4" (Re-pregunta)
        comportamiento = (
            f"RE-PREGUNTA: El usuario ya tiene su oferta y ahora comenta: '{last_msg}'. "
            "NO celebres de nuevo. Responde su duda brevemente y dile que para avanzar "
        )
    else:
        # Este es el caso de "Turno 3" (Celebración)
        comportamiento = (
            "PRESENTACIÓN: Invita al usuario a revisar los detalles en la tarjeta de "
            "transparencia."
        )

    context = f"""
    {transicion_msg}

    --- CONTEXTO DE LA OFERTA ---
    Usuario: {nombre}
    Categoría Final: Plan {final_category} | Otorgamiento de Upgrade por Nivel de Estudios: {has_upgrade} | Línea de Crédito: ${credit_line_amount} CLP | Costo Mensual: ${monthly_cost} CLP.

    --- INSTRUCCIÓN ACTUAL ---
    {comportamiento}
    """
    return context

# ── Construir el contexto para la Llamada B (generador) para nodo ACCOUNT_OTP_VALIDATION ──────────────
def _build_otp_generation_context(nombre: str, attempts: int, last_msg: str, error: bool = False, just_completed: str = None, blocked: bool = False) -> str:
    """Construye el contexto para el prompt de generación de OTP."""
    context = f"Usuario: {nombre}\n"
    context += f"Intentos realizados: {attempts}/3\n"
    
    # Siguiendo el patrón: Si NO hay just_completed, es RE-PREGUNTA
    is_re_pregunta = just_completed is None

    if blocked:
        context += "ESTADO: BLOQUEADO (Máximo de intentos alcanzado).\n"
    elif error:
        context += "ESTADO: RE-PREGUNTA (ERROR: El código anterior fue incorrecto).\n"
    elif is_re_pregunta:
        context += "ESTADO: RE-PREGUNTA (CONTINUACIÓN: El usuario está conversando).\n"
    else:
        context += "ESTADO: AVISO NUEVO (El usuario acaba de llegar a este paso).\n"
        
    context += f"Último mensaje: {last_msg}"
    return context

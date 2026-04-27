"""
app/graph/nodes/credit.py
─────────────────────────────────────────────────────────────
Nodos del flujo de Crédito de Consumo.

Ruta del grafo: loan_init → loan_risk_engine → END
  - loan_init        (ID LangGraph) → current_node = "LOAN_INIT"
  - loan_risk_engine  (ID LangGraph) → current_node = "LOAN_RISK_ENGINE"
"""

from langchain_core.messages import AIMessage, HumanMessage
from app.infra.gemini_client import get_structured_model
from app.graph.state import FluxState
from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction, LoanSimExtraction
from app.infra.supabase import update_application_semaphores

# ======================================================================================================
# LLM Y PROMPTS
# ======================================================================================================

# ── CONFIGURACIÓN DE INTELIGENCIA (SINGLETONS) ──────────────
# Usamos get_structured_model para instanciar Gemini con salida validada.

_profile_extractor = get_structured_model(LoanProfileExtraction)
_sim_extractor     = get_structured_model(LoanSimExtraction)


# ── SYSTEM PROMPTS (IDENTIDAD FLUX + REGLAS) ────────────────

# ── 1. IDENTIDAD CORE (Reutilizable en todo el bot)
FLUX_IDENTITY = (
    "Eres Flux, el genio amigable de las finanzas en Chile. "
    "Hablas de tú, eres cercano, ágil y traduces la burocracia a lenguaje humano. "
    "Entiendes perfectamente el contexto chileno y modismos locales."
)

# ── 2. REGLAS DE EXTRACCIÓN (Solo para nodos de captura)
# Estas reglas son comunes para Profile y Simulación (dinero/tiempo)
EXTRACTION_RULES = (
    "REGLAS DE NORMALIZACIÓN:\n"
    "- 'palo' = 1.000.000 | 'luca' = 1.000.\n"
    "- Convierte años a meses (ej: '2 años' = 24).\n"
    "- Si un dato no fue mencionado, déjalo como null.\n"
    "- No inventes datos que el usuario no haya dicho."
)

# ── 3. SYSTEM PROMPTS ESPECÍFICOS POR NODO

# Para LOAN_COLLECTING_PROFILE
SYSTEM_PROMPT_PROFILE = f"""
{FLUX_IDENTITY}
TAREA: Analiza el mensaje e identifica los datos del PERFIL financiero.
{EXTRACTION_RULES}
- Normaliza estudios a: POSTGRADO, UNIVERSITARIO, TECNICO o MEDIA.
Extrae: renta mensual, antigüedad laboral (meses) y nivel estudios.
"""

# Para LOAN_COLLECTING_SIMULATION
SYSTEM_PROMPT_SIM = f"""
{FLUX_IDENTITY}
TAREA: Analiza el mensaje e identifica los datos de la SIMULACIÓN.
{EXTRACTION_RULES}
Extrae: monto solicitado y cuotas (plazo).
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
        4. Actualizar semáforo: LOAN_INIT / SUCCESS / PENDING.

    OUTPUT (campos del State que modifica):
        - messages: Saludo de bienvenida al flujo de crédito.
        - session["current_node"]: "LOAN_INIT".
        - collecting_data["loan_profile"]: {} (limpio).
        - collecting_data["loan_sim"]: {} (limpio).
    """
    prep = state.get("preparation_data", {})
    session = state.get("session", {})

    nombre = prep.get("nombre", "")
    first_name = nombre.split()[0] if nombre else "amig@"

    product_intent = session.get("product_intent")
    if product_intent != "LOAN":
        msg = "Hubo un error de navegación. Por favor, indica nuevamente qué necesitas."
    else:
        msg = (
            f"¡Perfecto, {first_name}! Vamos a revisar tu solicitud de **Crédito de Consumo**. "
            f"Es un proceso rápido. Primero necesito conocer un poco tu perfil financiero. "
            f"¿Cuál es tu renta líquida mensual?"
        )

    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_INIT",   # Valor semántico UPPER_CASE para Supabase
            node_status="SUCCESS",         # El INIT es síncrono: terminó al retornar
            engine_status="PENDING",       # El motor aún no ha arrancado
        )

    return {
        "messages": [AIMessage(content=msg)],
        "session": {**session, "current_node": "LOAN_INIT"},
        "collecting_data": {
            "loan_profile": {},
            "loan_sim": {},
        },
    }


# ── 2. NODO DE RECOLECCION PERFIL (loan_collecting_profile) ───────────────────────────────────

def loan_collecting_profile_node(state: FluxState) -> dict:
    """
    Nodo LOAN_COLLECTING_PROFILE: extrae renta, antigüedad y nivel de estudios.

    ID LangGraph : loan_collecting_profile
    current_node : LOAN_COLLECTING_PROFILE

    MODO A (Extracción exitosa):
        - Actualiza collecting_data["loan_profile"] con los datos extraídos.
        - No emite mensaje (el grafo avanza silenciosamente si todos los datos están presentes).
        - Si faltan datos: emite re-pregunta específica.

    MODO B (Re-pregunta):
        - Conserva los datos ya recolectados en el State (merge, no reemplaza).
        - Retorna mensaje empático solicitando el dato faltante.

    NOTA DE PERSISTENCIA:
        El merge de datos es crítico para el Checkpointer. Si el usuario
        da la renta en un mensaje y la antigüedad en otro, ambos deben
        acumularse en loan_profile, no sobreescribirse.
    """
    # 1. Extracción de variables
    session = state.get("session", {})
    collecting = state.get("collecting_data", {})
    messages = state.get("messages", [])
    current_profile = collecting.get("loan_profile", {}) # datos previos

    # 2. Captura del último mensaje del usuario
    last_user_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")

    # 3. Invocación de Gemini para extracción
    extracted = _profile_extractor.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_PROFILE},
        {"role": "user",   "content": last_user_msg},
    ])
    
    # 4. Merge defensivo: solo actualizar campos que llegaron con valor (evita borrar 0 por None)
    updated_profile = {**current_profile}
    if extracted.renta is not None: 
        updated_profile["renta"] = extracted.renta
    if extracted.antiguedad_laboral is not None: 
        updated_profile["antiguedad_laboral"] = extracted.antiguedad_laboral
    if extracted.nivel_estudios is not None: 
        updated_profile["nivel_estudios"] = extracted.nivel_estudios

    # 5. Determinar campos faltantes
    missing = [f for f in ["renta", "antiguedad_laboral", "nivel_estudios"] if not updated_profile.get(f)]

    # 6. Preparar la respuesta base
    output = {
        "collecting_data": {**collecting, "loan_profile": updated_profile},
        "session": {**session, "current_node": "LOAN_COLLECTING_PROFILE"}
    }

    application_id = session.get("application_id") 

    if not missing:
        # ÉXITO: Actualizamos Supabase y avanzamos silenciosamente
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="LOAN_COLLECTING_PROFILE",
                node_status="SUCCESS",
                engine_status="PENDING",
            )
        return output
    
    else:
        # RE-PREGUNTA CON CONTEXTO: Añadimos mensaje de Flux al output
        re_ask_msg = _build_flux_reprompt(missing, updated_profile, "perfil")
        output["messages"] = [AIMessage(content=re_ask_msg)]
        return output
            
# ── 3. NODO DE RECOLECCION MONTO Y PLAZO (loan_collecting_simulation) ───────────────────────────────────

def loan_collecting_simulation_node(state: FluxState) -> dict:
    pass    


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
    session = state.get("session", {})
    prep = state.get("preparation_data", {})
    collecting = state.get("collecting_data", {})

    loan_profile = collecting.get("loan_profile", {})
    loan_sim = collecting.get("loan_sim", {})

    renta = loan_profile.get("renta", 0)
    monto_solicitado = loan_sim.get("monto_solicitado", 0)
    plazo_solicitado = loan_sim.get("plazo_solicitado", 0)

    # TODO Fase 2: engine_result = credit_eng.calculate_risk_score(...)
    engine_result = {
        "status_proceso": "PRE_APPROVED",
        "scoring_puntos": 0,
        "nivel_riesgo": "",
        "tasa_interes_mensual": 0.0,
        "cuota_mensual": 0,
        "cuota_maxima_permitida": int(renta * 0.30),
        "capacidad_pago_valida": True,
        "ctc": 0,
        "total_intereses": 0,
        "cae": 0.0,
        "monto_aprobado": monto_solicitado,
        "plazo_aprobado": plazo_solicitado,
        "motivo_rechazo": None,
    }

    application_id = session.get("application_id")
    if application_id:
        update_application_semaphores(
            application_id=application_id,
            current_node_id="LOAN_RISK_ENGINE",
            node_status="SUCCESS",
            engine_status="COMPLETED",
        )

    return {
        "evaluation_results": {
            "loan_engine": engine_result,
        },
        "session": {**session, "current_node": "LOAN_RISK_ENGINE"},
    }

# ======================================================================================================
# NODOS DEL FLUJO DE CREDITO DE CONSUMO
# ======================================================================================================

# ── HELPERS DE RECOLECCIÓN (UTILITIES) ──────────────────────

# ── Obtener campos faltantes del perfil
def _get_missing_profile_fields(profile: dict) -> list[str]:
    """Retorna lista de campos requeridos que aún no tienen valor."""
    required = ["renta", "antiguedad_laboral", "nivel_estudios"]
    # Usamos 'is None' para ser precisos con los datos del LLM
    return [f for f in required if profile.get(f) is None]

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
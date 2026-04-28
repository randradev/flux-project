## PASO 4 — Implementación de la Doble Llamada en el Nodo

> **Objetivo:** Refactorizar `loan_collecting_profile_node` para implementar el flujo Llamada A → Llamada B de forma transaccional.

---

### Sub-paso 4.1 — Agregar el singleton del modelo generador en `credit.py` [CÓDIGO]

**Archivo:** `app/graph/nodes/credit.py`

Al inicio del archivo, donde se instancian los modelos:

```python
from app.infra.gemini_client import get_structured_model, get_generation_model

# Singletons de modelos (se instancian una vez al importar el módulo)
_profile_extractor = get_structured_model(LoanProfileExtraction)
_sim_extractor     = get_structured_model(LoanSimExtraction)
_flux_generator    = get_generation_model()  # NUEVO — Llamada B
```

---

### Sub-paso 4.2 — Crear el helper `_build_generation_context` [CÓDIGO]

**Archivo:** `app/graph/nodes/credit.py`

Este helper construye el bloque de contexto estructurado que recibe el generador. Es el "puente" entre la Llamada A y la Llamada B.

```python
def _build_generation_context(
    nombre: str,
    intencion: str,
    known_profile: dict,
    missing: list[str],
    newly_extracted: dict,
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
    
    context = f"""CONTEXTO PARA TU RESPUESTA:
    
Usuario: {nombre}
Intención detectada en su último mensaje: {intencion}

Datos del perfil YA CONOCIDOS (no volver a pedir):
{chr(10).join(known_lines) if known_lines else "  - (ninguno aún)"}

Datos recién entregados en este turno (para celebrar/comentar si hay alguno):
{chr(10).join(new_lines) if new_lines else "  - (ninguno en este mensaje)"}

Datos que AÚN FALTAN (pide exactamente el primero de la lista, no todos):
{chr(10).join(f"  - {l}" for l in missing_labels) if missing_labels else "  - (ninguno, perfil completo)"}

INSTRUCCIÓN: Genera la respuesta de Flux según este contexto. 
Si hay datos nuevos, celébrarlos brevemente. Luego pide solo el PRIMER dato faltante.
Si la intención es SALUDO u OTRO, responde con empatía y redirige amablemente a pedir el primer dato faltante.
Si la intención es PREGUNTA, reconoce la duda brevemente y redirige al proceso.
"""
    return context
```

---

### Sub-paso 4.3 — Refactorizar `loan_collecting_profile_node` con Doble Llamada [CÓDIGO]

**Archivo:** `app/graph/nodes/credit.py`

Esta es la implementación central. El nodo orquesta las dos llamadas y hace un único `return` transaccional al final.

```python
def loan_collecting_profile_node(state: FluxState) -> dict:
    """
    Nodo LOAN_COLLECTING_PROFILE: recolección del perfil financiero del usuario.
    
    ID LangGraph : loan_collecting_profile
    current_node : LOAN_COLLECTING_PROFILE
    
    ARQUITECTURA INTERNA — DOBLE LLAMADA:
    
      Llamada A (Extractor):
        - Modelo   : gemini-2.0-flash, temperature=0.0, function_calling
        - Input    : Último mensaje del usuario
        - Output   : LoanProfileExtraction (JSON validado por Pydantic)
        - Objetivo : Extraer datos financieros. Clasificar intención.
                     Jamás genera texto conversacional.
    
      Llamada B (Generador) — Solo si se necesita emitir un mensaje:
        - Modelo   : gemini-2.0-flash, temperature=0.7, texto libre
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
    # ── 1. EXTRACCIÓN DE VARIABLES DEL STATE ───────────────────
    session         = state.get("session", {})
    collecting      = state.get("collecting_data", {})
    prep            = state.get("preparation_data", {})
    messages        = state.get("messages", [])
    
    current_profile = collecting.get("loan_profile", {})
    nombre          = prep.get("nombre", "")
    first_name      = nombre.split()[0] if nombre else "amig@"
    application_id  = session.get("application_id")
    
    # ── 2. CAPTURA DEL ÚLTIMO MENSAJE DEL USUARIO ──────────────
    last_user_msg = next(
        (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
        ""
    )
    
    # Guardrail: si no hay mensaje del usuario, re-preguntar desde el estado actual
    if not last_user_msg.strip():
        missing = _get_missing_profile_fields(current_profile)
        context = _build_generation_context(
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
    
    # ── 3. LLAMADA A — EXTRACCIÓN ──────────────────────────────
    extracted: LoanProfileExtraction = _profile_extractor.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_EXTRACTION_PROFILE},
        {"role": "user",   "content": last_user_msg},
    ])
    
    # ── 4. MERGE DEFENSIVO ─────────────────────────────────────
    # Solo actualizar campos que el extractor encontró en ESTE turno.
    # Los campos None del extractor no sobreescriben datos previos del State.
    newly_extracted = {}  # Diccionario de lo nuevo: para que Flux lo comente
    updated_profile = {**current_profile}
    
    if extracted.intencion == "DATO_FINANCIERO":
        if extracted.renta is not None:
            updated_profile["renta"] = extracted.renta
            if current_profile.get("renta") != extracted.renta:  # Es realmente nuevo
                newly_extracted["renta"] = extracted.renta
        
        if extracted.antiguedad_laboral is not None:
            updated_profile["antiguedad_laboral"] = extracted.antiguedad_laboral
            if current_profile.get("antiguedad_laboral") != extracted.antiguedad_laboral:
                newly_extracted["antiguedad_laboral"] = extracted.antiguedad_laboral
        
        if extracted.nivel_estudios is not None:
            updated_profile["nivel_estudios"] = extracted.nivel_estudios
            if current_profile.get("nivel_estudios") != extracted.nivel_estudios:
                newly_extracted["nivel_estudios"] = extracted.nivel_estudios
    # Si intencion != DATO_FINANCIERO: no se hace merge. current_profile se preserva intacto.
    
    # ── 5. EVALUACIÓN DE COMPLETITUD ───────────────────────────
    missing = _get_missing_profile_fields(updated_profile)
    
    # ── 6. PREPARAR OUTPUT BASE (siempre presente) ──────────────
    output = {
        "collecting_data": {**collecting, "loan_profile": updated_profile},
        "session":         {**session, "current_node": "LOAN_COLLECTING_PROFILE"},
    }
    
    # ── 7. DECISIÓN: ¿Avance silencioso o Llamada B? ───────────
    if not missing:
        # AVANCE SILENCIOSO: Todos los datos son válidos y completos.
        # La Llamada B NO se invoca. El grafo avanza al siguiente nodo.
        if application_id:
            update_application_semaphores(
                application_id=application_id,
                current_node_id="LOAN_COLLECTING_PROFILE",
                node_status="SUCCESS",
                engine_status="PENDING",
            )
        return output  # ← Return transaccional sin mensajes
    
    # ── 8. LLAMADA B — GENERACIÓN ──────────────────────────────
    # Solo se ejecuta si hay campos faltantes o la intención requiere respuesta.
    context = _build_generation_context(
        nombre=first_name,
        intencion=extracted.intencion,
        known_profile=updated_profile,
        missing=missing,
        newly_extracted=newly_extracted,
    )
    
    flux_response = _flux_generator.invoke([
        {"role": "system", "content": SYSTEM_PROMPT_GENERATION_PROFILE},
        {"role": "user",   "content": context},
    ])
    
    # ── 9. RETURN TRANSACCIONAL ────────────────────────────────
    # Un único return con todos los cambios al State.
    output["messages"] = [AIMessage(content=flux_response.content)]
    return output
```

---

**✅ CRITERIO PASS Sub-paso 4.3** [TEST-UNITARIO con mocks]:

```python
# tests/unit/test_loan_collecting_profile_node.py
# No requiere credenciales de Vertex AI — mockea ambos modelos.

from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from app.graph.nodes.credit import loan_collecting_profile_node
from app.graph.nodes.schemas.loan_schemas import LoanProfileExtraction


def make_state(user_msg: str, profile: dict = None):
    return {
        "messages":       [HumanMessage(content=user_msg)],
        "collecting_data": {"loan_profile": profile or {}, "loan_sim": {}},
        "session":        {"current_node": "LOAN_COLLECTING_PROFILE", "application_id": None},
        "preparation_data": {"nombre": "Juan Pérez", "edad": 30},
    }


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_avance_silencioso_no_invoca_generador(mock_extractor, mock_generator):
    """Con perfil completo: Llamada B (generador) NO debe invocarse."""
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        renta=2_000_000,
        antiguedad_laboral=36,
        nivel_estudios="UNIVERSITARIO"
    )
    
    result = loan_collecting_profile_node(
        make_state("Gano 2 millones, llevo 3 años, soy universitario")
    )
    
    mock_generator.invoke.assert_not_called()  # ← La prueba crítica
    assert "messages" not in result or len(result.get("messages", [])) == 0
    assert result["collecting_data"]["loan_profile"]["renta"] == 2_000_000


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_saludo_no_contamina_state(mock_extractor, mock_generator):
    """Un saludo no debe modificar el loan_profile."""
    mock_extractor.invoke.return_value = LoanProfileExtraction(intencion="SALUDO")
    mock_generator.invoke.return_value = MagicMock(content="¡Hola! Estamos en tu solicitud de crédito. ¿Cuál es tu renta?")
    
    state = make_state("Hola!", profile={"renta": 1_000_000})  # Renta ya conocida
    result = loan_collecting_profile_node(state)
    
    # El perfil no debe haber cambiado
    assert result["collecting_data"]["loan_profile"].get("renta") == 1_000_000
    # El generador sí debe haberse invocado
    mock_generator.invoke.assert_called_once()
    # El resultado debe tener un mensaje
    assert "messages" in result and len(result["messages"]) > 0


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_centinelas_pydantic_no_actualizan_perfil(mock_extractor, mock_generator):
    """Si el LLM alucina centinelas, Pydantic los normaliza a None y el perfil no se contamina."""
    # Simular que el LLM retornó valores centinela que Pydantic ya normalizó
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        renta=0,               # Centinela → normalizado a None por Pydantic
        antiguedad_laboral=-1, # Centinela → normalizado a None por Pydantic
        nivel_estudios="MEDIA" # Válido
    )
    mock_generator.invoke.return_value = MagicMock(content="Casi listo, solo me falta tu renta y antigüedad.")
    
    state = make_state("algo irrelevante")
    result = loan_collecting_profile_node(state)
    
    profile = result["collecting_data"]["loan_profile"]
    assert profile.get("renta") is None,              "renta=0 no debe escribirse"
    assert profile.get("antiguedad_laboral") is None,  "ant=-1 no debe escribirse"
    assert profile.get("nivel_estudios") == "MEDIA",   "MEDIA sí debe escribirse"


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_merge_acumulativo_entre_turnos(mock_extractor, mock_generator):
    """Los datos de turnos anteriores se preservan cuando llegan datos nuevos."""
    mock_extractor.invoke.return_value = LoanProfileExtraction(
        intencion="DATO_FINANCIERO",
        antiguedad_laboral=24  # Solo antigüedad nueva
    )
    mock_generator.invoke.return_value = MagicMock(content="¡Anotado! ¿Y tu nivel de estudios?")
    
    # Estado previo: ya tiene renta
    state = make_state("Llevo 2 años trabajando", profile={"renta": 1_500_000})
    result = loan_collecting_profile_node(state)
    
    profile = result["collecting_data"]["loan_profile"]
    assert profile.get("renta") == 1_500_000,         "La renta previa debe conservarse"
    assert profile.get("antiguedad_laboral") == 24,    "La nueva antigüedad debe guardarse"


@patch("app.graph.nodes.credit._flux_generator")
@patch("app.graph.nodes.credit._profile_extractor")
def test_un_solo_return_transaccional(mock_extractor, mock_generator):
    """El nodo debe retornar siempre los tres campos del State en un solo dict."""
    mock_extractor.invoke.return_value = LoanProfileExtraction(intencion="SALUDO")
    mock_generator.invoke.return_value = MagicMock(content="Hola, retomemos.")
    
    result = loan_collecting_profile_node(make_state("Hola"))
    
    assert "collecting_data" in result, "collecting_data debe estar siempre en el output"
    assert "session" in result,         "session debe estar siempre en el output"
    assert result["session"]["current_node"] == "LOAN_COLLECTING_PROFILE"
```

---
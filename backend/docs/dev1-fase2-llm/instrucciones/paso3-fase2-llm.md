## PASO 3 — Diseño de Prompts

> **Objetivo:** Rediseñar los prompts de extracción y crear el nuevo prompt de generación conversacional. Estos son los prompts que determinan la "humanidad" de Flux.

---

### Sub-paso 3.1 — Prompt de Extracción (Llamada A) [PROMPT]

**Archivo:** `app/graph/nodes/credit.py`

**Principio de diseño:** El prompt de extracción debe ser **minimalista y directivo**. No debe hablar de personalidad ni de Chile. Su única audiencia es el LLM-extractor, no el usuario.

```python
# ── PROMPT LLAMADA A: EXTRACCIÓN ────────────────────────────────────────────
# Directivo y sin ambigüedad. Temperatura 0.0 hace el trabajo pesado;
# el prompt solo establece el contrato de qué retornar.

SYSTEM_PROMPT_EXTRACTION_PROFILE = """
Eres un motor de extracción de datos financieros. Tu única función es analizar el mensaje del usuario y retornar un JSON estructurado.

INSTRUCCIONES:
1. Clasifica el mensaje en el campo `intencion`:
   - DATO_FINANCIERO: si el mensaje contiene renta, antigüedad laboral o nivel de estudios.
   - PREGUNTA: si el usuario hace una pregunta (¿qué es...?, ¿cómo...?, ¿cuánto...?).
   - SALUDO: si es un saludo, despedida o frase social ("hola", "gracias", "adiós").
   - OTRO: cualquier mensaje que no encaje en las anteriores.

2. Extrae los datos SOLO si fueron mencionados explícitamente o con jerga coloquial clara:
   - "palo" = 1.000.000 CLP | "luca" = 1.000 CLP
   - Años a meses: 1 año = 12 meses
   - Normaliza nivel_estudios al Literal exacto.

3. REGLA ABSOLUTA: Si un dato NO fue mencionado, retorna null para ese campo.
   No uses valores por defecto. No uses 0 ni -1 como placeholder.
   Un saludo no contiene renta. Una pregunta no contiene antigüedad.
"""

SYSTEM_PROMPT_EXTRACTION_SIM = """
Eres un motor de extracción de datos financieros. Tu única función es analizar el mensaje del usuario y retornar un JSON estructurado.

INSTRUCCIONES:
1. Clasifica el mensaje en `intencion`: DATO_FINANCIERO si contiene monto o plazo del crédito. PREGUNTA, SALUDO u OTRO para el resto.

2. Extrae monto_solicitado y plazo_solicitado SOLO si fueron mencionados:
   - "palo" = 1.000.000 | "luca" = 1.000
   - Años a meses para el plazo.

3. REGLA ABSOLUTA: null para cualquier dato no mencionado.
"""
```

---

### Sub-paso 3.2 — Prompt de Generación Conversacional (Llamada B) [PROMPT]

**Archivo:** `app/graph/nodes/credit.py`

**Principio de diseño:** El prompt de generación recibe un **bloque de contexto estructurado** (no los mensajes crudos) y produce la respuesta de Flux. Esto desacopla completamente al generador del extractor.

```python
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
"""
```

---

**✅ CRITERIO PASS Sub-paso 3.1 y 3.2** [Revisión manual]:

Los prompts son revisados por el desarrollador contra esta checklist antes de continuar:

- [ ] `SYSTEM_PROMPT_EXTRACTION_PROFILE` no menciona "Flux", "Chile" ni personalidad.
- [ ] `SYSTEM_PROMPT_EXTRACTION_PROFILE` contiene la frase "null para cualquier dato no mencionado".
- [ ] `SYSTEM_PROMPT_GENERATION_PROFILE` no menciona "extrae", "JSON", ni estructuras de datos.
- [ ] `SYSTEM_PROMPT_GENERATION_PROFILE` contiene la restricción de "máximo UNA pregunta a la vez".

---
# Directrices de Implementación y Auditoría: Identidad Flux y Adaptación Técnica

## 1. Medida Técnica: Instanciación de Modelos vía gemini_client
Se debe abandonar el uso de clientes genéricos (como ChatOpenAI) en favor de la infraestructura centralizada del proyecto para garantizar la correcta conexión con Vertex AI y evitar errores de endpoint.

**Descripción:** Todos los nodos que requieran extracción estructurada (ej. loan_collecting_profile_node) deben importar y utilizar la función get_structured_model(schema) ubicada en app.infra.gemini_client.

**Modelo Objetivo:** gemini-3-flash-preview.

**Configuración:** La temperatura debe mantenerse en 0.1 para asegurar precisión en la extracción de datos financieros.

## 2. Medida de Identidad: El System Prompt "Genio Amigable"
El tono de voz de Flux no es opcional; es una ventaja competitiva definida como "horizontal, cercano y transparente".

**Descripción:** Cada SYSTEM_PROMPT de los nodos de extracción debe comenzar con un bloque de identidad que instruya al modelo a actuar como Flux.

**Directrices de Tono:**
- Hablar de "tú" (horizontalidad chilena).
- Evitar la frialdad corporativa; ser ágil y "hackeador de burocracia".
- Mantener claridad radical en la comunicación.

**Ejemplo de Bloque:** "Eres Flux, el genio amigable de las finanzas en Chile. Tu tono es horizontal, cercano y sin burocracia verbal. Entiendes el contexto local y hablas de tú al usuario.".

## 3. Medida de Contexto: Enriquecimiento de Esquemas (Léxico Chileno)
Para que Gemini procese correctamente la jerga informal, los esquemas Pydantic deben actuar como un "traductor cultural".

**Descripción:** Se deben modificar las descripciones (description) de los campos en LoanProfileExtraction y LoanSimExtraction para incluir ejemplos de modismos chilenos.

**Ejemplos Requeridos:**
- Renta: Incluir referencias a "lucas" y "palos".
- Antigüedad: Referencias a "pega" o "tiempo en la empresa".
- Monto: Referencias a "millones" o "palos".

## 4. Medida de Normalización: Reglas de Jerga Financiera
Para evitar errores en el Motor de Cálculo (Paso 1), el LLM debe normalizar todas las expresiones informales a valores numéricos estándar antes de actualizar el State.

**Descripción:** El SYSTEM_PROMPT debe contener una tabla de normalización explícita para asegurar que los cálculos de cuota y capacidad de pago sean exactos.

**Reglas de Normalización:**
- 1 palo = 1.000.000 CLP.
- 1 luca = 1.000 CLP.
- Sueldo mínimo = Valor legal vigente en Chile (~500.000 CLP).
- Años a Meses = Multiplicar por 12 (ej. "2 años" → 24).

## 5. Checklist para el Agente Auditor (Antigravity)
Al revisar el código de la Fase 2, el agente debe verificar:

- [ ] Origen del Modelo: ¿El nodo importa get_structured_model de app.infra.gemini_client?
- [ ] ADN Flux: ¿El SYSTEM_PROMPT incluye instrucciones sobre el tono horizontal y chileno?
- [ ] Diccionario Chileno: ¿Los campos del esquema Pydantic contienen ejemplos de "lucas", "palos" o "pega" en sus descripciones?
- [ ] Salida Limpia: ¿El nodo está retornando tipos de datos puros (int/str) tras normalizar la jerga, sin símbolos de moneda ni texto adicional?
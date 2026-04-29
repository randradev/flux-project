# IMPACTO DE LA ESTABILIZACIÓN DEL LLM EN LA FASE 2 PARA EL RESTO DEL PLAN DE TRABAJO DE LA FASE 2

## 1. Fase de Estabilización del LLM
Se ha completado una fase de estabilización crítica para el módulo de crédito. El objetivo principal fue erradicar las alucinaciones sistemáticas (como el "fantasma del 600.000") y asegurar que el estado del sistema (State) sea inmutable ante mensajes irrelevantes. Se pasó de una lógica de "confianza ciega" en el modelo a una Arquitectura de Doble Llamada con validación técnica rigurosa.

**Resumen de cambios realizados (No taxativo):**
- **Arquitectura de Doble Llamada**: Separación física del proceso en Llamada A (Extracción técnica, Temp 0.0) y Llamada B (Generación conversacional, Temp 0.7).
- **Sentinel Pattern**: Uso de valores centinela (0 o -1) normalizados a None mediante validadores de Pydantic para evitar el "avance silencioso" con basura técnica.
- **Filtrado por Intención**: Incorporación de un clasificador de intenciones en el extractor para proteger el State de ruidos o saludos.
- **Razonamiento Previo (CoT)**: Obligatoriedad de un campo razonamiento en el esquema de extracción para forzar al modelo a analizar el texto antes de asignar valores.

## 2. Análisis de Impactos en el Flujo de Crédito
A continuación, se detallan los impactos identificados que deben replicarse desde el Paso 3 (Motor de Riesgo) hasta el Cierre:

**A. El Rol de la Llamada B en Nodos No-Extractores**
- **Antes**: Los nodos que no requerían datos (como "Rechazo" u "Oferta") usaban prompts genéricos o una sola llamada al LLM mezclando lógica y respuesta.
- **Ahora**: Todos los nodos donde Flux habla adoptan el patrón de Llamada B. Reciben un contexto procesado, pero no ejecutan extracción.
- **Por qué**: Para mantener la coherencia de personalidad y la "escucha activa" sin el riesgo de que el modelo intente extraer datos inexistentes por sesgo de formato.
- **Impacto**: Estabilidad total en la voz de la marca y eliminación de errores de parsing en pasos donde no hay nada que parsear.

**B. El "Disparo de Transición" (Trigger)**
- **Antes**: El flujo avanzaba solo si los campos del State estaban llenos.
- **Ahora**: Se utilizan Flags de Evento (ej. profile_just_completed, simulation_just_completed) para disparar transiciones naturales.
- **Por qué**: El LLM necesita saber exactamente en qué momento se acaba de completar un proceso técnico para cambiar su tono de "recolector" a "informador".
- **Impacto**: Transiciones conversacionales fluidas y eliminación de re-preguntas redundantes cuando el motor de riesgo ya tiene el resultado.

**C. Esquemas Pydantic: De "Extracción" a "Intención"**
- **Antes**: El foco del esquema era puramente el dato financiero (renta, monto).
- **Ahora**: El esquema prioriza la Intención del Usuario (DATO_FINANCIERO, PREGUNTA, SALUDO).
- **Por qué**: Si el usuario hace una pregunta sobre el producto, el sistema debe detectarlo como una intención y no intentar "encajar" la pregunta en un campo numérico.
- **Impacto**: Robustez ante el cambio de contexto del usuario y protección de la integridad de los datos ya guardados.

**D. La "Burbuja de Contexto" (Memoria de Corto Plazo)**
- **Antes**: Se pasaba todo el historial de mensajes al LLM, lo que causaba "fugas de atención" (el modelo recordaba números de turnos pasados y los repetía).
- **Ahora**: Se implementa un Contexto Aislado mediante el helper _build_generation_context.
- **Por qué**: Limitar la atención del modelo solo a lo que es relevante para el turno actual evita que alucine datos antiguos en campos nuevos.
- **Impacto**: Eliminación drástica de la persistencia de errores y alucinaciones de "memoria residual".

**3. Notas Técnicas Especiales**
**NOTA 1: Validación OTP (Seguridad y Moderación)**
La validación de la clave OTP debe operar bajo un modelo de Entrada Estricta. El LLM actúa únicamente como moderador, guiando al usuario y explicando el proceso. La extracción del código de 6 dígitos no debe ser delegada al LLM; el código se ingresa en un campo de input determinista de la interfaz.

*Observación Técnica:* Se debe asegurar que el State de LangGraph se actualice mediante una Action externa o un Tool que el LLM llame solo cuando la UI confirme que el código se envió, manteniendo al LLM como el "locutor" de lo que sucede en el backend.

**NOTA 2: Formalización y Cierre (Determinismo de Consentimiento)**
Este nodo es 100% determinista por razones de transparencia y seguridad legal. El consentimiento del usuario ("Acepto" / "Rechazo") se captura exclusivamente a través de botones físicos en la interfaz.

*Operación:* El LLM no interpreta si el usuario "parece" estar de acuerdo en el chat. El flujo del grafo solo avanza cuando recibe el payload directo del botón presionado. El rol del LLM en este paso se limita a resumir las condiciones finales y explicar las implicancias de la firma digital, actuando como un asistente de cierre, pero nunca como el validador del consentimiento.
# ESTADOS MAESTROS TRANSVERSALES

## 1. BLOQUE DE GESTIÓN DE INTENCIONES
- AMBIGUITY_HANDLER: Se activa cuando el LLM no está seguro (ej: el usuario responde algo vago). Su función es re-encauzar al usuario sin perder el contexto.
    - Función: Gestionar cuando el usuario responde cosas que no sirven (ej: "está lloviendo", "no sé", "luego te digo").
    - Comportamiento: Es el encargado de re-preguntar de forma amable, manteniendo al usuario en el nodo actual hasta que se reciba un dato válido o una consulta (RAG).

## 2. BLOQUE DE CONOCIMIENTO Y ASISTENCIA
- KNOWLEDGE_BASE_RAG: El buscador. Consulta los documentos (.md, políticas, reglamentos) para responder dudas técnicas sin salir del chat.
    - Función: Responder dudas sobre Flux o el producto específico sin abandonar el flujo.
    - Comportamiento: Siempre termina con una frase de transición: "Respondida tu duda, continuemos con...".

## 3. BLOQUE DE RESILIENCIA TÉCNICA
- SERVICE_ERROR_HANDLER: Maneja caídas de APIs (como el motor de riesgo o el generador de PDF). Ofrece reintentar o avisar cuando vuelva.
    - Función: Actuará cuando falle el Motor de Riesgo, la DB, el generador de PDF, APIs de consumo de terceros, etc.
    - Comportamiento: Informa al usuario que su progreso está guardado y que puede volver en unos minutos. Evita que el usuario piense que "se rompió" el bot.

## 4. BLOQUE DE SEGURIDAD Y AUDITORÍA
- SECURITY_WATCHDOG: Monitorea comportamientos de riesgo, intentos de inyección de texto para engañar a la IA o insultos.
    - Función: Controlar los intentos fallidos de identidad y comportamientos maliciosos.
    - Comportamiento: Bloquea la aplicación y marca el estado en la DB como BLOCKED.
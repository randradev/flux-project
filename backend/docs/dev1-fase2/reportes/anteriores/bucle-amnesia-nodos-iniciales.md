# Informe de Arquitectura: Resolución del "Bucle de Amnesia" y Estabilización de la Fase 2

## I. El Problema Central: La Naturaleza de LangGraph
El error fundamental que hemos detectado es la falta de persistencia lógica en el ruteo. En LangGraph, el grafo se destruye y renace en cada interacción (cada mensaje del usuario). Como el punto de entrada (entry_point) es siempre el mismo, el sistema tiende a repetir sus pasos iniciales si no tiene una "memoria de navegación" sólida.

### El "Bucle de Amnesia" (Síntoma)
1. El usuario elige un producto.
2. El sistema saluda.
3. El usuario entrega un dato (ej. su renta).
4. El sistema vuelve al inicio, olvida que ya pidió la renta y vuelve a saludar, borrando el progreso.

## II. Auditoría de Nodos: Responsabilidades vs. Problemas
- **Nodo: welcome_node:**
    - **Responsabilidad Teórica:** Cargar perfil desde Supabase (RUT, edad, nombre) y preparar el estado.
    - **Problema actual (Fase 2):** El "Spammer": Siempre añade un mensaje de saludo al historial y sobrescribe el current_node, borrando el rastro de productos activos.
- **Nodo: intent_router:**
    - **Responsabilidad Teórica:** Clasificar la intención del usuario (LLM Tipo A) si no hay un botón presionado.
    - **Problema actual:** El Obstáculo: Se ejecuta incluso cuando la intención ya es clara (clic en botón), añadiendo latencia y riesgo de error.
- **Nodo: loan_init:**
    - **Responsabilidad Teórica:** Punto de entrada al crédito. Limpia contextos previos y da la bienvenida al producto.
    - **Problema actual:** El Robot: Tiene un saludo fijo ("hardcodeado") y realiza un reset agresivo que borra los datos que el usuario acaba de enviar.
- **Nodo: loan_collecting_profile:**
    - **Responsabilidad Teórica:** Nodo de recolección de datos (renta, actividad, etc.).
    - **Problema actual:** El Olvidadizo: Al no estar bien conectado con los ruteadores iniciales, el sistema no sabe cómo regresar aquí tras el "renacimiento" del grafo.

## III. Propuesta de Requerimientos Críticos de Cambio
1. El "Welcome Silencioso" (Lógica Técnica vs Visual):
    - El welcome_node debe dejar de ser una "pantalla de bienvenida" obligatoria para convertirse en un Nodo de Hidratación de Datos.
        - **Lógica:** Si el usuario viene de un clic de botón (ya existe product_intent) o si la sesión ya tiene mensajes, el nodo debe cargar los datos del perfil en silencio, sin generar ningún AIMessage.
        - **Objetivo:** Evitar el doble saludo y permitir que el primer mensaje que vea el usuario sea el del producto específico. 

2. Eliminación de Saludos "Hardcodeados" (Llamada Tipo B)
    - El nodo loan_init (y futuros inits de Cuenta o DAP) no deben usar strings fijos.
        - **Acción:** Implementar una Llamada Tipo B. Esto significa usar el LLM para generar una transición empática.
        - **Ejemplo:** En lugar de decir siempre lo mismo, el LLM recibe: "El usuario se llama Juan y tiene 30 años, dale la bienvenida al crédito de consumo y pídele su renta". Flux responderá de forma variada y humana

3. Sincronización del Estado (El "Punto de Guardado")
    - Debemos ser estrictos con la variable current_node en la sesión:
        - **Regla:** Un nodo solo puede actualizar el current_node si es para avanzar.
        - **Sincronización:** Cuando loan_init lanza la pregunta sobre la renta, debe marcar inmediatamente el current_node como LOAN_COLLECTING_PROFILE. Así, el ruteador sabrá exactamente a dónde volver en el siguiente turno.

## IV. La Nueva Lógica de Ruteo (Edges)
La función route_after_welcome en edges.py es el cerebro que detiene el bucle. Debe operar bajo esta jerarquía:
1. **Prioridad 1 (Reanudación):** Si current_node indica que ya estamos dentro de un proceso de crédito, saltar directamente a ese nodo (bypass total de bienvenida e intención).
2. **Prioridad 2 (Botón):** Si product_intent existe (clic en interfaz), saltar al init del producto.
3. **Prioridad 3 (Chat Libre):** Si no hay nada de lo anterior, enviar al intent_router para que el LLM decida. En este escenario, el nodo debe ejecutar una Llamada Tipo A de extracción estructurada, utilizando un esquema Pydantic (definido en un nuevo archivo common_schemas.py) y un prompt de sistema idéntico en metodología a los nodos de recolección de crédito. Esto garantiza que la intención del usuario se categorice de forma robusta y sin ambigüedades antes de derivar al flujo correspondiente.

## V. Conclusión
Para que esta estabilización sea exitosa y fluida, el trabajo debería ser:
1. **Limpiar el Entry Point:** Que welcome sea invisible si no es estrictamente necesario saludar.
2. **Humanizar la Entrada:** Que loan_init sea quien inicie la conversación del producto usando inteligencia artificial, no plantillas fijas.
3. **Blindar el Ruteo:** Que los edges respeten el estado guardado por encima de cualquier otra lógica.

**Resultado Esperado:** El usuario hace clic en "Crédito" y Flux responde inmediatamente: "¡Hola [Nombre]! Qué bueno que quieras ver lo de tu crédito. Para empezar, ¿me podrías decir cuál es tu renta líquida mensual?". Sin repeticiones, sin bucles y con memoria total del estado.

## VI. Estrategia de Pruebas: El Simulador de Orquestación Evolutivo
Para asegurar que la complejidad creciente de la Fase 2 (y futuras fases) no degrade la experiencia de usuario, se establece el Script de Simulación como el validador principal de cada incremento de código.

1. **Arquitectura del Script (Calidad Claude)** El script no se limitará a ejecutar una función; será un entorno de ejecución aislado que replicará el ciclo de vida de una conversación real:
- Persistencia de Turnos: Mantendrá un thread_id consistente para validar que el Checkpointer de LangGraph recupere el estado correctamente entre mensajes.
- Inspección de State Diff: Después de cada nodo, el script imprimirá qué campos del State cambiaron (ej: "Nodo X modificó loan_profile añadiendo renta: 2000000").
- Validación de Stop-and-Go: Probará específicamente que el grafo se detenga (interrupción) cuando necesite input del usuario y que, al recibirlo, no re-ejecute la lógica de inicialización.

2. **Uso como Test de Regresión Permanente:**A medida que se agreguen nuevos nodos (Motor de Riesgos, Validación OTP, Formalización), el script permitirá realizar:
    - **Pruebas de "Camino Feliz" (Happy Path):** Ejecución automática de un flujo completo desde el saludo hasta la firma del contrato en segundos.
    - **Pruebas de Cambio de Intención:** Simular que un usuario está en medio de un crédito y de pronto pregunta por una Cuenta Corriente, validando si el intent_router maneja la interrupción sin romper el proceso previo.
    - **Debugging de Prompts:** Permitirá iterar las Llamadas Tipo B (mensajes generados) rápidamente en consola para ajustar el tono y la claridad antes de desplegar al frontend.

3. **Beneficios para el Ciclo de Desarrollo**
    - **Independencia del Frontend:** Permite avanzar en toda la lógica financiera y de conversación aunque la interfaz aún no esté lista.
    - **Certificación de Nodos:** Cada nuevo nodo agregado al workflow.py deberá pasar la suite de pruebas del simulador antes de considerarse "completado".
    - **Documentación Viva:** El log de salida del script sirve como documentación técnica de cómo se espera que Flux se comporte en cada escenario.
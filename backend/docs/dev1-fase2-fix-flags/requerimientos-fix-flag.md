# Hallazgos sobre el uso de flags
Tras realizar pruebas manuales al finalizar el sub-proceso de fixear los nodos iniciales, se registró que el nodo de recolección de datos quedaba "atrapado" en un ciclo infinito. Al revisar, se determinó que se requiere un "Ruteo Consciente de Progreso", y que esto sea implementado a nivel general, como principio arquitectónico.

## Estructura de Datos y Persistencia
Definición estratégica del State y lógica de persistencia.

**Acción Requerida:** Diseñar e implementar el nuevo contenedor de estados de avance dentro del objeto session. Esta fase es el cimiento de la transición inteligente; sin este "contenedor" estandarizado, el ruteador y los nodos no podrán comunicarse de forma coherente.

**Instrucciones Específicas:**
1. Diseño de Namespaces por Producto:
    - Definir e Investigar: Claude debe revisar el archivo state.py actual y proponer una integración para session["progress"] que agrupe los flags históricos por producto (ej: loan, account, dap).
    - Restricción de Diseño: El diseño debe ser quirúrgico: alterar lo menos posible el esquema actual de Pydantic/State, pero garantizando que sea 100% escalable. Debe evitar el uso de listas planas que puedan causar colisiones de nombres entre productos.
2. Unificación de la Flag de Evento:
    - Refactorización: Eliminar flags locales como profile_just_completed y sustituirlas por una flag global única denominada session["just_completed_step"] (tipo Optional[str]).
    - Propósito: Esta flag indicará al LLM de Generación (Llamada B) qué hito se acaba de cumplir (ej: "PROFILE", "SIMULATION", "OTP") para adaptar el tono conversacional (celebración y transición) sin repetir saludos. Claude debe definir la ubicación exacta dentro del session para que sea accesible globalmente por todos los helpers de generación.
3. Implementación de Persistencia Selectiva:
    - Flags Históricas (session["progress"][producto]): Deben ser persistentes. Si el sistema se reinicia, el ruteador debe saber que el usuario ya completó el perfil.
    - Flag Volátil (just_completed_step): Debe tener un ciclo de vida de un solo turno. Claude debe investigar y proponer el mecanismo de limpieza (reset a None) para asegurar que se borre inmediatamente después de que el LLM genere la respuesta exitosa al usuario.

**Entregables:**
- Propuesta de esquema de state.py actualizado.
- Definición de las constantes o Enums para los valores de just_completed_step.
- Informe de impacto: confirmación de que los cambios no rompen la carga de sesiones antiguas.

**Por qué es vital:** Esta fase elimina la "amnesia" del sistema y permite que el ruteador deje de ser ciego. Al separar el "qué completó" (Histórico) del "qué acaba de completar" (Evento), permitimos que el bot sea técnicamente preciso y conversacionalmente fluido al mismo tiempo.

## Refactorización de Inteligencia, Helpers y Lógica de Consumo
Consumo, limpieza de flags y actualización de helpers.

**Acción requerida:** Reconfigurar la inteligencia de extracción y los asistentes de generación para que operen bajo el nuevo esquema de flags. El objetivo es pasar de una lógica de "flags locales" a una Lógica de Consumo Centralizada, donde cada componente sepa exactamente cuándo un dato ha sido recolectado y cuándo debe celebrarlo.

**Instrucciones Específicas:**
1. Migración de Inteligencia en Nodos:
    - Investigar y Revisar: Claude debe entrar en app/graph/nodes/credit.py e identificar todos los puntos donde se setean flags de finalización.
    - Actualización: En loan_collecting_profile_node y loan_collecting_sim_node, sustituir la flag antigua profile_just_completed por la asignación doble:
        - session["progress"][producto]["paso_completed"] = True (Histórica).
        - session["just_completed_step"] = "VALOR_DEL_PASO" (Evento global).
    - Revisión de Nodos Adicionales: Claude debe investigar si existen nodos como loan_init o stubs de otros productos que requieran esta misma actualización para mantener la consistencia.
2. Refactorización de Helpers de Generación:
    - Actualizar: Modificar los helpers de contexto (ej: _build_sim_generation_context, _build_profile_generation_context, _get_missing_profile_fields) para que dejen de buscar flags booleanas locales.
    - Lógica Nueva: Ahora estos helpers deben recibir el just_completed_step global y usarlo para decidir si el prompt debe incluir instrucciones de "Celebración y Transición".
3. Implementación de la "Regla de Consumo":
    - Definir el Punto de Limpieza: Claude debe implementar la lógica de limpieza obligatoria. La Flag just_completed_step debe ser reseteada a None inmediatamente después de que el LLM genere la respuesta.
    - Responsabilidad: Claude debe proponer si la limpieza ocurre al final del generator_node o dentro de la función de llamada a la API de Gemini (Llamada B), asegurando que la flag solo viva exactamente un turno. Esto evita el error crítico de que el bot felicite al usuario dos veces por el mismo hito en turnos subsiguientes (ej: ante una pregunta de RAG).
4. Lógica de "Nodo Destino":
    - Investigar: Claude debe asegurar que el nodo que recibe el control (el destino del salto) sea capaz de operar correctamente aunque la flag sea limpiada por el generador. Debe haber una sincronía perfecta para que el generador "lea" antes de que el estado se "limpie".

**Entregables:**
- Código refactorizado de credit.py y archivos de helpers asociados.
- Implementación del mecanismo de "auto-limpieza" de la flag de evento.
- Confirmación de que el flujo de "Missing Fields" (campos faltantes) sigue funcionando correctamente con el nuevo esquema.

**Por qué es vital:** Sin esta refactorización, el bot sufriría de "ecolalia": repetiría felicitaciones de pasos ya superados. Esta fase garantiza que la conversación se sienta natural, fluida y, sobre todo, que el sistema sea consciente de lo que acaba de suceder en el micro-segundo anterior.

## Navegación Inter-Turno e Inteligencia de Ruteo
El Cerebro de edges.py y resiliencia ante errores de salto.

**Acción Requerida:** Implementar la "Capa de Transición Inteligente" en el ruteador central. Esta lógica debe ser capaz de reanudar la sesión no solo basándose en dónde se quedó el usuario (current_node), sino en qué fue lo último que logró completar con éxito, permitiendo saltos entre nodos de forma transparente entre turnos.

**Instrucciones Específicas:**
1. Implementación del _SUCCESS_MAP:
    - Definir la Estructura: Claude debe crear una matriz (diccionario) denominada _SUCCESS_MAP dentro de app/graph/edges.py.
    - Diseño Jerárquico: El mapa debe respetar la separación por productos definida en la primera fase (ej: { "LOAN": { "loan_collecting_profile": "loan_collecting_simulation" } }).
    - Investigación: Claude debe asegurarse de que los nombres de los nodos en este mapa coincidan exactamente con los IDs definidos en workflow.py.
2. Jerarquía de Prioridades en route_after_welcome:
    - P0 - Intención del Usuario: Si el clasificador de intenciones detecta un cambio de producto o una acción global (ej: "ir a cuenta corriente"), el ruteador debe priorizar este destino. El éxito del paso anterior (si existe) se guarda en el historial, pero no fuerza la navegación.
    - P1 - Salto por Éxito (Nueva): Si no hay una intención disruptiva, el ruteador debe revisar session["progress"][producto]. Si el paso actual figura como completado en el historial, debe consultar el _SUCCESS_MAP para redirigir al usuario al siguiente nodo lógico.
    - P2 - Reanudación Estándar: Si no hay banderas de éxito nuevas, se mantiene el comportamiento actual de reanudar en el current_node.
3. Blindaje y Manejo de Errores:
    - Validación de Destinos: Antes de ejecutar un salto basado en el _SUCCESS_MAP, Claude debe implementar una verificación de existencia. Si el nodo destino no existe en el grafo o no está definido en el mapa para ese producto, el sistema no debe "romperse".
    - Fallback Seguro: En caso de error en el mapeo, el ruteador debe forzar un fallback a END (o a un nodo de error genérico) y generar un log de error detallado para depuración.
4. Respeto a la Implementación Existente:
    - Claude debe investigar cómo funcionan los mapas actuales (_RESUME_MAP, etc.) en edges.py para que la nueva lógica de éxito se integre como una capa superior, sin borrar o invalidar la lógica de reanudación básica.

**Entregables:**
- Archivo app/graph/edges.py actualizado con el _SUCCESS_MAP.
- Función route_after_welcome refactorizada con la nueva lógica de prioridades (P0, P1, P2).
- Mecanismo de logging para capturar fallos en las transiciones de éxito.

**Por qué es vital:** Esta fase es la solución definitiva al "bucle infinito" de recolección de datos. Al darle al ruteador la capacidad de ver el progreso histórico, garantizamos que el usuario siempre avance. Es el seguro de vida del sistema ante desconexiones o reinicios: Flux siempre sabrá cuál es el siguiente paso lógico.

## Transiciones Intra-Turno y Optimización de UX
Flujo continuo sin silencios y lógica de adaptación de prompt post-salto.

**Acción Requerida:** Implementar mecanismos de salto inmediato dentro del mismo ciclo de ejecución del grafo. El objetivo es que, cuando un usuario complete un requisito, el sistema no se detenga a esperar un nuevo mensaje, sino que "salte" al siguiente nodo de inmediato y entregue una respuesta compuesta (Celebración del paso anterior + Inicio del siguiente).

**Instrucciones Específicas:**
1. Configuración de Aristas Condicionales:
    - Rediseñar Salidas de Nodos: Claude debe modificar la configuración del grafo en workflow.py (o donde se definan las aristas de los nodos de recolección).
    - Lógica de Decisión Directa: Cada nodo de recolección (Perfil, Simulación, etc.) debe terminar con una evaluación:
        - ¿Paso Completado? -> La arista debe apuntar directamente al siguiente nodo en el flujo (ej: de loan_collecting_profile a loan_collecting_simulation) sin pasar por END.
        - ¿Paso Incompleto? -> La arista apunta a END para esperar la siguiente interacción del usuario.
    - Investigar: Claude debe asegurar que esta lógica no genere bucles infinitos en caso de que el nodo destino también se considere "completado" por error.
2. Lógica de Entrada "Post-Step" en Nodos Destino:
    - Detección de Salto: Los nodos que pueden recibir un control inmediato (como Simulación o Motor de Riesgo) deben ser capaces de detectar que no están siendo llamados por un mensaje nuevo del usuario, sino por una transición de éxito del nodo anterior.
    - Investigación y Propuesta: Claude debe proponer cómo el nodo destino identificará este estado (probablemente leyendo la flag just_completed_step que aún no ha sido limpiada).
    - Adaptación de Contexto: Si se detecta un salto, el nodo destino debe omitir cualquier saludo de "bienvenida al paso" y enfocarse exclusivamente en la siguiente pregunta, permitiendo que el Generador (Llamada B) concatene la felicitación del paso anterior con la nueva solicitud.
3. Prevención de "Silencios de Grafo":
    - Garantía de Respuesta: Claude debe verificar que, bajo ninguna circunstancia, un flujo de éxito termine en un nodo que no genere una salida de texto hacia el usuario. Si el nodo final de una cadena de saltos no tiene capacidad de respuesta, debe haber un fallback que active el Generador.
4. Manejo de la Flag de Transición:
    - Claude debe asegurar que, aunque ocurran varios saltos en el mismo turno, la flag just_completed_step se mantenga con el valor del hito alcanzado hasta que el Generador la consuma al final de la cadena de ejecución.

**Entregables:**
- Actualización de las aristas (edges) en la definición del grafo (workflow.py).
- Refactorización de la lógica de entrada de los nodos destino para manejar transiciones fluidas.
- Protocolo de pruebas de "un solo turno": Confirmar que enviar el último dato de perfil dispara automáticamente la primera pregunta de simulación en el mismo globo de texto.

**Por qué es vital:** Sin esta fase, el bot se siente "torpe" y obliga al usuario a trabajar de más. La transición intra-turno es lo que diferencia a un formulario secuencial de un asistente inteligente. Permite que la respuesta de Flux sea: "¡Perfecto, ya completamos tu perfil! Ahora, para simular tu crédito, ¿qué monto tienes en mente?", todo en una sola interacción.
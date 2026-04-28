# Problemas Fase 2 Paso 2

## 1. Estado del Proyecto e Implementación (Fase 2)

Al momento de originarse el problema, el proyecto se encontraba en la Fase 2 (Flujo de Crédito de Consumo).
- La infraestructura base (Namespaces, State, integración con Supabase) está validada y estable.
- El Motor de Cálculo (CreditEngine) está terminado al 100% con sus pruebas unitarias exitosas.
- Nos encontrábamos específicamente implementando y auditando los Nodos de Recolección de Datos (la lógica para extraer renta, antigüedad y estudios del chat).

## 2. ¿Qué estábamos haciendo?
Estábamos realizando pruebas de humo manuales utilizando un script de "Playground" (loan_playground.py). El objetivo era validar que el nodo de recolección de perfil (loan_collecting_profile_node) fuera capaz de identificar cuándo falta información y cuándo debe avanzar silenciosamente hacia el motor de riesgo.

## 3. Problemas Detectados
- Inyección de Datos Fantasmas: Al enviar mensajes irrelevantes o simples saludos (ej: "Hola!", "Conoces a Joe Black?"), el sistema de extracción devuelve valores numéricos y categorías de estudios que el usuario nunca mencionó.
- Valores Deterministas Inesperados: Se detectó la aparición constante de valores específicos como renta: 0, antiguedad_laboral: -1 y nivel_estudios: 'MEDIA'. El valor -1 es especialmente inusual ya que no existe en ninguna parte del código fuente ni en las reglas de negocio.
- Comportamiento Robótico y Determinista: Las respuestas del bot no parecen generadas por un LLM; se sienten como un programa de consola rígido con frases pre-fabricadas. Esto ocurre porque, al recibir siempre los mismos valores "fantasma" (0 y -1), el sistema de plantillas de respuesta genera siempre la misma cadena de texto, perdiendo toda la naturalidad y flexibilidad conversacional de un LLM.
- Falla de la Lógica de Re-pregunta: Debido a que estos valores "fantasmas" no son nulos, la lógica del nodo los interpreta como información válida y capturada. Esto provoca un "avance silencioso" del flujo, impidiendo que el bot le pida al usuario los datos reales que faltan.
- Desconexión con los Tests Automatizados: Se descubrió que la batería de pruebas automáticas existentes arrojaba un éxito del 100%, ocultando este problema. Esto se debe a que los tests utilizan "Mocks" (simulaciones) que devuelven resultados ideales, sin poner a prueba el comportamiento real del modelo de lenguaje ante lenguaje natural ambiguo.

## 4. Descripción Detallada del Test (loan_playground.py)
El archivo `backend/apps/flow/src/tests/loan_playground.py` es un script de prueba manual diseñado para simular conversaciones con el bot sin necesidad de ejecutar la API completa o una interfaz de usuario (llama a la API de Google Vertex AI, el LLM, pero no llama a la API del proyecto,FastAPI). Su propósito es facilitar la depuración rápida ("debugging") de los flujos conversacionales y los nodos de extracción de información.

**¿Cómo funciona?**
- **Simulación de Estado**: Utiliza una clase Mock para simular la base de datos Supabase. Esto permite crear y modificar estados de conversación (como credit_application, credit_history) directamente en memoria.
- **Ejecución por Pasos (Steps)**: El flujo está dividido en pasos discretos (ej: PASO_PREGUNTA_SALARIO, PASO_VALIDACION_EDAD). Para cada paso, el script:
    - Prepara el Estado Inicial: Configura las variables de estado necesarias (ej: income = None, years_at_company = None).
    - Envía el Mensaje: Simula una solicitud HTTP POST a la endpoint /api/flow/conversation, enviando el texto del usuario.
    - Procesa la Respuesta: Captura la respuesta del sistema, que incluye el nuevo texto generado por el LLM y el estado actualizado.
- **Validación Manual**: Muestra el estado y la respuesta en pantalla para que el desarrollador verifique manualmente si el comportamiento es correcto.

**Flujo de Recolección (Collecting Node):**
Específicamente para el problema detectado, el script prueba el nodo loan_collecting_profile_node. Configura un estado con valores por defecto (como antiguedad_laboral = -1) y envía mensajes de prueba.

El problema: Al ejecutarlo, se observa que el bot "avanza" correctamente a la siguiente fase (ejecutando PASO_PREGUNTA_EDAD) incluso cuando la información capturada es basura (como renta 0 o antiguedad -1). Esto confirma que el nodo no está detectando correctamente que la información es inválida y no está solicitando aclaraciones ("re-preguntando").

**Características del test construido:**
- **Aislamiento del Grafo**: El test no utiliza el motor de LangGraph compilado. En su lugar, importa e invoca directamente la función del nodo (loan_collecting_profile_node(state)).
- **Estado Manual**: El FluxState se inicializa como un diccionario manual dentro del script, sin persistencia en base de datos ni checkpointer.
- **Manejo de Mensajes**: El script captura el input() del usuario y lo inyecta como un objeto HumanMessage en la lista state["messages"].
    - **Detalle técnico**: En su última versión, el script limpia la lista de mensajes en cada iteración para pasarle al LLM únicamente el último mensaje, intentando aislar la extracción pura.
- **Invocación del Modelo**: El nodo utiliza un cliente Vertex AI (gemini-3-flash-preview) configurado con temperature=0.0 y with_structured_output(schema, method="json_mode").
- **Merge de Datos**: El script recibe el diccionario de salida del nodo y realiza un state.update(result) manual.

**Pista:** Es vital determinar si el hecho de invocar el nodo fuera del grafo (CompiledGraph) o el hecho de truncar el historial de mensajes está causando que el modelo de Vertex AI pierda contexto y "colapse" hacia esos valores deterministas por defecto.
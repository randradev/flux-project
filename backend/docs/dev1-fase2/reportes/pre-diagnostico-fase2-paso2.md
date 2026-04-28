# Informe de Situación: Desafíos Técnicos y de Experiencia (Módulo Perfil de Crédito)
*Estado del Branch: Revertido a loan_profile (Estabilización)*
*Objetivo: Resolver la "alucinación estructural" y recuperar la identidad conversacional de Flux.*

## Problema 1: El Desafío de la Extracción: "Fantasmas en los Datos"
El problema principal no es la lógica del código, sino la presión de formato que sufre el LLM (with_structured_output). Al forzar a Gemini a devolver un JSON rígido, el modelo "entra en pánico" ante mensajes irrelevantes (como un simple "hola") y rellena los campos con valores basura.
- Valores detectados: renta: 0, antiguedad_laboral: -1, nivel_estudios: "MEDIA".
- Diagnóstico: El modelo no se siente con la libertad de devolver null. Al inventar un -1 (que es un valor "truthy" en Python), engaña a nuestra lógica de missing fields, provocando un Avance Silencioso. El sistema cree que tiene los datos y deja de preguntar, dejando el flujo en un callejón sin salida con datos falsos.

## Problema 2: El Desafío de la Identidad: "El Síndrome del Robot"
Se ha identificado una degradación crítica en la "humanidad" de Flux. Actualmente, el nodo se comporta como un script de terminal y no como un asistente inteligente.
- Problema: Las respuestas son predefinidas y estáticas (generadas por funciones helper como _build_flux_reprompt).
- Impacto: El LLM no reconoce el nombre del usuario, no reacciona a saludos y repite frases calcadas mensaje tras mensaje.
- Necesidad: El LLM debe recuperar el control de la narrativa. La respuesta al usuario debe ser generada por el modelo, integrando los datos que ya conoce y los que faltan en una frase natural, eliminando las respuestas "hardcodeadas".

## Análisis del Informe del Agente (Evaluación de Hipótesis)
He revisado el diagnóstico del agente de hoy. Aquí está el filtro de relevancia para la discusión:

1. Hipótesis del Agente: Incompatibilidad LangChain/Pydantic/Vertex:
    - Nivel de Probabilidad: Baja
    - Comentario: Es poco probable que sea un bug de librería. El -1 suele ser una alucinación del modelo intentando cumplir con un esquema que no tiene instrucciones claras para "datos no encontrados".

2. Hipótesis del Agente: Falla de Mocks en Tests
    - Nivel de Probabilidad: Alta
    - Comentario: Sentido total. Los tests automatizados pasaban porque asumíamos que el LLM siempre devolvería lo que le pedíamos. Se deberían implementar tests automatizados con datos "ruidosos".

3. Hipótesis del Agente: Lógica de Avance Silencioso
    - Nivel de Probabilidad: Alta
    - Comentario: Sentido total. El código actual no discrimina que un número negativo es basura. Es un error de validación en el nodo que debemos cerrar.

4. Hipótesis del Agente: Endurecimiento del Nodo (Validar > 0)
    - Nivel de Probabilidad: Baja / Parche
    - Comentario: Es una solución reactiva. El problema real está en el Prompt de Extracción y en no permitir que el modelo genere su propia respuesta.

## Estrategia de Solución: "Retorno a la Humanidad"
1. **Limpieza de Prompts:** Rediseñar el EXTRACTION_PROMPT para dar permiso explícito de devolver null y prohibir la invención de valores por defecto.
2. **Conversational Extraction:** Modificar el esquema de salida para que el LLM incluya un campo respuesta_flux. Esto permitirá que sea el modelo quien diga: "¡Hola Ricardo! Qué bueno saludarte. Para empezar..." en lugar de una frase pre-hecha.
3. **Validación Estricta:** Implementar el filtro de valores positivos en el merge de datos del nodo para evitar que cualquier "basura" persistente ensucie el estado del crédito.
4. **Referencia al "Proyecto Anterior":** Usar como benchmark el comportamiento del proyecto anterior (donde el modelo fluía mejor) para ajustar la temperatura y el sistema de turnos.
Nota final: No avanzaremos a loan_simulation hasta que el playground demuestre que Flux puede recibir un "hola", saludar de vuelta amablemente y pedir los datos del perfil sin inventar rentas de cero pesos.
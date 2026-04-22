# ESTADOS UTILITARIOS TRANSVERSALES

## 1. NODO DE DESPEDIDA Y FEEDBACK (GLOBAL_END)
Cuando el usuario termina un proceso (ya sea porque se le entregó el crédito o porque fue rechazado), no deberías simplemente "cortar" la conexión.
- Función: Cerrar la sesión de forma elegante.

**INPUTS:**
- final_status: SUCCESS, REJECTED o CLOSED_BY_USER
- product_name: (ej: "Crédito de Consumo", "Cuenta Corriente", "Depósito a Plazo")
- display_data: (Un diccionario/objeto flexible definido por el estado padre).

**OUTPUTS:**
- final_message (str):
    - Descripción: Es la respuesta final generada por el LLM.
    - Lógica: La IA utiliza el final_status y los datos en display_data para construir una despedida personalizada.
    - Ejemplo (SUCCESS): "¡Felicidades, Juan! Tu Crédito de Consumo ha sido cursado. Puedes descargar tu contrato aquí [URL]. ¡Gracias por confiar en Flux!"
    - Ejemplo (CLOSED): "Entiendo, Juan. No te preocupes, la oferta de $5.000.000 no se volverá a mostrar si no es lo que buscas. ¡Aquí estaré si cambias de opinión!"
- ui_action (str):
    - Valor: DISABLE_INPUT
    - Descripción: Señal para el frontend que bloquea la barra de escritura del chat, indicando que el proceso ha terminado.
- session_persistence (obj):
    - is_active: false
    - completion_date: timestamp
    - Descripción: Actualización para la tabla de sesiones en la DB para marcar la conversación como terminada.

## 2. NODO DE RECUPERACIÓN DE CONTEXTO (RESUME_HANDLER)
Como el usuario puede volver desde el Dashboard después de un error o de haberse ido a dormir:
- Función: Cuando el usuario reabre un chat IN_PROGRESS, este nodo lee la base de datos y genera el saludo de bienvenida personalizado: "Hola de nuevo, [Nombre]. Nos habíamos quedado en la validación de tu renta, ¿continuamos?".
- Sin este nodo: El bot saludaría siempre como si fuera la primera vez, lo cual rompe la magia.
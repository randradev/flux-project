# Protocolo Universal de Arquitectura: Flag `just_completed_step` y Contexto Bifurcado

**Para: Agente QA de Antigravity**
**Objetivo:** Estandarizar la implementación de la flag de salto intra-turno (`just_completed_step`) en todos los nodos post-motor, garantizando que no haya bucles infinitos y asegurando una naturalidad conversacional absoluta (cero saludos repetitivos).

## REGLA DE ORO CONVERSACIONAL (LLAMADA B)
El bot **NUNCA DEBE SALUDAR** en los nodos intermedios. El saludo inicial ya ocurrió en el perfilamiento. La dinámica universal para un avance automático es: **Celebrar el hito anterior + Presentar la nueva información o acción requerida.**

---

## 1. Patrón Universal de Limpieza y Captura (Aplica a TODOS los nodos)

Al inicio de la función de CUALQUIER nodo, antes de procesar lógica de negocio o LLMs, se debe implementar la captura y limpieza estricta de la flag:

```python
# 1. Capturar la sesión y la flag
session = state.get("session", {})
just_completed = session.get("just_completed_step")

# 2. Determinar si es salto intra-turno (Booleano universal)
is_intra_turn_jump = (just_completed == CompletedStep.[EVENTO_DEL_NODO_ANTERIOR])

# 3. LIMPIEZA INMEDIATA: Crear la base del output de sesión sin la flag
clean_session = {
    **session,
    "current_node": "[ID_DEL_NODO_ACTUAL]",
    "just_completed_step": None  # SE CONSUME EL TICKET AQUÍ
}
```

## 2. Patrón Universal de Construcción de Contexto (Solo Nodos de Interacción)

Para los nodos donde el bot debe hablar y esperar al usuario (Llamada B), la construcción del contexto que se enviará al prompt del LLM DEBE bifurcarse usando la variable is_intra_turn_jump.

Se debe usar un helper o un bloque de string formateado que siga estrictamente esta abstracción:

```python
# Construcción del contexto basado en el estado del salto
if is_intra_turn_jump:
    instruccion_dinamica = (
        "ESTADO: El usuario acaba de llegar aquí automáticamente tras completar el paso anterior. "
        "INSTRUCCIÓN: NO SALUDES. Celebra brevemente el paso exitoso anterior y preséntale "
        "los nuevos datos o la acción que debe realizar ahora."
    )
else:
    instruccion_dinamica = (
        "ESTADO: El usuario ya estaba en este paso y escribió un mensaje en el chat. "
        "INSTRUCCIÓN: Responde a su duda o comentario con empatía, y recuérdale sutilmente "
        "cuál es la acción principal que debe realizar para avanzar."
    )

context = f"""
CONTEXTO DEL SISTEMA:
{instruccion_dinamica}

DATOS DEL PASO ACTUAL:
[Inyectar variables relevantes del nodo: montos, estados de OTP, links de contrato, etc.]

ÚLTIMO MENSAJE DEL USUARIO: "{last_user_msg}"
"""
```

*Nota para el Agente: Al revisar el código del desarrollador, debes exigir que el LLM reciba una instrucción clara y distinta dependiendo de si es la primera vez que pisa el nodo (salto) o si está atrapado en él conversando.*

## 3. Patrón Universal de Gatillo o Retención (En el Return)

El diccionario de salida (return) de cada nodo debe definir cómo queda la flag para el siguiente ciclo del grafo.

### Caso A: Nodo de Interacción (Receptor / Estación de espera)

El bot habló y necesita que el usuario responda o apriete un botón de la UI.
- Obligación: Retornar clean_session tal cual. La flag DEBE ir en None.

```python
return {
    "messages": [AIMessage(content=clean_content)],
    "session": clean_session, # just_completed_step va en None
    # ... otros updates (progress, data)
}
```

### Caso B: Nodo de Proceso (Gatillo / Backend)

El nodo completó una tarea en el backend (ej. calcular riesgo, validar código, generar PDF) y necesita saltar al siguiente paso sin esperar al usuario.
- Obligación: Inyectar el nuevo CompletedStep en la sesión limpia. NO se devuelven mensajes (AIMessage).

```python
return {
    "session": {
        **clean_session,
        "just_completed_step": CompletedStep.[EVENTO_RECIEN_COMPLETADO],
        "progress": { ... } # Actualización histórica obligatoria
    },
    # ... updates de backend (evaluation_results, etc.)
}
```

## 4. Checklist de Auditoría (Instrucciones para Antigravity)

Agente, por cada nodo implementado, no darás el visto bueno hasta comprobar estos 4 puntos en el código:

1. [ ] Lectura Temprana: ¿Se lee just_completed_step al principio de la función?
2. [ ] Booleano de Salto: ¿Existe una variable is_intra_turn_jump evaluada correctamente?
3. [ ] Limpieza Anticipada: ¿Se asegura que la flag pase a None en el objeto base de session antes del return?
4. [ ] Contexto Bifurcado (Si aplica): ¿La Llamada B distingue claramente entre el saludo/celebración inicial (cuando is_intra_turn_jump es True) y la respuesta a una duda (cuando es False)?
5. [ ] Gatillo Correcto: Si el nodo es de proceso, ¿sobrescribe el None con el Enum correspondiente en el return?
# Informe de Autopsia Técnica: El Bucle de Amnesia (Fase 2)

Este documento detalla el fallo sistemático en la reanudación de sesiones del Grafo FLUX durante las pruebas de integración E2E, analizando la causa raíz desde el estado inicial (Post-Paso 4) y los intentos fallidos de estabilización.

## 1. Situación Inicial (Estado Base para el Reset)
Al finalizar la implementación del Paso 4 (Nodo de Pre-aprobación), el sistema presentaba tres vulnerabilidades críticas en su arquitectura de flujo:

1. **Ruteo Stateless (edges.py):** La función `route_after_welcome` estaba diseñada solo para el inicio: `if intent == "LOAN": return "loan_init"`. Esto forzaba un reinicio cada vez que el grafo pasaba por el punto de entrada.
2. **Nodos con Reset Agresivo (credit.py):** El nodo `loan_init_node` limpiaba los namespaces `loan_profile` y `loan_sim` incondicionalmente.
3. **Bucle Infinito en Recolección:** La arista `loan_collecting_profile` -> `loan_collecting_profile` generaba una recursión infinita en un solo `invoke()` cuando faltaban datos, ya que no existía un mecanismo de interrupción natural.

## 2. Cronología de Intentos y Fallos

### Intento 1: Modo Streaming (Playground v3.1)
*   **Hipótesis:** Usar `app.stream` permitiría detectar mensajes y detener la ejecución manualmente antes de que el grafo entrara en bucle.
*   **Resultado:** **FALLIDO.** LangGraph ejecuta la lógica interna de los nodos y sus aristas condicionales de forma atómica durante el tick del stream. El motor agotaba el límite de recursión (25) antes de emitir el primer chunk de salida.

### Intento 2: Forzado de Punto de Entrada (Playground v3.2)
*   **Hipótesis:** Si el problema es el nodo `welcome`, forzamos el inicio en `loan_init`.
*   **Resultado:** **FALLIDO.** Al ser el punto de entrada, cada respuesta del usuario provocaba un inicio desde `loan_init`, activando el "Reset Agresivo" mencionado en el punto 1. El perfil del usuario nunca avanzaba de 0/3.

### Intento 3: Interrupciones e Inteligencia de Ruteo (Playground v3.3)
*   **Hipótesis:** Usar `interrupt_after` para forzar paradas en nodos clave y modificar `edges.py` para detectar `current_node`.
*   **Resultado:** **FALLIDO (Bucle de Saludo).** Aunque el ruteador intentaba avanzar, el nodo `welcome_node` seguía ejecutándose en cada reanudación. Debido a que la lógica de reanudación en `common.py` dependía de un campo `previous_node` (que no se estaba actualizando), Flux siempre saludaba como si fuera la primera vez.

## 3. Causa Raíz Identificada
El problema no es un error de código único, sino una **falta de sincronización entre el estado de la sesión y el motor de ruteo**:
1.  **Welcome como Entry Point:** Al ser el inicio de cada "tick" de `invoke`, el nodo de bienvenida debe ser "transparente" si la sesión ya está avanzada.
2.  **Falta de Resiliencia en Edges:** Las aristas deben priorizar el `current_node` guardado en la sesión sobre la intención global del producto.
3.  **Contrato de Reanudación:** No existía un flag claro (`is_resumed`) que los nodos pudieran consultar para evitar repetir saludos o limpiezas de datos.

## 4. Recomendaciones para la Re-implementación
Para una solución limpia después del reset a Git:
*   **Ajustar `common.py` (Welcome):** La detección de reanudación debe basarse en `len(messages) > 1` o en la existencia de un `current_node` distinto a `WELCOME_NODE`.
*   **Ajustar `edges.py` (Router):** `route_after_welcome` DEBE tener un bloque de prioridad superior que retorne `state["session"]["current_node"].lower()` si este existe.
*   **Ajustar `credit.py` (Init):** `loan_init` solo debe limpiar datos si la sesión es estrictamente nueva o si el usuario solicita reiniciar.
*   **Configuración de Compilación:** El grafo final en `workflow.py` (o al menos en el simulador) debe considerar interrupciones en cada nodo que requiera input humano para preservar el hilo de ejecución correctamente.

---
*Este informe cierra la sesión de depuración del Playground v3.0.*

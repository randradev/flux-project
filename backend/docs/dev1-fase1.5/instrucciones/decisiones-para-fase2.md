# 🧠 Memoria de Arquitectura y Decisiones de Diseño — Proyecto FLUX
*Estado: Finalizando Fase 1.5 (Migración a Namespaces)*
*Propósito: Guía de referencia para la implementación de Flujos Completos en Fase 2.*

## 1. El Pilar Maestro: Arquitectura de Namespaces (v2.0)
Se ha abandonado el uso de diccionarios genéricos (collected_data, control_flags) en favor de una estructura de Namespaces Especializados basados en TypedDict.
- **Regla de Aislamiento:** Cada producto (Loan, Account, DAP) posee sus propios sub-cajones dentro de collecting_data y evaluation_results.
- **Invariante:* *Un producto NUNCA escribe en el namespace de otro.
- **Atomic Reset:** Cada flujo DEBE comenzar con un nodo INIT que realice una limpieza atómica de sus namespaces específicos (asignando {}) para evitar contaminación de sesiones anteriores.

## 2. El Patrón "Orquestador Ligero" (Wrapper)
Los nodos del Grafo no son el "cerebro" del cálculo, sino los porteros del flujo.
- **Delegación de Carga:** Todos los cálculos pesados, algoritmos de scoring y lógica financiera viven en /modules/ (ej: credit_eng.py, dap_eng.py).
- **Nodos como Wrappers:** El nodo se encarga de:
    - 1. Extraer datos del State.
    - 2. Invocar al módulo externo.
    - 3. Persistir el resultado en el State.
    - 4. Notificar a la infraestructura de semáforos.
- **Escalabilidad Futura:** Este mismo patrón se aplicará a la Generación de Reportes PDF y la Lógica de OTP/Seguridad, que funcionarán como servicios importados.

## 3. Sincronía y Visibilidad: La Regla de Oro #3
La interfaz de usuario (Frontend) y los orquestadores externos dependen de la base de datos, no de la memoria interna del grafo.
- **Semáforos Obligatorios:** Todo nodo relevante debe invocar update_application_semaphores().
- **Fuente de Verdad:** Los estados de sincronía (node_status, engine_status) viven en Supabase, no en el state.py. Esto evita la "Doble Fuente de Verdad".
- **Blindaje de Infraestructura:** La función de actualización permite valores None para actualizaciones parciales, pero procesa strings vacíos mediante validación explícita (is not None).

## 4. Simetría Arquitectónica Multi-Producto
El sistema está diseñado para que el comportamiento sea predecible sin importar el producto financiero.
- **Ciclo de Vida Estandarizado:** WELCOME → PRODUCT_INIT (Reset) → COLLECTION → ENGINE (Processing) → OFFER/END.
- **Contratos de Salida:** Todos los motores deben poblar el namespace evaluation_results con estructuras coherentes para que el nodo de oferta (FinalDisplay) sea agnóstico al producto.

## 5. Resumen de Namespaces Clave
- **preparation_data:** Datos universales ya procesados (ej: edad calculada).
- **collecting_data:** Entidades crudas extraídas del chat por el LLM.
- **evaluation_results:** Resultados post-procesamiento de los motores financieros.
- **flow_result:** (Preparado) Para el cierre post-mortem de la sesión.
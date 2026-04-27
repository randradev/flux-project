## 🟢 CONSIDERACIONES ADICIONALES POR CAMBIOS DURANTE EL DESARROLLO DE LA FASE 1.5:

Debido a las decisiones de diseño tomadas durante la implementación (que expandieron el alcance original del plan), la suite de pruebas para el cierre de esta fase y el inicio de la Fase 2 debe validar los siguientes puntos críticos que no estaban previstos inicialmente:

### 1. Validación de la Regla de Oro de Sincronía de Semáforos:

- **El Test:** No basta con verificar el return del nodo. Se debe usar un mock sobre update_application_semaphores para asegurar que cada nodo (INIT y ENGINE) llame a la base de datos con los parámetros correctos.

- **Qué validar:** Que el current_node_id enviado coincida exactamente con el nombre del nodo en el flujo y que el engine_status cambie a COMPLETED al finalizar los motores.

### 2. Pruebas de "Orquestación Ligera" (Módulos vs. Nodos):

- El Test: Verificar que los nodos de tipo ENGINE funcionen correctamente como wrappers.

- Qué validar: En esta fase, los tests deben confirmar que el nodo extrae los datos de los nuevos namespaces (collecting_data -> loan_profile, etc.) y los entrega correctamente al objeto de resultado, dejando el espacio preparado para la futura integración con /modules/

### 3. Integridad del Motor de Cuenta Corriente (ACCOUNT_ENGINE):

- El Test: Dado que este motor no existía en el plan original, se deben crear tests de integración específicos en tests/test_account_nodes_v2.py.

- Qué validar: Que el motor de cuenta corriente lea de su sub-cajón específico (account_profile) y no colisione con datos de loan_profile aunque compartan nombres de campos similares (como renta o edad).

### 4. Robustez de la Infraestructura Supabase (Bypass de RLS):

- El Test: Validar la función de infraestructura update_application_semaphores.

- Qué validar: Probar específicamente el "Edge Case" del string vacío. El test debe confirmar que si se pasa un valor "" (vacío), la función sí actualiza el campo en la DB (gracias a la corrección is not None), mientras que si se pasa None, el campo se ignora.

### 5. Serialización de los nuevos Namespaces de Cierre:

- El Test: El test de serialización JSON (test_state_serializable_to_json) debe incluir ahora los objetos FlowResult y FinalDisplay.

- Qué validar: Asegurar que las nuevas estructuras de cierre (que incluyen campos opcionales y tipos complejos) no rompan el checkpointer de Supabase al intentar persistir el estado al final de la conversación.

### 6. Simetría en el Reset Atómico:

- El Test: Simular un cambio de intención del usuario (ej: de Crédito a DAP) en una misma sesión.

- Qué validar: Que el nodo DAP_INIT limpie efectivamente los namespaces de loan_profile y loan_sim (o que el sistema garantice aislamiento total) para que el motor de inversión no reciba "basura" de la interacción anterior de crédito.
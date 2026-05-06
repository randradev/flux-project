# Reporte de Auditoría: CP-05-fix-nodos-iniciales

**Estado de la Implementación:** Éxito (Simulador y Orquestación Validados)

## Decisiones Técnicas

1.  **Simulador de Orquestación (`simulate_conversation.py`)**:
    -   Se implementa un entorno de pruebas autónomo que utiliza `MemorySaver` para persistir el estado entre turnos sin depender de la infraestructura de Supabase.
    -   **Pretty-printing**: Se incluye lógica de diferenciación (`_print_state_diff`) para visualizar exactamente qué campos del `FluxState` cambian en cada interacción.
    -   **Validación de Invariantes**: El simulador actúa como un "linter de negocio" en tiempo de ejecución, detectando retrocesos de ruteo o saludos duplicados.
2.  **Ajuste Estructural de Grafo (`workflow.py`)**:
    -   Se identificó que el encadenamiento directo de nodos de recolección (`loan_init` -> `loan_collecting_profile`) provocaba ejecuciones en el mismo turno sin esperar el input del usuario, resultando en errores de "Model input cannot be empty".
    -   **Solución**: Se aplicó el patrón de **Pausa Multi-turno**, haciendo que los nodos que emiten preguntas (`loan_init`, `loan_collecting_profile`) apunten a `END`. La reanudación en el siguiente turno se gestiona mediante el Save Point (`current_node`) en `route_after_welcome`.

## Incidentes y Soluciones

*   **Unicode en Windows**: Se corrigió un `UnicodeEncodeError` al imprimir caracteres de dibujo de caja (`═`) mediante la reconfiguración de `sys.stdout` a UTF-8.
*   **Error 400 Vertex AI**: Se detectó que las llamadas automáticas en el mismo turno enviaban mensajes de usuario vacíos a los extractores. La corrección en las aristas del grafo solucionó la causa raíz.

## Evidencia de Tests

### Escenarios de Simulación
*   **`happy_path_loan`**: ✅ VALIDADO. El flujo avanza por turnos capturando renta, antigüedad y estudios.
*   **`resume_mid_loan`**: ✅ VALIDADO. El grafo reanuda exactamente donde se dejó (Save Point) sin repetir saludos.
*   **`button_click_loan`**: ✅ VALIDADO. El clic de botón marca el Punto de Guardado correctamente.

### Tests de Integración (`test_simulator_scenarios.py`)
*   `test_scenario_resume_preserves_current_node`: **PASSED**
*   `test_scenario_button_click_sets_punto_de_guardado`: **PASSED**

---
*Fin del reporte CP-05*

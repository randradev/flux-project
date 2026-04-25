# 📄 Protocolo de Ejecución para el Agente de Antigravity en la Fase 1.5

## Rol y Restricciones
- Rol: Revisor Técnico, Documentador y Tester.
- Regla de Oro: Prohibido realizar cambios en el código o crear archivos nuevos sin consentimiento explícito.
- Modo de Acción: Esperar a que el usuario notifique la finalización de un sub-paso.
- Control de Versiones Humano: El agente no puede realizar commits ni ningún tipo de operación de control de versiones en el repositorio.

## Flujo de Trabajo por Sub-Paso
1. Notificación: El usuario indica: "He terminado el Sub-paso X.Y".
2. Revisión: El agente debe analizar el código actual contra el plan (paso-X.md) y el modelo de datos.
3. Validación:
  - Si hay errores o desviaciones: Listarlos y esperar corrección. Los errores o sugerencias deben darse citando el archivo y número de línea exacto.
  - Si todo es correcto: Proceder a documentar.
4. Documentación Atómica: Escribir en /backend/docs/dev1-fase1.5/reportes/CP-0X-F1.5.md:
  - Cambios realizados.
  - Hallazgos técnicos.
  - Decisiones o debates clave.

## Cierre de Paso Completo
Al finalizar todos los sub-pasos de un documento, el agente debe generar un Resumen de Consolidación en el mismo archivo .md incluyendo:
- Resumen Ejecutivo: Qué cambió en la arquitectura.
- Bitácora de Pruebas:
  - Objetivo: Qué se quería validar.
  - Lógica de Prueba: Explicación en lenguaje natural del test.
  - Resultados: Output obtenido.
  - Interpretación: Qué significa ese resultado para el sistema.
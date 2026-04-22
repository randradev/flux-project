# Crédito: Flujo de Estados
## I. Flujo de Preparación y Datos
1. LOAN_INIT: El sistema recupera datos de la DB (nombre, rut, fecha_nacimiento) y calcula la edad.
2. LOAN_COLLECTING_PROFILE: El bot solicita los datos declarativos que no están en la DB (renta, antigüedad, nivel_estudios).
3. LOAN_COLLECTING_SIMULATION: El bot solicita las variables del crédito (monto, plazo).

## II. Flujo de Evaluación y Oferta
4. LOAN_RISK_ENGINE: Nodo de servicio. El backend procesa el Motor de Riesgo (Scoring, Tasa y Amortización Francesa).
    - Si califica y tiene capacidad de pago: Salta a LOAN_PRE_APPROVED
    - Si no cumple políticas o excede la capacidad de pago: Salta a LOAN_REJECTED_POLICY
5. LOAN_PRE_APPROVED: Tarjeta de Transparencia. Se muestra la oferta final calculada. El flujo se detiene hasta que el usuario presione "Aceptar".

## IV. Flujo de Formalización y Cierre
6. LOAN_OTP_VALIDATION: Generación y verificación del código de seguridad enviado al usuario. Maneja hasta 3 intentos.
7. LOAN_FORMALIZATION: Nodo de servicio. Generación dinámica del contrato PDF (ReportLab) y aplicación de sello de integridad SHA-256
8. LOAN_COMPLETED: Estado final. Entrega del contrato, visualización del Hash y mensaje de cierre

## V. Estados de Manejo de Errores y Excepciones
Desvíos que controlan el comportamiento cuando algo sale mal:

9. LOAN_REJECTED_POLICY: (Cierre) El usuario no cumple mínimos (edad, renta o antigüedad). Salta a estado transversal GLOBAL_END
10. LOAN_SECURITY_BLOCK: (Bloqueo) El usuario falló 3 veces el OTP. La solicitud queda congelada por seguridad.  Salta a END (termina el grafo)
11. LOAN_CLOSED_BY_USER: (Cierre voluntario) El usuario decide no aceptar la oferta en la Tarjeta de Transparencia. El bot confirma la cancelación, limpia las variables temporales y finaliza la sesión. Salta a estado transversal GLOBAL_END
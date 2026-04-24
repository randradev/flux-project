### 1. CRÉDITO DE CONSUMO
#### 1.1. Descripión:
Producto financiero orientado a personas naturales que permite obtener financiamiento en dinero, el cual debe ser devuelto en cuotas mensuales con interés.
#### 1.2. Datos Requeridos:
- RUT
- Nombre
- Edad
- Renta
- Nivel de Estudios (grado académico)
- Antigüedad Laboral
- Monto solicitado
- Plazo (cuotas)
#### 1.3. Condiciones Principales:
- Edad Mínima: 18 años
- Renta Mínima: $500.000
- Antigüedad Laboral Mínima: 6 meses
- Monto: CLP $100.000 a CLP $30.000.000 (según segmentación de tramo del cliente)
- Plazo: 6 a 48 cuotas
- Evaluación crediticia obligatoria a través del motor de cálculo de riesgo.
- Tasa de interés variable según nivel de riesgo
- Formalización mediante aceptación digital y firma
#### 1.4 Motor de Cálculo de Riesgo:
- Eligibilidad Mínima: Verificar que la Edad, Renta y Antigüedad Laboral mínima se cumplan. Si no se cumple, el motor arroja un error controlado de requisitos incumplidos.
- Cálculo de Scoring (0-100 pts): Aplicación de puntajes ponderados según nivel de estudios, antigüedad laboral, tramo de edad y renta líquida. El nivel de riesgo se determinará mediante un puntaje de 0 a 100 puntos:
    - Ponderaciones:
        - Estudios: Postgrado (+20 pts), Universitario (+15 pts), Técnico (+10 pts), Media (+5 pts).
        - Antigüedad: >2 años (+20 pts), 1 – 2 años (+10 pts), <1 año (+5 pts).
        - Edad: 25 – 55 años (+20 pts), 18 – 24 años (+5 pts), 56 – 65 años (+5 pts).
        - Renta: > $3MM (+40 pts), $1MM - $3MM (+25pts), <$1MM (+10 pts).
    - Resultados:
        - Riesgo bajo: > 80 puntos.
        - Riesgo medio: 50 – 80 puntos.
        - Riesgo alto: < 50 puntos.
    - Fórmula Matemática: S = P estudios + P antigüedad + P edad + P renta
- Cálculo de de Cuota Mensual: Aplicación de la fórmula de Amortización Francesa para determinar el monto fijo a pagar cada mes: $$M = P \frac{i(1+i)^n}{(1+i)^n - 1}$$. Se debe redondear el resultado al entero superior más cercano.
- Asignación de tasa de interés:
    - Riesgo bajo: tasa baja, de 1,2% mensual.
    - Riesgo medio: tasa media, de 2,0% mensual.
    - Riesgo alto: tasa alta, de 3,5% mensual.
- Validación de Capacidad de Pago: Verificación final de que la cuota mensual del crédito propuesto no exceda el 30% de la renta líquida del solicitante. Si se excede, el motor arroja un error de capacidad de pago y se detiene.
- Cálculo del Costo Total del Crédito (CTC): Cálculo del monto total que el cliente terminará pagando al final del periodo ($Cuota \times Plazo$). Se debe redondear el resultado al entero superior más cercano.
- Cálculo Total Intereses: Diferencia entre el CTC y el monto original solicitado.
- Cálculo Carga Anual Equivalente (CAE): Conversión de la tasa periódica a una tasa anual compuesta para transparencia del cliente, con la fórmula de interés compuesto: $$CAE = (1 + i)^{12} - 1$$.
#### 1.5 Pasos posteriores
- Tras ser aprobado por el motor de cálculo de riesgo, se genera la "Tarjeta de Transparencia" con: Monto solicitado, Plazo, Cuota Mensual, Tasa de Interés Mensual, CAE, CTC, Total Intereses y Categoría de Riesgo. Debe tener un botón "Aceptar", y debe ser la única vía a partir de la cual se puede aceptar el crédito (no sirve decir sí por el chat). También debe tener un botón de "Rechazar", que lleva a un estado de cierre voluntario.
- Tras la aceptación, se envía un código para autenticación OTP, el chat avisa y muestra en la intefaz un campo para rellenar con el código. Si la autenticación falla, el chat debe avisar que falló y ofrecer una nueva instancia de autenticación. Si falla 3 veces, se rechaza el crédito y se realiza un bloqueo de seguridad.
- Si la autenticación es exitosa, se genera un pdf con un hashing SHA-256 como contrato, y el bot felicita y se despide.
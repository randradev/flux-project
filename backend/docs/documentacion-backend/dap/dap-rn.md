# 3. DEPÓSITO A PLAZO
## 3.1. Descripción:
Producto de inversión en el cual el cliente deposita una suma de dinero por un período determinado, obteniendo una rentabilidad fija.
## 3.2. Datos Requeridos:
- RUT
- Nombre
- Edad
- Monto a invertir
- Plazo de inversión (taxonómico de acuerdo a plazos disponibles)
- Tipo de moneda (taxonómico de acuerdo a monedas disponibles)
## 3.3 Condiciones Principales:
- Edad Mínima: 18 años.
- Monto Mínimo: CLP $50.000
- Monto Máximo: CLP $50.000.000
- Plazos Disponibles (en días corridos):
  - 7 días
  - 14 días
  - 30 días
  - 180 días
  - 360 días
- Monedas disponibles:
  - CLP
  - UF
  - USD
- No permite retiro anticipado (No tiene implicancia para la lógica, solo para efectos de informar)
- Formalización mediante aceptación digital y firma.
## 3.4 Motor de Cálculo de Inversión
- Eligibilidad Mínima:
    - Conversión a CLP para cálculo de rango permitido.
    - Verificar que el monto e encuentre dentro del rango permitido ($50.000 a $50.000.000 CLP).
    - Verificar que la Edad Mínima (18 años) se cumpla.
- Consumo de API: El motor consulta el valor del día de la UF, USD e IPC (corrección monetaria).
- Cálculo de Tasa Mensual: Se Compone de 3 factores sumatorios:
    - Tasa Base: Interés fijo de 0.2% mensual para todas las inversiones.
    - Premio por Plazo: Bonificación de 0.05% por cada 30 días de permanencia. Es una lógica de escalones (step function) y no lineal: Lógica del Motor: El premio solo se suma si $Plazo \geq 30$: De 7 a 29 días: $+0\%$.; De 30 a 59 días: $+0.05\%$.; De 60 a 89 días: $+0.10\%$, y así sucesivamente.
    - Ajuste por IPC: SOLO SI LA MONEDA ESCOGIDA POR EL USUARIO ES CLP, se suma la corrección monetaria vigente.
    - Fórmula General: $$i_{total} = i_{base} + P_{plazo} + \Delta IPC$$ (si no está en CLP, Delta ICP = 0)
- Cálculo de Tasa del Periodo ($i_{periodo}$): Es la tasa real y proporcional que se aplicará según los días exactos de la inversión. Fórmula: $$i_{periodo} = i_{mensual} \times \left(\frac{Plazo\_Días}{30}\right)$$
- Cálculo de Ganancia Estimada: Ponderación por Periodo: La tasa mensual se ajusta proporcionalmente a la duración real del depósito ($Tasa \times Plazo/30$).
- Proyección de Rentabilidad: Se multiplica el capital original por la tasa del periodo para obtener la Ganancia Estimada.
- Cálculo de Retorno Final: Suma del capital inicial más la ganancia generada.
## 3.5 Pasos posteriores
- Tras realizar los cálculos de forma exitosa, se genera la "Tarjeta de Transparencia" con:
    - Monto Invertido
    - Ganancia Estimada
    - Monto Final
    - Tasa del Periodo
    - Ganancia Estimada
    - Indicadores de Referencia (Valor del IPC aplicado y, en caso de UF/USD, el precio de cambio utilizado para la validación de límites).
- La Tarjeta de Transparencia debe tener un botón "Aceptar", y debe ser la única vía a partir de la cual se puede aceptar un Depósito a Plazo (no sirve decir sí por el chat). También debe tener un botón de "Rechazar", que lleva a un estado de cierre voluntario.
- Tras la aceptación, se envía un código para autenticación OTP, el chat avisa y muestra en la intefaz un campo para rellenar con el código. Si la autenticación falla, el chat debe avisar que falló y ofrecer una nueva instancia de autenticación. Si falla 3 veces, se rechaza el Depósito a Plazo y se realiza un bloqueo de seguridad.
- Si la autenticación es exitosa, se genera un pdf con un hashing SHA-256 como contrato, y el bot felicita y se despide.
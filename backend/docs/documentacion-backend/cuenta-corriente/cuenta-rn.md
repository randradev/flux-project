# 2. CUENTA CORRIENTE
## 2.1. Descripción:
Producto bancario que permite al cliente administrar dinero mediante una cuenta, incluyendo depósitos, retiros y uso de medios de pago.
## 2.2. Datos Requeridos:
- RUT
- Nombre
- Edad
- Renta
- Nivel de Estudios (grado académico)
- Antigüedad Laboral
## 2.3. Condiciones Principales:
- Edad Mínima: 18 años
- Renta Mínima: $500.000
- Antigüedad Laboral Mínima: 6 meses
- Evaluación Comercial Obligatoria (para definir perfil)
- Clasificación de cuenta según perfil:
  - Cuenta START (nivel básico)
  - Cuenta MEDIUM (nivel medio)
  - Cuenta ADVANCE (nivel alto)
- Formalización mediante aceptación digital y firma
## 2.4. Motor de Evaluación Comercial
- Eligibilidad Mínima: Verificar que la Edad, Renta y Antigüedad Laboral mínima se cumplan.
- Asignación de Tramo Base: Se asigna START, MEDIUM o ADVANCE según el monto de la renta:
    - Cuenta START: Renta entre $500.000 y $1.000.000.
    - Cuenta MEDIUM: Renta entre $1.000.001 y $2.500.000.
    - Cuenta ADVANCE: Renta superior a $2.500.001
- Aplicación de Upgrade (solo si el nivel de estudios es UNIVERSITARIO o POSTGRADO): Si el nivel de estudios es Universitario o Postgrado, se sube una categoría (START -> MEDIUM o MEDIUM -> ADVANCE). Si es ADVANCE, se mantiene. El beneficio no es acumulable. Tener uno o ambos otorga el mismo y único "salto" de una categoría.
- Cálculo de Línea de Crédito:
    - Si la categoría FINAL es START o la antigüedad laboral es < 12 meses: Línea de crédito = $0.
    - Si la categoría FINAL es MEDIUM o ADVANCE Y la Antigüedad es ≥ 12 meses: Línea de crédito = 50% de la renta.
## 2.5 Pasos posteriores
- Tras pasar exitosamente la evaluación comercial, se genera la "Tarjeta de Transparencia" con:
    - Nombre del Plan (START, MEDIUM o ADVANCE)
    - Categoría Alcanzada: (Indicar si es por "Renta" o por "Beneficio Nivel de Estudios", Esto genera valor percibido para el usuario).
    - Cupo de Línea de Crédito.
    - Costo Mensual ($0, constante, no hay lógica para calcularlo, solo se muestra).
- Ejemplo :
    - Plan: MEDIUM (Upgrade aplicado por Título Universitario)
    - Línea de Crédito: $500.000.
    - Costo Mensual: $0 (Promoción MVP).
- La Tarjeta de Transparencia debe tener un botón "Aceptar", y debe ser la única vía a partir de la cual se puede aceptar la cuenta corriente (no sirve decir sí por el chat). También debe tener un botón de "Rechazar", que lleva a un estado de cierre voluntario.
- Tras la aceptación, se envía un código para autenticación OTP, el chat avisa y muestra en la intefaz un campo para rellenar con el código. Si la autenticación falla, el chat debe avisar que falló y ofrecer una nueva instancia de autenticación. Si falla 3 veces, se rechaza la cuenta corriente.
- Si la autenticación es exitosa, se genera un pdf con un hashing SHA-256 como contrato, y el bot felicita y se despide.
# Mapa de Interacción Determinista (UX vs LLM) - Proyecto Flux

Este documento define la frontera de responsabilidad entre los componentes de la interfaz de usuario (UI) y el Modelo de Lenguaje (LLM). Su objetivo es eliminar alucinaciones en pasos críticos de seguridad y cumplimiento legal.

## 1. Definición de Responsabilidades Generales

| Componente | Responsabilidad | Método de Entrada |
| :--- | :--- | :--- |
| **LLM (Flux)** | Moderación, guía empática, resolución de dudas y explicación de procesos. | Texto (Chat) |
| **UI (Frontend)** | Captura de datos críticos y confirmaciones legales. | Inputs, Botones, Selectores |

---

## 2. Mapa de Nodos Post-Simulación

A partir del éxito del Motor de Riesgo, el flujo se vuelve híbrido (Conversación + Componentes Fijos).

### PASO 4: Validación OTP (Seguridad)
* **Rol de Flux:** Explicar que se ha enviado un SMS, motivar al usuario a revisar su teléfono y manejar errores (ej: "El código expiró").
* **Captura de Dato:** Campo de texto numérico (6 dígitos) en la interfaz.
* **Actualización de State:** El backend valida la OTP y actualiza el State. Flux recibe el resultado del éxito/fallo.
* **PROHIBIDO:** No intentar extraer el código OTP desde el mensaje de texto del usuario.

### PASO 5: Formalización y Cierre (Legal)
* **Rol de Flux:** Resumir las condiciones finales (monto, tasa, cuotas) y explicar la importancia de la firma.
* **Captura de Dato:** Botón "Acepto Contrato" y Botón "Rechazar Oferta".
* **Actualización de State:** El payload del botón dispara la transición del grafo.
* **PROHIBIDO:** No interpretar frases como "me parece bien" o "ok" como una aceptación legal. El botón es el único gatillo válido.

---

## 3. Guía de "Voz de Flux" (Llamada B)

En estos nodos deterministas, Flux utiliza solo la **Llamada B (Generación)** con los siguientes matices de personalidad:

| Nodo | Tono de Voz | Objetivo Conversacional |
| :--- | :--- | :--- |
| **OTP** | Seguro y Vigilante | Transmitir seguridad sobre el proceso de validación de identidad. |
| **Pre-Aprobado** | Entusiasta y Transparente | Celebrar la aprobación mientras se detallan claramente los costos. |
| **Formalización** | Directo y Asistencial | Guiar al usuario hacia el botón de firma sin presionar, pero con claridad. |
| **Rechazo** | Empático y Educativo | Explicar las razones del rechazo y dar consejos para el futuro. |

---

## 4. Gestión de Excepciones

Si el usuario escribe en el chat durante un paso determinista (ej: en la OTP pregunta "¿Qué pasa si no me llega?"):
1.  **Detección de Intención:** Se usa una Llamada A ligera para detectar si es una `PREGUNTA`.
2.  **Respuesta de Flux:** Responde la duda técnica.
3.  **Call to Action (CTA):** Flux siempre termina la respuesta recordando la acción determinista: *"Puedes pedir un nuevo código en el botón de abajo si no te llega"*.
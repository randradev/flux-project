# FLUX PRODUCT BLUEPRINT: ARQUITECTURA DE ORQUESTACIÓN Y ESTADOS

## 1. PROPÓSITO DEL PROYECTO
FLUX tiene como objetivo transformar la solicitud de productos bancarios tradicionales en una experiencia fluida y asistida. El sistema utiliza grafos de estado para orquestar la lógica de negocio, permitiendo que un asistente virtual guíe al usuario desde la intención inicial hasta la formalización legal de un producto, eliminando la fricción de los formularios estáticos.

## 2. ESTRUCTURA DE PRODUCTOS (MVP)
La plataforma está diseñada para gestionar tres flujos financieros principales, cada uno con su propia lógica de riesgo y validación:
1. Crédito de Consumo: Financiamiento con evaluación de riesgo basada en scoring, capacidad de pago y amortización francesa.
2. Cuenta Corriente: Proceso de apertura segmentado (Start, Medium, Advance) según perfilamiento de estudios y renta.
3. DAP (Depósito a Plazo): Simulación de inversiones basada en capital y plazos de retención.

## 3. ARQUITECTURA DEL FLUJO
El sistema no opera como un chat genérico, sino como un motor de estados persistente. Cada producto se divide en fases críticas que el usuario visualiza en tiempo real:
- Identificación y Perfilamiento: Recuperación de datos base de la DB y captura de variables declarativas (Renta, Estudios, Antigüedad).
- Evaluación Automatizada: Ejecución de motores de cálculo (ej. Motor de Riesgo) para determinar la elegibilidad en milisegundos.
- Oferta Dinámica: Presentación de una "Tarjeta de Transparencia" con las condiciones finales, la cual actúa como el único nodo de decisión para el usuario.
- Seguridad y Formalización: Validación de identidad mediante OTP y generación de contratos legales en PDF con sellado de integridad mediante hashing SHA-256.

## 4. COMPONENTES DEL ECOSISTEMA CONVERSACIONAL
Para garantizar la flexibilidad y la trazabilidad, el proyecto integra:
- Router de Intenciones: Al iniciar un "Nuevo Chat", el sistema segmenta la conversación por producto, permitiendo que el LLM mantenga el contexto específico de cada solicitud.
- Extracción de Entidades: El asistente identifica y extrae datos clave del lenguaje natural del usuario, depositándolos en un estado estructurado (JSONB) que alimenta tanto la UI como los motores de cálculo.
- Persistencia de Sesión (Checkpoints): Capacidad de retomar cualquier proceso en el estado exacto donde se abandonó, manteniendo el historial de transiciones para análisis de embudo (funnel).

## 5. DEFINICIÓN DE LA INTERFAZ DE USUARIO (DASHBOARD)
La experiencia de usuario se divide en tres áreas funcionales integradas:
- Navegación y Contexto: Acceso a historiales y segmentación de chats activos por tipo de producto para mantener hilos de conversación independientes.
- Monitor de Estado (Proceso Flux): Un panel visual que refleja el progreso del grafo de estados y los datos capturados/detectados por el LLM, brindando transparencia total sobre lo que el sistema "sabe" del usuario.
- Canal de Interacción: Chat reactivo que soporta tanto mensajes de texto como componentes enriquecidos (tarjetas, inputs de seguridad, visualizadores de PDF).

## 6. GESTIÓN DE EXCEPCIONES
El sistema contempla estados de seguridad y cierre controlados, tales como bloqueos por intentos fallidos de autenticación (OTP), rechazos automáticos por políticas de riesgo y cierres voluntarios, asegurando que cada sesión termine con un estado de auditoría claro.
# Interpretacion general del proyecto FLUX

Este proyecto busca construir una banca digital conversacional. La idea central no es tener un chatbot generico, sino un asistente que guie al usuario por procesos financieros concretos usando un grafo de estados.

En simple: FLUX quiere reemplazar formularios bancarios largos por una conversacion guiada. El usuario escribe lo que necesita, el sistema detecta si quiere un credito, una cuenta corriente o un deposito a plazo, y desde ahi lo lleva paso a paso hasta una respuesta, oferta, validacion de identidad y contrato.

El proyecto esta pensado para tres productos principales:

- Credito de consumo.
- Cuenta corriente.
- DAP, es decir deposito a plazo.

La promesa del sistema es que el usuario siempre sepa en que etapa esta, que datos se han detectado, que falta por completar y cual es el resultado final. Por eso el proyecto insiste tanto en el "estado" y en el "Flux Progress Monitor": el frontend debe funcionar como una especie de GPS visual del proceso.

## Estado general observado

El proyecto esta dividido en tres partes claras:

- `frontend`: una interfaz React/Vite.
- `backend`: una API FastAPI con LangGraph, Supabase y Vertex AI/Gemini.
- `documentacion-gral` y `backend/docs`: documentos de arquitectura, datos, fases e instrucciones.

Tambien se ve una separacion por roles de equipo:

- Dev 1: backend, IA, grafo y orquestacion.
- Dev 2: frontend y experiencia de usuario.
- Dev 3: seguridad, OTP, contratos PDF e integridad documental.

Actualmente, el backend tiene una base real de Fase 1: endpoints, autenticacion, streaming SSE, grafo inicial y stubs de productos. El frontend, en cambio, todavia se ve como una maqueta funcional: esta todo principalmente en `frontend/src/main.jsx`, usa datos simulados y no parece estar conectado realmente al backend.

## Frontend explicado humanamente

El frontend es la cara visible de FLUX. Su mision es que el usuario no sienta que esta llenando un formulario bancario, sino conversando con un asistente que lo acompana.

Lo que muestra hoy:

- Una pantalla de login simple.
- Un dashboard con tres zonas:
  - panel lateral de historial de chats;
  - panel de proceso, donde se muestran hitos y datos detectados;
  - panel de chat, donde ocurre la conversacion.
- Datos simulados para credito, cuenta corriente y DAP.
- Un avance de pasos tambien simulado: cuando el usuario escribe algo, el frontend infiere el producto por palabras clave y avanza el paso.

En terminos humanos, el frontend quiere responder a estas preguntas del usuario:

- Donde estoy dentro del proceso?
- Que producto estoy solicitando?
- Que datos ya sabe el sistema?
- Que falta?
- Que puedo hacer ahora?

El problema actual es que esa experiencia aun esta mayormente mockeada. La documentacion pide que el Dev 2 la convierta en una interfaz real conectada al backend: leer eventos de streaming, consumir historial, enviar token JWT, mostrar nodos reales del grafo y reemplazar datos estaticos por datos que vengan de Supabase/backend.

## Backend explicado humanamente

El backend es el cerebro operativo. Recibe mensajes, valida quien es el usuario, decide que flujo corresponde y guarda el estado para que la conversacion pueda retomarse despues.

Sus piezas principales son:

- FastAPI: expone la API.
- LangGraph: organiza la conversacion como un grafo de estados.
- Gemini/Vertex AI: clasifica intenciones y, mas adelante, extraera datos desde lenguaje natural.
- Supabase: guarda usuarios, conversaciones, mensajes, solicitudes, documentos y checkpoints.
- Pydantic/settings: valida configuracion y variables de entorno.

Lo que ya se ve implementado:

- `POST /api/v1/chat`: recibe mensajes y responde por streaming SSE.
- `GET /api/v1/history`: lista conversaciones del usuario.
- `GET /api/v1/history/{conversation_id}`: recupera mensajes de una conversacion.
- Validacion de JWT con Supabase Auth.
- Creacion o recuperacion de threads conversacionales.
- Persistencia de mensajes.
- Grafo inicial con nodos:
  - `welcome`;
  - `intent_router`;
  - `loan_entry`;
  - `account_entry`;
  - `dap_entry`;
  - `general_response`.

Lo importante: hoy los flujos de credito, cuenta y DAP son stubs. Es decir, el sistema detecta la intencion y responde que el flujo completo vendra despues, pero todavia no ejecuta calculos financieros reales ni genera contratos desde esos flujos.

Los modulos de negocio (`credit_eng.py`, `account_eng.py`, `eco_service.py`, `security.py`, `pdf_factory.py`) existen como estructura, pero estan vacios. Eso calza con la planificacion: primero se arma el esqueleto, luego se completan motores, seguridad y documentos.

## Documentacion general

La documentacion es bastante completa y funciona como plano maestro del sistema.

Los documentos principales explican:

- La vision de producto: banca conversacional en lenguaje humano.
- La arquitectura por capas: frontend, API, grafo, modulos de negocio, datos.
- El modelo de datos en Supabase.
- Las fases de implementacion.
- Los contratos entre frontend y backend.
- Las responsabilidades de Dev 1, Dev 2 y Dev 3.

Hay una idea que se repite mucho: la base de datos es la fuente de verdad. En especial, `financial_applications` aparece como la tabla que sincroniza a los tres roles. El backend escribe el paso actual, estados de proceso y resultados; el frontend lee esos campos para pintar la experiencia; seguridad/documentos actualiza OTP, contratos y hash.

La documentacion tambien define una regla clave para Dev 2: el frontend no debe "inventar" en que etapa esta el usuario. Debe leer el estado real del backend/base de datos y representarlo visualmente.

## Rol del Dev 2 en las 3 fases

En simple, Dev 2 es quien convierte el cerebro del sistema en una experiencia usable. No decide las reglas financieras ni la seguridad profunda; su trabajo es mostrar el estado correcto, permitir acciones del usuario y hacer que el proceso se sienta claro, confiable y fluido.

### Fase 1: ordenar y conectar la interfaz

Objetivo simple: que el frontend deje de ser una maqueta desordenada y pueda hablar con el backend.

Dev 2 debe:

- Separar el frontend en componentes, hooks, servicios y estado global.
- Sacar datos falsos o reducirlos a mocks temporales controlados.
- Crear una capa de servicio para llamar al backend.
- Leer el streaming del endpoint `/api/v1/chat`.
- Implementar login y registro con Supabase Auth.
- Enviar el token JWT al backend en cada mensaje.
- Conectar el historial lateral con `/api/v1/history`.
- Mostrar en pantalla el nodo actual del grafo, aunque el backend aun responda solo con saludos o stubs.
- Agregar opcion para borrar conversaciones cuando exista soporte.

En palabras simples: en Fase 1, Dev 2 prepara la casa. Ordena la interfaz, conecta el chat real y deja listo el panel de progreso para escuchar al backend.

### Fase 2: hacer usable el flujo de credito

Objetivo simple: que el usuario pueda vivir el proceso completo de credito de consumo desde la interfaz.

Dev 2 debe:

- Mapear los nodos de credito del backend a etiquetas entendibles para el usuario.
- Hacer que el Flux Progress Monitor avance automaticamente segun `current_step` o el nodo actual.
- Crear la tarjeta de oferta o "Tarjeta de Transparencia".
- Mostrar datos reales de la oferta: monto aprobado, tasa, cuota, CAE y resultados del motor de riesgo.
- Agregar botones para aceptar o rechazar la oferta.
- Crear el widget de OTP con input de 6 digitos.
- Mostrar errores de OTP, intentos agotados y estados de bloqueo.
- Mostrar pantallas o modales cuando el credito sea rechazado o cerrado.

En palabras simples: en Fase 2, Dev 2 transforma el credito en una experiencia interactiva. El usuario no solo conversa; tambien ve su oferta, decide, valida su identidad y entiende que esta pasando.

### Fase 3: pulir, transparentar y completar la experiencia

Objetivo simple: que la aplicacion se sienta terminada, profesional y confiable.

Dev 2 debe:

- Integrar un visor de PDF para contratos digitales.
- Mostrar el hash SHA-256 del documento como sello de integridad.
- Explicar visualmente, de forma simple, que ese hash ayuda a verificar que el contrato no fue alterado.
- Agregar animaciones suaves cuando el proceso avanza.
- Agregar skeletons o estados de carga en momentos pesados, por ejemplo cuando se calcula riesgo o se genera un documento.
- Mejorar el historial y perfil del usuario.
- Permitir retomar procesos pendientes.
- Permitir acceder o descargar contratos antiguos cuando el backend lo permita.
- Mostrar estados finales de exito de forma clara.

En palabras simples: en Fase 3, Dev 2 le da terminacion de producto real a FLUX. Hace que el usuario confie en lo que ve, entienda los documentos y pueda volver a sus procesos sin perderse.

## Resumen corto del Dev 2

Fase 1: conectar y ordenar.

Fase 2: construir la experiencia completa del credito.

Fase 3: pulir la confianza, contratos, historial y experiencia final.

La frase mas simple para describir su rol seria:

Dev 2 es responsable de que el estado real del backend se transforme en una interfaz clara, util y confiable para el usuario.

## Lectura final

FLUX esta pensado como un sistema bancario conversacional serio, no como un chatbot decorativo. El backend actua como motor de estados y fuente de verdad; el frontend debe representar ese estado sin inventarlo; la documentacion intenta mantener alineados a los tres desarrolladores.

El punto mas importante para avanzar es cerrar la brecha entre maqueta y producto: hoy el frontend ya muestra la experiencia deseada, pero necesita conectarse al backend real y obedecer los estados persistidos. Ese es justamente el centro del trabajo del Dev 2.

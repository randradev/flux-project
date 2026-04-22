# PLAN DE IMPLEMENTACIÓN DETALLADO
## FASE 1 — Dev 1 (AI Orchestrator & Backend Lead)
### Proyecto FLUX · Ejecutado por Agente de Antigravity

---

> **REGLA DE ORO DEL AGENTE**
> Este plan está diseñado para ejecución por un agente bajo supervisión humana estricta.
> El agente **DEBE**:
> - Detenerse al final de cada sub-paso y pedir confirmación explícita antes de continuar.
> - Crear el archivo `CP-0X-dev1-fase1.md` al comenzar cada Paso (siendo `X` el número del paso).
> - Actualizar ese archivo con un reporte breve tras completar cada sub-paso.
> - Nunca realizar cambios no contemplados sin solicitar permiso explícito.
> - Al finalizar cada Paso completo, agregar al archivo CP el reporte final con las pruebas ejecutadas.
>
> **Cualquier acción no cubierta por este plan requiere permiso explícito del desarrollador humano antes de ejecutarse.**

---

## RESUMEN DE PASOS

| Paso | Nombre | Entregable |
|------|--------|------------|
| Paso 1 | Setup de Infraestructura y Entorno | Servidor FastAPI levantando localmente |
| Paso 2 | Capa de Persistencia y Datos (DB) | Supabase con schema completo, seed y cliente funcional |
| Paso 3 | Configuración de Vertex AI (Gemini) | Cliente Gemini con Dual-Init verificado |
| Paso 4 | Core del Grafo LangGraph | Grafo básico que clasifica intenciones y persiste estado |
| Paso 5 | Autenticación y Threading de Sesión | JWT validation + thread_id vinculado al usuario |
| Paso 6 | API Endpoints Básicos | /chat con streaming y /history funcionales |

---

## CONVENCIONES DEL DOCUMENTO

- **[CREAR]** → El agente debe crear un archivo nuevo.
- **[MODIFICAR]** → El agente modifica un archivo existente.
- **[EJECUTAR]** → El agente corre un comando en terminal.
- **[DETENCIÓN OBLIGATORIA]** → El agente para, actualiza el CP y espera confirmación.
- **[DECISIÓN TÉCNICA]** → El agente debe documentar la decisión en el CP si toma una variante.

---

# ENTREGABLE FINAL — FASE 1, DEV 1

Al completar los 6 pasos y sus checkpoints, el entregable es:

## Servidor FastAPI Funcional

Un servidor en `http://localhost:8000` con:

| Capacidad | Descripción |
|-----------|-------------|
| ✅ Levanta sin errores | `uvicorn main:app --reload` inicia sin excepciones |
| ✅ Conectado a Supabase | Schema completo, seed de catálogos, helpers de CRUD |
| ✅ Conectado a Vertex AI | Cliente Gemini Dual-Init con ADC verificado |
| ✅ Grafo LangGraph activo | Detecta intenciones LOAN / ACCOUNT / DAP / GENERAL |
| ✅ Estado persistente | PostgresSaver guarda el estado en Supabase entre sesiones |
| ✅ Autenticación JWT | Todos los endpoints validan el token de Supabase Auth |
| ✅ Streaming de respuestas | POST /chat devuelve SSE en tiempo real |
| ✅ Historial de chats | GET /history recupera conversaciones del usuario |

## Archivos de Checkpoint Generados

```
/backend/
├── CP-01-dev1-fase1.md   ← Setup de infraestructura
├── CP-02-dev1-fase1.md   ← Capa de persistencia
├── CP-03-dev1-fase1.md   ← Vertex AI
├── CP-04-dev1-fase1.md   ← Core del Grafo
├── CP-05-dev1-fase1.md   ← Autenticación
└── CP-06-dev1-fase1.md   ← API Endpoints
```
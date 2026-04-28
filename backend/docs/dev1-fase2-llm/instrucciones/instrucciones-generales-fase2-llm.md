# Flux — Fase 2, Paso 2
# Solución y Plan de Implementación: Arquitectura de Doble Llamada

**Versión:** 3.0 — Decoupled Execution + Validación de Nulos + Recuperación de Humanidad  
**Estado:** Listo para implementación  
**Archivos afectados:** `credit.py`, `loan_schemas.py`, `gemini_client.py`, `loan_playground.py`  
**Archivos inmutables:** `state.py`, `workflow.py`, `edges.py`, `supabase.py`

---

## PARTE I: DISEÑO DE LA SOLUCIÓN

### 1.1 Problema Consolidado

El diagnóstico anterior identificó cuatro causas raíz que se potencian entre sí:

| # | Causa | Síntoma visible |
|---|---|---|
| CR-1 | Check `not valor` en lugar de `is None` | `-1` y `0` pasan como datos válidos, avance silencioso con basura |
| CR-2 | `json_mode` sin `temperature=0.0` | El modelo alucina valores centinela (`-1`, `0`, `"MEDIA"`) para campos vacíos |
| CR-3 | Sin pre-filtro de intención | Saludos y mensajes irrelevantes contaminan el State |
| CR-4 | Extracción y generación en un solo paso | El modelo prioriza coherencia gramatical sobre fidelidad de extracción; la respuesta suena robótica |

La nueva arquitectura de **Doble Llamada** resuelve CR-2 y CR-4 de raíz al separar física y conceptualmente la extracción de la generación conversacional. Los fixes de código (CR-1 y CR-3) se mantienen tal como se diseñaron en el diagnóstico anterior.

---

### 1.2 Arquitectura de Doble Llamada (Decoupled Execution)

#### Flujo interno del nodo `loan_collecting_profile_node`

```
Mensaje del usuario
        │
        ▼
┌─────────────────────────────────────────────────┐
│  LLAMADA A — EXTRACTOR (LLM #1)                 │
│  Modelo : gemini-3-flash-preview                │
│  Temp   : 0.0                                   │
│  Output : structured_output (function_calling)  │
│  Retorna: LoanProfileExtraction (JSON validado) │
│  Incluye: campo `intencion` como pre-filtro     │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
        ¿intencion == DATO_FINANCIERO?
         /                           \
       NO                            SÍ
        │                             │
        ▼                             ▼
  [No actualizar               [Merge defensivo]
   el State]                   [Check is None]
        │                      [Validar centinelas]
        │                             │
        ▼                             ▼
  ¿Hay campos                  ¿missing == []?
  faltantes previos?            /           \
        │                     SÍ            NO
        ▼                      │             │
  [Calcular               [Avance       [Calcular
  contexto de             silencioso]   contexto de
  re-pregunta]                          re-pregunta]
        │                                    │
        └──────────────┬─────────────────────┘
                       ▼
        ┌─────────────────────────────────────────────────┐
        │  LLAMADA B — GENERADOR (LLM #2)                 │
        │  Modelo : gemini-3-flash-preview                │
        │  Temp   : 0.7                                   │
        │  Output : texto libre (sin schema)              │
        │  Input  : contexto estructurado + personalidad  │
        │  Retorna: string con respuesta de Flux          │
        └─────────────────┬───────────────────────────────┘
                          │
                          ▼
              [Actualización transaccional
               del FluxState: un solo return]
```

#### Principio de diseño de cada llamada

| Llamada | Responsabilidad | Lo que NO hace |
|---|---|---|
| **A — Extractor** | Identificar y normalizar datos financieros del mensaje | Generar texto, ser amigable, comentar los datos |
| **B — Generador** | Producir la respuesta conversacional de Flux | Extraer datos, evaluar si los datos son completos |

Esta separación es la misma que usaba el sistema anterior (Llamada 1 / Llamada 2 en el informe `informe-llm-version-anterior.md`), pero ahora implementada dentro de la solidez de LangGraph en lugar del código espagueti previo.

---

### 1.3 Contrato de Datos del Nodo

```
INPUT  (desde FluxState):
  state["messages"]                          → Historial completo de mensajes
  state["collecting_data"]["loan_profile"]   → Datos ya recolectados (puede ser {})
  state["preparation_data"]["nombre"]        → Nombre del usuario (para personalización)
  state["session"]["application_id"]         → Para semáforos Supabase

OUTPUT (al FluxState — actualización transaccional única):
  state["messages"]           += [AIMessage(content=respuesta_flux)]  ← Solo si hay re-pregunta
  state["collecting_data"]["loan_profile"]   → Perfil actualizado (merge)
  state["session"]["current_node"]           → "LOAN_COLLECTING_PROFILE"
```

**Regla de transaccionalidad:** El nodo realiza **un único `return`** al final, con todos los campos del State que modifica. No hay returns intermedios salvo en el caso de error técnico. Esto garantiza que el checkpointer de LangGraph recibe un snapshot consistente.

---

## PARTE II: PLAN DE IMPLEMENTACIÓN

### Convenciones del Plan

- **[CÓDIGO]** — Cambio de código puro, sin invocar APIs externas.
- **[PROMPT]** — Cambio de prompt o configuración del LLM.
- **[TEST-UNITARIO]** — Verificable sin credenciales de Vertex AI.
- **[TEST-INTEGRACIÓN]** — Requiere credenciales reales de Vertex AI.
- **✅ CRITERIO PASS** — Condición explícita que debe cumplirse para cerrar el sub-paso.

---

## APÉNDICE: Mapa de Archivos Finales

```
app/
├── graph/
│   ├── nodes/
│   │   ├── credit.py                    ← MODIFICADO v2.1
│   │   └── schemas/
│   │       └── loan_schemas.py          ← MODIFICADO v2.1
│   ├── state.py                         ← INMUTABLE
│   ├── workflow.py                      ← INMUTABLE
│   └── edges.py                         ← INMUTABLE
├── infra/
│   ├── gemini_client.py                 ← MODIFICADO v2.1
│   └── supabase.py                      ← INMUTABLE
└── ...

backend/scratch/
└── loan_playground.py                   ← MODIFICADO v2.1

tests/
├── unit/
│   ├── test_credit_helpers.py           ← NUEVO
│   ├── test_loan_schemas.py             ← NUEVO
│   ├── test_gemini_client.py            ← NUEVO
│   └── test_loan_collecting_profile_node.py  ← NUEVO
└── integration/
    └── test_loan_collecting_profile_integration.py  ← NUEVO
```

---

*Documento generado para Flux — Fase 2, Paso 2. Versión 3.0.*
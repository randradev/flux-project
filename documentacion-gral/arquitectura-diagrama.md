# Diagrama de Arquitectura

```mermaid
graph TD
    %% APIs Externas (Flancos)
    Gemini_API((Gemini API))
    Eco_API((API Indicadores))

    %% CAPA 1: UI
    subgraph L1 [1. Capa de Presentación]
        UI[Chat Interface]
        MON[Flux Progress Monitor]
        COMP[Dynamic Components]
    end

    %% CAPA 2: GATEWAY
    subgraph L2 [2. Capa de Comunicación]
        GW[API Gateway / WS]
        ATH[Auth Guard]
    end

    %% CAPA 3: CEREBRO
    subgraph L3 [3. Orquestación Cognitiva]
        STATE{State Manager}
        RT[Intent Router]
        EXT[Entity Extractor]
    end

    %% CAPA TRANSVERSAL (Lado Derecho para evitar cruces)
    subgraph Transversals [Nodos Transversales]
        RAG[Knowledge Base]
        AMB[Ambiguity Handler]
        ERR[Service Error]
        GEND[GLOBAL_END]
    end

    %% CAPA 4: NEGOCIO
    subgraph L4 [4. Lógica de Negocio]
        CR[Credit Module]
        AC[Account Module]
        DP[Deposits Module]
        SEC[Security Service]
        DOC[Document Service]
    end

    %% CAPA 5: DATA
    subgraph L5 [5. Infraestructura y Datos]
        DB[(PostgreSQL + pgvector)]
        STG[(Supabase Storage)]
    end

    %% --- FLUJO DE CONTROL ---
    UI <--> GW
    GW <--> ATH
    ATH <--> STATE
    STATE -.-> MON

    %% --- RELACIONES IA ---
    STATE <--> RT
    RT <--> EXT
    EXT <--> Gemini_API

    %% --- RELACIONES PRODUCTO ---
    STATE === CR
    STATE === AC
    STATE === DP
    STATE === SEC

    %% --- CONSUMO EXTERNO ---
    Eco_API -.-> CR
    Eco_API -.-> DP

    %% --- SALIDAS LÓGICAS ---
    CR & AC & DP ---> GEND
    SEC ---> ERR
    RAG <--> DB

    %% --- PERSISTENCIA ---
    CR & AC & DP & SEC ----> DB
    DOC ----> STG
    DOC ----> DB

    %% --- ESTILOS ---
    style GEND fill:#f96,stroke:#333,stroke-width:2px
    style SEC fill:#f66,stroke:#333,stroke-width:2px
    style Gemini_API fill:#6af,stroke:#333
    style Eco_API fill:#9cf,stroke:#333
    style Transversals fill:#fffdf0,stroke:#d4a017,stroke-dasharray: 5 5
```mermaid
graph TD
    %% --- ENTRADA DESDE DASHBOARD ---
    START((Nueva Solicitud)) --> LOAN_INIT[LOAN_INIT: Carga datos de DB]
    
    %% --- BUCLE DE RECOLECCIÓN CON CAPA TRANSVERSAL ---
    LOAN_INIT --> DATA_COLLECT{¿Input es Dato, Duda o Ruido?}
    
    %% Desvíos Transversales
    DATA_COLLECT -- "Es una Duda" --> K_RAG[KNOWLEDGE_BASE_RAG: Responde duda]
    K_RAG -- "Transition: 'Retomando...'" --> DATA_COLLECT
    
    DATA_COLLECT -- "Es Ruido/Ambigüedad" --> AMBIGUITY[AMBIGUITY: Re-solicita dato]
    AMBIGUITY --> DATA_COLLECT
    
    %% Flujo Principal
    DATA_COLLECT -- "Es Dato Válido" --> LOAN_COLLECT_PROFILE[LOAN_COLLECTING_PROFILE: Renta/Antigüedad/Estudios]
    LOAN_COLLECT_PROFILE --> LOAN_COLLECT_SIM[LOAN_COLLECTING_SIMULATION: Monto/Plazo]
    
    %% --- EVALUACIÓN Y ERRORES ---
    LOAN_COLLECT_SIM --> RISK_ENGINE{{LOAN_RISK_ENGINE}}
    
    RISK_ENGINE -- "Fallo Técnico" --> S_ERROR[SERVICE_ERROR: Pausa flujo]
    RISK_ENGINE -- "Rechazo" --> REJECTED[LOAN_REJECTED_POLICY]
    RISK_ENGINE -- "Aprobado" --> PRE_APP[/LOAN_PRE_APPROVED: Tarjeta Transparencia/]
    
    %% --- FORMALIZACIÓN Y SEGURIDAD ---
    PRE_APP -- "Acepta" --> OTP[LOAN_OTP_VALIDATION]
    PRE_APP -- "Rechaza" --> CLOSED[LOAN_CLOSED_BY_USER]
    
    OTP -- "Éxito" --> FORMAL[LOAN_FORMALIZATION: ReportLab + SHA256]
    OTP -- "Fallo Crítico/Malicioso" --> WATCHDOG[SECURITY_WATCHDOG: Bloqueo DB]
    
    FORMAL --> COMPLETED[LOAN_COMPLETED: Entrega Contrato]
    
    %% --- CIERRES ---
    REJECTED --> END((FIN))
    CLOSED --> END
    COMPLETED --> END
    WATCHDOG --> END
    S_ERROR -.-> |Retoma desde Dashboard| LOAN_INIT

    %% ESTILOS
    style DATA_COLLECT fill:#f9f,stroke:#333
    style K_RAG fill:#fffbca,stroke:#d4a017
    style AMBIGUITY fill:#fffbca,stroke:#d4a017
    style S_ERROR fill:#ffcccb,stroke:#f00
    style WATCHDOG fill:#000,stroke:#f00,color:#fff
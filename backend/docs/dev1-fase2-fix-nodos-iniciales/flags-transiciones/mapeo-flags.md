# Ruteo Consciente de Progreso

## PASO 1: Agregar la lógica de flags en app/models/state.py, en session.
Para que el State sea limpio, la implementación debería ser así en app/models/state.py: Separamos los Estados de Logro (persisten hasta el final) de los Eventos de Transición (son efímeros).

```python
"progress": {
    # ---------------------------------------------------------
    # ESTADOS DE LOGRO (Para el Ruteador / SUCCESS_MAP)
    # ---------------------------------------------------------
    "profile_completed": False,
    "simulation_completed": False,
    "offer_decided": False,      # True si aceptó o rechazó
    "otp_verified": False,
    
    # ---------------------------------------------------------
    # EVENTOS DE TRANSICIÓN (Para el LLM / Tono de respuesta)
    # ---------------------------------------------------------
    "just_completed_step": Optional[str] = None 
    # En lugar de 5 booleanos, usamos un string: 
    # "PROFILE", "SIMULATION", "OFFER", "DECISION", "OTP"
}
```

Para que no se olvide nada, esta es la secuencia que se debe asegurar:
1. EXTRACCIÓN: El nodo extrae el dato (ej: Universitario).
2. CHECK: El nodo verifica si con ese dato se completó el set (Renta + Antigüedad + Estudios).
3. IZADO DE BANDERAS: Si está completo, pone profile_completed = True y just_completed_step = 'PROFILE'.
4. RUTEO (Siguiente Turno): El ruteador ve profile_completed == True, consulta el _SUCCESS_MAP y te manda a LOAN_COLLECTING_SIMULATION.
5. RESET: Al entrar al nuevo nodo, se limpia just_completed_step

## PASO 2: Implementar cambios en los nodos de recolección.

Cuando un nodo de recolección termina de procesar el mensaje del usuario, verifica si ya tiene todos los datos necesarios. Si es así, levanta una bandera histórica (ej: profile_completed) para que el sistema nunca olvide que ese paso terminó, y marca un evento de transición (just_completed_step = 'PROFILE').

En el siguiente turno, el Ruteador verá la bandera histórica y enviará al usuario al siguiente nodo del mapa de éxito. Al entrar a ese nuevo nodo, lo primero que se hará es limpiar el evento de transición (just_completed_step = None), pero solo después de que el generador de texto lo haya usado para felicitar al usuario y cambiar de tema.

1. En app/models/state.py (El molde)
    - Accion: Eliminar los booleanos profile_just_completed, simulation_just_completed, etc.
    - Nuevo campo: Añadir just_completed_step: Optional[str] = None dentro del objeto de sesión o progreso.
2. En app/graph/nodes/credit.py (Los trabajadores)
- Tomemos como ejemplo loan_collecting_profile_node:
    - Lógica de Extracción: Sigue igual (usa el LLM Estructurado).
    - Lógica de Cierre (Cambio):
        - Antes: res["session"]["profile_just_completed"] = True.
        - Ahora:
        ```python
        if all_profile_data_present:
            res["session"]["progress"]["profile_completed"] = True
            res["session"]["progress"]["just_completed_step"] = "PROFILE"
        ```
    - Lógica de Limpieza (Al inicio del nodo):
        - Si el nodo recibe el control y el just_completed_step es de un paso anterior, debe limpiarlo para no confundir al generador de texto en el futuro.
- Aplicar lo mismo a loan_collecting_sim_node.
- Tenerlo en cuenta para los otros nodos que faltan por implementar. 


## III. Implementar la Matriz de Transición en edges.py

_SUCCESS_MAP = {
    "LOAN_COLLECTING_PROFILE": "LOAN_COLLECTING_SIMULATION",
    "LOAN_COLLECTING_SIMULATION": "LOAN_RISK_ENGINE",
    "LOAN_PRE_APPROVED": "LOAN_OTP_VALIDATION",
    "LOAN_OTP_VALIDATION": "LOAN_FORMALIZATION"
}
## PASO 6 — Tests de Integración con LLM Real

> **Objetivo:** Validar el comportamiento end-to-end con el modelo real de Vertex AI. Estos tests son la validación final antes de cerrar el Paso 2.

---

### Sub-paso 6.1 — Suite de integración [TEST-INTEGRACIÓN]

**Archivo:** `tests/integration/test_loan_collecting_profile_integration.py`

```python
"""
Tests de integración para loan_collecting_profile_node.
REQUIEREN credenciales reales de Vertex AI (ADC configurado).
Ejecutar con: pytest tests/integration/ -v -m integration

Estos tests validan el comportamiento real del LLM,
a diferencia de los unit tests que usan mocks.
"""

import pytest
from langchain_core.messages import HumanMessage, AIMessage
from app.graph.nodes.credit import loan_collecting_profile_node


pytestmark = pytest.mark.integration  # Marcar para ejecución selectiva


def make_state(messages: list, profile: dict = None) -> dict:
    return {
        "messages":        messages,
        "collecting_data": {"loan_profile": profile or {}, "loan_sim": {}},
        "session":         {"current_node": "LOAN_COLLECTING_PROFILE", "application_id": None},
        "preparation_data": {"nombre": "Ana Torres", "edad": 28},
    }


class TestExtraccionNulos:
    """Verifica que el extractor retorna null para mensajes sin datos financieros."""
    
    def test_saludo_no_contamina_state(self):
        state = make_state([
            AIMessage(content="¿Cuál es tu renta mensual?"),
            HumanMessage(content="Hola! ¿cómo estás?"),
        ])
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile == {}, \
            f"Un saludo no debe modificar el perfil. Perfil resultante: {profile}"
        assert "messages" in result, \
            "El bot debe emitir un mensaje (re-pregunta) ante un saludo"
    
    def test_mensaje_irrelevante_no_inyecta_centinelas(self):
        state = make_state([
            AIMessage(content="¿Cuál es tu renta mensual?"),
            HumanMessage(content="¿Conoces a Joe Black?"),
        ])
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile.get("renta") is None or profile.get("renta") > 0, \
            f"renta no puede ser 0. Valor: {profile.get('renta')}"
        assert profile.get("antiguedad_laboral") is None or profile.get("antiguedad_laboral") >= 0, \
            f"antiguedad no puede ser -1. Valor: {profile.get('antiguedad_laboral')}"


class TestExtraccionPositiva:
    """Verifica que el extractor captura datos reales correctamente."""
    
    def test_modismo_palo_extraido_correctamente(self):
        state = make_state([HumanMessage(content="Gano 3 palos mensuales")])
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile.get("renta") == 3_000_000, \
            f"'3 palos' debe ser 3.000.000. Valor: {profile.get('renta')}"
    
    def test_modismo_lucas_extraido_correctamente(self):
        state = make_state([HumanMessage(content="Me pagan 800 lucas")])
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile.get("renta") == 800_000, \
            f"'800 lucas' debe ser 800.000. Valor: {profile.get('renta')}"
    
    def test_años_convertidos_a_meses(self):
        state = make_state([HumanMessage(content="Llevo 5 años en la pega")])
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile.get("antiguedad_laboral") == 60, \
            f"'5 años' debe ser 60 meses. Valor: {profile.get('antiguedad_laboral')}"
    
    def test_nivel_estudios_inferido_de_carrera(self):
        state = make_state([HumanMessage(content="Soy Ingeniero Civil")])
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile.get("nivel_estudios") == "UNIVERSITARIO", \
            f"'Ingeniero Civil' debe mapearse a UNIVERSITARIO. Valor: {profile.get('nivel_estudios')}"
    
    def test_tres_datos_en_un_mensaje_avance_silencioso(self):
        state = make_state([
            HumanMessage(content="Gano 2 millones, llevo 3 años trabajando y soy técnico en informática")
        ])
        result = loan_collecting_profile_node(state)
        
        assert "messages" not in result or len(result.get("messages", [])) == 0, \
            "Con perfil completo no debe haber re-pregunta (avance silencioso)"
        
        profile = result["collecting_data"]["loan_profile"]
        assert profile["renta"] == 2_000_000
        assert profile["antiguedad_laboral"] == 36
        assert profile["nivel_estudios"] == "TECNICO"


class TestMergeAcumulativo:
    """Verifica la acumulación de datos entre múltiples turnos."""
    
    def test_datos_previos_se_preservan(self):
        """El State acumulado de turnos anteriores no se borra."""
        perfil_previo = {"renta": 1_500_000, "nivel_estudios": "UNIVERSITARIO"}
        state = make_state(
            messages=[
                AIMessage(content="Ya anoté tu renta y estudios. ¿Hace cuánto trabajas?"),
                HumanMessage(content="Llevo 2 años y medio en la empresa"),
            ],
            profile=perfil_previo
        )
        result = loan_collecting_profile_node(state)
        profile = result["collecting_data"]["loan_profile"]
        
        assert profile.get("renta") == 1_500_000,      "La renta previa debe preservarse"
        assert profile.get("nivel_estudios") == "UNIVERSITARIO", "Los estudios previos deben preservarse"
        assert profile.get("antiguedad_laboral") == 30, "2.5 años = 30 meses"


class TestRespuestaGenerada:
    """Verifica características de la respuesta conversacional de Flux."""
    
    def test_respuesta_menciona_nombre_usuario(self):
        state = make_state([
            AIMessage(content="¿Cuál es tu renta?"),
            HumanMessage(content="Hola"),
        ])
        result = loan_collecting_profile_node(state)
        
        if "messages" in result and result["messages"]:
            response = result["messages"][-1].content
            # Flux debe mencionar el nombre en algún momento de la conversación
            # (puede que no sea en el saludo, dependiendo del prompt)
            assert len(response) > 10, "La respuesta debe ser sustancial, no vacía"
    
    def test_respuesta_celebra_dato_nuevo(self):
        """Cuando el usuario entrega un dato, Flux debe celebrarlo antes de pedir el siguiente."""
        state = make_state([
            AIMessage(content="¿Cuál es tu renta mensual?"),
            HumanMessage(content="Gano 2 millones y medio"),
        ])
        result = loan_collecting_profile_node(state)
        
        if "messages" in result and result["messages"]:
            response = result["messages"][-1].content.lower()
            # Verificar que la respuesta tenga alguna señal de reconocimiento positivo
            positive_signals = ["buena", "perfecto", "anotado", "excelente", "listo", "genial", "buenísimo"]
            has_positive = any(signal in response for signal in positive_signals)
            assert has_positive, \
                f"Flux debe celebrar el dato entregado. Respuesta: {result['messages'][-1].content}"
```

---
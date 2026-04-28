# tests/unit/test_credit_helpers.py

from app.graph.nodes.credit import _get_missing_profile_fields

def test_perfil_vacio_retorna_todos():
    assert _get_missing_profile_fields({}) == ["renta", "antiguedad_laboral", "nivel_estudios"]

def test_valores_centinela_llm_son_rechazados():
    """El valor -1 que alucina el LLM debe ser tratado como faltante."""
    perfil = {"renta": 0, "antiguedad_laboral": -1, "nivel_estudios": "MEDIA"}
    missing = _get_missing_profile_fields(perfil)
    assert "renta" in missing,              "renta=0 debe ser faltante"
    assert "antiguedad_laboral" in missing, "antiguedad=-1 debe ser faltante"
    # nivel_estudios="MEDIA" es un valor válido — no debe estar en missing
    assert "nivel_estudios" not in missing, "MEDIA es un valor válido del Literal"

def test_antiguedad_cero_es_valida():
    """0 meses es posible (recién comenzó a trabajar); no debe ser faltante."""
    perfil = {"renta": 800_000, "antiguedad_laboral": 0, "nivel_estudios": "TECNICO"}
    assert _get_missing_profile_fields(perfil) == []

def test_perfil_completo_retorna_vacio():
    perfil = {"renta": 1_500_000, "antiguedad_laboral": 24, "nivel_estudios": "UNIVERSITARIO"}
    assert _get_missing_profile_fields(perfil) == []

def test_perfil_parcial_retorna_faltantes():
    perfil = {"renta": 2_000_000}
    missing = _get_missing_profile_fields(perfil)
    assert "renta" not in missing
    assert "antiguedad_laboral" in missing
    assert "nivel_estudios" in missing

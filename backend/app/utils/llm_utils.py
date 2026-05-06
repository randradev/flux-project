# backend/app/utils/llm_utils.py

def normalize_llm_response(content) -> str:
    """
    Normaliza el contenido de respuesta de un LLM (como Gemini) a un string.
    
    Maneja los casos donde el SDK devuelve una lista de bloques (dict)
    en lugar de un string plano, extrayendo y uniendo el campo 'text'.
    """
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        # Unir todos los bloques que tengan una llave 'text'
        return "".join(
            block.get("text", "") 
            for block in content 
            if isinstance(block, dict) and "text" in block
        )
    
    # Fallback para otros tipos inesperados
    return str(content) if content is not None else ""

import os
import sys

# Ajustar path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.infra.gemini_client import get_generation_model
from langchain_core.messages import HumanMessage

def inspect():
    print("--- Inspeccionando Respuesta de Gemini ---")
    model = get_generation_model()
    
    # Una pregunta simple para provocar una respuesta de texto
    response = model.invoke([
        HumanMessage(content="Hola, ¿quién eres? Responde en una oración corta.")
    ])
    
    print(f"\nTipo de response.content: {type(response.content)}")
    print(f"Contenido raw: {response.content}")
    
    if isinstance(response.content, list):
        print("\nDetalle de los bloques en la lista:")
        for i, block in enumerate(response.content):
            print(f" Bloque {i}: Tipo={type(block)} | Contenido={block}")

if __name__ == "__main__":
    inspect()

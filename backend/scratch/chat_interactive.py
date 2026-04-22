import os
import sys

# Añadir el directorio actual al path para importar app
sys.path.append(os.getcwd())

from app.infra.gemini_client import get_chat_model
from langchain_core.messages import HumanMessage

def start_chat():
    print("\n--- 🤖 FLUX Gemini Chat Demo ---")
    print("Escribe 'salir' para terminar.\n")
    
    model = get_chat_model()
    
    while True:
        try:
            user_input = input("Tú: ").strip() # .strip() elimina espacios y saltos de línea
        except EOFError:
            break
            
        if not user_input: # Si el input está vacío tras el strip, ignorar
            print("⚠️ Por favor, escribe un mensaje.")
            continue
        
        if user_input.lower() in ['salir', 'exit', 'quit']:
            break
            
        try:
            response = model.invoke([HumanMessage(content=user_input)])
            
            # El modelo Gemini 3 Preview a veces devuelve una estructura de lista compleja
            if isinstance(response.content, list):
                # Extraer el texto si es una lista de diccionarios
                text_parts = [part.get('text', '') for part in response.content if isinstance(part, dict) and 'text' in part]
                text_response = "".join(text_parts) if text_parts else str(response.content)
            else:
                text_response = response.content
                
            print(f"\nGemini: {text_response}\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")

if __name__ == "__main__":
    start_chat()

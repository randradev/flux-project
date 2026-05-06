import asyncio
from app.modules.consultant import get_consultant_response

# Simulamos un estado básico de LangGraph
mock_state = {
    "session": {
        "current_node": "LOAN_COLLECT_DATA"
    },
    "preparation_data": {
        "nombre": "Diego"
    },
    "collecting_data": {
        "loan_sim": {
            "renta": 800000,
            "monto": 2000000
        }
    }
}

async def test_queries():
    queries = [
        "¿Qué es Flux?", # General
        "¿Cuál es el monto máximo para el crédito?", # Producto específico (LOAN)
        "¿Tienen depósitos a plazo?", # Producto que aún no implementas en nodos
        "¿Me alcanza con mi sueldo de 800 lucas?" # Contextual (usa el state)
    ]

    for q in queries:
        print(f"\nUSUARIO: {q}")
        response = get_consultant_response(q, mock_state)
        print(f"FLUX: {response}")
        print("-" * 30)

if __name__ == "__main__":
    asyncio.run(test_queries())
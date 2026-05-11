import sys
import os
import datetime
import io

# Configurar salida a UTF-8 para evitar errores con emojis en Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Añadir el root del proyecto al path para poder importar los módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from backend.app.modules.pdf_factory import PDFFactory

def test_generate_dap_contract():
    print("--- Iniciando prueba de generacion de contrato DAP ---")
    
    factory = PDFFactory()
    
    # Datos Mock basados en el payload definido en el nodo de formalización
    mock_data = {
        "nombre": "JUAN PEREZ SOTO",
        "rut": "12.345.678-9",
        "monto_invertido": 5000000.0,
        "moneda": "CLP",
        "plazo_dias": 90,
        "tasa_mensual": 0.0075, # 0.75%
        "ganancia_estimada": 112500.0,
        "total_a_recibir": 5112500.0,
        "fecha_emision": datetime.datetime.now().strftime("%d/%m/%Y")
    }
    
    try:
        # Intentamos crear el PDF
        print(f"Generando PDF para {mock_data['nombre']}...")
        local_path, security_hash = factory.create_pdf("DEPOSITO_A_PLAZO", mock_data)
        
        print("\nEXITO: Contrato generado exitosamente.")
        print(f"Ruta local: {local_path}")
        print(f"Hash de seguridad: {security_hash}")
        
        # Verificamos que el archivo exista
        if os.path.exists(local_path):
            print(f"Tamano del archivo: {os.path.getsize(local_path)} bytes")
        else:
            print("AVISO: El archivo no se encuentra en la ruta especificada.")
            
    except Exception as e:
        print(f"ERROR durante la generacion: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_generate_dap_contract()

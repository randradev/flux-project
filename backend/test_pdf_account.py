# C:\Users\Admn\.gemini\antigravity\brain\19db90bf-6393-4c5a-884f-23276a82ab2f\scratch\test_pdf_account.py

import sys
import os

# Añadimos el path para poder importar la factory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "..", "Desktop", "FLUX", "Desarrollo", "flux-project", "backend")))

from app.modules.pdf_factory import PDFFactory

def test_generate_account_pdf():
    print("🚀 Iniciando prueba de generación de PDF para Cuenta Corriente...")
    
    # 1. Datos de prueba (Simulando el payload del nodo de formalización)
    dummy_data = {
        "nombre": "Juan Pérez Silva",
        "rut": "12.345.678-9",
        "final_category": "ADVANCE",
        "has_upgrade": True,
        "credit_line_amount": 1500000,
        "monthly_cost": 15000
    }
    
    try:
        # 2. Instanciar Factory
        factory = PDFFactory()
        
        # 3. Generar PDF
        # El tipo debe ser exactamente "CUENTA_CORRIENTE"
        path, security_hash = factory.create_pdf("CUENTA_CORRIENTE", dummy_data)
        
        print("\n✅ ¡PDF Generado con éxito!")
        print(f"📍 Ruta local: {path}")
        print(f"🛡️ Hash de seguridad: {security_hash}")
        
        # Verificar que el archivo existe
        if os.path.exists(path):
            print(f"📏 Tamaño del archivo: {os.path.getsize(path)} bytes")
        else:
            print("❌ El archivo no se encuentra en la ruta indicada.")
            
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")

if __name__ == "__main__":
    test_generate_account_pdf()

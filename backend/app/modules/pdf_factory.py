import hashlib
import json
import os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

class PDFFactory:
    def __init__(self):
        # 1. Gestión de Rutas Absolutas
        # Obtiene la ruta de 'app/modules/'
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Sube dos niveles para llegar a la raíz de 'backend' y define 'assets'
        assets_dir = os.path.abspath(os.path.join(current_dir, "..", "assets"))
        
        # Rutas específicas a archivos
        self.logo_path = os.path.join(assets_dir, "flux-logo.png")
        self.fonts_dir = os.path.join(assets_dir, "fonts")
        
        # DEBUG: Imprime estas rutas en tu consola para verificar
        print(f"DEBUG: Buscando logo en: {self.logo_path}")
        print(f"DEBUG: Buscando fuentes en: {self.fonts_dir}")

        # 2. Registro de Tipografía
        try:
            # IMPORTANTE: Revisa que los nombres de los archivos .ttf sean exactamente estos
            reg_font_path = os.path.join(self.fonts_dir, 'SpaceGrotesk-Regular.ttf')
            bold_font_path = os.path.join(self.fonts_dir, 'SpaceGrotesk-Bold.ttf')
            
            pdfmetrics.registerFont(TTFont('SpaceGrotesk', reg_font_path))
            pdfmetrics.registerFont(TTFont('SpaceGrotesk-Bold', bold_font_path))
            
            self.font_reg = "SpaceGrotesk"
            self.font_bold = "SpaceGrotesk-Bold"
            print("✅ Fuentes cargadas correctamente.")
        except Exception as e:
            print(f"❌ Error cargando fuentes: {e}")
            self.font_reg = "Helvetica"
            self.font_bold = "Helvetica-Bold"

    def _generate_sha256(self, data: dict) -> str:
        """Crea el sello de integridad del Namespace J."""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def _get_product_content(self, product_type: str, data: dict) -> dict:
        """
        CAPA DE DATOS: Define qué se muestra según el producto.
        Retorna un diccionario con 'titulo', 'resumen' (lista de tuplas) y 'legal'.
        """
        if product_type == "CREDITO_CONSUMO":
            return {
                "titulo": "Resumen de Crédito de Consumo",
                "resumen": [
                    ("Monto Aprobado", f"${data.get('monto_aprobado', 0):,} CLP"),
                    ("Plazo Solicitado", f"{data.get('plazo_aprobado', 0)} meses"),
                    ("Tasa de Interés", f"{data.get('tasa_interes_mensual', 0):.2%}"),
                    ("Costo Total (CTC)", f"${data.get('ctc', 0):,} CLP"),
                    ("Valor de Cuota", f"${data.get('cuota_mensual', 0):,} CLP")
                ],
                "legal": [
                    "• El cliente acepta los términos del crédito de consumo Flux.",
                    "• El monto será depositado tras la verificación final.",
                    "• La mora generará intereses según la tasa máxima convencional."
                ]
            }
        
        elif product_type == "CUENTA_CORRIENTE":
            return {
                "titulo": "Contrato de Apertura Cuenta Corriente",
                "resumen": [
                    ("Plan Seleccionado", data.get("plan_nombre", "Plan Flux Digital")),
                    ("Costo Mensual", "$0 (Costo Cero)"),
                    ("Línea de Crédito", f"${data.get('linea_aprobada', 0):,}")
                ],
                "legal": [
                    "• Sujeto a políticas de uso de cuenta corriente Flux.",
                    "• Incluye tarjeta de débito digital activa."
                ]
            }

        # Fallback genérico
        return {
            "titulo": "Documento de Formalización",
            "resumen": [("Dato", "Valor")],
            "legal": ["Términos generales."]
        }


    def create_pdf(self, product_type: str, data: dict):
        """
        MOTOR DE RENDERIZADO: Diseño Premium Flux.
        """
        security_hash = self._generate_sha256(data)
        content = self._get_product_content(product_type, data)

        clean_rut = data['rut'].replace('.', '').replace('-', '')
        filename = f"contrato_{product_type.lower()}_{clean_rut}.pdf"
        
        p = canvas.Canvas(filename, pagesize=LETTER)
        width, height = LETTER
        
        # --- 1. IDENTIDAD LATERAL (Azul Eléctrico) ---
        p.setFillColor(colors.HexColor("#304FFE"))
        p.rect(0, 0, 0.5 * cm, height, stroke=0, fill=1)

        # --- 2. HEADER ---
        # Logo (Platypus) - Esquina superior derecha
        if os.path.exists(self.logo_path):
            from reportlab.platypus import Image
            try:
                logo_img = Image(self.logo_path, width=3.8 * cm, height=1.8 * cm)
                logo_img.drawOn(p, width - 4.5 * cm, height - 2.5 * cm)
            except: pass

        # Título Principal
        p.setFillColor(colors.HexColor("#304FFE"))
        p.setFont(self.font_bold, 22)
        p.drawString(1.5 * cm, height - 2.2 * cm, content["titulo"].upper())
        
        # ID de Transacción (Acomodado abajo del título)
        p.setFont(self.font_reg, 8)
        p.setFillColor(colors.grey)
        p.drawString(1.5 * cm, height - 2.8 * cm, f"VERIFICACIÓN DIGITAL: {security_hash.upper()}")

        # --- 3. INFORMACIÓN DEL TITULAR ---
        y = height - 4.5 * cm
        p.setStrokeColor(colors.HexColor("#304FFE"))
        p.setLineWidth(1)
        p.line(1.5 * cm, y, width - 1.5 * cm, y) # Línea divisoria azul
        
        y -= 0.8 * cm
        p.setFillColor(colors.black)
        p.setFont(self.font_bold, 12)
        p.drawString(1.5 * cm, y, "TITULAR DEL PRODUCTO")
        
        p.setFont(self.font_reg, 11)
        p.drawString(1.5 * cm, y - 0.7 * cm, f"Nombre: {data['nombre']}")
        p.drawString(1.5 * cm, y - 1.3 * cm, f"RUT: {data['rut']}")

        # --- 4. DETALLE DEL PRODUCTO (Tabla Modernizada) ---
        y = y - 3.5 * cm
        # Fondo suave para la tabla
        p.setFillColor(colors.HexColor("#F4F7FF"))
        p.roundRect(1.5 * cm, y - (len(content['resumen']) * 0.8 + 0.6) * cm, width - 3 * cm, (len(content['resumen']) * 0.8 + 1.2) * cm, 0.3 * cm, stroke=0, fill=1)
        
        p.setFillColor(colors.HexColor("#304FFE"))
        p.setFont(self.font_bold, 11)
        p.drawString(2 * cm, y, "RESUMEN DE CONDICIONES")

        y_item = y - 1 * cm
        for label, value in content["resumen"]:
            p.setFont(self.font_reg, 10)
            p.setFillColor(colors.HexColor("#555555"))
            p.drawString(2.2 * cm, y_item, label)
            
            p.setFont(self.font_bold, 11)
            p.setFillColor(colors.black)
            p.drawRightString(width - 2.2 * cm, y_item, value)
            
            # Línea punteada sutil entre filas
            p.setDash(1, 2)
            p.setStrokeColor(colors.lightgrey)
            p.line(2.2 * cm, y_item - 0.2 * cm, width - 2.2 * cm, y_item - 0.2 * cm)
            p.setDash()
            
            y_item -= 0.8 * cm

        # --- 5. CLÁUSULAS LEGALES ---
        y_legal = y_item - 1.5 * cm
        p.setFillColor(colors.HexColor("#304FFE"))
        p.setFont(self.font_bold, 11)
        p.drawString(1.5 * cm, y_legal, "CONSIDERACIONES LEGALES")
        
        y_legal -= 0.7 * cm
        p.setFont(self.font_reg, 9)
        p.setFillColor(colors.black)
        for line in content["legal"]:
            # Viñeta naranja
            p.setFillColor(colors.HexColor("#FF6D00"))
            p.circle(1.7 * cm, y_legal + 0.1 * cm, 0.08 * cm, fill=1, stroke=0)
            
            p.setFillColor(colors.black)
            p.drawString(2 * cm, y_legal, line)
            y_legal -= 0.6 * cm

        # --- 6. FOOTER DE SEGURIDAD (Sello Naranja) ---
        p.setFillColor(colors.HexColor("#FF6D00"))
        p.rect(1.5 * cm, 1.5 * cm, width - 3 * cm, 1.2 * cm, stroke=0, fill=1)
        
        p.setFillColor(colors.white)
        p.setFont(self.font_bold, 9)
        p.drawCentredString(width / 2, 2.2 * cm, "DOCUMENTO FIRMADO ELECTRÓNICAMENTE")
        p.setFont(self.font_reg, 7)
        p.drawCentredString(width / 2, 1.8 * cm, f"HASH DE INTEGRIDAD: {security_hash}")

        p.save()
        return filename, security_hash

# --- SCRIPT DE PRUEBA (HARDCODED) ---
if __name__ == "__main__":
    factory = PDFFactory()
    mock_data = {
        "nombre": "Roberto Andrade",
        "rut": "12.345.678-9",
        "monto_aprobado": 5000000,
        "cuotas": 24,
        "tasa_mensual": 1.25
    }
    path, h = factory.create_pdf("CREDITO_CONSUMO", mock_data)
    print(f"PDF Creado: {path}")
    print(f"Hash: {h}")
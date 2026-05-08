import sys
import os

# Añadir el path del proyecto para importar el modulo
sys.path.append(os.getcwd())

from backend.app.modules.account_eng import AccountEngine, PolicyRejectionError, EngineCalculationError

def test_engine_v2():
    tests = [
        {
            "name": "Rechazo por Edad (Debe lanzar PolicyRejectionError)",
            "prep": {"edad": 17},
            "profile": {"renta": 800000, "antiguedad_laboral": 12, "nivel_estudios": "MEDIA"},
            "expect_exception": PolicyRejectionError,
            "expected_error": "ERR_EDAD"
        },
        {
            "name": "Aprobación START con Upgrade a MEDIUM (Atributos en el objeto)",
            "prep": {"edad": 30},
            "profile": {"renta": 800000, "antiguedad_laboral": 8, "nivel_estudios": "UNIVERSITARIO"},
            "expected_cat": "MEDIUM",
            "expected_upgrade": True
        },
        {
            "name": "Aprobación MEDIUM con Línea de Crédito",
            "prep": {"edad": 35},
            "profile": {"renta": 1500000, "antiguedad_laboral": 14, "nivel_estudios": "MEDIA"},
            "expected_cat": "MEDIUM",
            "expected_line": 750000
        },
        {
            "name": "Fallo por Datos Faltantes (Debe lanzar EngineCalculationError)",
            "prep": {"edad": 30},
            "profile": {"renta": 0, "antiguedad_laboral": 12, "nivel_estudios": "MEDIA"},
            "expect_exception": EngineCalculationError
        }
    ]

    print(f"{'Caso de Prueba':<65} | {'Resultado':<10}")
    print("-" * 80)

    for t in tests:
        try:
            # INSTANCIACIÓN (Como en el nodo)
            engine = AccountEngine(t["prep"], t["profile"])
            # EJECUCIÓN
            res = engine.run()
            
            if t.get("expect_exception"):
                print(f"{t['name']:<65} | FAILED (No lanzó excepción)")
                continue

            # Verificación de atributos en el objeto (Lo que necesita el nodo en el 'except')
            cat_ok = engine.final_category == t["expected_cat"]
            upgrade_ok = engine.has_upgrade == t.get("expected_upgrade", engine.has_upgrade)
            line_ok = engine.credit_line == t.get("expected_line", engine.credit_line)
            
            if cat_ok and upgrade_ok and line_ok:
                print(f"{t['name']:<65} | PASSED")
            else:
                print(f"{t['name']:<65} | FAILED (Atributos incorrectos)")

        except Exception as e:
            if t.get("expect_exception") and isinstance(e, t["expect_exception"]):
                # Verificamos si el motivo del error es el correcto para PolicyRejection
                if isinstance(e, PolicyRejectionError) and t.get("expected_error"):
                    if str(e) == t["expected_error"]:
                        print(f"{t['name']:<65} | PASSED (Lanzó {type(e).__name__})")
                    else:
                        print(f"{t['name']:<65} | FAILED (Motivo '{str(e)}' != '{t['expected_error']}')")
                else:
                    print(f"{t['name']:<65} | PASSED (Lanzó {type(e).__name__})")
            else:
                print(f"{t['name']:<65} | ERROR: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    test_engine_v2()

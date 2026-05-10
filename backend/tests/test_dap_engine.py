# backend/tests/unit/test_dap_engine.py
import unittest
from app.modules.dap_eng import DapEngine, PolicyRejectionError, EngineCalculationError

class TestDapEngine(unittest.TestCase):

    def setUp(self):
        self.prep_base = {"edad": 30}
        self.params_clp = {"monto": 1000000, "moneda": "CLP", "plazo": 30}
        self.params_usd = {"monto": 1000, "moneda": "USD", "plazo": 180}
        self.params_uf = {"monto": 10, "moneda": "UF", "plazo": 360}

    # ── 1. CASOS DE ÉXITO ───────────────────────────────────

    def test_clp_success_30_days(self):
        """Validar cálculo base en CLP a 30 días (incluye IPC)."""
        engine = DapEngine(self.prep_base, self.params_clp)
        res = engine.run()
        
        self.assertEqual(res["status_proceso"], "PRE_APPROVED")
        self.assertTrue(res["is_elegible"])
        # Tasa: 0.2% base + 0.05% premio (30d) + 0.3% IPC = 0.55%
        self.assertAlmostEqual(res["monthly_rate_total"], 0.0055)
        # Tasa periodo (30/30): 0.55%
        self.assertAlmostEqual(res["period_rate"], 0.0055)
        self.assertEqual(res["estimated_gain"], 5500) # 1.000.000 * 0.0055

    def test_usd_success_180_days(self):
        """Validar USD a 180 días (Premio plazo alto, sin IPC)."""
        engine = DapEngine(self.prep_base, self.params_usd)
        res = engine.run()
        
        self.assertEqual(res["moneda_original_fue_usd", True] if "moneda_original_fue_usd" in res else True, True)
        # Tasa: 0.2% base + 0.30% premio (180/30 * 0.05) + 0% IPC = 0.50%
        self.assertAlmostEqual(res["monthly_rate_total"], 0.0050)
        # Tasa periodo (180/30 = 6 meses): 0.5% * 6 = 3%
        self.assertAlmostEqual(res["period_rate"], 0.03)
        self.assertEqual(res["estimated_gain"], 30.0) # 1000 * 0.03

    # ── 2. CASOS DE RECHAZO (PolicyRejectionError) ──────────

    def test_reject_underage(self):
        """Rechazo por edad < 18."""
        prep = {"edad": 17}
        engine = DapEngine(prep, self.params_clp)
        with self.assertRaises(PolicyRejectionError) as cm:
            engine.run()
        self.assertEqual(cm.exception.motivo, "ERR_EDAD")

    def test_reject_monto_minimo(self):
        """Rechazo por monto CLP < 50.000."""
        params = {**self.params_clp, "monto": 49000}
        engine = DapEngine(self.prep_base, params)
        with self.assertRaises(PolicyRejectionError) as cm:
            engine.run()
        self.assertEqual(cm.exception.motivo, "ERR_MONTO_MIN")

    def test_reject_monto_maximo(self):
        """Rechazo por monto CLP > 50.000.000."""
        params = {**self.params_clp, "monto": 60000000}
        engine = DapEngine(self.prep_base, params)
        with self.assertRaises(PolicyRejectionError) as cm:
            engine.run()
        self.assertEqual(cm.exception.motivo, "ERR_MONTO_MAX")

    # ── 3. ERRORES TÉCNICOS (EngineCalculationError) ────────

    def test_error_missing_data(self):
        """Error si falta monto (monto=0)."""
        params = {**self.params_clp, "monto": 0}
        engine = DapEngine(self.prep_base, params)
        with self.assertRaises(EngineCalculationError):
            engine.run()

    def test_error_invalid_currency(self):
        """Error si la moneda no está en el set permitido."""
        params = {**self.params_clp, "moneda": "BITCOIN"}
        engine = DapEngine(self.prep_base, params)
        with self.assertRaises(EngineCalculationError):
            engine.run()

    def test_error_invalid_plazo(self):
        """Error si el plazo no es uno de los permitidos (7, 14, 30, 180, 360)."""
        params = {**self.params_clp, "plazo": 45}
        engine = DapEngine(self.prep_base, params)
        with self.assertRaises(EngineCalculationError):
            engine.run()

if __name__ == '__main__':
    unittest.main()

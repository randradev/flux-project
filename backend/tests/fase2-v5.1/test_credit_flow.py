"""
tests/unit/test_credit_flow.py
─────────────────────────────────────────────────────────────
Suite de validación v5.1 — Escritura Dual en Nodos Post-Motor

PROPÓSITO:
  Verificar que, al ejecutar cada función de nodo del flujo de crédito
  (Pasos 3–7), el estado resultante contiene las flags de progreso
  y de evento correctas (just_completed_step + progress.loan.*).

NODOS CUBIERTOS (14 tests):
  Paso 3 — loan_risk_engine_node   (2 tests)
  Paso 4 — loan_pre_approved_node  (3 tests)
  Paso 5 — loan_otp_validation_node (4 tests)
  Paso 6 — loan_formalization_node  (3 tests)
  Paso 7 — loan_completed_node      (2 tests)

INVARIANTES VERIFICADAS:
  - Escritura de just_completed_step con el Enum correcto.
  - Escritura de progress.loan.* = True cuando aplica.
  - Limpieza de just_completed_step = None en loops y caminos no-éxito.
  - Nodos terminales no escriben just_completed_step (campo ausente o None).

DEPENDENCIAS EXTERNAS SIMULADAS (sin acceso a Supabase, Gemini ni módulos):
  - _flux_generator.invoke → MagicMock
  - update_application_semaphores → patch
  - generate_otp / send_otp_email → patch
  - generate_loan_contract → patch
"""

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

# ─────────────────────────────────────────────────────────────
# FIXTURES BASE
# ─────────────────────────────────────────────────────────────

BASE_SESSION = {
    "current_node":        "LOAN_RISK_ENGINE",
    "application_id":      None,
    "progress":            {},
    "just_completed_step": None,
}

BASE_PREP = {
    "nombre": "Ana Torres",
    "mail":   "ana@test.cl",
    "rut":    "12.345.678-9",
    "edad":   30,
}

BASE_ENGINE_APPROVED = {
    "status_proceso":       "PRE_APPROVED",
    "monto_aprobado":       5_000_000,
    "plazo_aprobado":       24,
    "cuota_mensual":        250_000,
    "tasa_interes_mensual": 0.02,
    "cae":                  0.268,
    "ctc":                  6_000_000,
    "total_intereses":      1_000_000,
    "nivel_riesgo":         "MEDIO",
    "motivo_rechazo":       None,
    "monto_solicitado":     5_000_000,
    "scoring_puntos":       72,
    "capacidad_pago_valida": True,
    "cuota_maxima_permitida": 390_000,
}

BASE_ENGINE_REJECTED = {
    **BASE_ENGINE_APPROVED,
    "status_proceso": "REJECTED",
    "motivo_rechazo": "ERR_RENTA",
}

BASE_ENGINE_ERROR = {
    **BASE_ENGINE_APPROVED,
    "status_proceso": "ERROR",
}


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _get_session(result: dict) -> dict:
    """Extrae el dict session del resultado de un nodo."""
    return result.get("session", {})


def _get_just_completed(result: dict) -> str | None:
    return _get_session(result).get("just_completed_step")


def _get_loan_progress(result: dict) -> dict:
    return _get_session(result).get("progress", {}).get("loan", {})


# ─────────────────────────────────────────────────────────────
# PASO 3 — loan_risk_engine_node
# ─────────────────────────────────────────────────────────────

class TestLoanRiskEngineNode:
    """
    Verifica que loan_risk_engine_node escribe LOAN_ENGINE + progress
    cuando el motor devuelve PRE_APPROVED, y no escribe nada en REJECTED/ERROR.
    """

    def _run_engine(self, engine_result: dict) -> dict:
        """Helper: parchea CreditEngine y ejecuta el nodo."""
        with patch("app.graph.nodes.credit.update_application_semaphores"), \
             patch("app.graph.nodes.credit.CreditEngine") as mock_ce:
            mock_instance = MagicMock()
            mock_instance.evaluate.return_value = engine_result
            mock_ce.return_value = mock_instance

            from app.graph.nodes.credit import loan_risk_engine_node

            state = {
                "session":         BASE_SESSION,
                "preparation_data": BASE_PREP,
                "collecting_data": {
                    "loan_profile": {
                        "renta":             1_300_000,
                        "antiguedad_laboral": 24,
                        "nivel_estudios":    "UNIVERSITARIO",
                    },
                    "loan_sim": {
                        "monto_solicitado": 5_000_000,
                        "plazo_solicitado": 24,
                    },
                },
                "messages": [],
            }
            return loan_risk_engine_node(state)

    def test_aprobado_escribe_loan_engine_flag(self):
        """PRE_APPROVED → just_completed_step == 'LOAN_ENGINE'."""
        from app.graph.constants import CompletedStep
        result = self._run_engine(BASE_ENGINE_APPROVED)
        assert _get_just_completed(result) == CompletedStep.LOAN_ENGINE, (
            f"Esperaba LOAN_ENGINE, obtuve: {_get_just_completed(result)}"
        )

    def test_aprobado_actualiza_progress_risk_evaluated(self):
        """PRE_APPROVED → progress.loan.risk_evaluated == True."""
        result = self._run_engine(BASE_ENGINE_APPROVED)
        assert _get_loan_progress(result).get("risk_evaluated") is True

    def test_rechazado_no_escribe_flag(self):
        """REJECTED → just_completed_step permanece None (camino terminal)."""
        result = self._run_engine(BASE_ENGINE_REJECTED)
        assert _get_just_completed(result) is None

    def test_error_no_escribe_flag(self):
        """ERROR → just_completed_step permanece None (camino terminal)."""
        result = self._run_engine(BASE_ENGINE_ERROR)
        assert _get_just_completed(result) is None


# ─────────────────────────────────────────────────────────────
# PASO 4 — loan_pre_approved_node
# ─────────────────────────────────────────────────────────────

class TestLoanPreApprovedNode:
    """
    Verifica que loan_pre_approved_node:
      - Escribe LOAN_PRE_APPROVED en toda ejecución (primera y loops).
      - Escribe progress.loan.pre_approved_shown = True en la primera ejecución.
      - Limpia el flag entrante LOAN_ENGINE del motor.
    """

    def _run_pre_approved(self, offer_loan: dict = None, session_override: dict = None) -> dict:
        session = {
            **BASE_SESSION,
            "current_node":        "LOAN_RISK_ENGINE",
            "just_completed_step": "LOAN_ENGINE",  # Flag entrante del motor
            **(session_override or {}),
        }
        state = {
            "session":          session,
            "preparation_data": BASE_PREP,
            "evaluation_results": {"loan_engine": BASE_ENGINE_APPROVED},
            "offer_data":       {"loan": offer_loan or {}},
            "messages":         [],
        }
        with patch("app.graph.nodes.credit._flux_generator") as mock_gen, \
             patch("app.graph.nodes.credit.update_application_semaphores"):
            mock_gen.invoke.return_value = MagicMock(content="¡Pre-aprobado, Ana!")
            from app.graph.nodes.credit import loan_pre_approved_node
            return loan_pre_approved_node(state)

    def test_primera_ejecucion_escribe_loan_pre_approved_flag(self):
        """Primera ejecución → just_completed_step == 'LOAN_PRE_APPROVED'."""
        from app.graph.constants import CompletedStep
        result = self._run_pre_approved(offer_loan={})
        assert _get_just_completed(result) == CompletedStep.LOAN_PRE_APPROVED

    def test_primera_ejecucion_escribe_progress_pre_approved_shown(self):
        """Primera ejecución → progress.loan.pre_approved_shown == True."""
        result = self._run_pre_approved(offer_loan={})
        assert _get_loan_progress(result).get("pre_approved_shown") is True

    def test_loop_mantiene_loan_pre_approved_flag(self):
        """
        Ejecución en loop (tarjeta ya mostrada) → still LOAN_PRE_APPROVED.
        Necesario para que P1 pueda recuperar la sesión si el usuario se desconecta.
        """
        from app.graph.constants import CompletedStep
        # Simular que la tarjeta ya fue mostrada (display_data presente)
        offer_loan_con_display = {
            "display_data": {"monto_aprobado": 5_000_000},
        }
        result = self._run_pre_approved(offer_loan=offer_loan_con_display)
        assert _get_just_completed(result) == CompletedStep.LOAN_PRE_APPROVED

    def test_flag_entrante_limpiado_correctamente(self):
        """
        El flag LOAN_ENGINE entrante del motor NO debe persistir en el return.
        El nodo lo consume y emite su propio flag LOAN_PRE_APPROVED.
        """
        result = self._run_pre_approved(offer_loan={})
        # El flag resultante NO debe ser LOAN_ENGINE
        assert _get_just_completed(result) != "LOAN_ENGINE"
        assert _get_just_completed(result) != "LOAN_RISK_EVALUATED"

    def test_no_setea_pre_approval_status(self):
        """NUNCA setea pre_approval_status (eso es rol del frontend)."""
        result = self._run_pre_approved(offer_loan={})
        loan_offer = result.get("offer_data", {}).get("loan", {})
        assert "pre_approval_status" not in loan_offer


# ─────────────────────────────────────────────────────────────
# PASO 5 — loan_otp_validation_node
# ─────────────────────────────────────────────────────────────

class TestLoanOtpValidationNode:
    """
    Verifica que loan_otp_validation_node:
      - Limpia just_completed_step = None en loops y bloqueo.
      - Escribe LOAN_OTP + progress.otp_verified en éxito.
      - NUNCA extrae el OTP del chat.
    """

    BASE_SESSION_OTP = {
        **BASE_SESSION,
        "current_node":        "LOAN_PRE_APPROVED",
        "just_completed_step": "LOAN_PRE_APPROVED",  # Flag entrante
    }

    def _run_otp(self, auth: dict, messages: list = None) -> dict:
        state = {
            "session":          self.BASE_SESSION_OTP,
            "preparation_data": BASE_PREP,
            "auth_control":     auth,
            "messages":         messages or [],
        }
        with patch("app.graph.nodes.credit._flux_generator") as mock_gen, \
             patch("app.graph.nodes.credit.update_application_semaphores"), \
             patch("app.graph.nodes.credit.generate_otp", return_value="654321"), \
             patch("app.graph.nodes.credit.send_otp_email", return_value=True):
            mock_gen.invoke.return_value = MagicMock(content="Código enviado.")
            from app.graph.nodes.credit import loan_otp_validation_node
            return loan_otp_validation_node(state)

    def test_otp_exitoso_escribe_loan_otp_flag(self):
        """OTP verificado → just_completed_step == 'LOAN_OTP'."""
        from app.graph.constants import CompletedStep
        result = self._run_otp(auth={
            "otp_generated":  "123456",
            "otp_user_input": "123456",
        })
        assert _get_just_completed(result) == CompletedStep.LOAN_OTP

    def test_otp_exitoso_escribe_progress_otp_verified(self):
        """OTP verificado → progress.loan.otp_verified == True."""
        result = self._run_otp(auth={
            "otp_generated":  "123456",
            "otp_user_input": "123456",
        })
        assert _get_loan_progress(result).get("otp_verified") is True

    def test_otp_fallido_limpia_flag(self):
        """Código incorrecto → just_completed_step == None (loop)."""
        result = self._run_otp(auth={
            "otp_generated":  "123456",
            "otp_user_input": "999999",
            "otp_attempts":   1,
        })
        assert _get_just_completed(result) is None

    def test_otp_init_limpia_flag_entrante(self):
        """Primera ejecución (init) → just_completed_step == None."""
        result = self._run_otp(auth={})  # otp_generated vacío = init
        assert _get_just_completed(result) is None

    def test_security_blocked_limpia_flag(self):
        """Bloqueo de seguridad → just_completed_step == None."""
        result = self._run_otp(auth={
            "otp_generated":    "123456",
            "otp_user_input":   "000000",
            "security_blocked": True,
            "otp_attempts":     3,
        })
        assert _get_just_completed(result) is None

    def test_nunca_extrae_otp_del_chat(self):
        """
        INVARIANTE DETERMINISTA: El nodo NUNCA válida un OTP enviado por texto en el chat.
        Aunque el usuario escriba el código correcto, otp_user_input NO debe derivarse
        del mensaje de chat.
        """
        # El usuario escribe el OTP correcto en el chat, pero auth_control NO tiene otp_user_input
        result = self._run_otp(
            auth={
                "otp_generated": "123456",
                # otp_user_input NO está en auth_control
            },
            messages=[HumanMessage(content="123456")],
        )
        # just_completed_step NO debe ser LOAN_OTP (porque no fue validado por el backend)
        assert _get_just_completed(result) != "LOAN_OTP"
        # El nodo tampoco debe haber escrito otp_user_input derivado del chat
        assert result.get("auth_control", {}).get("otp_user_input") is None


# ─────────────────────────────────────────────────────────────
# PASO 6 — loan_formalization_node
# ─────────────────────────────────────────────────────────────

class TestLoanFormalizationNode:
    """
    Verifica que loan_formalization_node:
      - Escribe LOAN_FORMALIZATION en toda ejecución (primera y loops).
      - Escribe progress.loan.contract_generated = True solo en la primera ejecución.
      - NUNCA interpreta el chat como firma.
    """

    BASE_SESSION_FORM = {
        **BASE_SESSION,
        "current_node":        "LOAN_OTP_VALIDATION",
        "just_completed_step": "LOAN_OTP",  # Flag entrante tras éxito OTP
    }

    def _run_formalization(self, offer_loan: dict = None) -> dict:
        state = {
            "session":            self.BASE_SESSION_FORM,
            "preparation_data":   BASE_PREP,
            "evaluation_results": {"loan_engine": BASE_ENGINE_APPROVED},
            "offer_data":         {"loan": offer_loan or {}},
            "messages":           [],
        }
        with patch("app.graph.nodes.credit._flux_generator") as mock_gen, \
             patch("app.graph.nodes.credit.update_application_semaphores"), \
             patch("app.graph.nodes.credit.generate_loan_contract",
                   return_value=("/contracts/test.pdf", "abc123sha256")):
            mock_gen.invoke.return_value = MagicMock(content="Contrato listo.")
            from app.graph.nodes.credit import loan_formalization_node
            return loan_formalization_node(state)

    def test_primera_ejecucion_escribe_loan_formalization_flag(self):
        """Primera ejecución (sin contrato) → just_completed_step == 'LOAN_FORMALIZATION'."""
        from app.graph.constants import CompletedStep
        result = self._run_formalization(offer_loan={})
        assert _get_just_completed(result) == CompletedStep.LOAN_FORMALIZATION

    def test_primera_ejecucion_escribe_progress_contract_generated(self):
        """Primera ejecución → progress.loan.contract_generated == True."""
        result = self._run_formalization(offer_loan={})
        assert _get_loan_progress(result).get("contract_generated") is True

    def test_loop_mantiene_formalization_flag(self):
        """
        Loop (contrato ya existe, esperando firma) → sigue siendo LOAN_FORMALIZATION.
        Permite que P1 recupere la sesión si el usuario se desconecta antes de firmar.
        """
        from app.graph.constants import CompletedStep
        offer_con_contrato = {
            "file_contrato_path": "/contracts/existing.pdf",
            "hash_sha256": "sha256existente",
        }
        result = self._run_formalization(offer_loan=offer_con_contrato)
        assert _get_just_completed(result) == CompletedStep.LOAN_FORMALIZATION

    def test_loop_no_sobreescribe_progress(self):
        """Loop (contrato ya existe) → progress.loan NO agrega contract_generated de nuevo."""
        # En loop el progress vendrá del session base que tiene {} por defecto.
        # Verificamos que contract_generated no está en el resultado cuando ya hay contrato.
        offer_con_contrato = {
            "file_contrato_path": "/contracts/existing.pdf",
            "hash_sha256": "sha256existente",
        }
        result = self._run_formalization(offer_loan=offer_con_contrato)
        # En loop, progress NO debe ser modificado (el campo "progress" no debe existir en session
        # o si existe debe ser el mismo vacío del BASE_SESSION)
        loan_prog = _get_loan_progress(result)
        assert loan_prog.get("contract_generated") is not True

    def test_no_acepta_texto_como_firma(self):
        """
        INVARIANTE DETERMINISTA: el chat NUNCA activa contract_status.
        Un mensaje de aceptación verbal no equivale a firma digital.
        """
        state = {
            "session":            self.BASE_SESSION_FORM,
            "preparation_data":   BASE_PREP,
            "evaluation_results": {"loan_engine": BASE_ENGINE_APPROVED},
            "offer_data":         {"loan": {"file_contrato_path": "/c.pdf"}},
            "messages":           [HumanMessage(content="Sí acepto todo el contrato")],
        }
        with patch("app.graph.nodes.credit._flux_generator") as mock_gen, \
             patch("app.graph.nodes.credit.update_application_semaphores"), \
             patch("app.graph.nodes.credit.generate_loan_contract",
                   return_value=("/c.pdf", "hash")):
            mock_gen.invoke.return_value = MagicMock(content="Perfecto, revisa el contrato.")
            from app.graph.nodes.credit import loan_formalization_node
            result = loan_formalization_node(state)

        contract_status = result.get("offer_data", {}).get("loan", {}).get("contract_status")
        assert contract_status is None, (
            "contract_status NO debe setearse desde el chat. "
            f"Valor obtenido: {contract_status}"
        )


# ─────────────────────────────────────────────────────────────
# PASO 7 — loan_completed_node
# ─────────────────────────────────────────────────────────────

class TestLoanCompletedNode:
    """
    Verifica que loan_completed_node:
      - Escribe flow_result.status_code == "SUCCESS".
      - Construye display_data con download_url correcta.
      - No escribe just_completed_step (es nodo terminal).
    """

    def _run_completed(self) -> dict:
        session = {
            **BASE_SESSION,
            "current_node":        "LOAN_FORMALIZATION",
            "just_completed_step": "LOAN_FORMALIZATION",
        }
        state = {
            "session":            session,
            "preparation_data":   BASE_PREP,
            "evaluation_results": {"loan_engine": BASE_ENGINE_APPROVED},
            "offer_data": {
                "loan": {
                    "file_contrato_path": "/contracts/final.pdf",
                    "hash_sha256":        "sha256final",
                    "contract_status":    "SIGNED_AND_STAMPED",
                },
            },
            "messages": [],
        }
        with patch("app.graph.nodes.credit._flux_generator") as mock_gen, \
             patch("app.graph.nodes.credit.update_application_semaphores"):
            mock_gen.invoke.return_value = MagicMock(content="¡Felicitaciones!")
            from app.graph.nodes.credit import loan_completed_node
            return loan_completed_node(state)

    def test_escribe_flow_result_success(self):
        """loan_completed_node → flow_result.status_code == 'SUCCESS'."""
        result = self._run_completed()
        assert result["flow_result"]["status_code"] == "SUCCESS"

    def test_escribe_display_data_con_download_url(self):
        """loan_completed_node → offer_data.loan.display_data.download_url correcto."""
        result = self._run_completed()
        display = result.get("offer_data", {}).get("loan", {}).get("display_data", {})
        assert display.get("download_url") == "/contracts/final.pdf"

    def test_no_escribe_just_completed_step(self):
        """
        Nodo terminal → just_completed_step NO debe ser seteado a un nuevo valor.
        (El State del nodo terminal no necesita saltar a ningún lado.)
        """
        result = self._run_completed()
        # El nodo puede no incluir just_completed_step en su return, o dejarlo como None.
        # Lo importante es que no propague un flag de hito intermedio.
        jcs = _get_just_completed(result)
        assert jcs != "LOAN_FORMALIZATION", (
            "El nodo terminal no debe propagar el flag entrante LOAN_FORMALIZATION."
        )


# ─────────────────────────────────────────────────────────────
# TESTS DE INTEGRACIÓN SEMÁNTICA — _SUCCESS_MAP
# ─────────────────────────────────────────────────────────────

class TestSuccessMapCobertura:
    """
    Verifica que _SUCCESS_MAP["LOAN"] cubre todos los hitos del flujo
    y que los enums existen en CompletedStep.
    """

    def test_todos_los_enums_v51_existen_en_completed_step(self):
        """Los 4 nuevos enums v5.1 deben existir en CompletedStep."""
        from app.graph.constants import CompletedStep

        assert hasattr(CompletedStep, "LOAN_ENGINE"),        "Falta LOAN_ENGINE"
        assert hasattr(CompletedStep, "LOAN_PRE_APPROVED"),  "Falta LOAN_PRE_APPROVED"
        assert hasattr(CompletedStep, "LOAN_OTP"),           "Falta LOAN_OTP"
        assert hasattr(CompletedStep, "LOAN_FORMALIZATION"), "Falta LOAN_FORMALIZATION"

    def test_loan_engine_tiene_valor_correcto(self):
        from app.graph.constants import CompletedStep
        assert CompletedStep.LOAN_ENGINE == "LOAN_ENGINE"

    def test_loan_pre_approved_tiene_valor_correcto(self):
        from app.graph.constants import CompletedStep
        assert CompletedStep.LOAN_PRE_APPROVED == "LOAN_PRE_APPROVED"

    def test_loan_otp_tiene_valor_correcto(self):
        from app.graph.constants import CompletedStep
        assert CompletedStep.LOAN_OTP == "LOAN_OTP"

    def test_loan_formalization_tiene_valor_correcto(self):
        from app.graph.constants import CompletedStep
        assert CompletedStep.LOAN_FORMALIZATION == "LOAN_FORMALIZATION"

    def test_success_map_loan_cubre_todos_los_hitos_v51(self):
        """
        _SUCCESS_MAP["LOAN"] debe incluir los 4 hitos nuevos de v5.1.
        Este test requiere que edges.py esté actualizado con las entradas nuevas.
        """
        from app.graph.constants import CompletedStep
        # Importar el mapa directamente del módulo de edges
        from app.graph import edges
        success_map_loan = edges._SUCCESS_MAP.get("LOAN", {})

        assert CompletedStep.LOAN_ENGINE       in success_map_loan, "LOAN_ENGINE ausente en _SUCCESS_MAP"
        assert CompletedStep.LOAN_PRE_APPROVED in success_map_loan, "LOAN_PRE_APPROVED ausente en _SUCCESS_MAP"
        assert CompletedStep.LOAN_OTP          in success_map_loan, "LOAN_OTP ausente en _SUCCESS_MAP"
        assert CompletedStep.LOAN_FORMALIZATION in success_map_loan, "LOAN_FORMALIZATION ausente en _SUCCESS_MAP"

    def test_success_map_loan_engine_apunta_a_pre_approved(self):
        from app.graph.constants import CompletedStep
        from app.graph import edges
        assert edges._SUCCESS_MAP["LOAN"][CompletedStep.LOAN_ENGINE] == "loan_pre_approved"

    def test_success_map_loan_otp_apunta_a_formalization(self):
        from app.graph.constants import CompletedStep
        from app.graph import edges
        assert edges._SUCCESS_MAP["LOAN"][CompletedStep.LOAN_OTP] == "loan_formalization"

    def test_success_map_loan_formalization_apunta_a_formalization(self):
        """Un usuario desconectado durante la firma vuelve a loan_formalization."""
        from app.graph.constants import CompletedStep
        from app.graph import edges
        assert edges._SUCCESS_MAP["LOAN"][CompletedStep.LOAN_FORMALIZATION] == "loan_formalization"

    def test_compat_regresiva_loan_risk_evaluated_sigue_mapeando(self):
        """
        COMPAT. REGRESIVA: LOAN_RISK_EVALUATED (v5.0) debe seguir mapeando
        a loan_pre_approved para no romper sesiones existentes en producción.
        """
        from app.graph.constants import CompletedStep
        from app.graph import edges
        # LOAN_RISK_EVALUATED debe seguir en el mapa
        assert CompletedStep.LOAN_RISK_EVALUATED in edges._SUCCESS_MAP["LOAN"], (
            "LOAN_RISK_EVALUATED debe mantenerse en _SUCCESS_MAP para compatibilidad regresiva."
        )
        assert edges._SUCCESS_MAP["LOAN"][CompletedStep.LOAN_RISK_EVALUATED] == "loan_pre_approved"
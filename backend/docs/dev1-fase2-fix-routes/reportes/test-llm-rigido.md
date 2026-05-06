════════════════════════════════════════════════════════════
  🎮 MODO PRUEBA MANUAL INTERACTIVA
════════════════════════════════════════════════════════════

[Sistema] Iniciando flujo con intención de crédito (Botón LOAN)...

────────────────────────────────────────────────────────────
TURNO 1
👤 Usuario: (sin mensaje — turno de inicio)

📊 State Diff:
  + evaluation_results: None → {}
  + collecting_data: None → {'loan_profile': {}, 'loan_sim': {}}
  + auth_control: None → {}
  + session: None → {'conversation_id': 'conv-test-001', 'application_id': None, 'product_intent': 'LOAN', 'current_node': 'LOAN_COLLECTING_PROFILE', 'previous_node': None, 'is_transversal_active': False}
  + user_data: None → {'user_id': 'test-user-001', 'full_name': 'Juan Pérez López', 'email': 'juan.perez@test.cl', 'rut': '12345678-9', 'birth_date': '1990-05-15', 'user_status': 'ACTIVE', 'user_category': None}
  + offer_data: None → {}
  + preparation_data: None → {'nombre': 'Juan Pérez López', 'rut': '12345678-9', 'mail': 'juan.perez@test.cl', 'edad': 35}     
  + flow_result: None → {}

🤖 Flux: ¡Qué buena, Juan! Te ayudaré a sacar adelante ese crédito de consumo para tus planes, así que para empezar, cuéntame ¿cuál es tu renta líquida mensual?

[Tú]: Excelente! gano 2 millones mensuales

────────────────────────────────────────────────────────────
TURNO 2
👤 Usuario: Excelente! gano 2 millones mensuales

[DEBUG-PROFILE] Mensaje Usuario: 'Excelente! gano 2 millones mensuales'
[DEBUG-PROFILE] LLM razonamiento: El usuario indica una renta de 2 millones. No se menciona antigüedad laboral ni nivel de estudios.
[DEBUG-PROFILE] LLM extraccion: renta=2000000, antiguedad=None, estudios=None

📊 State Diff:
  + collecting_data.loan_profile.renta: None → 2000000

👤 User: Excelente! gano 2 millones mensuales

🤖 Flux: ¡Buenazo, Juan! Con esos 2 millones mensuales estamos súper bien encaminados para tu crédito. ¿Hace cuánto tiempo que 
trabajas en tu empresa actual?

[Tú]: Súper! Trabajo en Microsoft hace 3 años

────────────────────────────────────────────────────────────
TURNO 3
👤 Usuario: Súper! Trabajo en Microsoft hace 3 años

[DEBUG-PROFILE] Mensaje Usuario: 'Súper! Trabajo en Microsoft hace 3 años'
[DEBUG-PROFILE] LLM razonamiento: Error
[DEBUG-PROFILE] LLM extraccion: renta=None, antiguedad=None, estudios=DESCONOCIDO

📊 State Diff:

👤 User: Súper! Trabajo en Microsoft hace 3 años

🤖 Flux: ¡Buenazo que trabajes en Microsoft, Juan! Pucha, mi sistema se mareó un poquito y no alcanzó a captar bien el tiempo que llevas ahí. ¿Me podrías repetir hace cuánto tiempo trabajas en ese lugar?

[Tú]: hace 3 años

────────────────────────────────────────────────────────────
TURNO 4
👤 Usuario: hace 3 años

[DEBUG-PROFILE] Mensaje Usuario: 'hace 3 años'
[DEBUG-PROFILE] LLM razonamiento: Error
[DEBUG-PROFILE] LLM extraccion: renta=None, antiguedad=None, estudios=DESCONOCIDO

📊 State Diff:

👤 User: hace 3 años

🤖 Flux: ¡Buenazo, Juan! Mi sistema se mareó un poquito con la respuesta, pero entiendo que llevas 3 años en tu pega actual. ¿Me confirmas si esa es efectivamente tu antigüedad laboral para seguir?

[Tú]: Sí, esa es mi antigüedad laboral, 3 años

────────────────────────────────────────────────────────────
TURNO 5
👤 Usuario: Sí, esa es mi antigüedad laboral, 3 años

[DEBUG-PROFILE] Mensaje Usuario: 'Sí, esa es mi antigüedad laboral, 3 años'
[DEBUG-PROFILE] LLM razonamiento: El usuario indica una antigüedad laboral de 3 años, lo que equivale a 36 meses. No se menciona renta ni nivel de estudios.
[DEBUG-PROFILE] LLM extraccion: renta=None, antiguedad=36, estudios=None

📊 State Diff:
  + collecting_data.loan_profile.antiguedad_laboral: None → 36

👤 User: Sí, esa es mi antigüedad laboral, 3 años

🤖 Flux: ¡Buenazo, Juan! Esos 3 años de antigüedad laboral están súper bien anotados para tu perfil. Ahora, para seguir avanzando con la evaluación, ¿cuál es tu nivel de estudios?

[Tú]: Soy titulado de Ingeniería Civil Informática

────────────────────────────────────────────────────────────
TURNO 6
👤 Usuario: Soy titulado de Ingeniería Civil Informática

[DEBUG-PROFILE] Mensaje Usuario: 'Soy titulado de Ingeniería Civil Informática'
[DEBUG-PROFILE] LLM razonamiento: Error
[DEBUG-PROFILE] LLM extraccion: renta=None, antiguedad=None, estudios=DESCONOCIDO

📊 State Diff:

👤 User: Soy titulado de Ingeniería Civil Informática

🤖 Flux: ¡Buenísimo ese título, Juan! Pucha, mi sistema se mareó un poco y no captó bien el dato. ¿Me podrías confirmar cuál es tu nivel de estudios para avanzar?

[Tú]: Soy Ingeniero Civil Informático

────────────────────────────────────────────────────────────
TURNO 7
👤 Usuario: Soy Ingeniero Civil Informático

[DEBUG-PROFILE] Mensaje Usuario: 'Soy Ingeniero Civil Informático'
[DEBUG-PROFILE] LLM razonamiento: Error
[DEBUG-PROFILE] LLM extraccion: renta=None, antiguedad=None, estudios=DESCONOCIDO

📊 State Diff:

👤 User: Soy Ingeniero Civil Informático

🤖 Flux: ¡Buenísima carrera, Juan! Pucha, mi sistema se mareó un poco y no alcanzó a anotar bien el nivel. ¿Ese título es de nivel universitario completo o técnico profesional?

[Tú]: Es de nivel universitario completo

────────────────────────────────────────────────────────────
TURNO 8
👤 Usuario: Es de nivel universitario completo

[DEBUG-PROFILE] Mensaje Usuario: 'Es de nivel universitario completo'
[DEBUG-PROFILE] LLM razonamiento: Error
[DEBUG-PROFILE] LLM extraccion: renta=None, antiguedad=None, estudios=DESCONOCIDO

📊 State Diff:

👤 User: Es de nivel universitario completo

🤖 Flux: ¡Pucha Juan, te escuché clarito lo de los estudios, pero mi sistema se mareó un poco y no alcanzó a guardarlo! ¿Me podrías repetir cuál es tu nivel de educación para dejarlo registrado? ¡Ya nos falta casi nada para terminar!

[Tú]: Universitario

────────────────────────────────────────────────────────────
TURNO 9
👤 Usuario: Universitario

[DEBUG-PROFILE] Mensaje Usuario: 'Universitario'
[DEBUG-PROFILE] LLM razonamiento: El usuario indica su nivel de estudios como 'Universitario'. No se menciona renta ni antigüedad laboral, por lo que se asigna 0 según la regla de oro.
[DEBUG-PROFILE] LLM extraccion: renta=None, antiguedad=None, estudios=UNIVERSITARIO

📊 State Diff:
  + collecting_data.loan_profile.nivel_estudios: None → UNIVERSITARIO
  + session.progress: None → {'loan': {'profile_completed': True}}
  ~ session.current_node: LOAN_COLLECTING_PROFILE → LOAN_COLLECTING_SIMULATION

👤 User: Universitario

🤖 Flux: ¡Buenazo, Juan! Ya tenemos tu perfil completo para buscar las mejores opciones. ¿Cuánta plata necesitas pedir para tu 
crédito?

[Tú]: Necesito 5 millones para pagar un magíster que quiero hacer

────────────────────────────────────────────────────────────
TURNO 10
👤 Usuario: Necesito 5 millones para pagar un magíster que quiero hacer

📊 State Diff:
  + collecting_data.loan_sim.monto_solicitado: None → 5000000

👤 User: Necesito 5 millones para pagar un magíster que quiero hacer

🤖 Flux: ¡Buenazo Juan, ya anoté los 5 millones para ese magíster! Ahora cuéntame, ¿en cuántas cuotas mensuales te gustaría pagarlo?

[Tú]: Puede ser en 12 cuotas?

────────────────────────────────────────────────────────────
TURNO 11
👤 Usuario: Puede ser en 12 cuotas?

📊 State Diff:

👤 User: Puede ser en 12 cuotas?

🤖 Flux: ¡Buenazo!, te escuché clarito lo de las 12 cuotas, pero mi sistema se mareó un poco al anotarlas. ¿Me confirmas si ese es el plazo definitivo que prefieres para pagar tu crédito? ¡Quedo atento para seguir!

[Tú]: Lo necesito pagar a 12 meses

────────────────────────────────────────────────────────────
TURNO 12
👤 Usuario: Lo necesito pagar a 12 meses

📊 State Diff:
  + evaluation_results.loan_engine: None → {'status_proceso': 'PRE_APPROVED', 'scoring_puntos': 80, 'nivel_riesgo': 'Medio', 'tasa_interes_mensual': 0.02, 'cuota_mensual': 472798, 'cuota_maxima_permitida': 600000, 'capacidad_pago_valida': True, 'ctc': 5673576, 'total_intereses': 673576, 'cae': 0.268242, 'monto_aprobado': 5000000, 'plazo_aprobado': 12, 'motivo_rechazo': None}    
  + collecting_data.loan_sim.plazo_solicitado: None → 12
  + session.progress.loan.simulation_completed: None → True
  ~ session.current_node: LOAN_COLLECTING_SIMULATION → LOAN_RISK_ENGINE
  + session.just_completed_step: None → LOAN_SIMULATION

👤 User: Lo necesito pagar a 12 meses
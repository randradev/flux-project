export const PRODUCT_INTENT_LABELS = {
  LOAN: 'Credito de Consumo',
  ACCOUNT: 'Cuenta Corriente',
  DAP: 'Deposito a Plazo',
  GENERAL: 'Consulta General'
};

export const PRODUCT_ICONS = {
  LOAN: 'CR',
  ACCOUNT: 'CC',
  DAP: 'DP',
  GENERAL: 'FL'
};

export const NODE_ALIASES = {
  welcome: 'WELCOME_NODE',
  intent_router: 'INTENT_ROUTER',
  loan_entry: 'LOAN_ENTRY_STUB',
  account_entry: 'ACCOUNT_ENTRY_STUB',
  dap_entry: 'DAP_ENTRY_STUB',
  general_response: 'GENERAL_RESPONSE',
  loan_init: 'LOAN_INIT',
  loan_collecting_profile: 'LOAN_COLLECTING_PROFILE',
  loan_collecting_simulation: 'LOAN_COLLECTING_SIMULATION',
  loan_risk_engine: 'LOAN_RISK_ENGINE',
  loan_pre_approved: 'LOAN_PRE_APPROVED',
  loan_otp_validation: 'LOAN_OTP_VALIDATION',
  loan_formalization: 'LOAN_FORMALIZATION',
  loan_completed: 'LOAN_COMPLETED',
  loan_rejected_policy: 'LOAN_REJECTED_POLICY',
  loan_security_block: 'LOAN_SECURITY_BLOCK',
  loan_closed_by_user: 'LOAN_CLOSED_BY_USER'
};

export const NODE_DETAILS = {
  WELCOME_NODE: {
    label: 'Recepcion',
    description: 'El backend saluda o retoma la conversacion.'
  },
  INTENT_ROUTER: {
    label: 'Clasificacion',
    description: 'LangGraph detecta el producto y decide el flujo.'
  },
  LOAN_ENTRY_STUB: {
    label: 'Stub de credito',
    description: 'Fase 1: el backend confirma credito, aun sin motor financiero.'
  },
  ACCOUNT_ENTRY_STUB: {
    label: 'Stub de cuenta',
    description: 'Fase 1: el backend confirma cuenta corriente, aun sin segmentacion.'
  },
  DAP_ENTRY_STUB: {
    label: 'Stub de DAP',
    description: 'Fase 1: el backend confirma deposito a plazo, aun sin calculo real.'
  },
  GENERAL_RESPONSE: {
    label: 'Respuesta general',
    description: 'El backend respondio fuera de un flujo especifico.'
  },
  LOAN_INIT: {
    label: 'Inicio credito',
    description: 'FLUX abre la solicitud de Credito de Consumo y prepara el perfil.'
  },
  LOAN_COLLECTING_PROFILE: {
    label: 'Perfil financiero',
    description: 'Se recopila renta, antiguedad laboral y nivel de estudios.'
  },
  LOAN_COLLECTING_SIMULATION: {
    label: 'Simulacion',
    description: 'Se define monto solicitado y plazo del credito.'
  },
  LOAN_RISK_ENGINE: {
    label: 'Motor de riesgo',
    description: 'El backend evalua scoring, tasa, cuota, CAE y capacidad de pago.'
  },
  LOAN_PRE_APPROVED: {
    label: 'Oferta transparente',
    description: 'El usuario revisa las condiciones y decide si acepta continuar.'
  },
  LOAN_OTP_VALIDATION: {
    label: 'Validacion OTP',
    description: 'FLUX confirma identidad mediante codigo de 6 digitos.'
  },
  LOAN_FORMALIZATION: {
    label: 'Formalizacion',
    description: 'El backend prepara el contrato y sello de integridad.'
  },
  LOAN_COMPLETED: {
    label: 'Credito completado',
    description: 'La solicitud fue finalizada correctamente.'
  },
  LOAN_REJECTED_POLICY: {
    label: 'Solicitud rechazada',
    description: 'La evaluacion no cumple una politica financiera.'
  },
  LOAN_SECURITY_BLOCK: {
    label: 'Bloqueo de seguridad',
    description: 'La solicitud fue bloqueada por intentos OTP fallidos.'
  },
  LOAN_CLOSED_BY_USER: {
    label: 'Cierre voluntario',
    description: 'El usuario decidio no continuar con la oferta.'
  }
};

export const PHASE_ONE_STEPS = [
  {
    id: 'WELCOME_NODE',
    label: 'Bienvenida',
    description: 'Inicio o reanudacion del hilo.'
  },
  {
    id: 'INTENT_ROUTER',
    label: 'Router',
    description: 'Clasificacion de la intencion del usuario.'
  },
  {
    id: 'FLOW_RESULT',
    label: 'Flujo activo',
    description: 'Entrada al stub del producto o respuesta general.'
  }
];

export const PRODUCT_STEPS = {
  GENERAL: PHASE_ONE_STEPS,
    LOAN: [
    {
      id: 'LOAN_INIT',
      label: 'Inicio',
      description: 'Creacion de la solicitud.',
      hidden: true
    },
    {
      id: 'LOAN_COLLECTING_PROFILE',
      label: 'Perfil',
      description: 'Renta, antiguedad y estudios.'
    },
    {
      id: 'LOAN_COLLECTING_SIMULATION',
      label: 'Simulacion',
      description: 'Monto y plazo.'
    },
    {
      id: 'LOAN_RISK_ENGINE',
      label: 'Evaluacion',
      description: 'Scoring, tasa y cuota.'
    },
    {
      id: 'LOAN_PRE_APPROVED',
      label: 'Oferta',
      description: 'Revision y decision.'
    },
    {
      id: 'LOAN_OTP_VALIDATION',
      label: 'OTP',
      description: 'Validacion de identidad.'
    },
    {
      id: 'LOAN_FORMALIZATION',
      label: 'Contrato',
      description: 'Formalizacion digital.'
    },
    {
      id: 'LOAN_COMPLETED',
      label: 'Completado',
      description: 'Cierre exitoso.',
      terminal: true
    },
    {
      id: 'LOAN_REJECTED_POLICY',
      label: 'Rechazo',
      description: 'Cierre por politica.',
      hidden: true,
      terminal: true
    },
    {
      id: 'LOAN_SECURITY_BLOCK',
      label: 'Bloqueo',
      description: 'Cierre por seguridad.',
      hidden: true,
      terminal: true
    },
    {
      id: 'LOAN_CLOSED_BY_USER',
      label: 'Cerrado',
      description: 'Cierre voluntario.',
      hidden: true,
      terminal: true
    }
  ]

};

const FINAL_NODE_IDS = new Set([
  'LOAN_ENTRY_STUB',
  'ACCOUNT_ENTRY_STUB',
  'DAP_ENTRY_STUB',
  'GENERAL_RESPONSE'
]);

const LOAN_TERMINAL_NODES = new Set([
  'LOAN_COMPLETED',
  'LOAN_REJECTED_POLICY',
  'LOAN_SECURITY_BLOCK',
  'LOAN_CLOSED_BY_USER'
]);

export function normalizeNodeId(nodeId) {
  if (!nodeId) {
    return null;
  }

  return NODE_ALIASES[nodeId] ?? NODE_ALIASES[String(nodeId).toLowerCase()] ?? nodeId;
}

export function getNodeMeta(nodeId) {
  const normalizedNodeId = normalizeNodeId(nodeId);

  if (!normalizedNodeId) {
    return {
      label: 'Sin nodo recibido',
      description: 'Aun no se recibe estado del backend para esta conversacion.'
    };
  }

  return (
    NODE_DETAILS[normalizedNodeId] ?? {
      label: normalizedNodeId,
      description: 'Nodo no mapeado en el frontend.'
    }
  );
}

export function getProductLabel(productIntent, fallbackName = '') {
  if (fallbackName) {
    return fallbackName;
  }

  return PRODUCT_INTENT_LABELS[productIntent] ?? 'Conversacion FLUX';
}

export function getProductIcon(productIntent, productName = '') {
  if (productIntent && PRODUCT_ICONS[productIntent]) {
    return PRODUCT_ICONS[productIntent];
  }

  const normalized = productName.toLowerCase();

  if (normalized.includes('credito')) {
    return PRODUCT_ICONS.LOAN;
  }

  if (normalized.includes('cuenta')) {
    return PRODUCT_ICONS.ACCOUNT;
  }

  if (normalized.includes('plazo') || normalized.includes('dap')) {
    return PRODUCT_ICONS.DAP;
  }

  return PRODUCT_ICONS.GENERAL;
}

export function getProductFromNode(nodeId, fallbackProduct = null) {
  const normalizedNodeId = normalizeNodeId(nodeId);

  if (normalizedNodeId?.startsWith('LOAN_')) {
    return 'LOAN';
  }

  if (normalizedNodeId?.startsWith('ACCOUNT_')) {
    return 'ACCOUNT';
  }

  if (normalizedNodeId?.startsWith('DAP_')) {
    return 'DAP';
  }

  return fallbackProduct ?? 'GENERAL';
}

export function getStepsForConversation(conversation) {
  const product = getProductFromNode(conversation?.currentNode, conversation?.productIntent);
  return PRODUCT_STEPS[product] ?? PRODUCT_STEPS.GENERAL;
}

export function getPhaseStepIndex(currentNode) {
  const normalizedNodeId = normalizeNodeId(currentNode);

  if (!normalizedNodeId || normalizedNodeId === 'WELCOME_NODE') {
    return 0;
  }

  if (normalizedNodeId === 'INTENT_ROUTER') {
    return 1;
  }

  if (FINAL_NODE_IDS.has(normalizedNodeId)) {
    return 2;
  }

  // Búsqueda agnóstica: buscamos el índice en el producto que corresponda al nodo
  const product = getProductFromNode(normalizedNodeId);
  const steps = PRODUCT_STEPS[product] || [];
  const index = steps.findIndex((step) => step.id === normalizedNodeId);
  
  return index >= 0 ? index : 0;
}

export function getMilestoneState(stepId, currentNode) {
  const normalizedNodeId = normalizeNodeId(currentNode);
  const product = getProductFromNode(normalizedNodeId);
  const allSteps = PRODUCT_STEPS[product] || [];
  const currentIndex = allSteps.findIndex((s) => s.id === normalizedNodeId);
  const stepIndex = allSteps.findIndex((s) => s.id === stepId);
  const currentStepObj = allSteps[currentIndex];
  // 1. Es el nodo activo
  if (normalizedNodeId === stepId) {
    return currentStepObj?.terminal ? 'terminal' : 'active';
  }
  // 2. Comparación de progreso basada en el orden de la lista completa
  if (currentIndex !== -1 && stepIndex !== -1) {
    return stepIndex < currentIndex ? 'complete' : 'waiting';
  }
  return 'waiting';
}
// ESTA ES LA FUNCIÓN QUE FALTABA:
export function getFlowResultLabel(currentNode) {
  return getNodeMeta(currentNode).label;
}
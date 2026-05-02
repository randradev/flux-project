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

const FINAL_NODE_IDS = new Set([
  'LOAN_ENTRY_STUB',
  'ACCOUNT_ENTRY_STUB',
  'DAP_ENTRY_STUB',
  'GENERAL_RESPONSE'
]);

export function getNodeMeta(nodeId) {
  if (!nodeId) {
    return {
      label: 'Sin nodo recibido',
      description: 'Aun no se recibe estado del backend para esta conversacion.'
    };
  }

  return (
    NODE_DETAILS[nodeId] ?? {
      label: nodeId,
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

export function getPhaseStepIndex(currentNode) {
  if (!currentNode || currentNode === 'WELCOME_NODE') {
    return 0;
  }

  if (currentNode === 'INTENT_ROUTER') {
    return 1;
  }

  if (FINAL_NODE_IDS.has(currentNode)) {
    return 2;
  }

  return 0;
}

export function getFlowResultLabel(currentNode) {
  return getNodeMeta(currentNode).label;
}

import React from 'react';

const CLOSURE_TYPES = {
  LOAN_COMPLETED: {
    title: '🎉 ¡Lo logramos!',
    message: 'Tu crédito está listo y los fondos van volando a tu cuenta. ¡Buenazo!',
    showDownload: true
  },
  LOAN_REJECTED_POLICY: {
    title: '😅 Pucha, por ahora no se pudo',
    message: 'Esta vez no pasamos los filtros, pero tranqui, es solo una pausa. ¡Sigue moviendo tus lucas con Flux y lo intentamos en un tiempo más!',
    showDownload: false
  },
  LOAN_SECURITY_BLOCK: {
    title: '🔒 Pausa de Seguridad',
    message: 'Tuvimos que frenar el proceso por seguridad. Mejor hablemos con soporte para destrabar esto, ¿dale?',
    showDownload: false
  },
  LOAN_CLOSED_BY_USER: {
    title: '👋 ¡Todo bien!',
    message: 'Cerramos la solicitud por acá. Si cambias de opinión, aquí te esperamos con la mejor energía.',
    showDownload: false
  }
};

export default function FlowClosure({ conversation }) {
  // 1. Identificamos el estado final (con un fallback seguro)
  const currentNode = conversation?.currentNode;
  const config = CLOSURE_TYPES[currentNode] || CLOSURE_TYPES.LOAN_CLOSED_BY_USER;

  // 2. Solo buscamos la URL si el trámite fue exitoso
  const offerData = conversation?.offerData?.loan || {};
  const downloadUrl = (currentNode === 'LOAN_COMPLETED') 
    ? (offerData.file_contrato_path || offerData.display_data?.download_url)
    : null;

  return (
    <div className="flow-closure-card" style={{ padding: '20px', textAlign: 'center', border: '1px solid #eee', borderRadius: '12px', margin: '10px 0' }}>
      <h3>{config.title}</h3>
      <p style={{ color: '#555', marginBottom: '15px' }}>{config.message}</p>
      
      {/* 3. El botón solo aparece si el estado es SUCCESS y existe la URL */}
      {config.showDownload && downloadUrl && (
        <div className="download-section" style={{ marginTop: '10px' }}>
          <a 
            href={downloadUrl} 
            target="_blank" 
            rel="noopener noreferrer"
            className="primary-button download-button"
            style={{ 
              textDecoration: 'none', 
              display: 'inline-block', 
              padding: '12px 24px',
              backgroundColor: '#007bff',
              color: 'white',
              borderRadius: '8px',
              fontWeight: 'bold',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
            }}
          >
            📥 Descargar Contrato (PDF)
          </a>
        </div>
      )}
      
      <small style={{ display: 'block', marginTop: '20px', color: '#999', fontSize: '11px' }}>
        OPERACIÓN ID: {conversation.id ? conversation.id.slice(0,8).toUpperCase() : 'N/A'}
      </small>
    </div>
  );
}


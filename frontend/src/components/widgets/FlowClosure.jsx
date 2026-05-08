import React from 'react';

export default function FlowClosure({ conversation }) {
  const offerData = conversation?.offerData?.loan || {};
  const downloadUrl = offerData.file_contrato_path || offerData.display_data?.download_url;

  return (
    <div className="flow-closure-card" style={{ padding: '20px', textAlign: 'center' }}>
      <h3>🎉 ¡Trámite Finalizado!</h3>
      <p>Tu crédito ha sido procesado con éxito y los fondos están en camino.</p>
      
      {downloadUrl && (
        <div className="download-section" style={{ marginTop: '15px' }}>
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
              fontWeight: 'bold'
            }}
          >
            📥 Descargar Contrato (PDF)
          </a>
        </div>
      )}
      
      <small style={{ display: 'block', marginTop: '20px', color: '#888' }}>
        ID de Operación: {conversation.id ? conversation.id.slice(0,8).toUpperCase() : 'N/A'}
      </small>
    </div>
  );
}

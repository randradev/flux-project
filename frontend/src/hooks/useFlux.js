import { useContext } from 'react';
import { FluxContext } from '../context/FluxContext';

export function useFlux() {
  const context = useContext(FluxContext);

  if (!context) {
    throw new Error('useFlux debe usarse dentro de FluxProvider.');
  }

  return context;
}

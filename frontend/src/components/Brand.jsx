import React from 'react';

export default function Brand({ compact = false }) {
  return (
    <span className={`brand ${compact ? 'brand-compact' : ''}`} aria-label="FLUX">
      <span>FLU</span>
      <span>X</span>
    </span>
  );
}

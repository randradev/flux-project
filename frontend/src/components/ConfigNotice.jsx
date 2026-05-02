import React from 'react';

export default function ConfigNotice({ title, lines }) {
  return (
    <section className="config-notice" aria-label={title}>
      <strong>{title}</strong>
      {lines.map((line) => (
        <p key={line}>{line}</p>
      ))}
    </section>
  );
}

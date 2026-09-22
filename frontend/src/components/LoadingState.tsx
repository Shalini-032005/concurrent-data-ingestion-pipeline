interface LoadingStateProps {
  lines?: number;
  label?: string;
}

export function LoadingState({ lines = 3, label }: LoadingStateProps) {
  return (
    <div className="panel-body" aria-busy="true" aria-live="polite">
      {label && (
        <p style={{ fontSize: 12, color: "var(--text-faint)", marginBottom: 10 }}>{label}</p>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className="skeleton skeleton-line" style={{ width: `${88 - i * 12}%` }} />
        ))}
      </div>
    </div>
  );
}

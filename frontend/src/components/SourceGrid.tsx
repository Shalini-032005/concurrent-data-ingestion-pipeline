import { SourceCard } from "./SourceCard";
import { EmptyState } from "./EmptyState";
import type { SourceStatus } from "../types/dashboard";

interface SourceGridProps {
  sources: SourceStatus[];
}

export function SourceGrid({ sources }: SourceGridProps) {
  if (sources.length === 0) {
    return <EmptyState message="No source data available." />;
  }

  return (
    <div className="source-grid">
      {sources.map((source) => (
        <SourceCard key={source.source} source={source} />
      ))}
    </div>
  );
}

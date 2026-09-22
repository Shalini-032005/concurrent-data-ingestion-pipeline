import { Inbox } from "lucide-react";

interface EmptyStateProps {
  message: string;
}

export function EmptyState({ message }: EmptyStateProps) {
  return (
    <div className="state-block">
      <Inbox size={22} className="state-icon" aria-hidden="true" />
      <p>{message}</p>
    </div>
  );
}

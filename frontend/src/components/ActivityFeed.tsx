import { CheckCircle2, Info, AlertTriangle, XCircle } from "lucide-react";
import { EmptyState } from "./EmptyState";
import { formatTime } from "../utils/formatters";
import type { ActivityItem } from "../types/dashboard";

interface ActivityFeedProps {
  items: ActivityItem[];
}

const ICON_BY_TONE = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
} as const;

export function ActivityFeed({ items }: ActivityFeedProps) {
  if (items.length === 0) {
    return <EmptyState message="No activity yet — run an ingestion to see live events here." />;
  }

  return (
    <div className="activity-feed">
      {items.map((item) => {
        const Icon = ICON_BY_TONE[item.tone];
        return (
          <div key={item.id} className={`activity-item tone-${item.tone}`}>
            <Icon size={14} className="activity-icon" aria-hidden="true" />
            <span className="activity-time">{formatTime(item.timestamp)}</span>
            <span>{item.message}</span>
          </div>
        );
      })}
    </div>
  );
}

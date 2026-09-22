import type { LucideIcon } from "lucide-react";
import { formatNumber } from "../utils/formatters";

interface StatCardProps {
  label: string;
  value: number | null | undefined;
  icon: LucideIcon;
  tone?: "green" | "amber" | "red" | "default";
}

export function StatCard({ label, value, icon: Icon, tone = "default" }: StatCardProps) {
  const toneClass = tone !== "default" ? ` accent-${tone}` : "";
  return (
    <div className="stat-cell">
      <span className="stat-label">
        <Icon size={13} />
        {label}
      </span>
      <span className={`stat-value${toneClass}`}>{formatNumber(value)}</span>
    </div>
  );
}

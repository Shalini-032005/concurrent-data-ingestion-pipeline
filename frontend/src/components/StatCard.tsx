import type { LucideIcon } from "lucide-react";
import { formatNumber } from "../utils/formatters";

interface StatCardProps {
  label: string;
  value: number | string | null | undefined;
  icon: LucideIcon;
  tone?: "green" | "amber" | "red" | "cyan" | "default";
}

export function StatCard({ label, value, icon: Icon, tone = "default" }: StatCardProps) {
  const toneClass = tone !== "default" ? ` accent-${tone}` : "";
  const displayVal = typeof value === "number" ? formatNumber(value) : (value ?? "—");
  return (
    <div className="stat-cell">
      <span className="stat-label">
        <Icon size={13} />
        {label}
      </span>
      <span className={`stat-value${toneClass}`}>{displayVal}</span>
    </div>
  );
}

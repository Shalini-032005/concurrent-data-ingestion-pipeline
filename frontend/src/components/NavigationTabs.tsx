import {
  Activity,
  AlertTriangle,
  Bell,
  GitBranch,
  GitCompare,
  HeartPulse,
  ShieldCheck,
} from "lucide-react";

export type TabId =
  | "overview"
  | "quality"
  | "anomalies"
  | "alerts"
  | "health"
  | "lineage"
  | "comparison";

interface NavigationTabsProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  activeAlertsCount?: number;
  anomaliesCount?: number;
}

export function NavigationTabs({
  activeTab,
  onTabChange,
  activeAlertsCount = 0,
  anomaliesCount = 0,
}: NavigationTabsProps) {
  const tabs = [
    { id: "overview" as TabId, label: "Overview", icon: Activity },
    { id: "quality" as TabId, label: "Data Quality", icon: ShieldCheck },
    {
      id: "anomalies" as TabId,
      label: "ML Anomalies",
      icon: AlertTriangle,
      badge: anomaliesCount > 0 ? anomaliesCount : undefined,
    },
    {
      id: "alerts" as TabId,
      label: "Alert Center",
      icon: Bell,
      badge: activeAlertsCount > 0 ? activeAlertsCount : undefined,
    },
    { id: "health" as TabId, label: "Pipeline Health", icon: HeartPulse },
    { id: "lineage" as TabId, label: "Data Lineage", icon: GitBranch },
    { id: "comparison" as TabId, label: "What Changed?", icon: GitCompare },
  ];

  return (
    <nav className="nav-tabs" aria-label="Platform navigation tabs">
      {tabs.map((t) => {
        const Icon = t.icon;
        const isActive = activeTab === t.id;
        return (
          <button
            key={t.id}
            type="button"
            className={`nav-tab ${isActive ? "active" : ""}`}
            onClick={() => onTabChange(t.id)}
          >
            <Icon size={16} />
            <span>{t.label}</span>
            {t.badge !== undefined && (
              <span className={`tab-badge ${t.id === "alerts" ? "badge-danger" : "badge-warning"}`}>
                {t.badge}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
}

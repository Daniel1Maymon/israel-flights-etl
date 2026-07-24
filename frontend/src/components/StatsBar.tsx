import { useEffect, useState } from "react";
import { Plane, PlaneTakeoff, PlaneLanding, Building2, MapPin } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { API_ENDPOINTS } from "@/config/api";

interface StatsOverview {
  departures: number;
  arrivals: number;
  total: number;
  airlines: number;
  destinations: number;
}

// How often to re-fetch so the bar reflects DB changes (ETL runs every ~15 min).
const REFRESH_MS = 60_000;

export const StatsBar = () => {
  const { t, language } = useLanguage();
  const [stats, setStats] = useState<StatsOverview | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const res = await fetch(API_ENDPOINTS.STATS_OVERVIEW);
        if (!res.ok) return;
        const data: StatsOverview = await res.json();
        if (!cancelled) setStats(data);
      } catch {
        // Keep the last known values on transient errors.
      }
    };

    load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const locale = language === "he" ? "he-IL" : "en-US";
  const fmt = (n: number | undefined) =>
    n === undefined ? "—" : n.toLocaleString(locale);

  // Logical order; the grid follows the page direction, so this reads
  // left-to-right in English and right-to-left in Hebrew.
  // NB: avoid the `grid-cols-2` class here — a global RTL rule in index.css
  // reorders first/last children of any `.grid-cols-2`, which scrambles the bar.
  const items = [
    { icon: PlaneTakeoff, value: stats?.departures, label: t("stats.departures") },
    { icon: PlaneLanding, value: stats?.arrivals, label: t("stats.arrivals") },
    { icon: Plane, value: stats?.total, label: t("stats.total") },
    { icon: Building2, value: stats?.airlines, label: t("stats.airlines") },
    { icon: MapPin, value: stats?.destinations, label: t("stats.destinations") },
  ];

  return (
    <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
      {items.map(({ icon: Icon, value, label }) => (
        <div
          key={label}
          className="flex items-center justify-center gap-2 rounded-lg border border-border bg-card px-2 py-3"
        >
          <Icon className="h-6 w-6 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div className="flex flex-col items-center text-center">
            <span
              className="text-2xl font-semibold text-foreground tabular-nums leading-none"
              dir="ltr"
            >
              {fmt(value)}
            </span>
            <span className="mt-1 text-[11px] text-muted-foreground">
              {label}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
};

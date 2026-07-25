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

  // flex-wrap rather than a grid: with 5 items the leftover row (2 tiles on a 3-wide phone)
  // centres instead of hanging off one edge. `basis` reproduces the 3-up / 5-up column widths.
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {items.map(({ icon: Icon, value, label }) => (
        <div
          key={label}
          className="flex min-w-0 basis-[calc(33.333%-0.5rem)] flex-col items-center justify-center gap-1 rounded-lg border border-border bg-card px-1.5 py-2.5 sm:basis-[calc(20%-0.64rem)] sm:flex-row sm:gap-2 sm:px-2 sm:py-3"
        >
          <Icon
            className="h-4 w-4 shrink-0 text-muted-foreground sm:h-6 sm:w-6"
            aria-hidden="true"
          />
          <div className="flex min-w-0 flex-col items-center text-center">
            {/* Phone tiles are ~90px wide; a 6-figure count at text-2xl needs ~85px and used to
                spill straight out of the card. Scale the number with the viewport instead. */}
            <span
              className="text-base font-semibold text-foreground tabular-nums leading-none sm:text-2xl"
              dir="ltr"
            >
              {fmt(value)}
            </span>
            <span className="mt-1 text-[10px] leading-tight text-muted-foreground sm:text-[11px]">
              {label}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
};

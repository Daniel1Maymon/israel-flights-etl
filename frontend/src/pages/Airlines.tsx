import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTheme } from "next-themes";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowDown, ArrowUp, ArrowUpDown, TrendingDown, TrendingUp } from "lucide-react";
import { PageLayout } from "@/components/PageLayout";
import { AirlineSearch, type AirlineOption } from "@/components/AirlineSearch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useLanguage } from "@/contexts/LanguageContext";
import { API_ENDPOINTS } from "@/config/api";
import { SINGLE_SERIES_COLOR, ANNOTATION_COLOR, shortMonth } from "@/lib/insightsChart";

interface Kpis {
  scheduled: number;
  cancelled: number;
  cancelled_pct: number;
  on_time_pct: number;
  avg_delay_when_late: number | null;
  worst_delay: number | null;
  destinations: number;
}
interface WorstDelayFlight {
  flight_number: string;
  city_en: string | null;
  city_he: string | null;
  scheduled_time: string | null;
  delay_minutes: number;
}
interface Profile {
  airline_code: string;
  airline_name: string;
  is_israeli: boolean;
  carrier: Kpis;
  worst_delay_flight: WorstDelayFlight | null;
  delay_distribution: {
    early: number;
    on_time: number;
    late: number;
    very_late: number;
    cancelled: number;
  };
  monthly: {
    month: string;
    scheduled: number;
    measured: number;
    on_time_pct: number;
    cancelled_pct: number;
  }[];
}
interface Route {
  city_en: string;
  city_he: string | null;
  country_en: string | null;
  total_flights: number;
  on_time_pct: number;
  cancelled_pct: number;
  avg_delay_minutes_positive_only: number | null;
}

type SortField = "city" | "total_flights" | "on_time_pct" | "cancelled_pct" | "avg_delay";

/** Routes below this many flights are noise — a 2-flight route at 100% is not a finding. */
const MIN_ROUTE_FLIGHTS = 10;

/**
 * Higher bar for the best/worst callouts than for the table.
 *
 * The table shows each route's flight count, so the reader can weigh a thin row themselves. A
 * callout makes a claim on the reader's behalf and needs a sample that supports it: at 10 flights
 * this page announced Bacau (12 departures, a third of them cancelled) as El Al's best route,
 * ahead of Abu Dhabi's 63.5% across 1,143. Same failure the hourly insight guards against.
 */
const MIN_CALLOUT_FLIGHTS = 50;

/**
 * A month needs this many operated, measurable flights before its on-time share is plotted.
 *
 * During the disruption several carriers cancelled nearly everything, leaving a handful of flights
 * that happened to leave on time. Delta rendered as 100% on-time in March 2026 off roughly a dozen
 * departures — a spike to the top of the chart for the month it almost stopped flying. Such months
 * are left as gaps in the line, which is the honest reading: not "perfect", but "barely operated".
 */
const MIN_TREND_FLIGHTS = 30;

/** Shown when no airline is in the URL, so /airlines is never a blank prompt. */
const DEFAULT_AIRLINE_CODE = "LY";

const fill = (template: string, values: Record<string, string | number>) =>
  Object.entries(values).reduce(
    (acc, [k, v]) => acc.replaceAll(`{${k}}`, String(v)),
    template,
  );

const Airlines = () => {
  const { code: codeParam } = useParams<{ code: string }>();
  const code = codeParam ?? DEFAULT_AIRLINE_CODE;
  const navigate = useNavigate();
  const { t, language, isRTL } = useLanguage();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const locale = language === "he" ? "he-IL" : "en-US";
  const pick = (p: { light: string; dark: string }) => (isDark ? p.dark : p.light);

  const [profile, setProfile] = useState<Profile | null>(null);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [filter, setFilter] = useState("");
  const [sortField, setSortField] = useState<SortField>("total_flights");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    if (!code) {
      setProfile(null);
      setRoutes([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    Promise.all([
      fetch(API_ENDPOINTS.AIRLINE_PROFILE(code)).then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      }),
      fetch(`${API_ENDPOINTS.AIRLINE_ROUTES(code)}?min_flights=${MIN_ROUTE_FLIGHTS}`).then((r) =>
        r.json(),
      ),
    ])
      .then(([p, r]) => {
        if (cancelled) return;
        setProfile(p);
        setRoutes(r.routes ?? []);
      })
      .catch(() => {
        if (!cancelled) {
          setProfile(null);
          setRoutes([]);
          setNotFound(true);
        }
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [code]);

  const ownAverage = profile?.carrier.on_time_pct ?? 0;

  // null (not 0) for thin months, so Recharts leaves a gap instead of drawing a plunge to zero.
  const trendData = useMemo(
    () =>
      (profile?.monthly ?? []).map((m) => ({
        ...m,
        on_time_pct: m.measured >= MIN_TREND_FLIGHTS ? m.on_time_pct : null,
      })),
    [profile],
  );
  const routeName = (r: Route) => (language === "he" && r.city_he ? r.city_he : r.city_en);

  /** "1169 · לרנקה · 4 באפר׳" — which flight the worst-delay figure actually came from. */
  const worstDelayCaption = useMemo(() => {
    const w = profile?.worst_delay_flight;
    if (!w) return undefined;
    const city = (language === "he" && w.city_he ? w.city_he : w.city_en) ?? "";
    const when = w.scheduled_time
      ? new Date(w.scheduled_time).toLocaleDateString(locale, { day: "numeric", month: "short" })
      : "";
    return [w.flight_number, city, when].filter(Boolean).join(" · ");
  }, [profile, language, locale]);

  // Only routes with a sample big enough to support a headline claim are eligible. If fewer than
  // two qualify there is nothing meaningful to contrast, and the callouts are hidden entirely
  // rather than shown with a caveat nobody reads.
  const calloutPool = useMemo(
    () => routes.filter((r) => r.total_flights >= MIN_CALLOUT_FLIGHTS),
    [routes],
  );
  const best = useMemo(
    () =>
      calloutPool.length >= 2
        ? calloutPool.reduce((a, b) => (b.on_time_pct > a.on_time_pct ? b : a))
        : null,
    [calloutPool],
  );
  const worst = useMemo(
    () =>
      calloutPool.length >= 2
        ? calloutPool.reduce((a, b) => (b.on_time_pct < a.on_time_pct ? b : a))
        : null,
    [calloutPool],
  );

  const visibleRoutes = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const matched = q
      ? routes.filter(
          (r) =>
            r.city_en?.toLowerCase().includes(q) ||
            r.city_he?.toLowerCase().includes(q) ||
            r.country_en?.toLowerCase().includes(q),
        )
      : routes;
    const dir = sortDir === "asc" ? 1 : -1;
    return [...matched].sort((a, b) => {
      if (sortField === "city") return dir * routeName(a).localeCompare(routeName(b));
      if (sortField === "avg_delay") {
        return dir * ((a.avg_delay_minutes_positive_only ?? 0) - (b.avg_delay_minutes_positive_only ?? 0));
      }
      return dir * ((a[sortField] as number) - (b[sortField] as number));
    });
  }, [routes, filter, sortField, sortDir, language]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortField(field);
      setSortDir(field === "city" ? "asc" : "desc");
    }
  };

  const SortIcon = ({ field }: { field: SortField }) =>
    field !== sortField ? (
      <ArrowUpDown className="h-3 w-3" />
    ) : sortDir === "asc" ? (
      <ArrowUp className="h-3 w-3" />
    ) : (
      <ArrowDown className="h-3 w-3" />
    );

  const th = (field: SortField, label: string, extra = "") => (
    <th className={`px-2 py-2 font-semibold ${extra}`}>
      <button
        onClick={() => toggleSort(field)}
        className="inline-flex items-center gap-1 hover:text-foreground"
      >
        {label} <SortIcon field={field} />
      </button>
    </th>
  );

  /** Deviation from the airline's OWN average — the page's core comparison. */
  const Delta = ({ value }: { value: number }) => {
    const d = value - ownAverage;
    const strong = Math.abs(d) >= 1;
    return (
      <span
        className={`inline-flex items-center gap-0.5 tabular-nums ${
          !strong ? "text-muted-foreground" : d > 0 ? "text-success" : "text-destructive"
        }`}
      >
        {strong && (d > 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />)}
        {d > 0 ? "+" : ""}
        {d.toFixed(1)}
      </span>
    );
  };

  const distribution = profile
    ? [
        { key: "early", value: profile.delay_distribution.early, color: "#6ba3dd" },
        { key: "onTime", value: profile.delay_distribution.on_time, color: "#1baf7a" },
        { key: "late", value: profile.delay_distribution.late, color: "#eda100" },
        { key: "veryLate", value: profile.delay_distribution.very_late, color: "#e2724f" },
        { key: "cancelled", value: profile.delay_distribution.cancelled, color: "#cf3b3b" },
      ]
    : [];
  const distTotal = distribution.reduce((s, d) => s + d.value, 0);

  const axisStyle = { fontSize: 11, fill: "hsl(var(--muted-foreground))" };
  const tooltipStyle = {
    backgroundColor: "hsl(var(--card))",
    border: "1px solid hsl(var(--border))",
    borderRadius: "0.5rem",
    fontSize: "12px",
    color: "hsl(var(--foreground))",
  };

  const kpi = (label: string, value: string, sub?: string) => (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="text-xl font-bold text-foreground tabular-nums sm:text-2xl">{value}</div>
      <div className="mt-0.5 text-xs font-medium text-foreground">{label}</div>
      {sub && <div className="mt-0.5 text-[11px] text-muted-foreground">{sub}</div>}
    </div>
  );

  return (
    <PageLayout>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground sm:text-3xl">{t("airlines.title")}</h1>
        <p className="mt-1 text-sm text-muted-foreground sm:text-base">{t("airlines.subtitle")}</p>
      </div>

      <div className="mb-8">
        <AirlineSearch
          value={profile?.airline_name ?? ""}
          onSelect={(a: AirlineOption) => navigate(`/airlines/${encodeURIComponent(a.airline_code)}`)}
        />
      </div>

      {loading && <p className="py-16 text-center text-muted-foreground">{t("common.loading")}</p>}

      {!loading && notFound && (
        <p className="py-16 text-center text-muted-foreground">{t("airlines.notFound")}</p>
      )}

      {!loading && profile && (
        <div className="space-y-6">
          {/* ── KPI tiles ── */}
          <div>
            <h2 className="mb-3 text-xl font-bold text-foreground">{profile.airline_name}</h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {kpi(t("airlines.kpi.flights"), profile.carrier.scheduled.toLocaleString(locale))}
              {kpi(t("airlines.kpi.onTime"), `${profile.carrier.on_time_pct.toFixed(1)}%`)}
              {kpi(t("airlines.kpi.cancelled"), `${profile.carrier.cancelled_pct.toFixed(1)}%`)}
              {kpi(
                t("airlines.kpi.avgDelay"),
                profile.carrier.avg_delay_when_late != null
                  ? `${profile.carrier.avg_delay_when_late} ${t("airlines.minutes")}`
                  : "—",
              )}
              {kpi(t("airlines.kpi.destinations"), String(profile.carrier.destinations))}
              {kpi(
                t("airlines.kpi.worstDelay"),
                profile.carrier.worst_delay != null
                  ? `${profile.carrier.worst_delay} ${t("airlines.minutes")}`
                  : "—",
                // A MAX is set by one departure out of thousands. Naming that flight stops the
                // tile reading as a characteristic of the airline — Arkia's 2,883 minutes is a
                // single Larnaca service held two days during the disruption, ten times its own
                // 99th percentile.
                worstDelayCaption,
              )}
            </div>
          </div>

          {/* ── Delay profile ── */}
          <Card className="border border-border/60">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold sm:text-xl">
                {t("airlines.profile.title")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* A single 100% bar: the question is what share of flights fall in each band, and
                  a stacked bar answers it without asking the reader to compare axis heights. */}
              <div className="flex h-8 w-full overflow-hidden rounded-md" dir="ltr">
                {distribution.map((d) =>
                  d.value === 0 ? null : (
                    <div
                      key={d.key}
                      className="h-full"
                      style={{
                        width: `${(d.value / distTotal) * 100}%`,
                        backgroundColor: d.color,
                        // 2px surface gap so adjacent bands stay legible where they meet.
                        boxShadow: "inset -2px 0 0 hsl(var(--card))",
                      }}
                      title={`${t(`airlines.profile.${d.key}`)}: ${d.value.toLocaleString(locale)}`}
                    />
                  ),
                )}
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs">
                {distribution.map((d) => (
                  <span key={d.key} className="inline-flex items-center gap-1.5">
                    <span
                      className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
                      style={{ backgroundColor: d.color }}
                    />
                    <span className="text-muted-foreground">{t(`airlines.profile.${d.key}`)}</span>
                    <span className="font-medium text-foreground tabular-nums">
                      {distTotal ? ((d.value / distTotal) * 100).toFixed(1) : "0"}%
                    </span>
                  </span>
                ))}
              </div>
              <p className="border-t border-border/50 pt-3 text-xs leading-relaxed text-muted-foreground/80">
                {t("airlines.profile.caption")}
              </p>
            </CardContent>
          </Card>

          {/* ── Monthly trend ── */}
          <Card className="border border-border/60">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold sm:text-xl">
                {t("airlines.trend.title")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div dir="ltr">
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={trendData} margin={{ top: 8, right: 8, bottom: 0, left: -4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis
                      dataKey="month"
                      tickFormatter={(m) => shortMonth(String(m), locale)}
                      tick={axisStyle}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis unit="%" domain={[0, 100]} tick={axisStyle} tickLine={false} axisLine={false} width={52} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      labelFormatter={(m) => shortMonth(String(m), locale)}
                      formatter={(v: number) => [v == null ? "—" : `${v}%`, t("airlines.kpi.onTime")]}
                    />
                    {/* Its own average as the reference — this page compares the airline to
                        itself, never to other carriers. */}
                    <ReferenceLine
                      y={ownAverage}
                      stroke={pick(ANNOTATION_COLOR)}
                      strokeDasharray="4 3"
                      label={{
                        value: `${t("airlines.ownAverage")} ${ownAverage.toFixed(1)}%`,
                        position: "insideTopLeft",
                        fill: "hsl(var(--muted-foreground))",
                        fontSize: 11,
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="on_time_pct"
                      stroke={pick(SINGLE_SERIES_COLOR)}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <p className="border-t border-border/50 pt-3 text-xs leading-relaxed text-muted-foreground/80">
                {t("airlines.trend.caption")}
              </p>
            </CardContent>
          </Card>

          {/* ── Per-destination table (the centrepiece) ── */}
          <Card className="border border-border/60">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-semibold sm:text-xl">
                {t("airlines.routes.title")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 p-0">
              {best && worst && best !== worst && (
                <div className="grid grid-cols-1 gap-2 px-4 pt-2 sm:grid-cols-2">
                  <div className="rounded-lg border border-success/40 bg-success/10 px-3 py-2 text-sm">
                    <div className="text-xs text-muted-foreground">{t("airlines.routes.best")}</div>
                    <div className="font-semibold text-foreground">
                      {routeName(best)} — {best.on_time_pct.toFixed(1)}%{" "}
                      <span className="text-xs font-normal">
                        (<Delta value={best.on_time_pct} />)
                      </span>
                      {/* Sample size is stated, so the claim can be judged rather than trusted. */}
                      <span className="ms-1 text-xs font-normal text-muted-foreground">
                        · {best.total_flights.toLocaleString(locale)} {t("airlines.routes.flights").toLowerCase()}
                      </span>
                    </div>
                  </div>
                  <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm">
                    <div className="text-xs text-muted-foreground">{t("airlines.routes.worst")}</div>
                    <div className="font-semibold text-foreground">
                      {routeName(worst)} — {worst.on_time_pct.toFixed(1)}%{" "}
                      <span className="text-xs font-normal">
                        (<Delta value={worst.on_time_pct} />)
                      </span>
                      <span className="ms-1 text-xs font-normal text-muted-foreground">
                        · {worst.total_flights.toLocaleString(locale)}{" "}
                        {t("airlines.routes.flights").toLowerCase()}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              <div className="px-4">
                <Input
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  placeholder={t("airlines.routes.search")}
                  className="h-9 max-w-xs"
                />
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm sm:min-w-[640px]">
                  <thead>
                    <tr className="border-b border-border/50 text-xs text-muted-foreground">
                      {th("city", t("airlines.routes.destination"), "text-start")}
                      {th("total_flights", t("airlines.routes.flights"), "text-center hidden sm:table-cell")}
                      {th("on_time_pct", t("airlines.routes.onTime"), "text-center")}
                      <th className="px-2 py-2 text-center font-semibold">
                        {t("airlines.routes.vsOwn")}
                      </th>
                      {th("cancelled_pct", t("airlines.routes.cancelled"), "text-center hidden sm:table-cell")}
                      {th("avg_delay", t("airlines.routes.avgDelay"), "text-center hidden md:table-cell")}
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRoutes.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                          {t("airlines.routes.none")}
                        </td>
                      </tr>
                    )}
                    {visibleRoutes.map((r) => (
                      <tr key={r.city_en} className="border-b border-border/30 hover:bg-muted/30">
                        <td className="px-2 py-2 text-start font-medium text-foreground">
                          {routeName(r)}
                        </td>
                        <td className="hidden px-2 py-2 text-center tabular-nums text-muted-foreground sm:table-cell">
                          {r.total_flights.toLocaleString(locale)}
                        </td>
                        <td className="px-2 py-2 text-center tabular-nums font-semibold text-foreground">
                          {r.on_time_pct.toFixed(1)}%
                        </td>
                        <td className="px-2 py-2 text-center text-xs">
                          <Delta value={r.on_time_pct} />
                        </td>
                        <td className="hidden px-2 py-2 text-center tabular-nums text-muted-foreground sm:table-cell">
                          {r.cancelled_pct.toFixed(1)}%
                        </td>
                        <td className="hidden px-2 py-2 text-center tabular-nums text-muted-foreground md:table-cell">
                          {r.avg_delay_minutes_positive_only != null
                            ? `${r.avg_delay_minutes_positive_only} ${t("airlines.minutes")}`
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <p className="border-t border-border/50 px-4 py-3 text-xs leading-relaxed text-muted-foreground/80">
                {t("airlines.routes.caption")}{" "}
                {fill(t("airlines.routes.minFlights"), { n: MIN_ROUTE_FLIGHTS })}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </PageLayout>
  );
};

export default Airlines;

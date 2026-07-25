import { useEffect, useMemo, useState } from "react";
import { Ban, PlaneTakeoff, TrendingUp, CheckCircle2 } from "lucide-react";
import { PageLayout } from "@/components/PageLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/LanguageContext";
import { API_ENDPOINTS } from "@/config/api";
import { BUCKET_ORDER, BUCKET_STYLES, type RecoveryBucket } from "@/lib/insightsChart";

interface Carrier {
  airline_code: string;
  airline_name: string;
  baseline_monthly: number;
  last30_flights: number;
  recovery_pct: number | null;
  return_date: string | null;
  bucket: RecoveryBucket;
}
interface RecoveryResponse {
  carriers: Carrier[];
  crisis_window: { start: string; end: string } | null;
  summary: Partial<Record<RecoveryBucket, number>>;
  baseline_period?: { start: string; end: string; months: number };
}

const BUCKET_ICONS = {
  never_returned: Ban,
  partial: PlaneTakeoff,
  recovered: CheckCircle2,
  expanded: TrendingUp,
} as const;

const fill = (template: string, values: Record<string, string | number>) =>
  Object.entries(values).reduce(
    (acc, [key, value]) => acc.replaceAll(`{${key}}`, String(value)),
    template,
  );

const Recovery = () => {
  const { t, language } = useLanguage();
  const locale = language === "he" ? "he-IL" : "en-US";

  const [data, setData] = useState<RecoveryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<RecoveryBucket | "all">("all");

  useEffect(() => {
    let cancelled = false;
    fetch(API_ENDPOINTS.INSIGHTS_RECOVERY)
      .then((r) => r.json())
      .then((d: RecoveryResponse) => !cancelled && setData(d))
      .catch(() => undefined)
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const carriers = data?.carriers ?? [];

  /** Timeline plots only carriers with a real return date, earliest first. */
  const timeline = useMemo(
    () =>
      carriers
        .filter((c) => c.return_date)
        .sort((a, b) => (a.return_date! < b.return_date! ? -1 : 1)),
    [carriers],
  );

  const stillGone = useMemo(
    () =>
      carriers
        .filter((c) => c.bucket === "never_returned")
        .sort((a, b) => b.baseline_monthly - a.baseline_monthly),
    [carriers],
  );

  const visible = useMemo(
    () =>
      filter === "all" ? carriers : carriers.filter((c) => c.bucket === filter),
    [carriers, filter],
  );

  const formatDate = (iso: string | null) =>
    iso ? new Date(iso).toLocaleDateString(locale, { day: "numeric", month: "short" }) : null;

  if (loading) {
    return (
      <PageLayout>
        <p className="py-20 text-center text-muted-foreground">{t("common.loading")}</p>
      </PageLayout>
    );
  }

  if (!data?.crisis_window || !carriers.length) {
    return (
      <PageLayout>
        <p className="py-20 text-center text-muted-foreground">{t("recovery.noData")}</p>
      </PageLayout>
    );
  }

  // Timeline bars are positioned across the span from the first return to the last, so the
  // clustering (most carriers back within weeks, a long tail into July) is visible as spacing.
  const firstReturn = timeline.length ? new Date(timeline[0].return_date!).getTime() : 0;
  const lastReturn = timeline.length
    ? new Date(timeline[timeline.length - 1].return_date!).getTime()
    : 1;
  const span = Math.max(1, lastReturn - firstReturn);

  return (
    <PageLayout>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground sm:text-3xl">{t("recovery.title")}</h1>
        <p className="mt-1 text-sm text-muted-foreground sm:text-base">{t("recovery.subtitle")}</p>
      </div>

      {/* ── Bucket summary tiles ── */}
      <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {BUCKET_ORDER.map((bucket) => {
          const Icon = BUCKET_ICONS[bucket];
          const count = data.summary[bucket] ?? 0;
          const active = filter === bucket;
          return (
            <button
              key={bucket}
              onClick={() => setFilter(active ? "all" : bucket)}
              aria-pressed={active}
              className={`rounded-lg border bg-card p-3 text-start transition-colors hover:bg-muted/40 ${
                active ? "border-foreground/60" : "border-border"
              }`}
            >
              <div className="flex items-center gap-2">
                {/* Icon + label + count: the bucket is never conveyed by colour alone. */}
                <span className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${BUCKET_STYLES[bucket].dot}`} />
                <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="text-2xl font-bold text-foreground tabular-nums">{count}</span>
              </div>
              <div className="mt-1 text-xs font-medium text-foreground">
                {t(`recovery.bucket.${bucket}`)}
              </div>
              <div className="mt-0.5 text-[11px] leading-tight text-muted-foreground">
                {t(`recovery.bucket.${bucket}.hint`)}
              </div>
            </button>
          );
        })}
      </div>

      {/* ── Still missing ── */}
      {stillGone.length > 0 && (
        <Card className="mb-6 border border-border/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg font-semibold sm:text-xl">
              {t("recovery.stillGone.title")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {stillGone.map((c) => (
                <span
                  key={c.airline_code}
                  className="inline-flex items-center gap-1.5 rounded-full border border-destructive/40 bg-destructive/10 px-3 py-1 text-xs text-foreground"
                >
                  <Ban className="h-3 w-3 text-destructive" aria-hidden="true" />
                  {c.airline_name}
                  <span className="text-muted-foreground">
                    ({Math.round(c.baseline_monthly)}/{t("insights.flights").toLowerCase()})
                  </span>
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Return timeline ── */}
      {timeline.length > 0 && (
        <Card className="mb-6 border border-border/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg font-semibold sm:text-xl">
              {t("recovery.timeline.title")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1.5">
              {timeline.map((c) => {
                const offset =
                  ((new Date(c.return_date!).getTime() - firstReturn) / span) * 100;
                return (
                  <div key={c.airline_code} className="flex items-center gap-2 text-xs">
                    <span className="w-28 shrink-0 truncate text-muted-foreground sm:w-44">
                      {c.airline_name}
                    </span>
                    <div className="relative h-4 flex-1 rounded bg-muted/50" dir="ltr">
                      <span
                        className={`absolute top-0.5 h-3 w-3 rounded-full ${BUCKET_STYLES[c.bucket].dot}`}
                        style={{ left: `calc(${offset}% - 6px)` }}
                        title={`${c.airline_name} — ${formatDate(c.return_date)}`}
                      />
                    </div>
                    <span className="w-14 shrink-0 text-end tabular-nums text-muted-foreground">
                      {formatDate(c.return_date)}
                    </span>
                  </div>
                );
              })}
            </div>
            <p className="border-t border-border/50 pt-3 text-xs leading-relaxed text-muted-foreground/80">
              {t("recovery.timeline.caption")}
            </p>
          </CardContent>
        </Card>
      )}

      {/* ── Full table ── */}
      <Card className="border border-border/60">
        <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 pb-2">
          <CardTitle className="text-lg font-semibold sm:text-xl">
            {t("recovery.table.title")}
          </CardTitle>
          {filter !== "all" && (
            <Button variant="outline" size="sm" onClick={() => setFilter("all")}>
              {t("recovery.filter.all")}
            </Button>
          )}
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm sm:min-w-[640px]">
              <thead>
                <tr className="border-b border-border/50 text-xs text-muted-foreground">
                  <th className="px-3 py-2 text-start font-semibold">{t("recovery.table.carrier")}</th>
                  <th className="hidden px-3 py-2 text-center font-semibold sm:table-cell">
                    {t("recovery.table.baseline")}
                  </th>
                  <th className="hidden px-3 py-2 text-center font-semibold sm:table-cell">
                    {t("recovery.table.last30")}
                  </th>
                  <th className="px-3 py-2 text-center font-semibold">{t("recovery.table.recovery")}</th>
                  <th className="hidden px-3 py-2 text-center font-semibold md:table-cell">
                    {t("recovery.table.returned")}
                  </th>
                  <th className="px-3 py-2 text-center font-semibold">{t("recovery.table.status")}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((c) => (
                  <tr key={c.airline_code} className="border-b border-border/30 hover:bg-muted/30">
                    <td className="px-3 py-2 text-start font-medium text-foreground">
                      {c.airline_name}
                    </td>
                    <td className="hidden px-3 py-2 text-center tabular-nums text-muted-foreground sm:table-cell">
                      {Math.round(c.baseline_monthly).toLocaleString(locale)}
                    </td>
                    <td className="hidden px-3 py-2 text-center tabular-nums text-muted-foreground sm:table-cell">
                      {c.last30_flights.toLocaleString(locale)}
                    </td>
                    <td className="px-3 py-2 text-center tabular-nums font-semibold text-foreground">
                      {c.recovery_pct == null ? "—" : `${Math.round(c.recovery_pct)}%`}
                    </td>
                    <td className="hidden px-3 py-2 text-center text-xs text-muted-foreground md:table-cell">
                      {/* No return date on a flying carrier means it never stopped — say so
                          rather than leaving a blank cell that reads as missing data. */}
                      {c.return_date
                        ? formatDate(c.return_date)
                        : c.bucket === "never_returned"
                          ? "—"
                          : t("recovery.neverStopped")}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <Badge className={`${BUCKET_STYLES[c.bucket].badge} whitespace-nowrap text-[10px] px-1.5 py-0`}>
                        {t(`recovery.bucket.${c.bucket}`)}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.baseline_period && (
            <p className="border-t border-border/50 px-3 py-3 text-xs leading-relaxed text-muted-foreground/80">
              {fill(t("recovery.methodology"), {
                start: data.baseline_period.start,
                end: data.baseline_period.end,
              })}
            </p>
          )}
        </CardContent>
      </Card>
    </PageLayout>
  );
};

export default Recovery;

import { useEffect, useMemo, useState } from "react";
import { useTheme } from "next-themes";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PageLayout } from "@/components/PageLayout";
import { StoryCard } from "@/components/StoryCard";
import { useLanguage } from "@/contexts/LanguageContext";
import { API_ENDPOINTS } from "@/config/api";
import {
  ANNOTATION_COLOR,
  NATIONALITY_COLORS,
  SINGLE_SERIES_COLOR,
  WEEKDAY_KEYS,
  shortMonth,
} from "@/lib/insightsChart";

interface MonthRow {
  month: string;
  israeli_scheduled: number;
  israeli_cancelled_pct: number;
  foreign_scheduled: number;
  foreign_cancelled_pct: number;
  total_cancelled_pct: number;
  israeli_share_pct: number;
}
interface CrisisWindow {
  start: string;
  end: string;
  months: string[];
  threshold_pct: number;
}
interface WeekdayRow {
  dow: number;
  flights: number;
  on_time_pct: number;
}
interface HourRow {
  hour: number;
  flights: number;
  on_time_pct: number;
}

/** The `t()` helper does plain lookups; stories need several substitutions per sentence. */
const fill = (template: string, values: Record<string, string | number>) =>
  Object.entries(values).reduce(
    (acc, [key, value]) => acc.replaceAll(`{${key}}`, String(value)),
    template,
  );

const CHART_HEIGHT = 260;

/** 10000 -> '10k'. A 5-digit tick needs a wider gutter than the axis has, and got clipped. */
const compact = (value: number) => (value >= 1000 ? `${value / 1000}k` : String(value));

const Insights = () => {
  const { t, language, isRTL } = useLanguage();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const locale = language === "he" ? "he-IL" : "en-US";

  const [months, setMonths] = useState<MonthRow[]>([]);
  const [crisis, setCrisis] = useState<CrisisWindow | null>(null);
  const [weekdays, setWeekdays] = useState<WeekdayRow[]>([]);
  const [hours, setHours] = useState<HourRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch(API_ENDPOINTS.INSIGHTS_MONTHLY).then((r) => r.json()),
      fetch(API_ENDPOINTS.INSIGHTS_WEEKDAY).then((r) => r.json()),
      fetch(API_ENDPOINTS.INSIGHTS_HOUR).then((r) => r.json()),
    ])
      .then(([monthly, weekday, hourly]) => {
        if (cancelled) return;
        setMonths(monthly.months ?? []);
        setCrisis(monthly.crisis_window ?? null);
        setWeekdays(weekday.weekdays ?? []);
        setHours(hourly.hours ?? []);
      })
      .catch(() => undefined)
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const pick = (pair: { light: string; dark: string }) => (isDark ? pair.dark : pair.light);

  // Every headline number below is computed from the fetched data, never hardcoded, so the copy
  // cannot drift away from the chart beneath it as the ETL keeps running.
  const facts = useMemo(() => {
    if (!months.length) return null;
    const byMonth = Object.fromEntries(months.map((m) => [m.month, m]));
    const crisisStart = crisis ? byMonth[crisis.start] : undefined;
    const crisisEnd = crisis ? byMonth[crisis.end] : undefined;
    const crisisStartIndex = crisis ? months.findIndex((m) => m.month === crisis.start) : -1;
    const beforeCrisis = crisisStartIndex > 0 ? months[crisisStartIndex - 1] : undefined;
    const latest = months[months.length - 1];

    const bestDay = weekdays.length
      ? weekdays.reduce((a, b) => (b.on_time_pct > a.on_time_pct ? b : a))
      : null;
    const worstDay = weekdays.length
      ? weekdays.reduce((a, b) => (b.on_time_pct < a.on_time_pct ? b : a))
      : null;
    // Ignore near-empty hours: a 3am slot with 60 flights swinging on a handful of departures is
    // noise, and naming it "the worst hour to fly" would be a claim the sample cannot support.
    const meaningfulHours = hours.filter((h) => h.flights >= 500);
    const bestHour = meaningfulHours.length
      ? meaningfulHours.reduce((a, b) => (b.on_time_pct > a.on_time_pct ? b : a))
      : null;
    const worstHour = meaningfulHours.length
      ? meaningfulHours.reduce((a, b) => (b.on_time_pct < a.on_time_pct ? b : a))
      : null;

    return { crisisStart, crisisEnd, beforeCrisis, latest, bestDay, worstDay, bestHour, worstHour };
  }, [months, crisis, weekdays, hours]);

  const monthLabel = (month: string) => shortMonth(month, locale);

  const weekdayData = weekdays.map((row) => ({ ...row, label: t(WEEKDAY_KEYS[row.dow]) }));
  const hourData = hours.map((row) => ({ ...row, label: `${String(row.hour).padStart(2, "0")}` }));

  const axisStyle = { fontSize: 11, fill: "hsl(var(--muted-foreground))" };
  const tooltipStyle = {
    backgroundColor: "hsl(var(--card))",
    border: "1px solid hsl(var(--border))",
    borderRadius: "0.5rem",
    fontSize: "12px",
    color: "hsl(var(--foreground))",
  };

  if (loading) {
    return (
      <PageLayout>
        <p className="py-20 text-center text-muted-foreground">{t("common.loading")}</p>
      </PageLayout>
    );
  }

  return (
    <PageLayout>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-foreground sm:text-3xl">{t("insights.title")}</h1>
        <p className="mt-1 text-sm text-muted-foreground sm:text-base">{t("insights.subtitle")}</p>
      </div>

      {/* Charts render left-to-right in both languages: time on a chart axis reads forward
          regardless of script, and mirroring it makes the trend line read backwards. */}
      <div className="space-y-6" dir="ltr">
        {/* ── Story 1: the disruption ── */}
        {facts?.crisisStart && facts.crisisEnd && crisis && (
          <div dir={isRTL ? "rtl" : "ltr"}>
            <StoryCard
              title={t("insights.sky.title")}
              body={fill(t("insights.sky.body"), {
                crisisStart: monthLabel(crisis.start),
                crisisEnd: monthLabel(crisis.end),
                foreignCancel: `${facts.crisisStart.foreign_cancelled_pct.toFixed(0)}%`,
                israeliCancel: `${facts.crisisStart.israeli_cancelled_pct.toFixed(0)}%`,
                foreignApril: facts.crisisEnd.foreign_scheduled.toLocaleString(locale),
                foreignBaseline: (facts.beforeCrisis?.foreign_scheduled ?? 0).toLocaleString(locale),
                // Israeli volume in the same month, so the contrast is stated as two counts the
                // reader can check against the chart rather than as a claim about "the schedule".
                israeliApril: facts.crisisEnd.israeli_scheduled.toLocaleString(locale),
              })}
              caption={t("insights.sky.caption")}
            >
              {/* Volume and cancellation rate are different measures on wildly different scales
                  (0-10,000 flights vs 0-100%). They get two charts sharing one x-axis, never one
                  chart with two y-scales: on a shared count axis the 81% cancellation month sat
                  flat against the baseline and the whole point of the card disappeared. */}
              <div dir="ltr" className="space-y-4">
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">
                    {t("insights.scheduled")}
                  </p>
                  <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
                    <BarChart data={months} margin={{ top: 8, right: 8, bottom: 0, left: -4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                      {/* Band comes from the API's derived window, so it follows the data rather
                          than needing an edit if another disruption occurs. */}
                      <ReferenceArea
                        x1={crisis.start}
                        x2={crisis.end}
                        fill={pick(ANNOTATION_COLOR)}
                        fillOpacity={0.09}
                      />
                      <XAxis dataKey="month" tickFormatter={monthLabel} tick={axisStyle} tickLine={false} axisLine={false} />
                      <YAxis tick={axisStyle} tickLine={false} axisLine={false} width={52} tickFormatter={compact} />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        labelFormatter={(value) => monthLabel(String(value))}
                        formatter={(value: number, name: string) => [value.toLocaleString(locale), name]}
                      />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar
                        dataKey="israeli_scheduled"
                        name={t("insights.israeli")}
                        stackId="a"
                        fill={pick(NATIONALITY_COLORS.israeli)}
                      />
                      <Bar
                        dataKey="foreign_scheduled"
                        name={t("insights.foreign")}
                        stackId="a"
                        fill={pick(NATIONALITY_COLORS.foreign)}
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">
                    {t("insights.cancelledPct")}
                  </p>
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={months} margin={{ top: 8, right: 8, bottom: 0, left: -4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                      <ReferenceArea
                        x1={crisis.start}
                        x2={crisis.end}
                        fill={pick(ANNOTATION_COLOR)}
                        fillOpacity={0.09}
                      />
                      <XAxis dataKey="month" tickFormatter={monthLabel} tick={axisStyle} tickLine={false} axisLine={false} />
                      <YAxis unit="%" domain={[0, 100]} tick={axisStyle} tickLine={false} axisLine={false} width={52} />
                      <Tooltip
                        contentStyle={tooltipStyle}
                        labelFormatter={(value) => monthLabel(String(value))}
                        formatter={(value: number, name: string) => [`${value}%`, name]}
                      />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Line
                        type="monotone"
                        dataKey="israeli_cancelled_pct"
                        name={t("insights.israeli")}
                        stroke={pick(NATIONALITY_COLORS.israeli)}
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        activeDot={{ r: 6 }}
                      />
                      <Line
                        type="monotone"
                        dataKey="foreign_cancelled_pct"
                        name={t("insights.foreign")}
                        stroke={pick(NATIONALITY_COLORS.foreign)}
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        activeDot={{ r: 6 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </StoryCard>
          </div>
        )}

        {/* ── Story 2: Shabbat ── */}
        {facts?.bestDay && facts.worstDay && (
          <div dir={isRTL ? "rtl" : "ltr"}>
            <StoryCard
              title={t("insights.shabbat.title")}
              body={fill(t("insights.shabbat.body"), {
                satPct: `${facts.bestDay.on_time_pct.toFixed(1)}%`,
                gap: (facts.bestDay.on_time_pct - facts.worstDay.on_time_pct).toFixed(0),
              })}
              caption={t("insights.shabbat.caption")}
            >
              <div dir="ltr">
                <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
                  <BarChart data={weekdayData} margin={{ top: 8, right: 8, bottom: 0, left: -4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="label" tick={axisStyle} tickLine={false} axisLine={false} />
                    <YAxis unit="%" tick={axisStyle} tickLine={false} axisLine={false} width={52} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      formatter={(value: number) => [`${value}%`, t("insights.onTimePct")]}
                    />
                    <Bar dataKey="on_time_pct" name={t("insights.onTimePct")} radius={[4, 4, 0, 0]}>
                      {weekdayData.map((row) => (
                        // The standout day is emphasised; the rest recede. Same hue, so this is
                        // emphasis rather than a second category needing a legend entry.
                        <Cell
                          key={row.dow}
                          fill={pick(SINGLE_SERIES_COLOR)}
                          fillOpacity={row.dow === facts.bestDay?.dow ? 1 : 0.45}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </StoryCard>
          </div>
        )}

        {/* ── Story 3: the afternoon wall ── */}
        {facts?.bestHour && facts.worstHour && (
          <div dir={isRTL ? "rtl" : "ltr"}>
            <StoryCard
              title={t("insights.wall.title")}
              body={fill(t("insights.wall.body"), {
                worstHour: String(facts.worstHour.hour).padStart(2, "0"),
                worstPct: `${facts.worstHour.on_time_pct.toFixed(1)}%`,
                bestHour: String(facts.bestHour.hour).padStart(2, "0"),
                bestPct: `${facts.bestHour.on_time_pct.toFixed(1)}%`,
              })}
              caption={t("insights.wall.caption")}
            >
              <div dir="ltr">
                <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
                  <LineChart data={hourData} margin={{ top: 8, right: 8, bottom: 0, left: -4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="label" tick={axisStyle} tickLine={false} axisLine={false} interval={2} />
                    <YAxis unit="%" tick={axisStyle} tickLine={false} axisLine={false} width={52} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      labelFormatter={(value) => `${value}:00`}
                      formatter={(value: number) => [`${value}%`, t("insights.onTimePct")]}
                    />
                    <Line
                      type="monotone"
                      dataKey="on_time_pct"
                      name={t("insights.onTimePct")}
                      stroke={pick(SINGLE_SERIES_COLOR)}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </StoryCard>
          </div>
        )}

        {/* ── Story 4: market share ── */}
        {facts?.latest && facts.beforeCrisis && (
          <div dir={isRTL ? "rtl" : "ltr"}>
            <StoryCard
              title={t("insights.share.title")}
              body={fill(t("insights.share.body"), {
                shareBefore: `${facts.beforeCrisis.israeli_share_pct.toFixed(0)}%`,
                shareNow: `${facts.latest.israeli_share_pct.toFixed(0)}%`,
              })}
              caption={t("insights.share.caption")}
            >
              <div dir="ltr">
                <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
                  <LineChart data={months} margin={{ top: 8, right: 8, bottom: 0, left: -4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    {crisis && (
                      <ReferenceArea
                        x1={crisis.start}
                        x2={crisis.end}
                        fill={pick(ANNOTATION_COLOR)}
                        fillOpacity={0.09}
                      />
                    )}
                    <XAxis dataKey="month" tickFormatter={monthLabel} tick={axisStyle} tickLine={false} axisLine={false} />
                    <YAxis unit="%" domain={[0, 100]} tick={axisStyle} tickLine={false} axisLine={false} width={52} />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      labelFormatter={(value) => monthLabel(String(value))}
                      formatter={(value: number) => [`${value}%`, t("insights.israeli")]}
                    />
                    <Line
                      type="monotone"
                      dataKey="israeli_share_pct"
                      name={t("insights.israeli")}
                      stroke={pick(NATIONALITY_COLORS.israeli)}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </StoryCard>
          </div>
        )}
      </div>
    </PageLayout>
  );
};

export default Insights;

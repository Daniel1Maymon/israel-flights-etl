/**
 * Chart palette and formatting shared by the /insights and /recovery pages.
 *
 * PALETTE PROVENANCE — do not swap these hex values casually.
 *
 * The two-series categorical pair (Israeli vs foreign) was validated in both modes:
 *   light #2a78d6/#eb6834 — CVD ΔE 24.7, normal-vision ΔE 33.6, contrast >= 3:1  → all pass
 *   dark  #3987e5/#d95926 — CVD ΔE 26.8, normal-vision ΔE 31.8, contrast >= 3:1  → all pass
 *
 * The four recovery buckets are deliberately NOT a categorical palette. Red-vs-amber cannot clear
 * the normal-vision separation floor anywhere inside the dark-mode lightness band — every amber
 * bright enough to separate from red overshoots the band — and neither can two steps of one hue in
 * a diverging arrangement. They are STATUS colors instead: they reuse the site's existing
 * success/warning/destructive tokens (the same ones the leaderboard badges already use, so a
 * returning visitor reads them without relearning), and every place they appear also carries an
 * icon, a text label and the numeric recovery percentage. Colour is never the sole encoding.
 */

/** Israeli vs foreign carriers. Fixed assignment — colour follows the entity, never its rank. */
export const NATIONALITY_COLORS = {
  israeli: { light: "#2a78d6", dark: "#3987e5" },
  foreign: { light: "#eb6834", dark: "#d95926" },
} as const;

/** Single-series charts (weekday, hour) use one hue; the title names the series, so no legend. */
export const SINGLE_SERIES_COLOR = { light: "#2a78d6", dark: "#3987e5" } as const;

/** Muted ink for the cancellation-rate reference line, so it reads as annotation not as a series. */
export const ANNOTATION_COLOR = { light: "#52514e", dark: "#c3c2b7" } as const;

export type RecoveryBucket = "never_returned" | "partial" | "recovered" | "expanded";

/**
 * Status styling per bucket. Tailwind classes rather than raw hex: they inherit the site's
 * light/dark token values, which are already contrast-checked for badge text.
 */
export const BUCKET_STYLES: Record<
  RecoveryBucket,
  { badge: string; dot: string; chart: { light: string; dark: string } }
> = {
  never_returned: {
    badge: "bg-destructive text-white",
    dot: "bg-destructive",
    chart: { light: "#cf3b3b", dark: "#e05252" },
  },
  partial: {
    badge: "bg-warning text-background",
    dot: "bg-warning",
    chart: { light: "#eda100", dark: "#c98500" },
  },
  recovered: {
    badge: "bg-success text-white",
    dot: "bg-success",
    chart: { light: "#1baf7a", dark: "#199e70" },
  },
  expanded: {
    badge: "bg-primary text-primary-foreground",
    dot: "bg-primary",
    chart: { light: "#2a78d6", dark: "#3987e5" },
  },
};

export const BUCKET_ORDER: RecoveryBucket[] = [
  "never_returned",
  "partial",
  "recovered",
  "expanded",
];

/** Weekday order follows PostgreSQL DOW (0 = Sunday), matching the API. */
export const WEEKDAY_KEYS = [
  "insights.dow.sun",
  "insights.dow.mon",
  "insights.dow.tue",
  "insights.dow.wed",
  "insights.dow.thu",
  "insights.dow.fri",
  "insights.dow.sat",
] as const;

/** 'YYYY-MM' -> a short label the month axis can show without overlapping. */
export const shortMonth = (month: string, locale: string) => {
  const [year, m] = month.split("-");
  const d = new Date(Number(year), Number(m) - 1, 1);
  return d.toLocaleDateString(locale, { month: "short", year: "2-digit" });
};

export const formatPct = (value: number | null | undefined) =>
  value == null ? "—" : `${value.toFixed(1)}%`;

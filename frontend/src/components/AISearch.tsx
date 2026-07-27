import { useState, useEffect, KeyboardEvent } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { useIsMobile } from "@/hooks/use-mobile";
import { API_ENDPOINTS } from "@/config/api";
import { Sparkles, Loader2, Database } from "lucide-react";

interface AISearchResponse {
  answer: string | null;
  rows: Record<string, unknown>[];
  columns: string[];
  source: "handler" | "fallback" | null;
  refused: boolean;
  reason: string | null;
  data_start?: string | null; // ISO dates, sent only with reason="no_data"
  data_end?: string | null;
}

// A refusal's wording comes from the backend (services/refusal_text.py), which also records it in
// ai_events — so what the user reads is what the admin dashboard replays. This copy exists only for
// a response that arrives with answer: null, i.e. an older backend behind a cached deploy. Keep it
// identical to the server's string: there are two things a user may see, an answer from the data or
// this one, and a stale client must not invent a third.
const GENERIC_REFUSAL = {
  en: "I don't have data that answers that. You can ask about flights at Ben Gurion — airlines, punctuality, delays, cancellations and destinations.",
  he: "אין לי נתונים שעונים על השאלה הזו. אפשר לשאול על טיסות בנתב\"ג — חברות תעופה, דיוק בזמנים, עיכובים, ביטולים ויעדים.",
};

export const AISearch = () => {
  const { t, language } = useLanguage();
  const isMobile = useIsMobile();
  const isHe = language === "he";
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AISearchResponse | null>(null);
  const [failed, setFailed] = useState(false);
  // Powers the provenance label above an answer ("Based on 158,977 flights"). Best-effort: if the
  // stats call fails we fall back to the generic wording rather than showing a placeholder count.
  const [totalFlights, setTotalFlights] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(API_ENDPOINTS.STATS_OVERVIEW)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { total?: number } | null) => {
        if (!cancelled && typeof data?.total === "number") setTotalFlights(data.total);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const localeNum = (n: number) => n.toLocaleString(isHe ? "he-IL" : "en-US");

  // Headline claim on the card: rounded DOWN to the nearest thousand so "over N" stays true
  // between ETL runs — the exact count belongs above the answer, not in the pitch.
  const corpusLabel =
    totalFlights === null || totalFlights < 1000
      ? null
      : t("ai.basedOnOver").replace("{count}", localeNum(Math.floor(totalFlights / 1000) * 1000));

  const ask = async () => {
    const q = question.trim();
    if (!q || loading) return;
    setLoading(true);
    setResult(null);
    setFailed(false);
    try {
      const res = await fetch(API_ENDPOINTS.AI_SEARCH, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include", // carry the rankair_uid cookie for per-user limits
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok) throw new Error(String(res.status));
      setResult((await res.json()) as AISearchResponse);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") ask();
  };

  const refusalText = (result: AISearchResponse) =>
    result.answer || (isHe ? GENERIC_REFUSAL.he : GENERIC_REFUSAL.en);

  const COLUMN_LABELS: Record<string, { en: string; he: string }> = {
    airline_name: { en: "Airline", he: "חברת תעופה" },
    total_flights: { en: "Total flights", he: 'סה"כ טיסות' },
    num_flights: { en: "Flights", he: "מספר טיסות" },
    flights: { en: "Flights", he: "טיסות" },
    on_time_pct: { en: "On-time %", he: "% בזמן" },
    cancel_pct: { en: "Cancelled %", he: "% ביטולים" },
    cancelled_pct: { en: "Cancelled %", he: "% ביטולים" },
    avg_delay_minutes: { en: "Avg delay (min)", he: "עיכוב ממוצע (דק')" },
    avg_delay: { en: "Avg delay (min)", he: "עיכוב ממוצע (דק')" },
    severe_delay_pct: { en: "Severe delay %", he: "% עיכוב חמור" },
    destination: { en: "Destination", he: "יעד" },
    location_city_en: { en: "Destination", he: "יעד" },
    country_en: { en: "Country", he: "מדינה" },
    terminal: { en: "Terminal", he: "טרמינל" },
  };

  const label = (c: string) => {
    const m = COLUMN_LABELS[c.toLowerCase()];
    if (m) return isHe ? m.he : m.en;
    return c.replace(/_/g, " ");
  };

  const fmt = (v: unknown) => {
    if (v === null || v === undefined) return "—";
    // numbers OR numeric strings (Postgres returns NUMERIC as a string) → round to 1 decimal
    const n = typeof v === "number" ? v : /^-?\d+(\.\d+)?$/.test(String(v).trim()) ? Number(v) : NaN;
    if (Number.isNaN(n)) return String(v);
    return Number.isInteger(n) ? String(n) : n.toFixed(1);
  };

  return (
    <div className="w-full max-w-3xl mx-auto" dir={isHe ? "rtl" : "ltr"}>
      {/* The AI query is the feature we want a first-time visitor to notice, so it reads as a
          dedicated panel — tinted card, own heading and explainer — rather than a second search
          box that could be mistaken for the destination lookup above it. */}
      <div className="rounded-2xl border border-primary/25 bg-gradient-to-b from-primary/[0.08] to-primary/[0.02] p-5 shadow-sm sm:p-6">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-primary px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-primary-foreground">
            {t("ai.badge")}
          </span>
          <h2 className="text-lg font-semibold text-foreground sm:text-xl">
            {t("ai.title")} <span aria-hidden="true">✨</span>
          </h2>
          {corpusLabel && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/25 bg-background/60 px-2.5 py-1 text-[11px] font-medium text-primary">
              <Database className="h-3 w-3" aria-hidden="true" />
              {corpusLabel}
            </span>
          )}
        </div>
        <p className="mt-2 text-sm text-muted-foreground">{t("ai.description")}</p>

        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={onKey}
            maxLength={500}
            // The full prompt clips mid-word inside a phone-width input, which reads as a broken
            // layout rather than a hint. Use a short one below the md breakpoint.
            placeholder={isMobile ? t("ai.placeholderShort") : t("ai.placeholder")}
            className="min-w-0 flex-1 rounded-xl border border-border bg-background px-4 py-3 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-primary sm:text-base"
          />
          <button
            onClick={ask}
            disabled={loading || !question.trim()}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Sparkles className="h-4 w-4" aria-hidden="true" />
            )}
            {t("ai.ask")}
          </button>
        </div>

        {failed && <p className="mt-3 text-sm text-destructive">{t("ai.error")}</p>}

        {result?.refused && (
          <div className="mt-4 rounded-xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
            {refusalText(result)}
          </div>
        )}

        {result && !result.refused && (
          <div className="mt-4 space-y-4">
            {/* Answer first, supporting rows below it. */}
            {/* No provenance label here: the card header already states the flight count, and
                repeating it directly under the input read as a duplicate. */}
            {result.answer && (
              <div className="rounded-xl border border-border bg-card px-4 py-3 text-[15px] leading-relaxed whitespace-pre-line">
                {result.answer}
              </div>
            )}
            {result.rows.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-border bg-card">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-muted-foreground">
                    <tr>
                      {result.columns.map((c) => (
                        <th key={c} className="px-3 py-2 text-start font-medium whitespace-nowrap">
                          {label(c)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, i) => (
                      <tr key={i} className="border-t border-border">
                        {result.columns.map((c) => (
                          <td key={c} className="px-3 py-2 whitespace-nowrap">
                            {fmt(row[c])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

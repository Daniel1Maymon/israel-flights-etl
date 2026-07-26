import { useState, KeyboardEvent } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { useIsMobile } from "@/hooks/use-mobile";
import { API_ENDPOINTS } from "@/config/api";
import { Sparkles, Loader2 } from "lucide-react";

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
  const { language } = useLanguage();
  const isMobile = useIsMobile();
  const isHe = language === "he";
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AISearchResponse | null>(null);
  const [failed, setFailed] = useState(false);

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
      <div className="flex items-center gap-2 rounded-2xl border border-border bg-card px-3 py-3 shadow-sm sm:px-4">
        <Sparkles className="h-5 w-5 text-primary shrink-0" aria-hidden="true" />
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKey}
          maxLength={500}
          // The full prompt is ~40 chars and clips mid-word inside a phone-width input, which
          // reads as a broken layout rather than a hint. Use a short one below the md breakpoint.
          placeholder={
            isHe
              ? isMobile
                ? "שאלו אותי על חברות התעופה…"
                : "שאלו אותי כל דבר על ביצועי חברות התעופה…"
              : isMobile
                ? "Ask about airline performance…"
                : "Ask me anything about airline performance…"
          }
          className="min-w-0 flex-1 bg-transparent outline-none text-sm placeholder:text-muted-foreground sm:text-base"
        />
        <button
          onClick={ask}
          disabled={loading || !question.trim()}
          className="shrink-0 rounded-xl bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50 sm:px-4"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : isHe ? "שאל" : "Ask"}
        </button>
      </div>

      {failed && (
        <p className="mt-3 text-sm text-destructive">
          {isHe ? "שגיאת רשת. נסו שוב." : "Network error. Please try again."}
        </p>
      )}

      {result?.refused && (
        <div className="mt-3 rounded-xl border border-border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
          {refusalText(result)}
        </div>
      )}

      {result && !result.refused && (
        <div className="mt-4 space-y-4">
          {result.answer && (
            <div className="rounded-xl border border-border bg-card px-4 py-3 text-[15px] leading-relaxed whitespace-pre-line">
              {result.answer}
            </div>
          )}
          {result.rows.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-border">
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
  );
};

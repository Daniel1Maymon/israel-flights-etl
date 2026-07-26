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

const REFUSALS: Record<string, { en: string; he: string }> = {
  off_domain: {
    en: "I can help with questions about flights, airlines, delays, and destinations from Ben Gurion. Try asking differently.",
    he: "אני יכול לעזור בשאלות על טיסות, חברות תעופה, עיכובים ויעדים מנתב\"ג. נסו לשאול אחרת.",
  },
  unsupported: {
    en: "I can't answer that specific question yet.",
    he: "אני עדיין לא יכול לענות על השאלה הזו.",
  },
  limit: {
    en: "You've reached today's question limit. Please try again tomorrow.",
    he: "הגעתם למכסת השאלות היומית. נסו שוב מחר.",
  },
  budget: {
    en: "AI search is busy right now — please use the destination search above.",
    he: "חיפוש ה-AI עמוס כרגע — השתמשו בחיפוש היעדים למעלה.",
  },
  error: {
    en: "Something went wrong. Try rephrasing your question.",
    he: "משהו השתבש. נסו לנסח מחדש את השאלה.",
  },
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

  const monthYear = (iso: string) =>
    new Date(iso).toLocaleDateString(isHe ? "he-IL" : "en-GB", { month: "long", year: "numeric" });

  // "Nothing found" alone is ambiguous: it reads the same for a filter that matched nothing and
  // for a question this dataset can't answer at all (an airline that stopped flying to TLV leaves
  // no rows behind). Name the coverage window and what the data is, so the user can tell which.
  const noDataText = (r: AISearchResponse) => {
    const range =
      r.data_start && r.data_end
        ? isHe
          ? ` הנתונים שלנו מכסים טיסות בנתב"ג מ${monthYear(r.data_start)} עד ${monthYear(r.data_end)}.`
          : ` Our data covers Ben Gurion flights from ${monthYear(r.data_start)} to ${monthYear(r.data_end)}.`
        : "";
    const scope = isHe
      ? ' אנחנו רושמים רק טיסות שמופיעות בלוח הטיסות של נתב"ג, כך שחברת תעופה שאינה טסה לישראל כלל לא תופיע בנתונים.'
      : " We only record flights that appear in the Ben Gurion schedule, so an airline that isn't flying to Israel at all leaves no trace in the data.";
    return (isHe ? "לא נמצאו טיסות שמתאימות לשאלה." : "No flights in our data match that question.") + range + scope;
  };

  // The backend now sends the refusal wording it recorded in ai_events, so what the user reads and
  // what the admin dashboard replays are the same string. The maps below stay as a fallback for
  // responses from an older backend (or a cached deploy) that still send answer: null.
  const refusalText = (result: AISearchResponse) => {
    if (result.answer) return result.answer;
    if (result.reason === "no_data") return noDataText(result);
    const r = REFUSALS[result.reason || "error"] || REFUSALS.error;
    return isHe ? r.he : r.en;
  };

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

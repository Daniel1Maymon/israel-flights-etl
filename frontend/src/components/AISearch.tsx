import { useState, KeyboardEvent } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { API_ENDPOINTS } from "@/config/api";
import { Sparkles, Loader2 } from "lucide-react";

interface AISearchResponse {
  answer: string | null;
  rows: Record<string, unknown>[];
  columns: string[];
  source: "handler" | "fallback" | null;
  refused: boolean;
  reason: string | null;
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

  const refusalText = (reason: string | null) => {
    const r = REFUSALS[reason || "error"] || REFUSALS.error;
    return isHe ? r.he : r.en;
  };

  const fmt = (v: unknown) =>
    typeof v === "number" ? Number.isInteger(v) ? v : v.toFixed(1) : String(v ?? "—");

  return (
    <div className="w-full max-w-3xl mx-auto" dir={isHe ? "rtl" : "ltr"}>
      <div className="flex items-center gap-2 rounded-2xl border border-border bg-card px-4 py-3 shadow-sm">
        <Sparkles className="h-5 w-5 text-primary shrink-0" aria-hidden="true" />
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKey}
          maxLength={500}
          placeholder={isHe ? "שאלו אותי כל דבר על ביצועי חברות התעופה…" : "Ask me anything about airline performance…"}
          className="flex-1 bg-transparent outline-none text-base placeholder:text-muted-foreground"
        />
        <button
          onClick={ask}
          disabled={loading || !question.trim()}
          className="rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
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
          {refusalText(result.reason)}
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
                        {c.replace(/_/g, " ")}
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

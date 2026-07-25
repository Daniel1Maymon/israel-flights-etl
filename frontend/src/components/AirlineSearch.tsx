import { useState, useRef, useEffect, useCallback } from "react";
import { Search, Plane } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { API_ENDPOINTS } from "@/config/api";

/** Quick picks: the carriers most visitors arrive looking for. */
const POPULAR_AIRLINES = [
  { code: "LY", label: "EL AL", he: "אל על" },
  { code: "IZ", label: "ARKIA", he: "ארקיע" },
  { code: "6H", label: "ISRAIR", he: "ישראאיר" },
  { code: "W6", label: "WIZZ AIR", he: "ויז אייר" },
];

export interface AirlineOption {
  airline_code: string;
  airline_name: string;
  total_flights: number;
  is_israeli: boolean;
}

interface Props {
  /** Currently selected airline name, shown in the input. */
  value: string;
  onSelect: (airline: AirlineOption) => void;
}

export const AirlineSearch = ({ value, onSelect }: Props) => {
  const { t, language } = useLanguage();
  const [query, setQuery] = useState(value);
  const [isOpen, setIsOpen] = useState(false);
  const [suggestions, setSuggestions] = useState<AirlineOption[]>([]);
  const ref = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => setQuery(value), [value]);

  const fetchSuggestions = useCallback((q: string) => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    // An empty query still fetches: opening the box shows the busiest carriers rather than a
    // blank panel, which is the difference between a browsable picker and a guessing game.
    const params = new URLSearchParams({ min_flights: "20" });
    if (q.trim()) params.set("q", q.trim());

    fetch(`${API_ENDPOINTS.AIRLINE_DIRECTORY}?${params}`, { signal: controller.signal })
      .then((r) => r.json())
      .then((d: { airlines?: AirlineOption[] }) => setSuggestions((d.airlines ?? []).slice(0, 10)))
      .catch((err) => {
        if (err.name !== "AbortError") setSuggestions([]);
      });
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => fetchSuggestions(query === value ? "" : query), 250);
    return () => clearTimeout(timer);
  }, [query, value, fetchSuggestions]);

  useEffect(() => {
    const handleOut = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener("mousedown", handleOut);
    return () => document.removeEventListener("mousedown", handleOut);
  }, []);

  const select = (airline: AirlineOption) => {
    setQuery(airline.airline_name);
    onSelect(airline);
    setIsOpen(false);
  };

  return (
    <div className="w-full max-w-2xl mx-auto text-center">
      <div className="relative" ref={ref}>
        <Search className="absolute start-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground pointer-events-none z-10" />
        <input
          type="text"
          dir="ltr"
          value={query}
          placeholder={t("airlines.searchPlaceholder")}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          className="w-full ltr:pl-12 ltr:pr-5 rtl:pr-12 rtl:pl-5 py-4 text-lg rounded-2xl border-2 border-border bg-background focus:border-primary focus:outline-none transition-colors shadow-sm sm:py-5 sm:text-xl"
        />

        {isOpen && suggestions.length > 0 && (
          <div className="absolute z-50 max-h-80 w-full overflow-y-auto mt-2 bg-popover border border-border rounded-xl shadow-lg">
            {suggestions.map((a) => (
              <button
                key={a.airline_code}
                onMouseDown={(e) => {
                  e.preventDefault();
                  select(a);
                }}
                className="w-full px-4 py-3 text-sm hover:bg-accent transition-colors text-start flex items-center justify-between gap-2"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <Plane className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span className="truncate">{a.airline_name}</span>
                </span>
                <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                  {a.total_flights.toLocaleString()}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      <p className="mt-4 text-sm text-muted-foreground">
        {t("airlines.popular")}{" "}
        {POPULAR_AIRLINES.map((a, i) => (
          <span key={a.code}>
            <button
              onClick={() =>
                select({
                  airline_code: a.code,
                  airline_name: a.label,
                  total_flights: 0,
                  is_israeli: false,
                })
              }
              className="text-foreground hover:text-primary hover:underline underline-offset-2 transition-colors"
            >
              {language === "he" ? a.he : a.label}
            </button>
            {i < POPULAR_AIRLINES.length - 1 && (
              <span className="mx-1.5 text-muted-foreground/40">·</span>
            )}
          </span>
        ))}
      </p>
    </div>
  );
};

import { useState, useRef, useEffect, useCallback } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { API_ENDPOINTS } from "@/config/api";
import { Search } from "lucide-react";

const POPULAR_DESTINATIONS = [
  { en: "London",   he: "לונדון"   },
  { en: "Rome",     he: "רומא"     },
  { en: "New York", he: "ניו יורק" },
  { en: "Paris",    he: "פריז"     },
  { en: "Athens",   he: "אתונה"    },
];

interface CityOption {
  city_en: string;
  city_he: string | null;
}

interface DestinationSearchProps {
  value: string;
  /** Always called with the English city name; city_he is the canonical Hebrew word used
   *  to match ALL airports for that city in the performance query. */
  onChange: (cityEn: string, cityHe?: string | null) => void;
}

export const DestinationSearch = ({ value, onChange }: DestinationSearchProps) => {
  const { t, language } = useLanguage();
  const [query, setQuery] = useState(value);
  const [isOpen, setIsOpen] = useState(false);
  const [suggestions, setSuggestions] = useState<CityOption[]>([]);
  const ref = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Display name respects current language for known popular destinations
  const getDisplayName = (englishName: string): string => {
    if (language !== "he") return englishName;
    const match = POPULAR_DESTINATIONS.find((d) => d.en === englishName);
    return match ? match.he : englishName;
  };

  // Keep input in sync if parent value or language changes
  useEffect(() => {
    setQuery(getDisplayName(value));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, language]);

  /**
   * Deduplicate cities so each real-world city appears only once.
   *
   * The backend may return multiple rows for the same city because
   * location_city_en contains airport-area names like "LONDON",
   * "LONDON LUTON", and "STANSTED" (all serving London).
   *
   * Strategy: group by the FIRST Hebrew word. "לונדון לוטון" and
   * "לונדון" share the same first word "לונדון", so only the first
   * entry (shortest city_en) is kept. The canonical city_he stored
   * is the first Hebrew word, so the performance query later runs
   * location_he ILIKE '%לונדון%' and captures EVERY London airport.
   */
  const deduplicateCities = (raw: CityOption[]): CityOption[] => {
    const seen = new Set<string>();
    const result: CityOption[] = [];
    for (const city of raw) {
      const key = city.city_he ? city.city_he.split(" ")[0] : city.city_en;
      if (!seen.has(key)) {
        seen.add(key);
        result.push({
          city_en: city.city_en,
          city_he: city.city_he ? city.city_he.split(" ")[0] : null,
        });
      }
    }
    return result;
  };

  // Debounced server-side autocomplete
  const fetchSuggestions = useCallback((q: string) => {
    if (abortRef.current) abortRef.current.abort();

    if (!q.trim()) {
      setSuggestions([]);
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;

    const url = `${API_ENDPOINTS.DESTINATION_CITIES}?q=${encodeURIComponent(q.trim())}`;

    fetch(url, { signal: controller.signal })
      .then((r) => r.json())
      .then((data: { cities?: CityOption[] }) => {
        setSuggestions(deduplicateCities(data.cities ?? []));
      })
      .catch((err) => {
        if (err.name !== "AbortError") setSuggestions([]);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 300 ms debounce
  useEffect(() => {
    const timer = setTimeout(() => fetchSuggestions(query), 300);
    return () => clearTimeout(timer);
  }, [query, fetchSuggestions]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleOut = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener("mousedown", handleOut);
    return () => document.removeEventListener("mousedown", handleOut);
  }, []);

  const select = (cityEn: string, cityHe?: string | null) => {
    const displayName = language === "he" && cityHe ? cityHe : cityEn;
    setQuery(displayName);
    onChange(cityEn, cityHe ?? null);  // pass both for comprehensive airport matching
    setIsOpen(false);
    setSuggestions([]);
  };

  return (
    <div className="w-full max-w-2xl mx-auto text-center">
      <label className="block text-3xl font-semibold text-foreground mb-6">
        {t("search.whereFlying")}
      </label>

      <div className="relative" ref={ref}>
        <Search className="absolute start-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground pointer-events-none z-10" />
        <input
          type="text"
          dir="ltr"
          value={query}
          placeholder={t("search.placeholder")}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          className="w-full ltr:pl-12 ltr:pr-5 rtl:pr-12 rtl:pl-5 py-5 text-xl rounded-2xl border-2 border-border bg-background focus:border-primary focus:outline-none transition-colors shadow-sm"
        />

        {isOpen && suggestions.length > 0 && (
          <div className="absolute z-50 w-full mt-2 bg-popover border border-border rounded-xl shadow-lg overflow-hidden">
            {suggestions.map((city, i) => (
              <button
                key={`${city.city_en}-${i}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  select(city.city_en, city.city_he);
                }}
                className="w-full px-4 py-3 text-sm hover:bg-accent transition-colors text-start flex items-center justify-between gap-2"
              >
                <span>{city.city_en}</span>
                {city.city_he && (
                  <span className="text-muted-foreground text-xs shrink-0">{city.city_he}</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <p className="mt-5 text-sm text-muted-foreground">
        {t("search.popularDestinations")}{" "}
        {POPULAR_DESTINATIONS.map((dest, i) => (
          <span key={dest.en}>
            <button
              onClick={() => select(dest.en, dest.he)}
              className="text-foreground hover:text-primary hover:underline underline-offset-2 transition-colors"
            >
              {language === "he" ? dest.he : dest.en}
            </button>
            {i < POPULAR_DESTINATIONS.length - 1 && (
              <span className="mx-1.5 text-muted-foreground/40">·</span>
            )}
          </span>
        ))}
      </p>
    </div>
  );
};

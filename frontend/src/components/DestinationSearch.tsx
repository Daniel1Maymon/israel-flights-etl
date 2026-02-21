import { useState, useMemo, useRef, useEffect } from "react";
import { useApiData } from "@/hooks/useApiData";
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

interface DestinationSearchProps {
  value: string;
  onChange: (destination: string) => void;
}

export const DestinationSearch = ({ value, onChange }: DestinationSearchProps) => {
  const { t, language } = useLanguage();
  const [query, setQuery] = useState(value);
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Return the localised display name for a known English destination
  const getDisplayName = (englishName: string): string => {
    if (language !== "he") return englishName;
    const match = POPULAR_DESTINATIONS.find((d) => d.en === englishName);
    return match ? match.he : englishName;
  };

  // When the user types a Hebrew popular name, resolve it back to English for filtering
  const toEnglishQuery = (q: string): string => {
    const match = POPULAR_DESTINATIONS.find((d) => d.he === q);
    return match ? match.en : q;
  };

  // Keep input in sync if parent value or language changes
  useEffect(() => {
    setQuery(getDisplayName(value));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, language]);

  const { data: destinationsData } = useApiData(API_ENDPOINTS.DESTINATIONS);

  const allDestinations = useMemo(() => {
    if (!destinationsData) return [];
    const list: unknown[] = Array.isArray(destinationsData)
      ? destinationsData
      : Array.isArray((destinationsData as Record<string, unknown>)?.destinations)
        ? ((destinationsData as Record<string, unknown>).destinations as unknown[])
        : [];
    return list
      .map((d) => (d as Record<string, unknown>).destination ?? d)
      .filter((d): d is string => typeof d === "string" && d.trim() !== "")
      .sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
  }, [destinationsData]);

  const suggestions = useMemo(() => {
    // Resolve Hebrew display names back to English before filtering
    const q = toEnglishQuery(query.trim()).toLowerCase();
    if (!q) return allDestinations.slice(0, 8);
    return allDestinations.filter((d) => d.toLowerCase().includes(q)).slice(0, 8);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, allDestinations]);

  useEffect(() => {
    const handleOut = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false);
    };
    document.addEventListener("mousedown", handleOut);
    return () => document.removeEventListener("mousedown", handleOut);
  }, []);

  const select = (dest: string) => {
    setQuery(getDisplayName(dest)); // show localised name in the input
    onChange(dest);                 // always pass the English value up for API use
    setIsOpen(false);
  };

  return (
    // No dir override — flows naturally with the page (LTR or RTL)
    <div className="w-full max-w-2xl mx-auto text-center">
      <label className="block text-3xl font-semibold text-foreground mb-6">
        {t("search.whereFlying")}
      </label>

      <div className="relative" ref={ref}>
        {/* start-* mirrors to right in RTL automatically */}
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
          // In LTR icon is on the left  → large left padding, small right padding
          // In RTL icon is on the right → large right padding, small left padding
          className="w-full ltr:pl-12 ltr:pr-5 rtl:pr-12 rtl:pl-5 py-5 text-xl rounded-2xl border-2 border-border bg-background focus:border-primary focus:outline-none transition-colors shadow-sm"
        />

        {isOpen && suggestions.length > 0 && (
          <div className="absolute z-50 w-full mt-2 bg-popover border border-border rounded-xl shadow-lg overflow-hidden">
            {suggestions.map((dest, i) => (
              <button
                key={`${dest}-${i}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  select(dest);
                }}
                // text-start = left in LTR, right in RTL
                className="w-full px-4 py-3 text-sm hover:bg-accent transition-colors text-start"
              >
                {dest}
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
              onClick={() => select(dest.en)}
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

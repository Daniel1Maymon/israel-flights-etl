import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageToggle } from "@/components/LanguageToggle";
import { DatabaseToggle } from "@/components/DatabaseToggle";
import { DestinationSearch } from "@/components/DestinationSearch";
import { AISearch } from "@/components/AISearch";
import { StatsBar } from "@/components/StatsBar";
import {
  DestinationPerformanceTable,
  type AirlinePerformanceRow,
} from "@/components/DestinationPerformanceTable";
import { useLanguage } from "@/contexts/LanguageContext";
import { Github, Linkedin } from "lucide-react";
import { API_ENDPOINTS } from "@/config/api";

const Index = () => {
  const [selectedCity, setSelectedCity] = useState("");
  const [selectedCityHe, setSelectedCityHe] = useState<string | null>(null);
  const [performanceData, setPerformanceData] = useState<AirlinePerformanceRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [topAirlines, setTopAirlines] = useState<AirlinePerformanceRow[]>([]);
  const [topLoading, setTopLoading] = useState(true);
  const navigate = useNavigate();
  const { t, isRTL } = useLanguage();
  const abortRef = useRef<AbortController | null>(null);

  // Default leaderboard: fetch the FULL qualifying set (all airlines with >= 50
  // departures) so client-side column sorting ranks the whole DB; only the top 10
  // are displayed (see displayLimit on the table).
  useEffect(() => {
    const params = new URLSearchParams({ limit: "500", min_flights: "50" });
    fetch(`${API_ENDPOINTS.AIRLINES_TOP_ON_TIME}?${params.toString()}`)
      .then((r) => r.json())
      .then((data: { airlines?: AirlinePerformanceRow[] }) => {
        setTopAirlines(data.airlines ?? []);
      })
      .catch(() => setTopAirlines([]))
      .finally(() => setTopLoading(false));
  }, []);

  // Fetch airline performance whenever selectedCity changes
  useEffect(() => {
    if (!selectedCity || selectedCity === "All") {
      setPerformanceData([]);
      return;
    }

    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);

    const params = new URLSearchParams({ city: selectedCity });
    if (selectedCityHe) params.append("city_he", selectedCityHe);
    const url = `${API_ENDPOINTS.DESTINATION_AIRLINE_PERFORMANCE}?${params.toString()}`;

    fetch(url, { signal: controller.signal })
      .then((r) => r.json())
      .then((data: { airlines?: AirlinePerformanceRow[] }) => {
        setPerformanceData(data.airlines ?? []);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setPerformanceData([]);
      })
      .finally(() => setLoading(false));
  }, [selectedCity, selectedCityHe]);

  const handleDestinationChange = (cityEn: string, cityHe?: string | null) => {
    setSelectedCity(cityEn || "All");
    setSelectedCityHe(cityHe ?? null);
  };

  return (
    <div className="min-h-screen bg-background" dir={isRTL ? "rtl" : "ltr"}>
      <div className="container mx-auto px-4 max-w-7xl">
        {/* Compact top bar */}
        <div className="py-4 mb-4 border-b border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <img src="/favicon.png" alt="RankAir" className="h-10 w-10 rounded-xl" />
              <span className="text-2xl font-bold text-foreground">
                <span className="sm:hidden">RankAir</span>
                <span className="hidden sm:inline">{t("dashboard.title")}</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="hidden sm:block">
                <DatabaseToggle
                  isDatabaseMode={false}
                  onToggle={() => navigate("/flight-board")}
                />
              </div>
              <LanguageToggle />
              <ThemeToggle />
            </div>
          </div>
          {/* Flight board button — mobile only, full width below logo row */}
          <div className="mt-2 sm:hidden">
            <DatabaseToggle
              isDatabaseMode={false}
              onToggle={() => navigate("/flight-board")}
            />
          </div>
        </div>

        {/* Overview stats (departures) */}
        <div className="mb-4 max-w-md mx-auto">
          <StatsBar />
        </div>

        {/* Subtitle */}
        <div className="mb-8 text-center space-y-1">
          <p className="text-lg text-muted-foreground">{t("dashboard.subtitle.line1")}</p>
          <p className="text-base text-muted-foreground/70">{t("dashboard.subtitle.line2")}</p>
        </div>

        {/* Hero search */}
        <div className="py-8 mb-6">
          <DestinationSearch value={selectedCity} onChange={handleDestinationChange} />
        </div>

        {/* AI natural-language search */}
        <div className="mb-10">
          <AISearch />
        </div>

        {/* Airline performance table — city results when a city is chosen,
            otherwise the default Top-10-by-on-time leaderboard. */}
        {selectedCity && selectedCity !== "All" ? (
          <DestinationPerformanceTable
            city={selectedCity}
            cityHe={selectedCityHe}
            data={performanceData}
            loading={loading}
          />
        ) : (
          <DestinationPerformanceTable
            city=""
            data={topAirlines}
            loading={topLoading}
            title={t("performance.topTableTitle")}
            initialSortField="on_time_pct"
            initialSortDir="desc"
            displayLimit={10}
          />
        )}

        {/* Credits */}
        <div className="mt-10 pb-8 text-center text-xs text-muted-foreground">
          <div className="flex flex-col items-center gap-1" dir="ltr">
            <span className="inline-flex items-center gap-1">
              <Github className="h-3.5 w-3.5" aria-hidden="true" />
              <span>GitHub:</span>{" "}
              <a
                href="https://github.com/Daniel1Maymon/israel-flights-etl"
                className="underline underline-offset-2 hover:text-foreground"
                target="_blank"
                rel="noreferrer"
              >
                israel-flights-etl
              </a>
            </span>
            <span className="inline-flex items-center gap-1">
              <Linkedin className="h-3.5 w-3.5" aria-hidden="true" />
              <span>LinkedIn:</span>{" "}
              <a
                href="https://www.linkedin.com/in/daniel-maymon/"
                className="underline underline-offset-2 hover:text-foreground"
                target="_blank"
                rel="noreferrer"
              >
                daniel-maymon
              </a>
            </span>
            <span>Data source: data.gov.il</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Index;

import { useState, useEffect, useRef } from "react";
import { PageLayout } from "@/components/PageLayout";
import { DestinationSearch } from "@/components/DestinationSearch";
import { AISearch } from "@/components/AISearch";
import { StatsBar } from "@/components/StatsBar";
import {
  DestinationPerformanceTable,
  type AirlinePerformanceRow,
} from "@/components/DestinationPerformanceTable";
import { useLanguage } from "@/contexts/LanguageContext";
import { API_ENDPOINTS } from "@/config/api";

const Index = () => {
  const [selectedCity, setSelectedCity] = useState("");
  const [selectedCityHe, setSelectedCityHe] = useState<string | null>(null);
  const [performanceData, setPerformanceData] = useState<AirlinePerformanceRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [topAirlines, setTopAirlines] = useState<AirlinePerformanceRow[]>([]);
  const [topLoading, setTopLoading] = useState(true);
  const { t } = useLanguage();
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
    <PageLayout>
      {/* Overview stats */}
      <div className="mb-4 max-w-3xl mx-auto">
        <StatsBar />
      </div>

      {/* Subtitle */}
      <div className="mb-6 text-center space-y-1 sm:mb-8">
        <p className="text-base text-muted-foreground sm:text-lg">{t("dashboard.subtitle.line1")}</p>
        <p className="text-sm text-muted-foreground/70 sm:text-base">{t("dashboard.subtitle.line2")}</p>
      </div>

      {/* Two distinct ways in: a plain destination lookup, or the AI query over the flight
          database. They used to be near-identical input boxes and were easy to confuse, so they
          are now separate blocks split by an explicit OR divider. */}
      <div className="pt-2 sm:pt-4">
        <DestinationSearch value={selectedCity} onChange={handleDestinationChange} />
      </div>

      <div className="relative mx-auto my-6 max-w-3xl sm:my-8">
        <div className="absolute inset-0 flex items-center" aria-hidden="true">
          <div className="w-full border-t border-border" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-background px-4 text-xs font-medium uppercase tracking-widest text-muted-foreground">
            {t("search.or")}
          </span>
        </div>
      </div>

      {/* AI natural-language search */}
      <div className="mb-8 sm:mb-12">
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
    </PageLayout>
  );
};

export default Index;

import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { AirlineTable } from "@/components/AirlineTable";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageToggle } from "@/components/LanguageToggle";
import { DatabaseToggle } from "@/components/DatabaseToggle";
import { DestinationSearch } from "@/components/DestinationSearch";
import { useLanguage } from "@/contexts/LanguageContext";
import { useAirlineData, type AirlineBackendKPI } from "@/hooks/useAirlineData";
import { type AirlineKPI } from "@/lib/mockData.ts";
import { Plane, BarChart3, Github, Linkedin } from "lucide-react";
import { API_ENDPOINTS } from "@/config/api";

const Index = () => {
  const [selectedAirport, setSelectedAirport] = useState("London");
  const navigate = useNavigate();
  const { t, isRTL } = useLanguage();

  // Build query params — destination only (date range kept at all-time default)
  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    if (selectedAirport && selectedAirport !== "All") {
      params.append("destination", selectedAirport);
    }
    return params.toString();
  }, [selectedAirport]);

  const AIRLINES_API_ENDPOINT = `${API_ENDPOINTS.AIRLINES_STATS}${queryString ? `?${queryString}` : ""}`;

  // Fetch airline performance data
  const { data: airlineData } = useAirlineData(AIRLINES_API_ENDPOINT);

  // Convert API response to the AirlineKPI shape used by AirlineTable
  const convertToMockFormat = (airlines: AirlineBackendKPI[]): AirlineKPI[] => {
    if (!Array.isArray(airlines) || airlines.length === 0) return [];
    return airlines
      .filter((a) => a && a.airline_name)
      .map((a, i) => ({
        airline: a.airline_name || `Unknown-${i}`,
        onTimePercentage: a.on_time_percentage || 0,
        avgDelayMinutes: a.avg_delay_all_flights ?? a.avg_delay_minutes ?? 0,
        cancellationPercentage: a.cancellation_percentage || 0,
        flightCount: a.total_flights || 0,
        destinations: [],
      }));
  };

  const realAirlines = useMemo<AirlineBackendKPI[]>(
    () => (Array.isArray(airlineData) ? airlineData : []),
    [airlineData]
  );

  const allAirlines: AirlineKPI[] = convertToMockFormat(realAirlines);
  // Only show airlines with enough flights to be meaningful
  const filteredAirlines = allAirlines.filter((a) => a.flightCount >= 20);

  const handleDestinationChange = (dest: string) => {
    setSelectedAirport(dest || "All");
  };

  return (
    <div className="min-h-screen bg-background" dir={isRTL ? "rtl" : "ltr"}>
      <div className="container mx-auto px-4 max-w-7xl">
        {/* Compact top bar */}
        <div className="flex items-center justify-between py-4 mb-8 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 p-2 bg-gradient-to-r from-primary to-info rounded-lg shadow-[var(--shadow-glow)]">
              <Plane className="h-5 w-5 text-primary-foreground" />
              <BarChart3 className="h-5 w-5 text-primary-foreground" />
            </div>
            <span className="text-lg font-bold text-foreground">{t("dashboard.title")}</span>
          </div>
          <div className="flex items-center gap-2">
            <DatabaseToggle
              isDatabaseMode={false}
              onToggle={() => navigate('/flight-board')}
            />
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </div>

        {/* Hero search — the main focus of the page */}
        <div className="py-8 mb-10">
          <DestinationSearch value={selectedAirport} onChange={handleDestinationChange} />
        </div>

        {/* Airline comparison results */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <AirlineTable data={filteredAirlines} isTop={true} limit={5} />
          <AirlineTable data={filteredAirlines} isTop={false} limit={5} />
        </div>

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

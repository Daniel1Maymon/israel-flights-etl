import { useState, useMemo, useRef, useEffect } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { useLanguage } from "@/contexts/LanguageContext";
import { useApiData } from "@/hooks/useApiData";
import { Search, MapPin, Plane, Globe, Building2 } from "lucide-react";
import { API_ENDPOINTS } from "@/config/api";

type SearchType = "airline" | "airport" | "country" | "city";

interface UnifiedSearchProps {
  selectedValue: string;
  onValueChange: (value: string, type: SearchType) => void;
  label: string;
  allowedTypes?: SearchType[];
  defaultType?: SearchType;
  resetSignal?: number;
}

export const UnifiedSearch = ({ selectedValue, onValueChange, label, allowedTypes, defaultType, resetSignal }: UnifiedSearchProps) => {
  const { t, isRTL } = useLanguage();
  
  // Determine default search type based on allowed types or prop
  const getDefaultType = (): SearchType => {
    if (defaultType) return defaultType;
    if (allowedTypes && allowedTypes.length > 0) return allowedTypes[0];
    return "airline";
  };
  
  const [searchType, setSearchType] = useState<SearchType>(getDefaultType());
  const [searchQuery, setSearchQuery] = useState("");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  
  // Fetch data based on search type
  const { data: airlinesData } = useApiData(API_ENDPOINTS.AIRLINES);
  const { data: destinationsData } = useApiData(API_ENDPOINTS.DESTINATIONS);
  
  // Process airlines
  const allAirlines = useMemo(() => {
    if (!airlinesData || airlinesData.length === 0) return [];
    return airlinesData
      .map((airline: any) => ({
        code: airline.airline_code || airline.code || '',
        name: airline.airline_name || airline.name || ''
      }))
      .filter((airline: { code: string; name: string }) => airline.name && airline.name.trim() !== '')
      .filter((airline: { code: string; name: string }, index: number, self: { code: string; name: string }[]) => 
        index === self.findIndex((a: { code: string; name: string }) => a.name.toLowerCase() === airline.name.toLowerCase())
      )
      .sort((a: { code: string; name: string }, b: { code: string; name: string }) => 
        a.name.toLowerCase().localeCompare(b.name.toLowerCase())
      )
      .map((a: { code: string; name: string }) => a.name);
  }, [airlinesData]);
  
  // Process airports (destinations)
  const allAirports = useMemo(() => {
    if (!destinationsData || destinationsData.length === 0) return [];
    // Handle both array and object responses
    const destinations = Array.isArray(destinationsData) 
      ? destinationsData 
      : (destinationsData as any)?.destinations || [];
    return destinations
      .map((dest: any) => dest.destination || dest)
      .filter((dest: string) => dest && dest.trim() !== '')
      .sort((a: string, b: string) => a.toLowerCase().localeCompare(b.toLowerCase()));
  }, [destinationsData]);
  
  // Fetch flights to extract countries and cities
  // Use pagination to get unique values efficiently (max size is 200 per backend)
  const { data: flightsResponse } = useApiData(`${API_ENDPOINTS.FLIGHTS}?page=1&size=200`);
  
  // Process countries and cities from flights
  const { countries, cities } = useMemo(() => {
    // Handle both array and object responses
    const flights = Array.isArray(flightsResponse)
      ? flightsResponse
      : (flightsResponse as any)?.data || [];
    
    if (!flights || flights.length === 0) {
      return { countries: [], cities: [] };
    }
    
    const countrySet = new Set<string>();
    const citySet = new Set<string>();
    
    flights.forEach((flight: any) => {
      if (flight.country_en && flight.country_en.trim()) {
        countrySet.add(flight.country_en.trim());
      }
      if (flight.location_city_en && flight.location_city_en.trim()) {
        citySet.add(flight.location_city_en.trim());
      }
    });
    
    return {
      countries: Array.from(countrySet).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase())),
      cities: Array.from(citySet).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()))
    };
  }, [flightsResponse]);
  
  // Get current search options based on type
  const getSearchOptions = (): string[] => {
    switch (searchType) {
      case "airline":
        return allAirlines;
      case "airport":
        return allAirports;
      case "country":
        return countries;
      case "city":
        return cities;
      default:
        return [];
    }
  };
  
  // Filter options based on search query
  const filteredOptions = useMemo(() => {
    const options = getSearchOptions();
    if (!searchQuery.trim()) return options;
    const searchLower = searchQuery.toLowerCase();
    return options.filter((option: string) => 
      option.toLowerCase().includes(searchLower)
    );
  }, [searchType, searchQuery, allAirlines, allAirports, countries, cities]);
  
  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (resetSignal === undefined) return;
    setSearchType(getDefaultType());
    setSearchQuery("");
    setIsDropdownOpen(false);
  }, [resetSignal, allowedTypes, defaultType]);
  
  const handleSelect = (value: string) => {
    onValueChange(value, searchType);
    setSearchQuery("");
    setIsDropdownOpen(false);
  };
  
  const getSearchTypeIcon = () => {
    switch (searchType) {
      case "airline":
        return <Plane className="h-4 w-4" />;
      case "airport":
        return <MapPin className="h-4 w-4" />;
      case "country":
        return <Globe className="h-4 w-4" />;
      case "city":
        return <Building2 className="h-4 w-4" />;
    }
  };
  
  const hasMultipleTypes = !allowedTypes || allowedTypes.length > 1;
  
  return (
    <div className="flex-1" ref={searchRef}>
      <label className="text-sm font-medium text-foreground mb-1 block text-left flex items-center gap-2">
        <Search className="h-4 w-4 text-primary" />
        {label}
      </label>
      <div className="flex gap-2">
        {/* Search Type Selector - only show if multiple types allowed */}
        {hasMultipleTypes && (
          <Select value={searchType} onValueChange={(value) => {
            setSearchType(value as SearchType);
            setSearchQuery("");
            setIsDropdownOpen(false);
          }}>
            <SelectTrigger className="w-[140px] bg-background border-border">
              <div className="flex items-center gap-2">
                {getSearchTypeIcon()}
                <SelectValue />
              </div>
            </SelectTrigger>
            <SelectContent>
              {(!allowedTypes || allowedTypes.includes("airline")) && (
                <SelectItem value="airline">
                  {t('filters.airline') || "Airline"}
                </SelectItem>
              )}
              {(!allowedTypes || allowedTypes.includes("airport")) && (
                <SelectItem value="airport">
                  {t('filters.airport') || "Airport"}
                </SelectItem>
              )}
              {(!allowedTypes || allowedTypes.includes("country")) && (
                <SelectItem value="country">
                  {t('filters.country') || "Country"}
                </SelectItem>
              )}
              {(!allowedTypes || allowedTypes.includes("city")) && (
                <SelectItem value="city">
                  {t('filters.city') || "City"}
                </SelectItem>
              )}
            </SelectContent>
          </Select>
        )}
        
        {/* Search Input */}
        <div className="relative flex-1">
          {!hasMultipleTypes && (
            <div className="absolute left-3 top-1/2 transform -translate-y-1/2 z-10 text-muted-foreground">
              {getSearchTypeIcon()}
            </div>
          )}
          <Input
            type="text"
            placeholder={
              searchType === "airline" ? (t('filters.searchAirline') || "Search airline...") :
              searchType === "airport" ? (t('filters.searchAirport') || "Search airport...") :
              searchType === "country" ? (t('filters.searchCountry') || "Search country...") :
              (t('filters.searchCity') || "Search city...")
            }
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setIsDropdownOpen(true);
            }}
            onFocus={() => setIsDropdownOpen(true)}
            className={hasMultipleTypes ? "bg-background border-border" : "pl-9 bg-background border-border"}
          />
          {isDropdownOpen && (searchQuery.trim() || filteredOptions.length > 0) && (
            <div className="absolute z-50 w-full mt-1 bg-popover border rounded-md shadow-lg max-h-[300px] overflow-y-auto">
              <div className="py-1">
                <div
                  className="px-2 py-1.5 text-sm cursor-pointer hover:bg-accent rounded-sm"
                  onClick={() => handleSelect("All")}
                >
                  {t('filters.all') || "All"}
                </div>
                {filteredOptions.length > 0 ? (
                  filteredOptions.map((option, index) => (
                    <div
                      key={`${searchType}-${option}-${index}`}
                      className="px-2 py-1.5 text-sm cursor-pointer hover:bg-accent rounded-sm"
                      onClick={() => handleSelect(option)}
                    >
                      {option}
                    </div>
                  ))
                ) : (
                  <div className="px-2 py-1.5 text-sm text-muted-foreground text-center">
                    {t('filters.noResults') || "No results found"}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

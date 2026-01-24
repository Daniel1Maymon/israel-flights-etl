export interface AirlineKPI {
  airline: string;
  onTimePercentage: number;
  avgDelayMinutes: number;
  cancellationPercentage: number;
  flightCount: number;
  destinations: string[];
}

export const mockAirlineData: AirlineKPI[] = [
  {
    airline: "Delta Air Lines",
    onTimePercentage: 87.2,
    avgDelayMinutes: 14.3,
    cancellationPercentage: 1.8,
    flightCount: 12453,
    destinations: ["New York", "Los Angeles", "Chicago", "Atlanta", "Miami"]
  },
  {
    airline: "Southwest Airlines",
    onTimePercentage: 84.6,
    avgDelayMinutes: 18.7,
    cancellationPercentage: 2.1,
    flightCount: 15678,
    destinations: ["Dallas", "Phoenix", "Las Vegas", "Denver", "Seattle"]
  },
  {
    airline: "American Airlines",
    onTimePercentage: 82.1,
    avgDelayMinutes: 21.4,
    cancellationPercentage: 2.5,
    flightCount: 14892,
    destinations: ["Miami", "Dallas", "Charlotte", "Philadelphia", "Phoenix"]
  },
  {
    airline: "United Airlines",
    onTimePercentage: 79.8,
    avgDelayMinutes: 24.1,
    cancellationPercentage: 2.8,
    flightCount: 13567,
    destinations: ["Chicago", "Denver", "San Francisco", "Houston", "Newark"]
  },
  {
    airline: "JetBlue Airways",
    onTimePercentage: 78.3,
    avgDelayMinutes: 26.8,
    cancellationPercentage: 3.2,
    flightCount: 8934,
    destinations: ["Boston", "New York", "Fort Lauderdale", "Orlando", "Long Beach"]
  },
  {
    airline: "Alaska Airlines",
    onTimePercentage: 76.9,
    avgDelayMinutes: 28.5,
    cancellationPercentage: 3.6,
    flightCount: 7821,
    destinations: ["Seattle", "Anchorage", "Portland", "San Francisco", "Los Angeles"]
  },
  {
    airline: "Spirit Airlines",
    onTimePercentage: 72.4,
    avgDelayMinutes: 34.2,
    cancellationPercentage: 4.7,
    flightCount: 6543,
    destinations: ["Fort Lauderdale", "Las Vegas", "Detroit", "Orlando", "Dallas"]
  },
  {
    airline: "Frontier Airlines",
    onTimePercentage: 69.7,
    avgDelayMinutes: 38.9,
    cancellationPercentage: 5.8,
    flightCount: 4912,
    destinations: ["Denver", "Orlando", "Las Vegas", "Phoenix", "Chicago"]
  },
  {
    airline: "Allegiant Air",
    onTimePercentage: 65.2,
    avgDelayMinutes: 45.3,
    cancellationPercentage: 7.2,
    flightCount: 3456,
    destinations: ["Las Vegas", "Orlando", "Phoenix", "Myrtle Beach", "St. Pete"]
  },
  {
    airline: "Sun Country Airlines",
    onTimePercentage: 61.8,
    avgDelayMinutes: 52.7,
    cancellationPercentage: 8.9,
    flightCount: 2187,
    destinations: ["Minneapolis", "Phoenix", "Las Vegas", "Dallas", "Denver"]
  }
];

export const getAllDestinations = (): string[] => {
  const destinations = new Set<string>();
  mockAirlineData.forEach(airline => {
    airline.destinations.forEach(dest => destinations.add(dest));
  });
  return Array.from(destinations).sort();
};

export const filterAirlinesByDestination = (destination: string): AirlineKPI[] => {
  if (!destination || destination === "All") return mockAirlineData;
  return mockAirlineData.filter(airline => 
    airline.destinations.includes(destination)
  );
};

export const getTopAirlines = (data: AirlineKPI[], limit = 5): AirlineKPI[] => {
  return [...data]
    .sort((a, b) => b.onTimePercentage - a.onTimePercentage)
    .slice(0, limit);
};

export const getBottomAirlines = (data: AirlineKPI[], limit = 5): AirlineKPI[] => {
  return [...data]
    .sort((a, b) => a.onTimePercentage - b.onTimePercentage)
    .slice(0, limit);
};
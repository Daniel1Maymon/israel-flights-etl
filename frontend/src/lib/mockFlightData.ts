export interface Flight {
  flight_id: string;
  airline_code: string;
  flight_number: string;
  direction: 'A' | 'D'; // A = Arrival, D = Departure
  location_iata: string;
  scheduled_time: string;
  actual_time: string;
  airline_name: string;
  location_en: string;
  location_he: string;
  location_city_en: string;
  country_en: string;
  country_he: string;
  terminal: string;
  checkin_counters: string;
  checkin_zone: string;
  status_en: string;
  status_he: string;
  delay_minutes: number;
  scrape_timestamp: string;
  raw_s3_path: string;
}

export const mockFlightData: Flight[] = [
  {
    flight_id: "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    airline_code: "LY",
    flight_number: "LY001",
    direction: "D",
    location_iata: "TLV",
    scheduled_time: "2024-01-15T08:30:00Z",
    actual_time: "2024-01-15T08:45:00Z",
    airline_name: "El Al Israel Airlines",
    location_en: "Ben Gurion Airport",
    location_he: "נמל התעופה בן גוריון",
    location_city_en: "Tel Aviv",
    country_en: "Israel",
    country_he: "ישראל",
    terminal: "3",
    checkin_counters: "1-12",
    checkin_zone: "A",
    status_en: "Boarding",
    status_he: "עלייה למטוס",
    delay_minutes: 15,
    scrape_timestamp: "2024-01-15T08:00:00Z",
    raw_s3_path: "s3://flight-data/raw/2024/01/15/ly001_tlv_0830.json"
  },
  {
    flight_id: "b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7",
    airline_code: "UA",
    flight_number: "UA123",
    direction: "A",
    location_iata: "TLV",
    scheduled_time: "2024-01-15T14:20:00Z",
    actual_time: "2024-01-15T14:35:00Z",
    airline_name: "United Airlines",
    location_en: "Ben Gurion Airport",
    location_he: "נמל התעופה בן גוריון",
    location_city_en: "Tel Aviv",
    country_en: "Israel",
    country_he: "ישראל",
    terminal: "3",
    checkin_counters: "15-25",
    checkin_zone: "B",
    status_en: "Landed",
    status_he: "נחת",
    delay_minutes: 15,
    scrape_timestamp: "2024-01-15T14:00:00Z",
    raw_s3_path: "s3://flight-data/raw/2024/01/15/ua123_tlv_1420.json"
  },
  {
    flight_id: "c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8",
    airline_code: "DL",
    flight_number: "DL456",
    direction: "D",
    location_iata: "TLV",
    scheduled_time: "2024-01-15T16:45:00Z",
    actual_time: "2024-01-15T16:45:00Z",
    airline_name: "Delta Air Lines",
    location_en: "Ben Gurion Airport",
    location_he: "נמל התעופה בן גוריון",
    location_city_en: "Tel Aviv",
    country_en: "Israel",
    country_he: "ישראל",
    terminal: "3",
    checkin_counters: "30-40",
    checkin_zone: "C",
    status_en: "On Time",
    status_he: "בזמן",
    delay_minutes: 0,
    scrape_timestamp: "2024-01-15T16:30:00Z",
    raw_s3_path: "s3://flight-data/raw/2024/01/15/dl456_tlv_1645.json"
  },
  {
    flight_id: "d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9",
    airline_code: "AF",
    flight_number: "AF789",
    direction: "A",
    location_iata: "TLV",
    scheduled_time: "2024-01-15T19:10:00Z",
    actual_time: "2024-01-15T19:25:00Z",
    airline_name: "Air France",
    location_en: "Ben Gurion Airport",
    location_he: "נמל התעופה בן גוריון",
    location_city_en: "Tel Aviv",
    country_en: "Israel",
    country_he: "ישראל",
    terminal: "3",
    checkin_counters: "45-55",
    checkin_zone: "D",
    status_en: "Landed",
    status_he: "נחת",
    delay_minutes: 15,
    scrape_timestamp: "2024-01-15T18:45:00Z",
    raw_s3_path: "s3://flight-data/raw/2024/01/15/af789_tlv_1910.json"
  },
  {
    flight_id: "e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
    airline_code: "BA",
    flight_number: "BA321",
    direction: "D",
    location_iata: "TLV",
    scheduled_time: "2024-01-15T21:30:00Z",
    actual_time: "2024-01-15T21:30:00Z",
    airline_name: "British Airways",
    location_en: "Ben Gurion Airport",
    location_he: "נמל התעופה בן גוריון",
    location_city_en: "Tel Aviv",
    country_en: "Israel",
    country_he: "ישראל",
    terminal: "3",
    checkin_counters: "60-70",
    checkin_zone: "E",
    status_en: "On Time",
    status_he: "בזמן",
    delay_minutes: 0,
    scrape_timestamp: "2024-01-15T21:00:00Z",
    raw_s3_path: "s3://flight-data/raw/2024/01/15/ba321_tlv_2130.json"
  }
];

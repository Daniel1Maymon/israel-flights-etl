# Field Mapping Table: Raw API Fields to Database Columns

This table shows the complete mapping from raw API fields (Hebrew codes) to transformed fields and final database column names.

## Field Mapping

| Raw Field (JSON API) | Transformed Field (CSV) | Database Column | Notes |
|----------------------|-------------------------|-----------------|-------|
| `CHOPER` | `airline_code` | `airline_code` | **Part of key** - IATA airline code |
| `CHFLTN` | `flight_number` | `flight_number` | **Part of key** - Flight number |
| `CHAORD` | `arrival_departure_code` | `direction` | **Part of key** - 'A' for Arrival, 'D' for Departure |
| `CHLOC1` | `airport_code` | `location_iata` | **Part of key** - Airport IATA code |
| `CHSTOL` | `scheduled_departure_time` → `scheduled_departure` | `scheduled_time` | **Part of key** - Scheduled departure/arrival time (converted to datetime) |
| `CHPTOL` | `actual_departure_time` → `actual_departure` | `actual_time` | **Updatable** - Actual departure/arrival time (converted to datetime) |
| `CHOPERD` | `airline_name` | `airline_name` | Full airline name |
| `CHLOC1D` | `airport_name_english` | `location_en` | Airport name in English |
| `CHLOC1TH` | `airport_name_hebrew` | `location_he` | Airport name in Hebrew |
| `CHLOC1T` | `city_name_english` | `location_city_en` | City name in English |
| `CHLOCCT` | `country_name_english` | `country_en` | Country name in English |
| `CHLOC1CH` | `country_name_hebrew` | `country_he` | Country name in Hebrew |
| `CHTERM` | `terminal_number` | `terminal` | **Updatable** - Terminal number |
| `CHCINT` | `check_in_time` | `checkin_counters` | **Updatable** - Check-in counters (e.g., "342-345") |
| `CHCKZN` | `check_in_zone` | `checkin_zone` | **Updatable** - Check-in zone (e.g., "B", "C") |
| `CHRMINE` | `status_english` | `status_en` | **Updatable** - Flight status in English |
| `CHRMINH` | `status_hebrew` | `status_he` | **Updatable** - Flight status in Hebrew |
| - | `delay_minutes` (calculated) | `delay_minutes` | **Updatable** - Calculated: (actual_departure - scheduled_departure) in minutes |
| - | `flight_id` (calculated) | `flight_id` | **Primary Key** - MD5 hash of: `airline_code_flight_number_direction_location_iata_scheduled_departure` |
| - | `scrape_timestamp` (generated) | `scrape_timestamp` | **Updatable** - Timestamp when data was scraped |
| - | `raw_s3_path` (generated) | `raw_s3_path` | **Updatable** - S3 path to raw data file |
| `_id` | `_id` | - | Not stored in database (internal API record ID) |

## Key Fields (Used for flight_id generation)

The following 5 fields form the natural key that is hashed to create the `flight_id`:

1. `airline_code` (from `CHOPER`)
2. `flight_number` (from `CHFLTN`)
3. `direction` (from `CHAORD`)
4. `location_iata` (from `CHLOC1`)
5. `scheduled_time` (from `CHSTOL`)

## Updatable Fields (Updated on conflict)

When a flight with the same `flight_id` already exists, these 9 fields are updated:

1. `actual_time` (from `CHPTOL`)
2. `terminal` (from `CHTERM`)
3. `checkin_counters` (from `CHCINT`)
4. `checkin_zone` (from `CHCKZN`)
5. `status_en` (from `CHRMINE`)
6. `status_he` (from `CHRMINH`)
7. `delay_minutes` (calculated)
8. `scrape_timestamp` (generated)
9. `raw_s3_path` (generated)

## Calculated/Generated Fields

- **`delay_minutes`**: Calculated during transformation as `(actual_departure - scheduled_departure).total_seconds() / 60.0`
- **`flight_id`**: MD5 hash of the natural key string: `f"{airline_code}_{flight_number}_{direction}_{location_iata}_{scheduled_departure}"`
- **`scrape_timestamp`**: Set to current timestamp when data is loaded into database
- **`raw_s3_path`**: Set to S3 path where processed CSV is stored

## Transformation Steps

1. **Raw JSON** → Column renaming (Hebrew codes → English names)
2. **Time conversion** → `scheduled_departure_time` and `actual_departure_time` converted to datetime objects (`scheduled_departure`, `actual_departure`)
3. **Delay calculation** → `delay_minutes` computed from time difference
4. **UUID generation** → `flight_id` computed from natural key fields
5. **Database mapping** → Transformed field names mapped to final database column names



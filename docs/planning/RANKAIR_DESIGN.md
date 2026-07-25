# RankAir – Decision Engine Design

## Product Purpose

RankAir answers one question for consumers booking flights:

> Is there a meaningful difference in operational reliability between airlines flying to a specific destination?

RankAir is a **reliability comparison and interpretation engine** — not a dashboard, prediction engine, or forecasting tool.

It analyzes recent operational performance of airlines on the same route and determines whether a meaningful reliability gap exists. Output is consumer interpretation, not raw analytics.

---

## Data Source

Raw data comes from the `flights` table (~100k rows, continuously scraped and appended).

Key columns: `flight_id`, `airline_name`, `airline_code`, `direction`, `location_iata`, `location_en`, `location_he`, `location_city_en`, `scheduled_time`, `actual_time`, `delay_minutes`, `status_en`

The table contains both arrivals and departures. RankAir analyzes **departures only**.

---

## Architecture

```
flights (raw table)
    ↓
destination normalization
    ↓
destination_airline_metrics (aggregate table)
    ↓
gap detection engine
    ↓
decision output
    ↓
LLM explanation layer
    ↓
consumer UI
```

---

## Destination Normalization

The engine compares airlines per **destination city**, not per airport code.

Multiple IATA codes are merged under a single city name before aggregation:

```
LONDON HEATHROW (LHR)  ┐
LONDON LUTON    (LTN)  ├──→  LONDON
LONDON GATWICK  (LGW)  ┘
```

Normalization is applied to `location_city_en` prior to aggregation.

---

## Aggregation Table

Metrics are **not** computed from `flights` on every request. Instead, a precomputed aggregation layer stores results per destination city, airline, and time window.

**Table:** `destination_airline_metrics`

| Column | Description |
|---|---|
| `destination_city_en` | Normalized city name (English) |
| `destination_city_he` | Normalized city name (Hebrew) |
| `airline_name` | Airline |
| `window_type` | Time window (`7d`, `30d`, `90d`) |
| `total_flights` | Flight count in window |
| `on_time_pct` | % flights on time |
| `cancel_pct` | % flights cancelled |
| `severe_delay_pct` | % flights with severe delay |
| `avg_delay_positive` | Average delay (positive only) |
| `p95_delay` | 95th percentile delay |
| `updated_at` | Last refresh timestamp |

Each row represents one `destination_city + airline + window_type` combination:

```
ATHENS | AEGEAN  | 30d
ATHENS | EL AL   | 30d
```

The table is **small and refreshed** (not appended) via periodic UPSERT jobs.

Initial implementation uses `30d`. The `window_type` column is included for future flexibility.

---

## Gap Detection Engine

The engine evaluates spreads between airlines on the same route and window.

Metrics evaluated:
- `on_time_pct` spread
- `cancel_pct` spread
- `severe_delay_pct` spread

If any spread exceeds a predefined threshold → **Meaningful Difference**
Otherwise → **No Meaningful Difference**

Example (Athens, last 30 days):
- On-time spread ≈ 64%
- Severe delay spread ≈ 16%
- Cancellation spread ≈ 9%

This validates the product premise: some routes contain real, consumer-relevant operational differences.

---

## LLM Explanation Layer

The LLM does **not** compute metrics or make predictions.

- **Input:** structured JSON decision output from the gap detection engine
- **Output:** 3–4 lines of natural language explanation for consumers

The LLM converts a structured result into a plain-language interpretation. It does not speculate beyond the data provided.

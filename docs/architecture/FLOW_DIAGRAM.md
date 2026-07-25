# Backend Flow Diagrams (Current)

## Request Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as FastAPI
    participant DB as PostgreSQL

    FE->>API: GET /api/v1/flights?page=1&size=20
    API->>API: CORS + request logging
    API->>DB: SELECT with filters/pagination
    DB-->>API: rows
    API-->>FE: JSON { data, pagination }
```

## ETL Runtime Flow

```mermaid
flowchart TD
    A[Scheduler Start] --> B[Initial ETL Run]
    B --> C{Records fetched?}
    C -->|No| D[Skip transform/load]
    C -->|Yes| E[Transform records]
    E --> F[Compute flight_id]
    F --> G[Upsert into flights table]
    D --> H[Wait interval]
    G --> H
    H --> I[Next scheduled run]
    I --> C
```

## Flight Board SSE Flow

```mermaid
flowchart TD
    A[Client connects /api/v1/flight-board/stream] --> B[Compute default or explicit date window]
    B --> C[Query flights for window]
    C --> D[Send SSE data event with full snapshot]
    D --> E[Emit keepalive comments]
    E --> F{Refresh interval reached?}
    F -->|No| E
    F -->|Yes| B
```

## API Surface Map

```mermaid
flowchart LR
    H[/health, /ready, /metrics/] --> API[FastAPI]
    F[/api/v1/flights/*/] --> API
    A[/api/v1/airlines/*/] --> API
    D[/api/v1/destinations/*/] --> API
    S[/api/v1/flight-board/stream/] --> API
    O[/api/v1/flight-board/options/] --> API
    API --> DB[(PostgreSQL flights)]
```

## Notes
- Authentication middleware is not part of the current request pipeline.
- Airflow diagrams from older versions are intentionally excluded from this current-state document.

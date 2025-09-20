# FastAPI Backend Flow Diagram

## Data Flow Architecture

```mermaid
graph TB
    subgraph "Frontend Layer"
        A[React Dashboard] --> B[HTTP Requests]
    end
    
    subgraph "API Gateway Layer"
        B --> C[FastAPI Application]
        C --> D[CORS Middleware]
        D --> E[Authentication Middleware]
        E --> F[Error Handling Middleware]
    end
    
    subgraph "API Endpoints Layer"
        F --> G[GET /api/v1/flights]
        F --> H[GET /api/v1/flights/{id}]
        F --> I[GET /api/v1/flights/search]
        F --> J[GET /api/v1/flights/stats]
        F --> K[GET /api/v1/airlines]
        F --> L[GET /api/v1/destinations]
    end
    
    subgraph "Business Logic Layer"
        G --> M[Flight Service]
        H --> M
        I --> M
        J --> M
        K --> M
        L --> M
        M --> N[Filtering & Pagination]
        M --> O[Search Logic]
        M --> P[Statistics Calculation]
    end
    
    subgraph "Data Access Layer"
        N --> Q[SQLAlchemy ORM]
        O --> Q
        P --> Q
        Q --> R[Database Session]
        R --> S[Query Builder]
    end
    
    subgraph "Database Layer"
        S --> T[(PostgreSQL)]
        T --> U[flights table]
        U --> V[~9,909 records]
    end
    
    subgraph "Response Flow"
        V --> W[Raw Data]
        W --> X[Pydantic Models]
        X --> Y[JSON Serialization]
        Y --> Z[HTTP Response]
        Z --> A
    end
    
    style A fill:#e1f5fe
    style T fill:#f3e5f5
    style C fill:#e8f5e8
    style M fill:#fff3e0
```

## Request Processing Flow

```mermaid
sequenceDiagram
    participant F as Frontend
    participant API as FastAPI
    participant MW as Middleware
    participant EP as Endpoint
    participant SVC as Service
    participant DB as Database
    
    F->>API: GET /api/v1/flights?page=1&size=50
    API->>MW: Process Request
    MW->>MW: CORS Check
    MW->>MW: Error Handling
    MW->>EP: Route to Endpoint
    EP->>SVC: Call Flight Service
    SVC->>SVC: Apply Filters
    SVC->>SVC: Build Query
    SVC->>DB: Execute SQL Query
    DB-->>SVC: Return Raw Data
    SVC->>SVC: Transform to Pydantic
    SVC-->>EP: Return Flight Objects
    EP->>EP: Add Pagination Metadata
    EP-->>MW: Return Response
    MW-->>API: Process Response
    API-->>F: JSON Response
```

## Error Handling Flow

```mermaid
flowchart TD
    A[Request Received] --> B{Valid Request?}
    B -->|No| C[400 Bad Request]
    B -->|Yes| D{Database Available?}
    D -->|No| E[500 Internal Server Error]
    D -->|Yes| F{Resource Exists?}
    F -->|No| G[404 Not Found]
    F -->|Yes| H{Query Valid?}
    H -->|No| I[422 Unprocessable Entity]
    H -->|Yes| J[200 OK Response]
    
    C --> K[Error Response JSON]
    E --> K
    G --> K
    I --> K
    J --> L[Success Response JSON]
    
    style C fill:#ffebee
    style E fill:#ffebee
    style G fill:#ffebee
    style I fill:#ffebee
    style J fill:#e8f5e8
```

## Filtering & Search Flow

```mermaid
flowchart LR
    A[Query Parameters] --> B{Filter Type?}
    B -->|Direction| C[WHERE direction = ?]
    B -->|Airline| D[WHERE airline_code = ?]
    B -->|Status| E[WHERE status_en = ?]
    B -->|Date Range| F[WHERE scheduled_time BETWEEN ? AND ?]
    B -->|Delay| G[WHERE delay_minutes BETWEEN ? AND ?]
    B -->|Search| H[WHERE column ILIKE %?%]
    
    C --> I[Build SQL Query]
    D --> I
    E --> I
    F --> I
    G --> I
    H --> I
    
    I --> J[Add Pagination]
    J --> K[Execute Query]
    K --> L[Return Results]
    
    style A fill:#e3f2fd
    style I fill:#fff3e0
    style L fill:#e8f5e8
```

## MVP Testing Flow

```mermaid
flowchart TD
    A[Start Testing] --> B[Health Check]
    B --> C{API Running?}
    C -->|No| D[Fix Setup Issues]
    C -->|Yes| E[Test Core Endpoints]
    
    E --> F[List Flights]
    E --> G[Single Flight]
    E --> H[Search Flights]
    E --> I[Airlines List]
    E --> J[Destinations List]
    
    F --> K{All Pass?}
    G --> K
    H --> K
    I --> K
    J --> K
    
    K -->|No| L[Debug Issues]
    K -->|Yes| M[Test Filtering]
    
    M --> N[Direction Filter]
    M --> O[Airline Filter]
    M --> P[Status Filter]
    M --> Q[Date Range Filter]
    
    N --> R{All Pass?}
    O --> R
    P --> R
    Q --> R
    
    R -->|No| S[Fix Filter Logic]
    R -->|Yes| T[Test Error Handling]
    
    T --> U[Invalid Flight ID]
    T --> V[Invalid Parameters]
    T --> W[Database Errors]
    
    U --> X{All Pass?}
    V --> X
    W --> X
    
    X -->|No| Y[Fix Error Handling]
    X -->|Yes| Z[MVP Ready]
    
    D --> B
    L --> E
    S --> M
    Y --> T
    
    style A fill:#e1f5fe
    style Z fill:#e8f5e8
    style D fill:#ffebee
    style L fill:#ffebee
    style S fill:#ffebee
    style Y fill:#ffebee
```

## Environment Setup Flow

```mermaid
flowchart TD
    A[Start Setup] --> B[Check Prerequisites]
    B --> C{Python 3.8+?}
    C -->|No| D[Install Python]
    C -->|Yes| E{PostgreSQL Running?}
    
    E -->|No| F[Start PostgreSQL]
    E -->|Yes| G{Database Exists?}
    
    G -->|No| H[Create Database]
    G -->|Yes| I[Create Virtual Environment]
    
    I --> J[Install Dependencies]
    J --> K[Set Environment Variables]
    K --> L[Start FastAPI Server]
    L --> M[Test Health Endpoint]
    
    M --> N{200 OK?}
    N -->|No| O[Debug Issues]
    N -->|Yes| P[Ready to Develop]
    
    D --> B
    F --> E
    H --> I
    O --> L
    
    style A fill:#e1f5fe
    style P fill:#e8f5e8
    style D fill:#ffebee
    style F fill:#ffebee
    style H fill:#ffebee
    style O fill:#ffebee
```

## Production Deployment Flow

```mermaid
flowchart TD
    A[Code Commit] --> B[CI/CD Pipeline]
    B --> C[Run Tests]
    C --> D{Tests Pass?}
    D -->|No| E[Fix Issues]
    D -->|Yes| F[Security Scan]
    
    F --> G{Security Pass?}
    G -->|No| H[Fix Vulnerabilities]
    G -->|Yes| I[Build Docker Image]
    
    I --> J[Push to Registry]
    J --> K[Deploy to Staging]
    K --> L[Run Integration Tests]
    L --> M{Integration Pass?}
    
    M -->|No| N[Debug Staging Issues]
    M -->|Yes| O[Deploy to Production]
    O --> P[Health Check]
    P --> Q{Health OK?}
    
    Q -->|No| R[Rollback]
    Q -->|Yes| S[Monitor Metrics]
    S --> T[Production Ready]
    
    E --> C
    H --> F
    N --> L
    R --> O
    
    style A fill:#e1f5fe
    style T fill:#e8f5e8
    style E fill:#ffebee
    style H fill:#ffebee
    style N fill:#ffebee
    style R fill:#ffebee
```

## Security & Monitoring Flow

```mermaid
flowchart TD
    A[Request Received] --> B[Rate Limiting Check]
    B --> C{Within Limits?}
    C -->|No| D[429 Too Many Requests]
    C -->|Yes| E[Authentication Check]
    
    E --> F{Valid Auth?}
    F -->|No| G[401 Unauthorized]
    F -->|Yes| H[Input Validation]
    
    H --> I{Valid Input?}
    I -->|No| J[400 Bad Request]
    I -->|Yes| K[Process Request]
    
    K --> L[Log Request]
    L --> M[Execute Business Logic]
    M --> N[Log Response]
    N --> O[Return Response]
    
    O --> P[Update Metrics]
    P --> Q[Check Alert Thresholds]
    Q --> R{Alert Triggered?}
    R -->|Yes| S[Send Alert]
    R -->|No| T[Continue Monitoring]
    
    D --> U[Log Security Event]
    G --> U
    J --> U
    S --> V[Notify Operations Team]
    
    style A fill:#e1f5fe
    style T fill:#e8f5e8
    style D fill:#ffebee
    style G fill:#ffebee
    style J fill:#ffebee
    style U fill:#fff3e0
    style V fill:#f3e5f5
```

## Disaster Recovery Flow

```mermaid
flowchart TD
    A[Disaster Detected] --> B[Assess Impact]
    B --> C{Database Down?}
    C -->|Yes| D[Activate Read Replica]
    C -->|No| E{Application Down?}
    
    E -->|Yes| F[Restart Application]
    E -->|No| G{Network Issue?}
    
    G -->|Yes| H[Switch to Backup Region]
    G -->|No| I[Check Dependencies]
    
    D --> J[Update DNS]
    F --> K[Health Check]
    H --> L[Verify Connectivity]
    I --> M{Fixed?}
    
    K --> N{App Healthy?}
    L --> O{Region Healthy?}
    M -->|No| P[Escalate to Team]
    M -->|Yes| Q[Monitor Recovery]
    
    N -->|No| R[Rollback to Previous Version]
    N -->|Yes| S[Continue Monitoring]
    O -->|No| T[Try Another Region]
    O -->|Yes| U[Update Load Balancer]
    
    R --> V[Investigate Root Cause]
    T --> W[Check All Regions]
    U --> X[Verify Traffic Flow]
    
    S --> Y[Recovery Complete]
    Q --> Y
    X --> Y
    
    P --> Z[Manual Intervention]
    V --> Z
    W --> Z
    
    style A fill:#ffebee
    style Y fill:#e8f5e8
    style P fill:#fff3e0
    style Z fill:#f3e5f5
```

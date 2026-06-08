# TrendEconomy

Aplikacja webowa do porównawczej analizy wskaźników ekonomicznych i demograficznych krajów Unii Europejskiej. Dane pobierane z dwóch niezależnych źródeł (Eurostat REST API i World Bank Open Data API), normalizowane, czyszczone i prezentowane w formie dashboardu z wykresami.

Projekt zaliczeniowy z przedmiotu Architektura Systemów Informatycznych.

## Stos

- Backend: FastAPI 0.115, SQLAlchemy 2, Alembic, structlog, httpx
- Baza: PostgreSQL 16
- Frontend: React 18 + Vite + Recharts
- Testy: pytest, Locust
- Konteneryzacja: Docker Compose (dev / test / prod), Nginx jako reverse proxy

## Szybkie uruchomienie (dev)

```
docker compose -f docker-compose.dev.yml up --build
```

Po starcie:

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Dashboard: http://localhost:5173

Pierwsze uruchomienie wykonuje automatycznie migracje Alembica i ładuje 27 krajów UE do bazy. Baza jest pusta — żeby pobrać dane, trzeba wywołać akwizycję:

```
curl -X POST http://localhost:8000/api/v1/ingestion/trigger ^
  -H "Content-Type: application/json" ^
  -d "{\"year_from\":2010,\"year_to\":2024,\"run_in_background\":false}"
```

Albo z poziomu dashboardu — przycisk „Pobierz dane".

## Endpointy

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET  | `/api/v1/countries/`              | Lista krajów |
| GET  | `/api/v1/countries/{iso2}`        | Szczegóły kraju |
| GET  | `/api/v1/indicators/`             | Lista wskaźników |
| GET  | `/api/v1/data/{indicator_code}`   | Dane wskaźnika dla wybranych krajów i zakresu lat |
| POST | `/api/v1/ingestion/trigger`       | Wyzwolenie akwizycji danych |
| GET  | `/api/v1/health`                  | Health check |

Pełna dokumentacja: Swagger pod `/docs`.

## Wskaźniki

| Kod                  | Źródło    | Opis                                  |
|----------------------|-----------|---------------------------------------|
| gdp_per_capita_eur   | Eurostat  | PKB per capita w EUR                  |
| gdp_per_capita_usd   | WorldBank | PKB per capita w USD                  |
| unemployment_rate_eu | Eurostat  | Stopa bezrobocia                      |
| unemployment_rate_wb | WorldBank | Stopa bezrobocia (modelowane ILO)     |
| population_total_eu  | Eurostat  | Populacja (stan na 1 stycznia)        |
| life_expectancy      | WorldBank | Oczekiwana długość życia              |
| inflation_cpi        | WorldBank | Inflacja CPI rok do roku              |

## Testy

```
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

Albo lokalnie w katalogu `backend/`:

```
pytest tests/unit/ -v
```

Testy wydajnościowe (Locust, headless, 30 s):

```
docker compose -f docker-compose.dev.yml exec backend locust ^
  -f tests/performance/locustfile.py --host http://backend:8000 ^
  --headless --users 10 --spawn-rate 2 --run-time 30s
```

## Produkcja

Wymaga ustawienia `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` w pliku `.env` (przykład w `.env.example`).

```
docker compose -f docker-compose.prod.yml up --build -d
```

Aplikacja dostępna przez Nginx na porcie 80.

## Struktura

```
backend/
  app/
    ingestion/      klienty Eurostat i World Bank + orchestrator
    processing/    normalizacja i czyszczenie danych
    routers/       endpointy FastAPI
    models/        modele SQLAlchemy
    schemas/       schematy Pydantic
  alembic/         migracje bazy
  tests/
    unit/          38 testów jednostkowych
    performance/   scenariusze Locust
frontend/
  src/             aplikacja React (App.jsx, App.module.css)
nginx/
  nginx.conf       reverse proxy dla produkcji
```

## Dokumentacja

Pełna dokumentacja techniczna z diagramami i tabelami: `TrendEconomy_Dokumentacja.docx`.

## Autorzy

Wiktoria Kawa, Ryszard Czarnecki — Politechnika Warszawska, MiNI, 2025/2026.

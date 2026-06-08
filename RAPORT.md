# Raport z wykonanej pracy

Projekt: **TrendEconomy** — analiza trendów ekonomicznych i demograficznych krajów Unii Europejskiej.
Przedmiot: Architektura Systemów Informatycznych, 2025/2026.

## Cel projektu

Zbudowanie wielowarstwowego systemu informatycznego pokazującego pełny cykl przetwarzania danych: akwizycja z dwóch niezależnych źródeł Open Data (Eurostat, World Bank), normalizacja i czyszczenie, utrwalanie w relacyjnej bazie, udostępnianie przez REST API oraz prezentacja w interaktywnym dashboardzie.

## Podział pracy

### Wiktoria Kawa

- Inicjalizacja repozytorium i struktury katalogów projektu.
- Modele bazy danych (SQLAlchemy): `Country`, `Indicator`, `DataPoint` wraz z relacjami, indeksami i ograniczeniem unikalności na trójce `(country_id, indicator_id, year)`.
- Pierwsza migracja Alembica oraz skrypt seedujący 27 krajów Unii Europejskiej do bazy.
- Konfiguracja FastAPI: punkt wejścia, logowanie strukturalne (`structlog`), middleware CORS i pomiaru czasu odpowiedzi.
- Pierwsze trzy routery REST: `/countries`, `/indicators`, `/data/{indicator_code}` oraz schematy Pydantic dla odpowiedzi.
- Frontend React + Vite + Recharts: komponent `App.jsx` (dashboard z wyborem wskaźnika, zakresu lat i krajów; karty metryk z deltą procentową; wykres liniowy z własnym tooltipem; obsługa stanów ładowania/błędu/pustych danych), arkusz stylów `App.module.css`, konfiguracja proxy Vite do backendu.
- Szkielet testów wydajnościowych Locust (`tests/performance/locustfile.py`) z dwoma klasami użytkowników (`DashboardUser`, `AnalystUser`) i scenariuszami obciążeniowymi.
- Pełna dokumentacja techniczna projektu w formacie Word (`TrendEconomy_Dokumentacja.docx`) — 14 rozdziałów, 11 tabel, diagramy komponentów i modelu danych.
- Drobne poprawki UI i rozszerzenie listy krajów w panelu wyboru do wszystkich 27 państw UE.

### Ryszard Czarnecki

- Moduł akwizycji danych (`app/ingestion/`):
  - `EurostatClient` — klient REST API Eurostatu z parserem formatu JSON-stat 2.0 (rozplatanie wielowymiarowej kostki na płaską listę obserwacji, mapowanie nietypowych kodów Eurostatu na ISO2: `EL→GR`, `UK→GB`, pomijanie okresów subrocznych).
  - `WorldBankClient` — klient World Bank Open Data API v2 z parserem dwuelementowej tablicy `[meta, records]`, wykrywaniem payloadów błędu.
  - Wspólny dla obu klientów mechanizm retry (3 próby z rosnącym opóźnieniem) dla błędów sieciowych i `5xx`/`429`, bez ponawiania błędów `4xx`.
  - `indicators_config.py` — deklaratywna konfiguracja 7 wskaźników (3 z Eurostatu, 4 z World Banku) wraz z filtrami wymiarów SDMX.
  - `run.py` — orchestrator wykonujący `UPSERT` (`INSERT ... ON CONFLICT DO UPDATE`) z deduplikacją wierszy chroniącą przed `CardinalityViolation` przy danych Eurostatu zawierających duplikaty po wymiarach pomocniczych.
  - CLI do ręcznego uruchamiania akwizycji oraz endpoint `POST /api/v1/ingestion/trigger` (synchroniczny i asynchroniczny przez `BackgroundTasks`).
- Moduł przetwarzania danych (`app/processing/`):
  - `normalizer.py` — centralne mapy konwersji kodów krajów ISO2 ↔ ISO3 dla 27 państw UE, korekta kodów Eurostatu, zaokrąglanie wartości liczbowych do 4 miejsc dziesiętnych.
  - `cleaner.py` — trzyetapowa walidacja serii obserwacji: odrzucenie wartości `None/NaN/inf`, walidacja zakresów domenowych (`VALIDATION_RULES` per wskaźnik), wykrywanie statystycznych wartości odstających metodą rozstępu międzykwartylowego (IQR, próg `K=3.0`) per kraj.
  - Implementacja percentyla z interpolacją liniową bez zależności od NumPy.
  - Raporty `CleaningReport` i `NormalizationReport` ze statystykami operacji, zapisywane do strukturalnych logów.
- Integracja modułu `processing` w pipeline'ie ingestion (fetch → normalize → clean → upsert) i rozszerzenie odpowiedzi endpointu o liczniki przetworzonych/odrzuconych obserwacji.
- Testy jednostkowe (`tests/unit/`) — 23 nowe testy pokrywające klientów API, parser JSON-stat, normalizator i cleaner (38 testów łącznie z modułem testów istniejących wcześniej).
- Konteneryzacja frontendu — multi-stage `frontend/Dockerfile` z trzema stage'ami (builder, dev z hot-reload, prod z Nginx serwującym zbudowane statyki), integracja frontendu z `docker-compose.dev.yml` i `docker-compose.prod.yml`.
- Rekonfiguracja Nginx jako reverse proxy w produkcji (przekierowanie `/api/`, `/docs`, `/redoc`, `/openapi.json` do backendu, `/` do kontenera frontendu).
- Naprawa końcówek linii CRLF z OneDrive blokujących uruchamianie skryptu `entrypoint.sh` w kontenerze (instalacja `dos2unix` w obrazie backendu, `dos2unix` w locie przed uruchomieniem skryptu w dev compose, plik `.gitattributes` wymuszający LF w repozytorium).
- Poprawa pliku Locusta — podmiana błędnych kodów wskaźników na rzeczywiste z `indicators_config.py` oraz usunięcie obejścia traktującego `404` jako sukces.
- Uporządkowanie komentarzy i docstringów w napisanych modułach.
- Plik `README.md` na poziomie repozytorium.

## Problemy napotkane i ich rozwiązania

- **CRLF z OneDrive psujący skrypty bash w kontenerze.** Pliki edytowane na Windowsie zapisywały się z końcówkami `\r\n`, przez co `entrypoint.sh` wywalał się w kontenerze Linuksa z błędem `set: invalid option`. Rozwiązanie: pakiet `dos2unix` w obrazie backendu konwertujący wszystkie skrypty podczas budowy oraz `dos2unix -q entrypoint.sh && bash entrypoint.sh` w entrypoincie `docker-compose.dev.yml` (jako zabezpieczenie przy mountowaniu hostowych plików). Dodatkowo `.gitattributes` z `eol=lf` w repozytorium.

- **`CardinalityViolation` przy upsercie danych Eurostatu.** Niektóre datasety (np. `une_rt_a`) zwracają wiele obserwacji dla tej samej trójki `(kraj, wskaźnik, rok)` różniących się wymiarami pomocniczymi nieuwzględnionymi w filtrach. PostgreSQL nie pozwala wykonać `INSERT ... ON CONFLICT` z dwoma wierszami o identycznym kluczu konfliktu w jednym statemencie. Rozwiązanie: deduplikacja wierszy w pamięci (`dict` po kluczu) przed zbudowaniem statementu SQL.

- **Przelotne błędy sieciowe `Network unreachable` przy zapytaniach do Eurostatu.** Rozwiązanie: prosty mechanizm retry (3 próby z liniowo rosnącym opóźnieniem, łapiący `httpx.TransportError` oraz `5xx`/`429`, ale nie `4xx`).

- **Niedopasowane kody wskaźników w testach Locust.** Wstępny szkielet używał placeholderów typu `gdp_per_capita_wb`, które nie istnieją w konfiguracji projektu — wszystkie zapytania do endpointu danych zwracały 404. Rozwiązanie: podmiana na rzeczywiste 7 kodów z `indicators_config.py` i usunięcie warunku traktującego 404 jako sukces.

## Statystyki projektu

- 27 krajów Unii Europejskiej w bazie.
- 7 wskaźników z dwóch niezależnych źródeł Open Data.
- 38 testów jednostkowych, wszystkie zielone.
- Testy wydajnościowe: ~250 żądań w 30 s przy 10 użytkownikach, średni czas odpowiedzi 7–8 ms, p95 = 11–13 ms, 0% błędów.
- Trzy środowiska Docker: dev (hot-reload), test (CI scenariusz), prod (reverse proxy Nginx).
- Pełna dokumentacja techniczna w formacie Word + interaktywna dokumentacja Swagger UI pod `/docs`.

## Repozytorium

https://github.com/wiktoriakawa/Architektura-System-w-Informatycznych---projekt

## Autorzy

Wiktoria Kawa, Ryszard Czarnecki — Politechnika Warszawska, Wydział Matematyki i Nauk Informacyjnych, semestr letni 2025/2026.

import { useState, useEffect, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from "recharts";
import styles from "./App.module.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const COUNTRY_COLORS = {
  PL: "#2563eb", DE: "#16a34a", FR: "#dc2626",
  IT: "#d97706", ES: "#7c3aed", RO: "#0891b2",
  NL: "#be185d", BE: "#65a30d", SE: "#0f766e",
  AT: "#9333ea", HU: "#b45309", CZ: "#1d4ed8",
};

const DASH_PATTERNS = {
  PL: "0", DE: "6 3", FR: "2 2", IT: "8 3 2 3",
  ES: "4 2", RO: "10 4", NL: "1 1", BE: "6 2 1 2",
  SE: "3 3", AT: "8 2", HU: "4 1", CZ: "5 5",
};

function MetricCard({ country, value, unit, delta }) {
  const sign = delta > 0 ? "+" : "";
  const deltaClass = delta > 0 ? styles.up : delta < 0 ? styles.down : "";
  return (
    <div className={styles.metricCard}>
      <div
        className={styles.metricAccent}
        style={{ background: COUNTRY_COLORS[country] || "#888" }}
      />
      <div className={styles.metricContent}>
        <span className={styles.metricCountry}>{country}</span>
        <span className={styles.metricValue}>
          {value !== null ? value : "—"}
          <span className={styles.metricUnit}> {unit}</span>
        </span>
        {delta !== null && (
          <span className={`${styles.metricDelta} ${deltaClass}`}>
            {sign}{delta}%
          </span>
        )}
      </div>
    </div>
  );
}

function CustomTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null;
  return (
    <div className={styles.tooltip}>
      <p className={styles.tooltipLabel}>{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.color }} className={styles.tooltipRow}>
          <span className={styles.tooltipCountry}>{p.dataKey}</span>
          <span className={styles.tooltipValue}>
            {p.value !== null ? `${p.value} ${unit}` : "—"}
          </span>
        </p>
      ))}
    </div>
  );
}

export default function App() {
  const [countries, setCountries] = useState([]);
  const [indicators, setIndicators] = useState([]);
  const [selectedCountries, setSelectedCountries] = useState(["PL", "DE", "FR"]);
  const [selectedIndicator, setSelectedIndicator] = useState("");
  const [yearFrom, setYearFrom] = useState(2010);
  const [yearTo, setYearTo] = useState(2023);
  const [chartData, setChartData] = useState([]);
  const [indicatorMeta, setIndicatorMeta] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [ingesting, setIngesting] = useState(false);
  const [ingestMsg, setIngestMsg] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/countries/`)
      .then((r) => r.json())
      .then(setCountries)
      .catch(() => setError("Nie można pobrać listy krajów."));

    fetch(`${API_BASE}/api/v1/indicators/`)
      .then((r) => r.json())
      .then((data) => {
        setIndicators(data);
        if (data.length > 0) setSelectedIndicator(data[0].code);
      })
      .catch(() => setError("Nie można pobrać listy wskaźników."));
  }, []);

  const fetchData = useCallback(() => {
    if (!selectedIndicator || selectedCountries.length === 0) return;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      countries: selectedCountries.join(","),
      year_from: yearFrom,
      year_to: yearTo,
    });
    fetch(`${API_BASE}/api/v1/data/${selectedIndicator}?${params}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((json) => {
        setIndicatorMeta({ name: json.indicator_name, unit: json.unit });
        const byYear = {};
        json.data.forEach(({ country, year, value }) => {
          if (!byYear[year]) byYear[year] = { year };
          byYear[year][country] = value !== null ? +value.toFixed(2) : null;
        });
        setChartData(Object.values(byYear).sort((a, b) => a.year - b.year));
      })
      .catch((e) => setError(`Błąd pobierania danych: ${e.message}`))
      .finally(() => setLoading(false));
  }, [selectedIndicator, selectedCountries, yearFrom, yearTo]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  function toggleCountry(code) {
    setSelectedCountries((prev) =>
      prev.includes(code)
        ? prev.length > 1 ? prev.filter((c) => c !== code) : prev
        : [...prev, code]
    );
  }

  function triggerIngestion() {
    setIngesting(true);
    setIngestMsg(null);
    fetch(`${API_BASE}/api/v1/ingestion/trigger`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ year_from: yearFrom, year_to: yearTo, run_in_background: true }),
    })
      .then((r) => r.json())
      .then((d) => setIngestMsg(d.status === "scheduled"
        ? "Ingestion uruchomiony w tle."
        : `Gotowe: ${d.data_points_upserted} punktów.`))
      .catch(() => setIngestMsg("Błąd uruchamiania ingestion."))
      .finally(() => setIngesting(false));
  }

  const metricCountries = selectedCountries.slice(0, 4);

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}>TrendEconomy</h1>
          <p className={styles.subtitle}>Trendy ekonomiczne i demograficzne krajów UE</p>
        </div>
        <div className={styles.headerRight}>
          <button
            className={styles.ingestBtn}
            onClick={triggerIngestion}
            disabled={ingesting}
          >
            {ingesting ? "Pobieranie..." : "Pobierz dane"}
          </button>
          {ingestMsg && <span className={styles.ingestMsg}>{ingestMsg}</span>}
        </div>
      </header>

      <main className={styles.main}>
        <section className={styles.controls}>
          <div className={styles.controlGroup}>
            <label className={styles.controlLabel}>Wskaźnik</label>
            <select
              className={styles.select}
              value={selectedIndicator}
              onChange={(e) => setSelectedIndicator(e.target.value)}
            >
              {indicators.map((i) => (
                <option key={i.code} value={i.code}>{i.name}</option>
              ))}
            </select>
          </div>

          <div className={styles.controlGroup}>
            <label className={styles.controlLabel}>Zakres lat</label>
            <div className={styles.yearInputs}>
              <input
                type="number"
                className={styles.yearInput}
                min="1995"
                max={yearTo}
                value={yearFrom}
                onChange={(e) => setYearFrom(+e.target.value)}
              />
              <span className={styles.yearSep}>–</span>
              <input
                type="number"
                className={styles.yearInput}
                min={yearFrom}
                max="2024"
                value={yearTo}
                onChange={(e) => setYearTo(+e.target.value)}
              />
            </div>
          </div>

          <div className={styles.controlGroup}>
            <label className={styles.controlLabel}>Kraje</label>
            <div className={styles.countryGrid}>
              {countries.slice(0, 12).map((c) => (
                <button
                  key={c.code_iso2}
                  className={`${styles.countryBtn} ${selectedCountries.includes(c.code_iso2) ? styles.countryBtnActive : ""}`}
                  style={selectedCountries.includes(c.code_iso2)
                    ? { borderColor: COUNTRY_COLORS[c.code_iso2] || "#888", color: COUNTRY_COLORS[c.code_iso2] || "#888" }
                    : {}}
                  onClick={() => toggleCountry(c.code_iso2)}
                >
                  {c.code_iso2}
                </button>
              ))}
            </div>
          </div>
        </section>

        {error && <div className={styles.error}>{error}</div>}

        <section className={styles.metrics}>
          {metricCountries.map((code) => {
            const points = chartData.map((row) => row[code]).filter((v) => v != null);
            const last = points[points.length - 1] ?? null;
            const prev = points[points.length - 2] ?? null;
            const delta = last !== null && prev !== null && prev !== 0
              ? +((last - prev) / prev * 100).toFixed(1)
              : null;
            return (
              <MetricCard
                key={code}
                country={code}
                value={last !== null ? last.toLocaleString("pl-PL") : null}
                unit={indicatorMeta?.unit || ""}
                delta={delta}
              />
            );
          })}
        </section>

        <section className={styles.chartSection}>
          <div className={styles.chartHeader}>
            <div>
              <h2 className={styles.chartTitle}>
                {indicatorMeta?.name || "Dane wskaźnika"}
              </h2>
              <p className={styles.chartMeta}>
                {yearFrom}–{yearTo} · {indicatorMeta?.unit}
              </p>
            </div>
            {loading && <span className={styles.loadingDot} />}
          </div>

          {chartData.length === 0 && !loading ? (
            <div className={styles.emptyState}>
              Brak danych — uruchom ingestion, aby pobrać dane z API.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartData} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="year" tick={{ fontSize: 12, fill: "#6b7280" }} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: "#6b7280" }} tickLine={false} axisLine={false} width={60} />
                <Tooltip content={<CustomTooltip unit={indicatorMeta?.unit || ""} />} />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
                {selectedCountries.map((code) => (
                  <Line
                    key={code}
                    type="monotone"
                    dataKey={code}
                    stroke={COUNTRY_COLORS[code] || "#888"}
                    strokeWidth={2}
                    strokeDasharray={DASH_PATTERNS[code] || "0"}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                    connectNulls={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </section>
      </main>
    </div>
  );
}
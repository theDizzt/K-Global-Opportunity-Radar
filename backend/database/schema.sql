CREATE TABLE IF NOT EXISTS data_sources (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS countries (
    iso3 TEXT PRIMARY KEY CHECK(length(iso3) = 3),
    name TEXT NOT NULL,
    english_name TEXT NOT NULL,
    region TEXT NOT NULL,
    flag TEXT NOT NULL,
    completeness INTEGER NOT NULL CHECK(completeness BETWEEN 0 AND 100),
    risk_level TEXT NOT NULL,
    risk_score INTEGER NOT NULL CHECK(risk_score BETWEEN 0 AND 100),
    reference_date TEXT NOT NULL,
    focus_fields TEXT NOT NULL,
    gap_opportunity TEXT NOT NULL,
    summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS country_indicators (
    country_iso3 TEXT NOT NULL REFERENCES countries(iso3) ON DELETE CASCADE,
    code TEXT NOT NULL,
    value INTEGER NOT NULL CHECK(value BETWEEN 0 AND 100),
    PRIMARY KEY (country_iso3, code)
);

CREATE TABLE IF NOT EXISTS signal_history (
    country_iso3 TEXT NOT NULL REFERENCES countries(iso3) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
    PRIMARY KEY (country_iso3, year)
);

CREATE TABLE IF NOT EXISTS projects (
    country_iso3 TEXT PRIMARY KEY REFERENCES countries(iso3) ON DELETE CASCADE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    partners TEXT NOT NULL,
    sdgs TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_iso3 TEXT NOT NULL REFERENCES countries(iso3) ON DELETE CASCADE,
    priority INTEGER NOT NULL,
    title TEXT NOT NULL,
    UNIQUE(country_iso3, priority)
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_iso3 TEXT NOT NULL REFERENCES countries(iso3) ON DELETE CASCADE,
    source_code TEXT NOT NULL REFERENCES data_sources(code),
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    reference_date TEXT NOT NULL,
    is_demo INTEGER NOT NULL DEFAULT 1 CHECK(is_demo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS risk_factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_iso3 TEXT NOT NULL REFERENCES countries(iso3) ON DELETE CASCADE,
    source_code TEXT NOT NULL REFERENCES data_sources(code),
    title TEXT NOT NULL,
    level TEXT NOT NULL,
    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS collection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code TEXT NOT NULL REFERENCES data_sources(code),
    collected_at TEXT NOT NULL,
    status TEXT NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0,
    message TEXT
);

CREATE INDEX IF NOT EXISTS idx_countries_region ON countries(region);
CREATE INDEX IF NOT EXISTS idx_evidence_country ON evidence(country_iso3);
CREATE INDEX IF NOT EXISTS idx_risks_country ON risk_factors(country_iso3);

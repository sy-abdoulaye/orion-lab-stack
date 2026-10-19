-- ============================================================
-- 01_schema.sql — Initialisation du schéma de la base mydb
-- Exécuté automatiquement au premier démarrage du conteneur
-- ============================================================

-- Créer la base de données si elle n'existe pas encore
CREATE DATABASE IF NOT EXISTS mydb;

-- ============================================================
-- Table exemple : événements applicatifs
-- MergeTree est le moteur standard de ClickHouse (OLAP)
-- ============================================================
CREATE TABLE IF NOT EXISTS mydb.events
(
    event_id     UUID         DEFAULT generateUUIDv4(),
    event_type   LowCardinality(String),
    user_id      UInt64,
    session_id   String,
    properties   Map(String, String),
    created_at   DateTime64(3) DEFAULT now64()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (event_type, user_id, created_at)
TTL created_at + INTERVAL 12 MONTH   -- Suppression auto après 12 mois
SETTINGS index_granularity = 8192;

-- ============================================================
-- Table exemple : métriques (séries temporelles)
-- ============================================================
CREATE TABLE IF NOT EXISTS mydb.metrics
(
    metric_name  LowCardinality(String),
    tags         Map(String, String),
    value        Float64,
    ts           DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(ts)
ORDER BY (metric_name, ts)
SETTINGS index_granularity = 8192;

-- ============================================================
-- Vue matérialisée : agréger les événements par heure
-- ============================================================
CREATE TABLE IF NOT EXISTS mydb.events_hourly_agg
(
    hour         DateTime,
    event_type   LowCardinality(String),
    event_count  UInt64,
    unique_users UInt64
)
ENGINE = SummingMergeTree()
ORDER BY (hour, event_type);

CREATE MATERIALIZED VIEW IF NOT EXISTS mydb.mv_events_hourly
TO mydb.events_hourly_agg
AS
SELECT
    toStartOfHour(created_at) AS hour,
    event_type,
    count()                   AS event_count,
    uniq(user_id)             AS unique_users
FROM mydb.events
GROUP BY hour, event_type;
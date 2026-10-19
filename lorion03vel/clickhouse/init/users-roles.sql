-- ============================================================
-- 02_users_and_roles.sql — Gestion des utilisateurs via SQL
-- Nécessite CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1
-- ============================================================

-- ============================================================
-- NB : le compte « admin » n'est PLUS créé ici.
-- Il est défini en XML (chiffré) dans config/users.d/admin.xml avec
-- access_management=1. C'est lui qui sert à manage-users.sh.
-- ============================================================

-- ============================================================
-- RÔLES
-- ============================================================

-- Rôle lecture seule sur mydb
CREATE ROLE IF NOT EXISTS role_reader;
GRANT SELECT ON mydb.* TO role_reader;

-- Rôle lecture/écriture sur mydb (sans DDL)
CREATE ROLE IF NOT EXISTS role_writer;
GRANT SELECT, INSERT ON mydb.* TO role_writer;

-- Rôle administration de mydb (DDL inclus)
CREATE ROLE IF NOT EXISTS role_db_admin;
GRANT ALL ON mydb.* TO role_db_admin;

-- ============================================================
-- UTILISATEURS APPLICATIFS
-- ============================================================

-- Utilisateur applicatif (backend)
CREATE USER IF NOT EXISTS app_backend
    IDENTIFIED WITH sha256_password BY 'AppBackend2024!'
    HOST ANY
    DEFAULT ROLE role_writer;

-- Utilisateur pour les outils de BI / reporting
CREATE USER IF NOT EXISTS bi_reader
    IDENTIFIED WITH sha256_password BY 'BiReader2024!'
    HOST ANY
    DEFAULT ROLE role_reader;

-- Utilisateur pour les migrations / scripts admin
CREATE USER IF NOT EXISTS db_migrator
    IDENTIFIED WITH sha256_password BY 'Migrator2024!'
    HOST ANY
    DEFAULT ROLE role_db_admin;

-- ============================================================
-- ATTRIBUTION DES RÔLES
-- ============================================================
GRANT role_writer   TO app_backend;
GRANT role_reader   TO bi_reader;
GRANT role_db_admin TO db_migrator;

-- ============================================================
-- QUOTAS PERSONNALISÉS (optionnel)
-- Limiter bi_reader à 100 requêtes/heure
-- ============================================================
CREATE QUOTA IF NOT EXISTS quota_readonly
    KEYED BY user_name
    FOR INTERVAL 1 hour MAX queries = 100, read_rows = 1000000000
    TO bi_reader;
-- ============================================================
-- GRAFANA (lorion02vel) — lecture seule sur gobgp
-- Créé le 2026-07-16 via clickhouse-client (admin). Le mot de passe vit dans
-- lorion02vel/grafana/secrets/clickhouse_grafana_password (hors git) : sur une
-- ré-initialisation du volume, rejouer ces requêtes avec ce secret :
--   CREATE ROLE IF NOT EXISTS role_grafana_reader;
--   GRANT SELECT ON gobgp.* TO role_grafana_reader;
--   CREATE USER IF NOT EXISTS grafana
--       IDENTIFIED WITH sha256_password BY '<secrets/clickhouse_grafana_password>'
--       HOST ANY DEFAULT ROLE role_grafana_reader;
--   GRANT role_grafana_reader TO grafana;
-- ============================================================

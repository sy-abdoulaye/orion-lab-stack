-- ============================================================
-- 01_reader_role.sql — Utilisateur ClickHouse en lecture seule pour
-- gobgp-neo4j-sync (00_setup.sql n'est pas retouché : ce fichier s'exécute
-- en complément, une fois, sur l'instance déjà en place).
--   clickhouse-client --host 10.10.3.141 --port 9000 \
--     --user admin --password --multiquery < 01_reader_role.sql
--
-- Remplacer <MOT_DE_PASSE> par le mot de passe choisi pour gobgp_reader avant
-- exécution, puis reporter ce même mot de passe dans
-- lorion03vel/gobgp-neo4j-sync/secrets/ch_gobgp_reader_password (chmod 600,
-- non commité) et CLICKHOUSE_PASSWORD dans gobgp-neo4j-sync/.env.
-- ============================================================

CREATE ROLE IF NOT EXISTS role_gobgp_reader;
GRANT SELECT ON gobgp.* TO role_gobgp_reader;
CREATE USER IF NOT EXISTS gobgp_reader
    IDENTIFIED WITH sha256_password BY '<MOT_DE_PASSE>'
    HOST ANY
    DEFAULT ROLE role_gobgp_reader;

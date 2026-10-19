-- ============================================================
-- 00_setup.sql — Base gobgp + tables + utilisateur applicatif dédié
-- À exécuter une fois avec un compte admin ClickHouse :
--   clickhouse-client --host 10.10.3.141 --port 9000 \
--     --user admin --password --multiquery < 00_setup.sql
--
-- Remplacer <MOT_DE_PASSE> par le mot de passe choisi pour gobgp_writer
-- avant exécution, puis reporter ce même mot de passe dans
-- lorion01vel/gobgp/secrets/ch_gobgp_password (chmod 600, non commité).
-- ============================================================

CREATE DATABASE IF NOT EXISTS gobgp;

CREATE TABLE IF NOT EXISTS gobgp.bgp_ls_links
(
    `Prefix`           String,
    `LocalRouterID`    String,
    `RemoteRouterID`   String,
    `LocalIgpRouterId` String,
    `RemoteIgpRouterId` String,
    `IgpMetric`        UInt64,
    `Age`              DateTime,
    `Asn`              UInt32,
    `SourceId`         String,
    `NeighborIp`       String,
    `BgpLsId`          UInt64
)
ENGINE = ReplacingMergeTree(Age)
ORDER BY (Prefix, LocalRouterID, RemoteRouterID, NeighborIp)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS gobgp.bgp_ls_nodes
(
    `Prefix`     String,
    `Node`       String,
    `IgpRouter`  String,
    `Asn`        UInt32,
    `Age`        DateTime,
    `BgpLsId`    UInt64,
    `overload`   String,
    `SourceId`   String,
    `NeighborIp` String
)
ENGINE = ReplacingMergeTree(Age)
ORDER BY (Prefix, Node, IgpRouter, NeighborIp)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS gobgp.bgp_ls_prefixV4
(
    `Prefix`         String,
    `IgpRouterID`    String,
    `Asn`            UInt32,
    `IpReachability` String,
    `SourceId`       String,
    `NeighborIp`     String,
    `Age`            DateTime,
    `BgpLsId`        UInt64
)
ENGINE = ReplacingMergeTree(Age)
ORDER BY (IgpRouterID, IpReachability, NeighborIp)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS gobgp.bgp_ls_prefixV6
(
    `Prefix`         String,
    `IgpRouterID`    String,
    `Asn`            UInt32,
    `IpReachability` String,
    `SourceId`       String,
    `NeighborIp`     String,
    `Age`            DateTime,
    `BgpLsId`        UInt64
)
ENGINE = ReplacingMergeTree(Age)
ORDER BY (IgpRouterID, IpReachability, NeighborIp)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS gobgp.SAFI_LINK_STATE_LINK
(
    `Family`                String,
    `Type`                  String,
    `Best`                  Bool,
    `NeighborIp`            String,
    `SourceId`              String,
    `Asn`                   UInt32,
    `Age`                   DateTime,
    `Withdraw`              Bool,
    `ProtocolID`            String,
    `LinkLocalIgpRouterId`  String,
    `LinkRemoteIgpRouterId` String,
    `LinkLocalOspfAreaId`   String,
    `LinkRemoteOspfAreaId`  String,
    `LinkLinkLocalId`       String,
    `LinkLinkRemoteId`      String,
    `LinkInterfaceAddrIpv4` String,
    `LinkNeighborAddrIpv4`  String,
    `LinkInterfaceAddrIpv6` String,
    `LinkNeighborAddrIpv6`  String,
    `LinkLocalRouterId`     String,
    `LinkRemoteRouterId`    String,
    `LinkIgpMetric`         UInt64,
    `LinkSrAdjacencySid`    UInt64,
    `LinkDefaultTeMetric`   UInt64,
    `LinkBandwidth`         UInt64,
    `DateSrv`               DateTime64(4)
)
ENGINE = ReplacingMergeTree(Age)
ORDER BY (LinkLocalIgpRouterId, LinkRemoteIgpRouterId, LinkLinkLocalId, LinkLinkRemoteId,
          LinkInterfaceAddrIpv4, LinkNeighborAddrIpv4, LinkInterfaceAddrIpv6, LinkNeighborAddrIpv6,
          LinkLocalRouterId, LinkRemoteRouterId)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS gobgp.SAFI_LINK_STATE_NODE
(
    `Family`               String,
    `Type`                 String,
    `Best`                 Bool,
    `NeighborIp`           String,
    `SourceId`             String,
    `Asn`                  UInt32,
    `Age`                  DateTime,
    `Withdraw`             Bool,
    `ProtocolID`           String,
    `NodeLocalIgpRouterId` String,
    `NodeLocalBgpLsId`     UInt64,
    `NodeName`             String,
    `NodeOverload`         Bool,
    `NodeRouterId`         String,
    `NodeIsisArea`         String,
    `DateSrv`              DateTime64(4)
)
ENGINE = ReplacingMergeTree(Age)
ORDER BY (NodeLocalIgpRouterId, ProtocolID, NeighborIp)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS gobgp.SAFI_LINK_STATE_PREFIXE_V4
(
    `Family`                    String,
    `Type`                      String,
    `Best`                      Bool,
    `NeighborIp`                String,
    `SourceId`                  String,
    `Asn`                       UInt32,
    `Age`                       DateTime,
    `Withdraw`                  Bool,
    `ProtocolID`                String,
    `PrefixeLocalIgpRouterId`   String,
    `PrefixeLocalBgpLsId`       UInt64,
    `PrefixeLocalOspfAreaId`    UInt64,
    `PrefixeIpReachability`     String,
    `PrefixeOspfRouteType`      String,
    `DateSrv`                   DateTime64(4)
)
ENGINE = ReplacingMergeTree(Age)
ORDER BY (PrefixeLocalIgpRouterId, PrefixeIpReachability, NeighborIp)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS gobgp.SAFI_LINK_STATE_PREFIXE_V6
(
    `Family`                    String,
    `Type`                      String,
    `Best`                      Bool,
    `NeighborIp`                String,
    `SourceId`                  String,
    `Asn`                       UInt32,
    `Age`                       DateTime,
    `Withdraw`                  Bool,
    `ProtocolID`                String,
    `PrefixeLocalIgpRouterId`   String,
    `PrefixeLocalBgpLsId`       UInt64,
    `PrefixeLocalOspfAreaId`    UInt64,
    `PrefixeIpReachability`     String,
    `PrefixeOspfRouteType`      String,
    `DateSrv`                   DateTime64(4)
)
ENGINE = ReplacingMergeTree(Age)
ORDER BY (PrefixeLocalIgpRouterId, PrefixeIpReachability, NeighborIp)
SETTINGS index_granularity = 8192;

-- ============================================================
-- Tables MONITOR__* — flux d'événements BGP en continu (append-only,
-- alimentées par Vector). MergeTree classique (pas ReplacingMergeTree) :
-- on veut conserver chaque événement, pas dédupliquer un état courant.
-- ============================================================

CREATE TABLE IF NOT EXISTS gobgp.monitor_bgp_ipv4unicast
(
    `Family`             String,
    `Prefix`             String,
    `PrefixLen`          UInt8,
    `Best`               Bool,
    `NeighborIp`         String,
    `SourceId`           String,
    `Asn`                UInt32,
    `Age`                DateTime,
    `Withdraw`           Bool,
    `Origin`             String,
    `AsPath`             String,
    `Med`                UInt32,
    `LocalPref`          UInt32,
    `Communities`        String,
    `ClusterList`        String,
    `OriginatorId`       String,
    `NextHops`           String,
    `AtomicAggregate`    Bool,
    `AggregatorAsn`      UInt32,
    `AggregatorAddress`  String
)
ENGINE = MergeTree
ORDER BY (Prefix, PrefixLen, Age)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS gobgp.monitor_bgp_ls_link
(
    `Family`                String,
    `Type`                  String,
    `Best`                  Bool,
    `NeighborIp`            String,
    `SourceId`              String,
    `Asn`                   UInt32,
    `Age`                   DateTime,
    `Withdraw`              Bool,
    `ProtocolID`            String,
    `LinkRemoteIgpRouterId` String,
    `LinkRemoteOspfAreaId`  String,
    `LinkLinkLocalId`       String,
    `LinkLinkRemoteId`      String,
    `LinkInterfaceAddrIpv4` String,
    `LinkNeighborAddrIpv4`  String,
    `LinkInterfaceAddrIpv6` String,
    `LinkNeighborAddrIpv6`  String,
    `LinkLocalRouterId`     String,
    `LinkRemoteRouterId`    String,
    `LinkIgpMetric`         UInt64,
    `LinkSrAdjacencySid`    UInt64,
    `LinkDefaultTeMetric`   UInt64,
    `LinkBandwidth`         UInt64
)
ENGINE = MergeTree
ORDER BY (LinkLocalRouterId, LinkRemoteRouterId, Age)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS gobgp.monitor_bgp_ls_node
(
    `Family`               String,
    `Type`                 String,
    `Best`                 Bool,
    `NeighborIp`           String,
    `SourceId`             String,
    `Asn`                  UInt32,
    `Age`                  DateTime,
    `Withdraw`             Bool,
    `ProtocolID`           String,
    `NodeLocalIgpRouterId` String,
    `NodeLocalBgpLsId`     UInt64,
    `NodeName`             String,
    `NodeOverload`         Bool,
    `NodeRouterId`         String,
    `NodeIsisArea`         String
)
ENGINE = MergeTree
ORDER BY (NodeLocalIgpRouterId, Age)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS gobgp.monitor_bgp_ls_prefixev4
(
    `Family`                  String,
    `Type`                    String,
    `Best`                    Bool,
    `NeighborIp`              String,
    `SourceId`                String,
    `Asn`                     UInt32,
    `Age`                     DateTime,
    `Withdraw`                Bool,
    `ProtocolID`              String,
    `PrefixeLocalIgpRouterId` String,
    `PrefixeLocalBgpLsId`     UInt64,
    `PrefixeLocalOspfAreaId`  UInt64,
    `PrefixeIpReachability`   String,
    `PrefixeOspfRouteType`    String
)
ENGINE = MergeTree
ORDER BY (PrefixeLocalIgpRouterId, PrefixeIpReachability, Age)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS gobgp.monitor_bgp_ls_prefixev6
(
    `Family`                  String,
    `Type`                    String,
    `Best`                    Bool,
    `NeighborIp`              String,
    `SourceId`                String,
    `Asn`                     UInt32,
    `Age`                     DateTime,
    `Withdraw`                Bool,
    `ProtocolID`              String,
    `PrefixeLocalIgpRouterId` String,
    `PrefixeLocalBgpLsId`     UInt64,
    `PrefixeLocalOspfAreaId`  UInt64,
    `PrefixeIpReachability`   String,
    `PrefixeOspfRouteType`    String
)
ENGINE = MergeTree
ORDER BY (PrefixeLocalIgpRouterId, PrefixeIpReachability, Age)
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS gobgp.monitor_bgp_lu
(
    `Family`          String,
    `Prefix`          String,
    `PrefixLen`       UInt8,
    `Label`           UInt32,
    `GetCommunities`  String,
    `Best`            Bool,
    `NeighborIp`      String,
    `SourceId`        String,
    `Asn`             UInt32,
    `Age`             DateTime,
    `Withdraw`        Bool,
    `NextHops`        String,
    `OriginatorId`    String,
    `ClusterList`     String,
    `Origin`          String,
    `LocalPref`       UInt32,
    `AsPath`          String
)
ENGINE = MergeTree
ORDER BY (Prefix, PrefixLen, Age)
SETTINGS index_granularity = 8192;

-- Note : "Communities" apparaît deux fois dans le header source de
-- MONITOR__bgp_vpn.csv (quirk de l'outil amont) -> 2e occurrence renommée Communities2.
CREATE TABLE IF NOT EXISTS gobgp.monitor_bgp_vpn
(
    `Family`         String,
    `Prefix`         String,
    `Label`          UInt32,
    `PrefixLen`      UInt8,
    `Communities`    String,
    `Best`           Bool,
    `NeighborIp`     String,
    `SourceId`       String,
    `Asn`            UInt32,
    `Age`            DateTime,
    `Withdraw`       Bool,
    `RdAdmin`        String,
    `RdAssigned`     String,
    `Origin`         String,
    `AsPath`         String,
    `Med`            UInt32,
    `LocalPref`      UInt32,
    `ExtCommunities` String,
    `ClusterList`    String,
    `OriginatorId`   String,
    `NextHops`       String,
    `Communities2`   String
)
ENGINE = MergeTree
ORDER BY (Prefix, PrefixLen, Age)
SETTINGS index_granularity = 8192;

-- ── Utilisateur applicatif dédié (moindre privilège, pas admin) ──
CREATE ROLE IF NOT EXISTS role_gobgp_writer;
GRANT SELECT, INSERT ON gobgp.* TO role_gobgp_writer;
CREATE USER IF NOT EXISTS gobgp_writer
    IDENTIFIED WITH sha256_password BY '<MOT_DE_PASSE>'
    HOST ANY
    DEFAULT ROLE role_gobgp_writer;

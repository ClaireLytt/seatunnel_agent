-- Grant surface demo: public exposure, broad privileges, PII-table grants.
GRANT SELECT ON DATABASE dwd TO PUBLIC;
GRANT ALL PRIVILEGES ON TABLE dws.agg_daily TO ROLE etl;
GRANT SELECT ON TABLE dwd.fact_orders TO USER analyst;
GRANT SELECT ON TABLE dwd.dead_end TO USER intern;
REVOKE SELECT ON TABLE dwd.dead_end FROM USER intern;

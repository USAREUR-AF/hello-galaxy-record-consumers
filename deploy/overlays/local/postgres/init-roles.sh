#!/bin/sh
# Run once by the PostgreSQL image when the data directory is first made.
# Two roles, each with what its service needs and nothing more:
#   receiver  creates the tables and writes rows
#   board     reads; it is granted SELECT on each table by the receiver
# The passwords come from the environment (in the cluster, from the Secret).
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v receiver_password="$RECEIVER_PASSWORD" -v board_password="$BOARD_PASSWORD" <<'SQL'
CREATE ROLE receiver LOGIN PASSWORD :'receiver_password';
CREATE ROLE board LOGIN PASSWORD :'board_password';
REVOKE ALL ON DATABASE records FROM PUBLIC;
GRANT CONNECT ON DATABASE records TO receiver, board;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO receiver;
GRANT USAGE ON SCHEMA public TO board;
SQL

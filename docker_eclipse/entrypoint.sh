#!/bin/bash
set -euo pipefail

export PATH="$JAVA_HOME/bin:$PATH"

# PostgreSQL: trust local connections and create the role/database used by
# eclipseCommandline.properties.
PGHBA=/etc/postgresql/12/main/pg_hba.conf
if [ -f "$PGHBA" ]; then
    sed -i -E 's/^(local[[:space:]]+all[[:space:]]+all[[:space:]]+).*/\1trust/' "$PGHBA"
    sed -i -E 's/^(host[[:space:]]+all[[:space:]]+all[[:space:]]+127\.0\.0\.1\/32[[:space:]]+).*/\1trust/' "$PGHBA"
    sed -i -E 's/^(host[[:space:]]+all[[:space:]]+all[[:space:]]+::1\/128[[:space:]]+).*/\1trust/' "$PGHBA"
fi
service postgresql start
for _ in $(seq 1 30); do
    pg_isready -q && break
    sleep 1
done

su postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='evermal'\"" | grep -q 1 \
    || su postgres -c "psql -c \"CREATE ROLE evermal LOGIN SUPERUSER\""
su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='comment_classification'\"" | grep -q 1 \
    || su postgres -c "createdb -O evermal comment_classification"

mkdir -p /workspace
exec xvfb-run -a /opt/eclipse/eclipse \
    -nosplash \
    -data /workspace \
    -application eclipse.commandline.application \
    -consoleLog \
    "$@"

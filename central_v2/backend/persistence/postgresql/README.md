# PostgreSQL persistence adapter

This package is an opt-in M3 adapter. Existing executors, migration registry,
`dual_write`, and `read_authority=legacy` remain untouched.

## Configuration

Install `requirements.txt` in the application environment. Supply either
`FOMINHA_PG_DSN` or the discrete `FOMINHA_PG_*` values shown in `.env.example`.
The package reads only process environment variables and does not load secrets
from project JSON, the operational data root, or a dotenv file. Set
`FOMINHA_ARTIFACT_ROOT` explicitly when constructing `ArtifactStore`; never use
an operational image directory as its root during development or tests.

## Isolated development database

Use a disposable local cluster and a fresh database. Example with PostgreSQL
16 binaries (adjust the installation paths if needed):

```sh
initdb -D /private/tmp/fominha-pg-m3/data --auth-local=trust --auth-host=trust
pg_ctl -D /private/tmp/fominha-pg-m3/data -l /private/tmp/fominha-pg-m3/server.log \
  -o "-h 127.0.0.1 -p 55432" start
createdb -h 127.0.0.1 -p 55432 fominha_m3_dev
createuser -h 127.0.0.1 -p 55432 fominha_dev
```

Set `FOMINHA_PG_MIGRATION_DSN` to the disposable cluster administrator
connection and `FOMINHA_PG_DSN` to the restricted application connection.
Apply migrations, then grant membership in the no-login role:

```sh
PYTHONPATH=central_v2/backend python3 -m persistence.postgresql check
FOMINHA_PG_MIGRATION_DSN="postgresql://postgres@127.0.0.1:55432/fominha_m3_dev" \
  PYTHONPATH=central_v2/backend python3 -m persistence.postgresql up
psql "$FOMINHA_PG_MIGRATION_DSN" -c "GRANT fominha_app TO fominha_dev"
PYTHONPATH=central_v2/backend python3 -m persistence.postgresql status
```

The down command rolls back exactly one latest migration and is for disposable
development databases only. Do not point it at an operational database.

## Integration tests

The PostgreSQL integration suite requires a fresh, empty database whose name
starts with `fominha_m3_test_`. Create a new database for each full suite run;
the tests reject other database names and refuse a database that already has
the migration ledger. Example:

```sh
createdb -h 127.0.0.1 -p 55432 fominha_m3_test_20261023
FOMINHA_PG_TEST_DSN="postgresql://fominha_dev@127.0.0.1:55432/fominha_m3_test_20261023" \
  PYTHONPATH=central_v2/backend python3 -m unittest discover -s dev/tests/postgresql -v
```

The suite applies migrations to that empty database and creates/drops a
separate temporary restore database. It uses only synthetic bytes and a
temporary Artifact Store; it does not clean or reset an existing database.

## Backups

Back up PostgreSQL custom format and the Artifact Store under one coordinated
maintenance point, recording the schema migration version, active revisions,
object keys and SHA-256 checksums in the backup manifest. A PostgreSQL-only dump
is not a complete recovery when blobs are missing.

```sh
pg_dump --format=custom --file=/private/tmp/fominha-m3.dump \
  --dbname="$FOMINHA_PG_DSN"
createdb -h 127.0.0.1 -p 55432 fominha_m3_restore
pg_restore --exit-on-error --dbname=fominha_m3_restore /private/tmp/fominha-m3.dump
```

Restore into a fresh disposable database; do not use `--clean` against a shared
or operational database. Required no-login roles are created by migrations;
restore environments must also preserve role definitions and memberships.

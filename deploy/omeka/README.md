# Omeka S, locally

A proof of concept: somewhere to see what transcripts look like once they are
in a collections system, and to develop `tetrak_publish` against something
real. It is not a deployment, and nothing here should be pointed at material
that matters.

## Running it

```bash
cd deploy/omeka
cp .env.example .env
docker compose up -d --build
open http://localhost:8080
```

The first visit runs Omeka's installer, which asks for the admin email and
password to create. Those are yours and are not stored in this directory.

```bash
docker compose down       # stop, keep the data
docker compose down -v    # stop, discard the data and start clean
```

## What it is

Two services and two named volumes. Omeka S needs a MySQL-compatible database,
and MariaDB is what its own documentation assumes.

Omeka has no official Docker image, and the community ones are abandoned,
amd64-only, or ignore environment configuration. So the `Dockerfile` here
builds one from the official release zip on `php:8.2-apache`, checking the zip
against a pinned SHA-256. `docker-entrypoint.sh` writes Omeka's
`config/database.ini` from the `OMEKA_DB_*` variables at start-up, so `.env`
stays the only place the credentials live. To upgrade Omeka, change
`OMEKA_VERSION` and `OMEKA_SHA256` in the `Dockerfile` together, bump the
image tag in `compose.yaml` to match, and rebuild.

Both versions are pinned rather than tracking `latest`, so a proof of concept
somebody comes back to in three months still comes up. The database has a real
health check and the app waits on it, because Omeka's installer fails
confusingly against a database that is still starting.

## Two deliberate choices

**It binds to `127.0.0.1`, not to every interface.** There is a window between
`compose up` and finishing the installer where anyone who can reach the port
can claim the admin account.

**The database credentials in `.env.example` are not secrets.** They are local
scaffolding for a service on localhost. `.env` is gitignored so a real one can
be kept without it being committed, but the honest position is that this stack
is not built to hold anything sensitive.

## Where the code goes

`src/tetrak_publish/` — destinations behind one interface, discovered from a
registry, following the pattern `src/tetrak_ocr/registry.py` established.
Publishing belongs to neither pipeline because both produce transcripts.

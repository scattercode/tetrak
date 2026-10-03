#!/bin/sh
# Write Omeka's database.ini from the environment, then hand over to Apache.
#
# Omeka reads its connection settings only from config/database.ini. Rendering
# it at start-up keeps .env the single place the credentials live, rather than
# repeating them in a mounted file.
set -eu

: "${OMEKA_DB_HOST:?OMEKA_DB_HOST is not set}"
: "${OMEKA_DB_NAME:?OMEKA_DB_NAME is not set -- copy .env.example to .env}"
: "${OMEKA_DB_USER:?OMEKA_DB_USER is not set -- copy .env.example to .env}"
: "${OMEKA_DB_PASSWORD:?OMEKA_DB_PASSWORD is not set -- copy .env.example to .env}"

cat > /var/www/html/config/database.ini <<EOF
user     = "${OMEKA_DB_USER}"
password = "${OMEKA_DB_PASSWORD}"
dbname   = "${OMEKA_DB_NAME}"
host     = "${OMEKA_DB_HOST}"
EOF

# A fresh named volume mounted over files/ comes up root-owned.
chown www-data:www-data /var/www/html/files

exec docker-php-entrypoint "$@"

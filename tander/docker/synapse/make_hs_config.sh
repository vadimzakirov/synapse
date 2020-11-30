#!/bin/bash

echo "Start generate $HOMESERVER_CONFIG_PATH"

# shellcheck disable=SC2059
printf "
Config parameters:
START_PORT: $START_PORT
CONNECT_DB_NAME: $CONNECT_DB_NAME
CONNECT_DB_USER: $CONNECT_DB_USER
CONNECT_DB_PASSWORD: $CONNECT_DB_PASSWORD
CONNECT_DB_PORT: $CONNECT_DB_PORT\n"

python -m synapse.app.homeserver \
    --server-name "$SYNAPSE_SERVER_NAME" \
    --config-path "$SYNAPSE_CONFIG_PATH" \
    --generate-config \
    --report-stats=no

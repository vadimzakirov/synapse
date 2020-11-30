#!/bin/bash
SYNAPSE_PACKAGE_PATH="/usr/local/lib/python3.8/site-packages/synapse"
pip install psycopg2
echo "Start copy synapse as system python package from /synapse to $SYNAPSE_PACKAGE_PATH"
cp -R /synapse /usr/local/lib/python3.8/site-packages
if [ -e "$SYNAPSE_CONFIG_PATH" ]
  then
    echo "homeserver.yaml already exists in $SYNAPSE_CONFIG_PATH: pass"
  else
    sh /scripts/make_hs_config.sh
fi
/usr/local/bin/python -m synapse.app.homeserver --config-path="$SYNAPSE_CONFIG_PATH"
while [ 1 ]
do
  cat
done

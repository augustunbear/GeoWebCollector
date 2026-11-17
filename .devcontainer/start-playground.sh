#!/usr/bin/env bash
set -euo pipefail

if ! curl --fail --silent --output /dev/null http://127.0.0.1:8766/api/operations; then
  nohup python -m geowebcollector.playground > /tmp/geowebcollector-playground.log 2>&1 < /dev/null &
fi

for attempt in {1..20}; do
  if curl --fail --silent --output /dev/null http://127.0.0.1:8766/api/operations; then
    printf 'Playground ready. Open the private 8766 port in Codespaces Ports.\n'
    exit 0
  fi
  sleep 1
done
printf 'Playground did not start; see /tmp/geowebcollector-playground.log\n' >&2
exit 1

#!/bin/sh
set -eu

until /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:29092 --list >/dev/null 2>&1; do
  sleep 2
done

for topic in docpipe-poc docpipe-poc-notifications; do
  /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server kafka:29092 \
    --create --topic "$topic" \
    --partitions 1 --replication-factor 1 --if-not-exists
done

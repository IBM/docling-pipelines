#!/bin/sh
set -e

# Wait for MinIO to be ready before doing anything.
# Retries every 2 seconds, gives up after 30 attempts (~60s).
i=0
until mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" > /dev/null 2>&1; do
  i=$((i+1))
  if [ "$i" -gt 30 ]; then echo "MinIO did not become ready. Exiting."; exit 1; fi
  sleep 2
done
echo "MinIO is ready."

# Create the bucket. Safe to re-run — skips if it already exists.
mc mb --ignore-existing "local/$MINIO_BUCKET"
echo "Bucket '$MINIO_BUCKET' ready."

# Seed the bucket with any PDFs from the local ./pdfs folder.
# Skips silently if no PDFs are present.
seeded=0
for f in /seed/*.pdf; do
  [ -f "$f" ] || continue
  mc cp "$f" "local/$MINIO_BUCKET/pdfs/"
  seeded=$((seeded+1))
done
echo "Seeded $seeded PDF(s) into $MINIO_BUCKET/pdfs/."

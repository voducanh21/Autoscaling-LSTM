#!/usr/bin/env bash
set -euo pipefail

: "${AIRFLOW_PASSWORD:?Set AIRFLOW_PASSWORD in Replit Secrets first}"
AIRFLOW_USERNAME="${AIRFLOW_USERNAME:-admin}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
secret_file="$tmp_dir/airflow-trigger.env"
umask 077
printf 'AIRFLOW_USERNAME=%s\nAIRFLOW_PASSWORD=%s\n' \
  "$AIRFLOW_USERNAME" "$AIRFLOW_PASSWORD" > "$secret_file"

kubectl create secret generic airflow-trigger-secret \
  --namespace airflow \
  --from-env-file="$secret_file" \
  --dry-run=client -o yaml | kubectl apply -f -

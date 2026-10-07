#!/usr/bin/env bash
set -euo pipefail

: "${AIRFLOW_MYSQL_ROOT_PASSWORD:?Set AIRFLOW_MYSQL_ROOT_PASSWORD in Replit Secrets first}"
: "${AIRFLOW_MYSQL_PASSWORD:?Set AIRFLOW_MYSQL_PASSWORD in Replit Secrets first}"
AIRFLOW_NAMESPACE="${AIRFLOW_NAMESPACE:-airflow}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
umask 077
secret_file="$tmp_dir/airflow-mysql.env"
printf 'mysql-root-password=%s\nmysql-password=%s\n' \
  "$AIRFLOW_MYSQL_ROOT_PASSWORD" "$AIRFLOW_MYSQL_PASSWORD" > "$secret_file"

kubectl create secret generic airflow-mysql-auth \
  --namespace "$AIRFLOW_NAMESPACE" \
  --from-env-file="$secret_file" \
  --dry-run=client -o yaml | kubectl apply -f -

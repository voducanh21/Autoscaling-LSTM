#!/usr/bin/env bash
set -euo pipefail

: "${MLFLOW_DATABASE_PASSWORD:?Set MLFLOW_DATABASE_PASSWORD in Replit Secrets first}"
: "${AWS_ACCESS_KEY_ID:?Set AWS_ACCESS_KEY_ID in Replit Secrets first}"
: "${AWS_SECRET_ACCESS_KEY:?Set AWS_SECRET_ACCESS_KEY in Replit Secrets first}"

MLFLOW_BACKEND_STORE_URI="$(python - <<'PY'
import os
from urllib.parse import quote

password = quote(os.environ["MLFLOW_DATABASE_PASSWORD"], safe="")
print(
    "postgresql://mlflow:"
    + password
    + "@mlflow-postgresql.mlflow.svc.cluster.local:5432/mlflow"
)
PY
)"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
umask 077

mlflow_file="$tmp_dir/mlflow-db.env"
printf 'MLFLOW_DATABASE_PASSWORD=%s\nMLFLOW_BACKEND_STORE_URI=%s\n' \
  "$MLFLOW_DATABASE_PASSWORD" "$MLFLOW_BACKEND_STORE_URI" > "$mlflow_file"
kubectl create secret generic mlflow-db-credentials \
  --namespace mlflow \
  --from-env-file="$mlflow_file" \
  --dry-run=client -o yaml | kubectl apply -f -

minio_file="$tmp_dir/minio-credentials.env"
printf 'AWS_ACCESS_KEY_ID=%s\nAWS_SECRET_ACCESS_KEY=%s\n' \
  "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY" > "$minio_file"
kubectl create secret generic minio-cred \
  --namespace mlflow \
  --from-env-file="$minio_file" \
  --dry-run=client -o yaml | kubectl apply -f -

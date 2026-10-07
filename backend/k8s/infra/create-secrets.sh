#!/usr/bin/env bash
set -euo pipefail

: "${JWT_SECRET:?Set JWT_SECRET in Replit Secrets first}"
: "${MYSQL_ROOT_PASSWORD:?Set MYSQL_ROOT_PASSWORD in Replit Secrets first}"
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in Replit Secrets first}"
: "${MONGO_INITDB_ROOT_PASSWORD:?Set MONGO_INITDB_ROOT_PASSWORD in Replit Secrets first}"
: "${SPRING_DATA_MONGODB_URI:?Set SPRING_DATA_MONGODB_URI in Replit Secrets first}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
umask 077

create_secret() {
  local namespace="$1"
  local name="$2"
  shift 2
  local file="$tmp_dir/${name}.env"
  : > "$file"
  while (($#)); do
    local key="$1"
    local env_name="$2"
    printf '%s=%s\n' "$key" "${!env_name}" >> "$file"
    shift 2
  done
  kubectl create secret generic "$name" \
    --namespace "$namespace" \
    --from-env-file="$file" \
    --dry-run=client -o yaml | kubectl apply -f -
}

create_secret infra mongo-secrets \
  MONGO_INITDB_ROOT_PASSWORD MONGO_INITDB_ROOT_PASSWORD
create_secret infra mysql-secrets \
  mysql_root_password MYSQL_ROOT_PASSWORD
create_secret infra postgres-secrets \
  postgres_password POSTGRES_PASSWORD
create_secret apps application-secrets \
  JWT_SECRET JWT_SECRET \
  MYSQL_ROOT_PASSWORD MYSQL_ROOT_PASSWORD \
  POSTGRES_PASSWORD POSTGRES_PASSWORD
create_secret apps order-service-mongodb \
  SPRING_DATA_MONGODB_URI SPRING_DATA_MONGODB_URI

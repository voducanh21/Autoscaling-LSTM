from datetime import datetime
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes import client as k8s

bronze_script = r"""
import os, sys, requests, pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PROM_URL    = os.getenv("PROM_URL")
BUCKET      = os.getenv("S3_BUCKET", "datalake")
PREFIX      = os.getenv("S3_PREFIX", "bronze/metrics")
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
AWS_KEY     = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET  = os.getenv("AWS_SECRET_ACCESS_KEY")
TZ_NAME     = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")

try:
    TZ = ZoneInfo(TZ_NAME)
except Exception:
    print(f"[WARN] ZoneInfo('{TZ_NAME}') not available. Fallback to UTC.", file=sys.stderr)
    TZ = timezone.utc

storage_opts = {
    "key": AWS_KEY,
    "secret": AWS_SECRET,
    "client_kwargs": {"endpoint_url": S3_ENDPOINT}
}

def prom_query(q):
    r = requests.get(f"{PROM_URL}/api/v1/query", params={"query": q}, timeout=10)
    r.raise_for_status()
    return r.json()["data"]["result"]

def get_scalar(query):
    res = prom_query(query)
    if not res:
        return None
    try:
        return float(res[0]["value"][1])
    except Exception:
        return None

def get_cpu_cores_1m(service):
    return get_scalar(f'sum(pod:cpu:usage1m{{namespace="apps",pod=~"{service}-.*"}})')

def get_mem_bytes(service):
    return get_scalar(f'sum(pod:mem:usage{{namespace="apps",pod=~"{service}-.*"}})')

def collect(service):
    rps = get_scalar(f'svc:qps:rate1m{{job="{service}"}}')
    p95_ms = get_scalar(f'svc:latency_p95_ms_1m{{job="{service}"}}')
    cpu = get_cpu_cores_1m(service)
    mem = get_mem_bytes(service)

    now = datetime.now(TZ)
    return {
        "ts": now.isoformat(),
        "service": str(service),
        "rps_1m": rps,
        "latency_p95_ms": p95_ms,
        "cpu_cores_1m": cpu,
        "mem_bytes": mem,
        "hour": now.hour,
        "dow": now.weekday()
    }

def main():
    jobs = {m["metric"]["job"] for m in prom_query("svc:qps:rate1m")}
    if not jobs:
        print("[WARN] No services discovered from svc:qps:rate1m"); return

    rows = [collect(svc) for svc in sorted(jobs)]
    df = pd.DataFrame(rows)

    df["service"] = df["service"].astype(str)
    df["ts"] = pd.to_datetime(df["ts"]).astype(str)
    df = df.astype({
        "rps_1m": "float64",
        "latency_p95_ms": "float64",
        "cpu_cores_1m": "float64",
        "mem_bytes": "float64",
        "hour": "int64",
        "dow": "int64",
    })

    now = datetime.now(TZ)
    date = now.strftime("%Y-%m-%d")
    part = int(now.timestamp())

    for svc, sub in df.groupby("service"):
        path = f"s3://{BUCKET}/{PREFIX}/date={date}/service={svc}/part-{part}.parquet"
        sub.to_parquet(
            path,
            index=False,
            engine="pyarrow",
            storage_options=storage_opts,
            use_dictionary=False
        )
        print(f"[OK] wrote {path} (tz={TZ_NAME})")

if __name__ == "__main__":
    main()
"""

with DAG(
        dag_id="bronze_metrics_dag",
        start_date=datetime(2025, 9, 1),
        schedule=None,
        catchup=False,
        tags=["bronze", "metrics"],
) as dag:

    bronze = KubernetesPodOperator(
        task_id="bronze_metrics",
        name="bronze-metrics",
        namespace="airflow",
        image="python:3.11-slim",
        cmds=["/bin/sh", "-lc"],
        arguments=[
            # Ghi script ra file, cài dependencies và chạy
            f"echo '{bronze_script}' > /app/metrics_dumper.py && "
            "pip install -q pandas pyarrow requests fsspec s3fs tzdata && "
            "python /app/metrics_dumper.py"
        ],
        env_vars={
            "PROM_URL": "http://kube-prometheus-kube-prome-prometheus.monitoring.svc.cluster.local:9090",
            "S3_BUCKET": "datalake",
            "S3_PREFIX": "bronze/metrics",
            "S3_ENDPOINT": "http://minio.minio.svc.cluster.local:9000",
            "TIMEZONE": "Asia/Ho_Chi_Minh",
        },
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="minio-cred"))
        ],
        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )

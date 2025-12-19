#!/usr/bin/env python3
import requests
import csv
import datetime

PROM_URL = "http://localhost:9090"  # sửa nếu Prometheus endpoint khác

# ================== CẤU HÌNH THỜI GIAN TEST ==================
START_ISO = "2025-12-11T13:56:26Z"   # startTime của load test
DURATION_MINUTES = 60               # số phút export
# =============================================================

STEP = "60s"  # mỗi phút 1 sample

# ===== METRICS trong svc-rules (theo job) =====
METRICS = {
    "p95_ms":   "svc:latency_p95_ms_1m",
    "rps_all":  "svc:qps:rate1m",
    "sla":      "svc:sla_violation_1m",
    "replicas": "svc:replicas:available:1m",
    "cpu":      "svc:cpu_usage_rate_1m",  # CPU theo SERVICE (cores/min)
}

# ===== LIST SERVICE HỢP LỆ (5 backend service) =====
VALID_SERVICES = {
    "api-gateway",
    "authentication-service",
    "order-service",
    "payment-service",
    "product-service",
}


def to_unix_ts(iso_str: str) -> int:
    """ISO 8601 → UNIX timestamp."""
    s = iso_str.strip()
    if s.endswith("Z"):
        s = s.replace("Z", "+00:00")
    return int(datetime.datetime.fromisoformat(s).timestamp())


def resolve_time_range():
    start_ts = to_unix_ts(START_ISO)
    end_ts = start_ts + DURATION_MINUTES * 60
    print(f"[INFO] START={start_ts}, END={end_ts}")
    return start_ts, end_ts


def query_range(expr: str, start: int, end: int, step: str):
    resp = requests.get(
        f"{PROM_URL}/api/v1/query_range",
        params={"query": expr, "start": start, "end": end, "step": step},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data["status"] != "success":
        raise RuntimeError(f"Query failed: {expr}")
    return data["data"]["result"]


def resolve_service(labels: dict) -> str:
    """svc-rules đang sum by (job) → dùng label `job`."""
    return labels.get("job", "unknown")


def main():
    start_ts, end_ts = resolve_time_range()

    rows = {}  # {(service, ts) -> metric values}

    for metric_name, expr in METRICS.items():
        print(f"[INFO] Querying {metric_name}")
        series_list = query_range(expr, start_ts, end_ts, STEP)

        for series in series_list:
            labels = series.get("metric", {})
            service = resolve_service(labels)

            # Chỉ lấy 5 backend service
            if service not in VALID_SERVICES:
                continue

            for ts, value in series["values"]:
                ts = int(float(ts))
                if value == "NaN":
                    continue

                key = (service, ts)
                rec = rows.setdefault(key, {})
                rec[metric_name] = float(value)

    # ===== GHI CSV =====
    with open("sla_export.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "timestamp_iso",
            "service",
            "p95_ms",
            "rps_all",
            "sla_violation_flag",
            "replicas",
            "cpu_total",
        ])

        for (service, ts), vals in sorted(rows.items(), key=lambda x: (x[0][1], x[0][0])):
            ts_iso = datetime.datetime.utcfromtimestamp(ts).isoformat()

            p95_ms = vals.get("p95_ms", "")
            rps_all = vals.get("rps_all", "")
            sla_raw = vals.get("sla", 0.0)
            sla_flag = 1 if sla_raw > 0 else 0
            replicas = vals.get("replicas", "")
            cpu = vals.get("cpu", "")

            w.writerow([
                ts_iso,
                service,
                p95_ms,
                rps_all,
                sla_flag,
                replicas,
                cpu,
            ])

    print("[DONE] Exported sla_export.csv")


if __name__ == "__main__":
    main()

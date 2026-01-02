#!/usr/bin/env python3
import requests
import csv
import datetime

PROM_URL = "http://localhost:9090"  # sửa nếu Prometheus endpoint khác

# ================== CẤU HÌNH THỜI GIAN TEST ==================
START_ISO = "2026-01-02T06:11:15Z"   # startTime của load test
DURATION_MINUTES = 60            # số phút export
# =============================================================

STEP = "60s"  # mỗi phút 1 sample

# SLA threshold (ms) để tính theo p95 nếu có
SLA_THRESHOLD_MS = 300.0

# ===== METRICS trong svc-rules (theo job) =====
METRICS = {
    "p95_ms":   "svc:latency_p95_ms_1m",
    "rps_all":  "svc:qps:rate1m",
    "sla":      "svc:sla_violation_1m",
    "replicas": "svc:replicas:available:1m",

    # CPU tổng theo service (cores)
    "cpu_total_cores": "svc:cpu_usage_rate_1m",

    # CPU utilization % giống HPA (usage / requests * 100)
    "cpu_util_hpa_pct": "100 * svc:cpu_usage_rate_1m / clamp_min(svc:cpu_requests, 0.001)",
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


def mean(xs):
    xs = [x for x in xs if x is not None]
    return (sum(xs) / len(xs)) if xs else None


def main():
    start_ts, end_ts = resolve_time_range()

    rows = {}  # {(service, ts) -> metric values}

    # ================== QUERY & BUILD ROWS ==================
    for metric_name, expr in METRICS.items():
        print(f"[INFO] Querying {metric_name}")
        series_list = query_range(expr, start_ts, end_ts, STEP)

        for series in series_list:
            labels = series.get("metric", {})
            service = resolve_service(labels)

            if service not in VALID_SERVICES:
                continue

            for ts, value in series.get("values", []):
                ts = int(float(ts))
                if value in ("NaN", "+Inf", "-Inf"):
                    continue

                key = (service, ts)
                rec = rows.setdefault(key, {})
                try:
                    rec[metric_name] = float(value)
                except Exception:
                    continue

    # ================== WRITE TIMESERIES CSV ==================
    with open("sla_export.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "timestamp_iso",
            "service",
            "p95_ms",
            "rps_all",
            "sla_violation_flag",
            "replicas",
            "cpu_total_cores",
            "cpu_util_hpa_pct",
        ])

        for service in sorted(VALID_SERVICES):
            ts_list = sorted([ts for (svc, ts) in rows.keys() if svc == service])
            for ts in ts_list:
                vals = rows.get((service, ts), {})
                ts_iso = datetime.datetime.fromtimestamp(
                    ts, tz=datetime.timezone.utc
                ).isoformat().replace("+00:00", "Z")

                p95_ms = vals.get("p95_ms", None)
                rps_all = vals.get("rps_all", None)
                sla_raw = vals.get("sla", 0.0)  # fallback
                replicas = vals.get("replicas", None)
                cpu_total = vals.get("cpu_total_cores", None)
                cpu_util = vals.get("cpu_util_hpa_pct", None)

                # SLA flag: ưu tiên tính bằng p95 nếu có, không thì fallback sang metric sla
                if p95_ms is not None:
                    sla_flag = 1 if float(p95_ms) > SLA_THRESHOLD_MS else 0
                else:
                    sla_flag = 1 if float(sla_raw) > 0 else 0

                w.writerow([
                    ts_iso,
                    service,
                    "" if p95_ms is None else p95_ms,
                    "" if rps_all is None else rps_all,
                    sla_flag,
                    "" if replicas is None else replicas,
                    "" if cpu_total is None else cpu_total,
                    "" if cpu_util is None else cpu_util,
                ])

    # ================== BUILD SUMMARY PER SERVICE ==================
    summary_rows = []
    for service in sorted(VALID_SERVICES):
        service_points = [(ts, rows[(service, ts)]) for (svc, ts) in rows.keys() if svc == service]
        service_points.sort(key=lambda x: x[0])

        n = 0
        n_violate = 0
        p95_vals = []
        rps_vals = []
        replicas_vals = []
        cpu_total_vals = []
        cpu_util_vals = []

        for ts, vals in service_points:
            p95_ms = vals.get("p95_ms", None)
            sla_raw = vals.get("sla", None)

            # chỉ đếm sample nếu có ít nhất p95 hoặc sla
            if p95_ms is None and sla_raw is None:
                continue

            n += 1

            # violate?
            if p95_ms is not None:
                p95_vals.append(float(p95_ms))
                violate = float(p95_ms) > SLA_THRESHOLD_MS
            else:
                violate = float(sla_raw) > 0.0

            if violate:
                n_violate += 1

            # các metric khác (nếu có)
            if vals.get("rps_all") is not None:
                rps_vals.append(float(vals["rps_all"]))
            if vals.get("replicas") is not None:
                replicas_vals.append(float(vals["replicas"]))
            if vals.get("cpu_total_cores") is not None:
                cpu_total_vals.append(float(vals["cpu_total_cores"]))
            if vals.get("cpu_util_hpa_pct") is not None:
                cpu_util_vals.append(float(vals["cpu_util_hpa_pct"]))

        violation_rate_pct = (100.0 * n_violate / n) if n > 0 else None
        compliance_pct = (100.0 - violation_rate_pct) if violation_rate_pct is not None else None

        summary_rows.append({
            "service": service,
            "start_iso": START_ISO,
            "duration_minutes": DURATION_MINUTES,
            "samples": n,
            "violation_samples": n_violate,
            "violation_rate_pct": violation_rate_pct,
            "compliance_pct": compliance_pct,
            "avg_p95_ms": mean(p95_vals),
            "max_p95_ms": (max(p95_vals) if p95_vals else None),
            "avg_rps": mean(rps_vals),
            "avg_replicas": mean(replicas_vals),
            "avg_cpu_total_cores": mean(cpu_total_vals),
            "avg_cpu_util_hpa_pct": mean(cpu_util_vals),
        })

    # ================== WRITE SUMMARY CSV ==================
    with open("sla_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "service",
                "start_iso",
                "duration_minutes",
                "samples",
                "violation_samples",
                "violation_rate_pct",
                "compliance_pct",
                "avg_p95_ms",
                "max_p95_ms",
                "avg_rps",
                "avg_replicas",
                "avg_cpu_total_cores",
                "avg_cpu_util_hpa_pct",
            ],
        )
        w.writeheader()
        for r in summary_rows:
            w.writerow(r)

    print("[DONE] Exported sla_export.csv and sla_summary.csv")


if __name__ == "__main__":
    main()

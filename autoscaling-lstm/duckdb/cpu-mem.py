#!/usr/bin/env python3
import os, csv, requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ============================================================
# 1) PROMETHEUS CONNECTION
# ============================================================
PROM_URL = os.getenv("PROM_URL", "http://localhost:9090").strip()
REQUEST_TIMEOUT = int(os.getenv("PROM_TIMEOUT_SECONDS", "30"))

# ============================================================
# 2) TIME RANGE
# ============================================================
START_ISO = os.getenv("START_ISO", "2026-01-02T06:11:15Z")
DURATION_MINUTES = int(os.getenv("DURATION_MINUTES", "60"))
STEP = int(os.getenv("STEP_SECONDS", "60"))

# ============================================================
# 3) LABELING / OUTPUT
# ============================================================
MODE = os.getenv("MODE", "keda").strip()  # baseline_hpa | proactive
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh"))

SERVICES = os.getenv(
    "SERVICES",
    "api-gateway,authentication-service,order-service,payment-service,product-service"
).split(",")
SERVICES = [s.strip() for s in SERVICES if s.strip()]

INCLUDE_TOTAL = os.getenv("INCLUDE_TOTAL", "true").lower() == "true"

# ============================================================
# 4) PROM QUERIES (requests cost)
# ============================================================
Q_CPU_REQ = 'svc:cpu_requests{job="%s"}'   # cores
Q_MEM_REQ = 'svc:mem_requests{job="%s"}'   # bytes

BYTES_PER_GIB = 1024 ** 3

# ============================================================
# UTILS
# ============================================================
def to_ts(s: str) -> int:
    s = s.strip()
    if s.endswith("Z"):
        s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())

def fmt_local(ts_epoch: int) -> str:
    return datetime.fromtimestamp(ts_epoch, tz=TZ).isoformat()

def resolve_time_range():
    start_ts = to_ts(START_ISO)
    end_ts = start_ts + DURATION_MINUTES * 60
    print(f"[INFO] PROM_URL={PROM_URL}")
    print(f"[INFO] MODE={MODE}")
    print(f"[INFO] START_ISO={START_ISO} -> start_ts={start_ts}")
    print(f"[INFO] DURATION_MINUTES={DURATION_MINUTES} -> end_ts={end_ts}")
    print(f"[INFO] STEP_SECONDS={STEP}")
    print(f"[INFO] SERVICES={SERVICES}")
    return start_ts, end_ts

def prom_query_range_raw(query: str, start_ts: int, end_ts: int, step: int):
    r = requests.get(
        f"{PROM_URL}/api/v1/query_range",
        params={"query": query, "start": start_ts, "end": end_ts, "step": step},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Prometheus error: {data}")
    return data.get("data", {}).get("result", [])

def prom_query_range_pick(query: str, svc: str, start_ts: int, end_ts: int, step: int):
    results = prom_query_range_raw(query, start_ts, end_ts, step)
    if not results:
        return []
    if len(results) == 1:
        return results[0].get("values", []) or []
    for item in results:
        metric = item.get("metric", {}) or {}
        if metric.get("job") == svc:
            return item.get("values", []) or []
    return results[0].get("values", []) or []

def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None

def write_csv(path: str, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

# ============================================================
# MAIN
# ============================================================
def main():
    start_ts, end_ts = resolve_time_range()

    ts_rows = []
    summary_rows = []

    total_all_cpu_req_s = 0.0
    total_all_mem_req_gib_s = 0.0
    total_all_cpu_req_s_counted = False
    total_all_mem_req_s_counted = False

    for svc in SERVICES:
        cpu_req_vals = prom_query_range_pick(Q_CPU_REQ % svc, svc, start_ts, end_ts, STEP)
        mem_req_vals = prom_query_range_pick(Q_MEM_REQ % svc, svc, start_ts, end_ts, STEP)

        # Merge by timestamp
        by_ts = {}
        for t, v in cpu_req_vals:
            by_ts.setdefault(int(float(t)), {})["cpu_requests_cores"] = safe_float(v)
        for t, v in mem_req_vals:
            by_ts.setdefault(int(float(t)), {})["mem_requests_bytes"] = safe_float(v)

        total_cpu_req_s = 0.0
        total_mem_req_gib_s = 0.0
        n_cpu = n_mem = 0

        for ts in sorted(by_ts.keys()):
            d = by_ts[ts]
            cpu_req = d.get("cpu_requests_cores")          # cores
            mem_req_b = d.get("mem_requests_bytes")        # bytes

            mem_req_gib = (mem_req_b / BYTES_PER_GIB) if mem_req_b is not None else None

            cpu_req_s = cpu_req * STEP if cpu_req is not None else None                 # core-seconds
            mem_req_gib_s = mem_req_gib * STEP if mem_req_gib is not None else None     # GiB-seconds

            if cpu_req_s is not None:
                total_cpu_req_s += cpu_req_s
                n_cpu += 1
            if mem_req_gib_s is not None:
                total_mem_req_gib_s += mem_req_gib_s
                n_mem += 1

            ts_rows.append({
                "ts_epoch": ts,
                "ts_local": fmt_local(ts),
                "mode": MODE,
                "service": svc,
                "step_seconds": STEP,
                "cpu_requests_cores": cpu_req,
                "mem_requests_gib": mem_req_gib,
                "cpu_requests_seconds": cpu_req_s,
                "mem_requests_gib_seconds": mem_req_gib_s,
            })

        cpu_total = total_cpu_req_s if n_cpu else None
        mem_total = total_mem_req_gib_s if n_mem else None

        if cpu_total is not None:
            total_all_cpu_req_s += cpu_total
            total_all_cpu_req_s_counted = True
        if mem_total is not None:
            total_all_mem_req_gib_s += mem_total
            total_all_mem_req_s_counted = True

        summary_rows.append({
            "mode": MODE,
            "service": svc,
            "total_cpu_requests_seconds": cpu_total,
            "total_mem_requests_gib_seconds": mem_total,
        })

        print(f"[INFO] svc={svc} points(cpu_req={len(cpu_req_vals)}, mem_req={len(mem_req_vals)})")

    if INCLUDE_TOTAL:
        summary_rows.append({
            "mode": MODE,
            "service": "__TOTAL__",
            "total_cpu_requests_seconds": total_all_cpu_req_s if total_all_cpu_req_s_counted else None,
            "total_mem_requests_gib_seconds": total_all_mem_req_gib_s if total_all_mem_req_s_counted else None,
        })

    ts_path = f"cost_requests_timeseries_{MODE}.csv"
    sum_path = f"cost_requests_summary_{MODE}.csv"

    ts_fields = [
        "ts_epoch","ts_local","mode","service","step_seconds",
        "cpu_requests_cores","mem_requests_gib",
        "cpu_requests_seconds","mem_requests_gib_seconds",
    ]
    sum_fields = [
        "mode","service",
        "total_cpu_requests_seconds","total_mem_requests_gib_seconds",
    ]

    write_csv(ts_path, ts_fields, ts_rows)
    write_csv(sum_path, sum_fields, summary_rows)

    print(f"[OK] Wrote {ts_path} and {sum_path}")

if __name__ == "__main__":
    main()

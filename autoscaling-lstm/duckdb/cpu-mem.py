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
START_ISO = os.getenv("START_ISO", "2025-12-30T05:00:00Z")
DURATION_MINUTES = int(os.getenv("DURATION_MINUTES", "30"))
STEP = int(os.getenv("STEP_SECONDS", "30"))

# ============================================================
# 3) LABELING / OUTPUT
# ============================================================
MODE = os.getenv("MODE", "baseline_hpa").strip()  # baseline_hpa | proactive
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh"))

SERVICES = os.getenv(
    "SERVICES",
    "api-gateway,authentication-service,order-service,payment-service,product-service"
).split(",")
SERVICES = [s.strip() for s in SERVICES if s.strip()]

# OPTIONAL: if you want to aggregate a "TOTAL" row in summary
INCLUDE_TOTAL = os.getenv("INCLUDE_TOTAL", "true").lower() == "true"

# ============================================================
# 4) PROM QUERIES (cost proof)
# Using requests-seconds as "cost" (allocated resources over time)
# Requires recording rules:
#   - svc:cpu_requests{job="<service>"}  (cores)
#   - svc:mem_requests{job="<service>"}  (bytes)
# ============================================================
Q_CPU_REQ = 'svc:cpu_requests{job="%s"}'
Q_MEM_REQ = 'svc:mem_requests{job="%s"}'

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
    """
    Return values [[ts, val], ...] for best series.
    Prefer series with label job == svc.
    """
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

def pct_change(baseline, proactive):
    if baseline is None or proactive is None:
        return None
    if baseline == 0:
        return None
    return (proactive / baseline - 1.0) * 100.0

# ============================================================
# MAIN
# ============================================================
def main():
    start_ts, end_ts = resolve_time_range()

    ts_rows = []
    summary_rows = []

    total_all_cpu_req_s = 0.0
    total_all_mem_req_s = 0.0
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
        total_mem_req_s = 0.0
        n_cpu = n_mem = 0

        for ts in sorted(by_ts.keys()):
            d = by_ts[ts]
            cpu_req = d.get("cpu_requests_cores")
            mem_req = d.get("mem_requests_bytes")

            cpu_req_s = cpu_req * STEP if cpu_req is not None else None
            mem_req_s = mem_req * STEP if mem_req is not None else None

            if cpu_req_s is not None:
                total_cpu_req_s += cpu_req_s
                n_cpu += 1
            if mem_req_s is not None:
                total_mem_req_s += mem_req_s
                n_mem += 1

            ts_rows.append({
                "ts_epoch": ts,
                "ts_local": fmt_local(ts),
                "mode": MODE,
                "service": svc,
                "step_seconds": STEP,
                "cpu_requests_cores": cpu_req,
                "mem_requests_bytes": mem_req,
                "cpu_requests_seconds": cpu_req_s,
                "mem_requests_seconds": mem_req_s,
            })

        cpu_total = total_cpu_req_s if n_cpu else None
        mem_total = total_mem_req_s if n_mem else None

        if cpu_total is not None:
            total_all_cpu_req_s += cpu_total
            total_all_cpu_req_s_counted = True
        if mem_total is not None:
            total_all_mem_req_s += mem_total
            total_all_mem_req_s_counted = True

        summary_rows.append({
            "mode": MODE,
            "service": svc,
            "total_cpu_requests_seconds": cpu_total,
            "total_mem_requests_seconds": mem_total,
        })

        print(f"[INFO] svc={svc} points(cpu_req={len(cpu_req_vals)}, mem_req={len(mem_req_vals)})")

    # Optional TOTAL across services
    if INCLUDE_TOTAL:
        summary_rows.append({
            "mode": MODE,
            "service": "__TOTAL__",
            "total_cpu_requests_seconds": total_all_cpu_req_s if total_all_cpu_req_s_counted else None,
            "total_mem_requests_seconds": total_all_mem_req_s if total_all_mem_req_s_counted else None,
        })

    ts_path = f"cost_requests_timeseries_{MODE}.csv"
    sum_path = f"cost_requests_summary_{MODE}.csv"

    ts_fields = [
        "ts_epoch","ts_local","mode","service","step_seconds",
        "cpu_requests_cores","mem_requests_bytes",
        "cpu_requests_seconds","mem_requests_seconds",
    ]
    sum_fields = [
        "mode","service",
        "total_cpu_requests_seconds","total_mem_requests_seconds",
    ]

    write_csv(ts_path, ts_fields, ts_rows)
    write_csv(sum_path, sum_fields, summary_rows)

    print(f"[OK] Wrote {ts_path} and {sum_path}")
    print("[NEXT] Run the same script twice (baseline_hpa + proactive) with identical START_ISO/DURATION/STEP.")
    print("[NEXT] Then run compare script below to assert <= 15%.")

    # Write a tiny compare helper script next to outputs (optional)
    compare_path = "compare_cost_15pct.py"
    if not os.path.exists(compare_path):
        with open(compare_path, "w", encoding="utf-8") as f:
            f.write(
                '#!/usr/bin/env python3\n'
                'import csv, os\n'
                'BASE=os.getenv("BASELINE","cost_requests_summary_baseline_hpa.csv")\n'
                'PRO=os.getenv("PROACTIVE","cost_requests_summary_proactive.csv")\n'
                'TH=float(os.getenv("THRESHOLD_PCT","15"))\n'
                'def read(p):\n'
                '  m={}\n'
                '  with open(p,"r",encoding="utf-8") as f:\n'
                '    r=csv.DictReader(f)\n'
                '    for row in r:\n'
                '      svc=row["service"]\n'
                '      def num(k):\n'
                '        v=row.get(k)\n'
                '        if v in (None,"","None"): return None\n'
                '        try: return float(v)\n'
                '        except: return None\n'
                '      m[svc]={\n'
                '        "cpu": num("total_cpu_requests_seconds"),\n'
                '        "mem": num("total_mem_requests_seconds"),\n'
                '      }\n'
                '  return m\n'
                'def pct(b,p):\n'
                '  if b is None or p is None or b==0: return None\n'
                '  return (p/b-1.0)*100.0\n'
                'b=read(BASE); p=read(PRO)\n'
                'svcs=sorted(set(b.keys())|set(p.keys()))\n'
                'print("service,cpu_increase_pct,mem_increase_pct,cpu_pass,mem_pass")\n'
                'for s in svcs:\n'
                '  bc=b.get(s,{}).get("cpu"); pc=p.get(s,{}).get("cpu")\n'
                '  bm=b.get(s,{}).get("mem"); pm=p.get(s,{}).get("mem")\n'
                '  dc=pct(bc,pc); dm=pct(bm,pm)\n'
                '  cpu_pass = (dc is not None and dc <= TH)\n'
                '  mem_pass = (dm is not None and dm <= TH)\n'
                '  print(f"{s},{dc},{dm},{cpu_pass},{mem_pass}")\n'
            )
        os.chmod(compare_path, 0o755)
        print(f"[INFO] Wrote helper: {compare_path}")

if __name__ == "__main__":
    main()

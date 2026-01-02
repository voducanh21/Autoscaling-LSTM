#!/usr/bin/env python3
import os
import csv
from collections import defaultdict

# ============================================================
# INPUT / OUTPUT
# ============================================================
MODE = os.getenv("MODE", "baseline_4").strip()
INCLUDE_TOTAL = os.getenv("INCLUDE_TOTAL", "true").lower() == "true"

# Optional: enforce order of services in output (if provided)
SERVICES = os.getenv(
    "SERVICES",
    "api-gateway,authentication-service,order-service,payment-service,product-service"
).split(",")
SERVICES = [s.strip() for s in SERVICES if s.strip()]

# Default file names follow your convention
IN_FILE = os.getenv("IN_FILE", f"cost_requests_timeseries_{MODE}.csv").strip()
OUT_FILE = os.getenv("OUT_FILE", f"cost_requests_summary_{MODE}.csv").strip()

# ============================================================
# UTILS
# ============================================================
def safe_float(x):
    try:
        if x is None:
            return None
        s = str(x).strip()
        if s == "" or s.lower() in ("none", "nan"):
            return None
        return float(s)
    except Exception:
        return None

def safe_int(x):
    try:
        if x is None:
            return None
        s = str(x).strip()
        if s == "" or s.lower() in ("none", "nan"):
            return None
        return int(float(s))
    except Exception:
        return None

def write_csv(path: str, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

# ============================================================
# MAIN: summarize from timeseries CSV
# ============================================================
def main():
    if not os.path.exists(IN_FILE):
        raise FileNotFoundError(f"Input file not found: {IN_FILE}")

    # Accumulators
    cpu_sum = defaultdict(float)
    mem_sum = defaultdict(float)
    cpu_has = defaultdict(bool)
    mem_has = defaultdict(bool)

    # For "mode" in output: prefer row["mode"] if present, else env MODE
    detected_mode = MODE

    # Track which services appear in file
    seen_services = set()

    with open(IN_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            svc = (row.get("service") or "").strip()
            if not svc:
                continue

            seen_services.add(svc)

            row_mode = (row.get("mode") or "").strip()
            if row_mode:
                detected_mode = row_mode

            step = safe_int(row.get("step_seconds"))

            # Prefer precomputed *_seconds columns if present
            cpu_s = safe_float(row.get("cpu_requests_seconds"))
            mem_gib_s = safe_float(row.get("mem_requests_gib_seconds"))

            # Fallback: compute from cores/gib * step if needed
            if cpu_s is None:
                cores = safe_float(row.get("cpu_requests_cores"))
                if cores is not None and step is not None:
                    cpu_s = cores * step

            if mem_gib_s is None:
                gib = safe_float(row.get("mem_requests_gib"))
                if gib is not None and step is not None:
                    mem_gib_s = gib * step

            if cpu_s is not None:
                cpu_sum[svc] += cpu_s
                cpu_has[svc] = True

            if mem_gib_s is not None:
                mem_sum[svc] += mem_gib_s
                mem_has[svc] = True

    # Decide output order:
    # - If SERVICES env is set (default list), keep that order but only include those present
    # - Otherwise, include all seen services sorted
    if SERVICES:
        ordered_services = [s for s in SERVICES if s in seen_services]
        # If file has extra services not in SERVICES, append them
        extras = sorted(seen_services - set(ordered_services))
        ordered_services.extend(extras)
    else:
        ordered_services = sorted(seen_services)

    summary_rows = []
    total_all_cpu = 0.0
    total_all_mem = 0.0
    total_cpu_counted = False
    total_mem_counted = False

    for svc in ordered_services:
        cpu_total = cpu_sum[svc] if cpu_has[svc] else None
        mem_total = mem_sum[svc] if mem_has[svc] else None

        if cpu_total is not None:
            total_all_cpu += cpu_total
            total_cpu_counted = True
        if mem_total is not None:
            total_all_mem += mem_total
            total_mem_counted = True

        summary_rows.append({
            "mode": detected_mode,
            "service": svc,
            "total_cpu_requests_seconds": cpu_total,
            "total_mem_requests_gib_seconds": mem_total,
        })

    if INCLUDE_TOTAL:
        summary_rows.append({
            "mode": detected_mode,
            "service": "__TOTAL__",
            "total_cpu_requests_seconds": total_all_cpu if total_cpu_counted else None,
            "total_mem_requests_gib_seconds": total_all_mem if total_mem_counted else None,
        })

    out_fields = [
        "mode",
        "service",
        "total_cpu_requests_seconds",
        "total_mem_requests_gib_seconds",
    ]
    write_csv(OUT_FILE, out_fields, summary_rows)

    print(f"[OK] Read  {IN_FILE}")
    print(f"[OK] Wrote {OUT_FILE}")

if __name__ == "__main__":
    main()

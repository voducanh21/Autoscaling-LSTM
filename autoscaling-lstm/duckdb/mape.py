#!/usr/bin/env python3
import os, csv, math, requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ============================================================
# 1) PROMETHEUS CONNECTION (LOCAL-FIRST)
# ============================================================
PROM_URL = os.getenv("PROM_URL", "http://localhost:9090").strip()
REQUEST_TIMEOUT = int(os.getenv("PROM_TIMEOUT_SECONDS", "30"))

# ============================================================
# 2) TIME RANGE
# ============================================================
START_ISO = os.getenv("START_ISO", "2025-12-29T16:50:41Z")
DURATION_MINUTES = int(os.getenv("DURATION_MINUTES", "180"))

# Query + output sampling
STEP = int(os.getenv("STEP_SECONDS", "60"))
OUTPUT_INTERVAL = int(os.getenv("OUTPUT_INTERVAL_SECONDS", "60"))

# ============================================================
# CONSTANTS
# ============================================================
APPS_NAMESPACE = os.getenv("APPS_NAMESPACE", "apps")
MODEL_NAMESPACE = os.getenv("MODEL_NAMESPACE", "model")

# Horizon must match training/serving assumption
HORIZON_MIN = int(os.getenv("HORIZON_MINUTES", "5"))
HORIZON_SEC = HORIZON_MIN * 60

# Smooth window must match training TARGET_MODE=smooth_before_shift
SMOOTH_WINDOW_MIN = int(os.getenv("SMOOTH_WINDOW_MINUTES", "5"))

TZ_NAME = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")
TZ = ZoneInfo(TZ_NAME)

SERVICES = [
    "api-gateway",
    "authentication-service",
    "order-service",
    "payment-service",
    "product-service",
]

# Prometheus label: service="predictor-exporter-<svc>"
EXPORTER_SERVICE_NAME = {
    "api-gateway": "predictor-exporter-api-gateway",
    "authentication-service": "predictor-exporter-authentication",
    "order-service": "predictor-exporter-order",
    "payment-service": "predictor-exporter-payment",
    "product-service": "predictor-exporter-product",
}

# ============================================================
# Replica target RPS / pod
# Priority:
# 1) TARGET_RPS_PER_POD_MAP="api-gateway=350,authentication-service=200,..."
# 2) TARGET_RPS_PER_POD (single value for all services)
# 3) fallback defaults below
# ============================================================
DEFAULT_TARGET_MAP = {
    "api-gateway": 350.0,
    "authentication-service": 200.0,
    "order-service": 200.0,
    "payment-service": 200.0,
    "product-service": 350.0,
}

def parse_target_map():
    m = dict(DEFAULT_TARGET_MAP)
    s_map = os.getenv("TARGET_RPS_PER_POD_MAP", "").strip()
    s_one = os.getenv("TARGET_RPS_PER_POD", "").strip()

    if s_map:
        for part in s_map.split(","):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            k = k.strip()
            try:
                m[k] = float(v.strip())
            except Exception:
                pass
        return m

    if s_one:
        try:
            v = float(s_one)
            for k in m.keys():
                m[k] = v
        except Exception:
            pass

    return m

TARGET_RPS_PER_POD_MAP = parse_target_map()

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

def resolve_time_range():
    start_ts = to_ts(START_ISO)
    end_ts = start_ts + DURATION_MINUTES * 60
    print(f"[INFO] PROM_URL={PROM_URL}")
    print(f"[INFO] START_ISO={START_ISO} -> start_ts={start_ts}")
    print(f"[INFO] DURATION_MINUTES={DURATION_MINUTES} -> end_ts={end_ts}")
    print(f"[INFO] STEP_SECONDS(query)={STEP}")
    print(f"[INFO] OUTPUT_INTERVAL_SECONDS(csv)={OUTPUT_INTERVAL}")
    print(f"[INFO] MODEL_NAMESPACE={MODEL_NAMESPACE}, APPS_NAMESPACE={APPS_NAMESPACE}")
    print(f"[INFO] HORIZON_MIN={HORIZON_MIN}, SMOOTH_WINDOW_MIN={SMOOTH_WINDOW_MIN}")
    print("[INFO] ALIGNMENT (decision-time): one CSV row at time t stores:")
    print("       pred(t)  = lstm_pred_* at time t (forecast for t+H)")
    print("       obs(t+H) = smoothed actual at target time, shifted back into bucket t")
    return start_ts, end_ts

def prom_query_range(query: str, start_ts: int, end_ts: int, step: int):
    r = requests.get(
        f"{PROM_URL}/api/v1/query_range",
        params={"query": query, "start": start_ts, "end": end_ts, "step": step},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Prometheus error: {data}")
    result = data.get("data", {}).get("result", [])
    if not result:
        return []
    return result[0].get("values", [])

def fmt_local(ts_epoch: int) -> str:
    return datetime.fromtimestamp(ts_epoch, tz=TZ).isoformat()

def mean(xs):
    return (sum(xs) / len(xs)) if xs else None

def percentile(xs, p: float):
    if not xs:
        return None
    ys = sorted(xs)
    if len(ys) == 1:
        return ys[0]
    k = (len(ys) - 1) * (p / 100.0)
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return ys[f]
    return ys[f] + (ys[c] - ys[f]) * (k - f)

def ts_bucket(ts: int, interval: int) -> int:
    return (ts // interval) * interval

def write_csv_timeseries(path: str, rows):
    fields = [
        "ts_epoch", "ts_local", "service",

        "obs_rps_smooth_tplusH",
        "obs_cpu_norm_smooth_tplusH",
        "obs_mem_norm_smooth_tplusH",

        "pred_rps_smooth_for_tplusH",
        "pred_cpu_norm_smooth_for_tplusH",
        "pred_mem_norm_smooth_for_tplusH",

        # signed + abs errors
        "err_rps",
        "abs_err_rps",
        "abs_err_cpu",
        "abs_err_mem",

        # normalized error to scaling target (mean_nae_target computed in summary)
        "nae_target",

        "desired_replicas_pred",
        "required_replicas_obs",
        "replica_error",
        "replica_abs_error",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)

def ceil_replicas(rps, target_rps_per_pod: float):
    if rps is None:
        return None
    try:
        v = float(rps)
        if math.isnan(v) or math.isinf(v):
            return None
        if v < 0:
            v = 0.0
        t = float(target_rps_per_pod)
        if t <= 0:
            return None
        return max(1, int(math.ceil(v / t)))
    except Exception:
        return None

# ============================================================
# MAIN
# ============================================================
def main():
    start_ts, end_ts = resolve_time_range()
    all_rows = []
    summary = []

    smooth_win = f"{SMOOTH_WINDOW_MIN}m"

    for svc in SERVICES:
        exporter_service = EXPORTER_SERVICE_NAME[svc]
        target_rps_per_pod = float(TARGET_RPS_PER_POD_MAP.get(svc, DEFAULT_TARGET_MAP.get(svc, 350.0)))

        # PRED at decision time t (forecast for t+H)
        pred_rps_q = f'avg(lstm_pred_rps{{namespace="{MODEL_NAMESPACE}",service="{exporter_service}"}})'
        pred_cpu_q = f'avg(lstm_pred_cpu{{namespace="{MODEL_NAMESPACE}",service="{exporter_service}"}})'
        pred_mem_q = f'avg(lstm_pred_mem{{namespace="{MODEL_NAMESPACE}",service="{exporter_service}"}})'

        # OBS at target time (t+H), smoothed like training
        # Query obs in [start+H .. end+H], then shift -H into decision buckets
        obs_rps_q = f'svc:rps_roll_mean_5m{{job="{svc}"}}'
        obs_cpu_q = f'avg_over_time(svc:cpu_norm{{job="{svc}"}}[{smooth_win}])'
        obs_mem_q = f'avg_over_time(svc:mem_norm{{job="{svc}"}}[{smooth_win}])'

        pred_rps_vals = prom_query_range(pred_rps_q, start_ts, end_ts, STEP)
        pred_cpu_vals = prom_query_range(pred_cpu_q, start_ts, end_ts, STEP)
        pred_mem_vals = prom_query_range(pred_mem_q, start_ts, end_ts, STEP)

        obs_rps_vals = prom_query_range(obs_rps_q, start_ts + HORIZON_SEC, end_ts + HORIZON_SEC, STEP)
        obs_cpu_vals = prom_query_range(obs_cpu_q, start_ts + HORIZON_SEC, end_ts + HORIZON_SEC, STEP)
        obs_mem_vals = prom_query_range(obs_mem_q, start_ts + HORIZON_SEC, end_ts + HORIZON_SEC, STEP)

        print(f"[INFO] svc={svc} (target_rps_per_pod={target_rps_per_pod})")
        print(f"       pred_rps_q={pred_rps_q}")
        print(f"       pred_cpu_q={pred_cpu_q}")
        print(f"       pred_mem_q={pred_mem_q}")
        print(f"       obs_rps_q ={obs_rps_q}")
        print(f"       obs_cpu_q ={obs_cpu_q}")
        print(f"       obs_mem_q ={obs_mem_q}")
        print(
            f"       points(raw) pred_rps={len(pred_rps_vals)}, pred_cpu={len(pred_cpu_vals)}, pred_mem={len(pred_mem_vals)}, "
            f"obs_rps={len(obs_rps_vals)}, obs_cpu={len(obs_cpu_vals)}, obs_mem={len(obs_mem_vals)}"
        )

        buckets = {}

        def ingest_bucketed(key, vals, shift_seconds: int = 0):
            for t, v in vals:
                try:
                    ts = int(float(t)) + int(shift_seconds)
                    b = ts_bucket(ts, OUTPUT_INTERVAL)
                    cur = buckets.setdefault(b, {})
                    # keep latest sample within bucket
                    cur["_latest_ts_" + key] = max(cur.get("_latest_ts_" + key, -1), ts)
                    cur[key] = float(v)
                except Exception:
                    pass

        # pred at time t
        ingest_bucketed("pred_rps", pred_rps_vals, shift_seconds=0)
        ingest_bucketed("pred_cpu", pred_cpu_vals, shift_seconds=0)
        ingest_bucketed("pred_mem", pred_mem_vals, shift_seconds=0)

        # obs at target time (t+H) shifted back into decision-time bucket t
        ingest_bucketed("obs_rps_tplusH", obs_rps_vals, shift_seconds=-HORIZON_SEC)
        ingest_bucketed("obs_cpu_tplusH", obs_cpu_vals, shift_seconds=-HORIZON_SEC)
        ingest_bucketed("obs_mem_tplusH", obs_mem_vals, shift_seconds=-HORIZON_SEC)

        # MAE + NAE accumulators
        abs_rps_list, abs_cpu_list, abs_mem_list = [], [], []
        nae_target_list = []

        # bias (signed error) accumulators
        err_rps_list = []

        # replica % error counters
        n_rep = 0
        n_rep_err = 0
        n_over = 0
        n_under = 0

        n_rows = 0

        for bts in sorted(buckets.keys()):
            d = buckets[bts]

            pred_rps = d.get("pred_rps")
            pred_cpu = d.get("pred_cpu")
            pred_mem = d.get("pred_mem")

            obs_rps = d.get("obs_rps_tplusH")
            obs_cpu = d.get("obs_cpu_tplusH")
            obs_mem = d.get("obs_mem_tplusH")

            # require both pred & obs for RPS (replica relies on RPS)
            if pred_rps is None or obs_rps is None:
                continue

            # signed error (bias)
            err_rps = float(pred_rps) - float(obs_rps)
            err_rps_list.append(err_rps)

            # abs errors (MAE components)
            abs_err_rps = abs(err_rps)
            abs_err_cpu = abs(float(obs_cpu) - float(pred_cpu)) if (obs_cpu is not None and pred_cpu is not None) else None
            abs_err_mem = abs(float(obs_mem) - float(pred_mem)) if (obs_mem is not None and pred_mem is not None) else None

            abs_rps_list.append(abs_err_rps)
            if abs_err_cpu is not None:
                abs_cpu_list.append(abs_err_cpu)
            if abs_err_mem is not None:
                abs_mem_list.append(abs_err_mem)

            nae_target = None
            if target_rps_per_pod and target_rps_per_pod > 0:
                nae_target = abs_err_rps / float(target_rps_per_pod)
                nae_target_list.append(nae_target)

            # replica impact at decision-time t
            desired_pred = ceil_replicas(pred_rps, target_rps_per_pod)
            required_obs = ceil_replicas(obs_rps, target_rps_per_pod)

            replica_error = None
            replica_abs_error = None
            if desired_pred is not None and required_obs is not None:
                replica_error = int(desired_pred - required_obs)
                replica_abs_error = int(abs(replica_error))

                n_rep += 1
                if replica_error != 0:
                    n_rep_err += 1
                if replica_error > 0:
                    n_over += 1
                elif replica_error < 0:
                    n_under += 1

            all_rows.append({
                "ts_epoch": bts,
                "ts_local": fmt_local(bts),
                "service": svc,

                "obs_rps_smooth_tplusH": obs_rps,
                "obs_cpu_norm_smooth_tplusH": obs_cpu,
                "obs_mem_norm_smooth_tplusH": obs_mem,

                "pred_rps_smooth_for_tplusH": pred_rps,
                "pred_cpu_norm_smooth_for_tplusH": pred_cpu,
                "pred_mem_norm_smooth_for_tplusH": pred_mem,

                "err_rps": err_rps,
                "abs_err_rps": abs_err_rps,
                "abs_err_cpu": abs_err_cpu,
                "abs_err_mem": abs_err_mem,

                "nae_target": nae_target,

                "desired_replicas_pred": desired_pred,
                "required_replicas_obs": required_obs,
                "replica_error": replica_error,
                "replica_abs_error": replica_abs_error,
            })
            n_rows += 1

        # =========================
        # Summary metrics
        # =========================
        mae_rps = mean(abs_rps_list)
        mae_cpu = mean(abs_cpu_list)
        mae_mem = mean(abs_mem_list)

        mean_nae_target = mean(nae_target_list)

        # bias (signed): >0 means over-predict, <0 means under-predict
        mean_bias_rps = mean(err_rps_list)
        mean_bias_target = (mean_bias_rps / target_rps_per_pod) if (mean_bias_rps is not None and target_rps_per_pod > 0) else None

        p10_bias_rps = percentile(err_rps_list, 10)
        p50_bias_rps = percentile(err_rps_list, 50)
        p90_bias_rps = percentile(err_rps_list, 90)

        replica_error_pct = (100.0 * n_rep_err / n_rep) if n_rep > 0 else None
        replica_over_pct  = (100.0 * n_over / n_rep) if n_rep > 0 else None
        replica_under_pct = (100.0 * n_under / n_rep) if n_rep > 0 else None

        summary.append({
            "service": svc,

            "mae_rps": mae_rps,
            "mae_cpu": mae_cpu,
            "mae_mem": mae_mem,

            "mean_nae_target": mean_nae_target,

            "mean_bias_rps": mean_bias_rps,
            "mean_bias_target": mean_bias_target,
            "p10_bias_rps": p10_bias_rps,
            "p50_bias_rps": p50_bias_rps,
            "p90_bias_rps": p90_bias_rps,

            "replica_error_pct": replica_error_pct,
            "replica_over_pct": replica_over_pct,
            "replica_under_pct": replica_under_pct,

            "n_rows_aligned": n_rows,
            "n_replica_points": n_rep,
        })

        print(
            f"[SUMMARY] svc={svc} | "
            f"MAE_RPS={mae_rps if mae_rps is not None else 'n/a'} | "
            f"mean_nae_target={mean_nae_target if mean_nae_target is not None else 'n/a'} | "
            f"bias(mean)={mean_bias_rps if mean_bias_rps is not None else 'n/a'} RPS "
            f"(target_norm={mean_bias_target if mean_bias_target is not None else 'n/a'}) | "
            f"bias_p10={p10_bias_rps if p10_bias_rps is not None else 'n/a'} "
            f"p50={p50_bias_rps if p50_bias_rps is not None else 'n/a'} "
            f"p90={p90_bias_rps if p90_bias_rps is not None else 'n/a'} | "
            f"MAE_CPU={mae_cpu if mae_cpu is not None else 'n/a'} | "
            f"MAE_MEM={mae_mem if mae_mem is not None else 'n/a'} | "
            f"replica_error%={replica_error_pct if replica_error_pct is not None else 'n/a'} "
            f"(over%={replica_over_pct if replica_over_pct is not None else 'n/a'}, under%={replica_under_pct if replica_under_pct is not None else 'n/a'}) | "
            f"rows={n_rows}, rep_points={n_rep}"
        )

    # ============================================================
    # WRITE CSVs
    # ============================================================
    write_csv_timeseries("forecast_eval_timeseries.csv", all_rows)

    with open("forecast_eval_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "service",
                "mae_rps",
                "mae_cpu",
                "mae_mem",
                "mean_nae_target",
                "mean_bias_rps",
                "mean_bias_target",
                "p10_bias_rps",
                "p50_bias_rps",
                "p90_bias_rps",
                "replica_error_pct", "replica_over_pct", "replica_under_pct",
                "n_rows_aligned", "n_replica_points",
            ],
        )
        w.writeheader()
        for s in summary:
            w.writerow(s)

    print("[OK] Wrote forecast_eval_timeseries.csv and forecast_eval_summary.csv")

if __name__ == "__main__":
    main()

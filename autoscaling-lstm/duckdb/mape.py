#!/usr/bin/env python3
import os, csv, requests
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
START_ISO = os.getenv("START_ISO", "2025-12-28T19:48:50Z")
DURATION_MINUTES = int(os.getenv("DURATION_MINUTES", "120"))

# Force 60s sampling (query + output)
STEP = int(os.getenv("STEP_SECONDS", "60"))
OUTPUT_INTERVAL = int(os.getenv("OUTPUT_INTERVAL_SECONDS", "60"))

# ============================================================
# CONSTANTS
# ============================================================
APPS_NAMESPACE = os.getenv("APPS_NAMESPACE", "apps")
MODEL_NAMESPACE = os.getenv("MODEL_NAMESPACE", "model")

# Fallback (trường hợp job label không như kỳ vọng)
PRED_JOB = os.getenv("PRED_JOB", "predictor-exporter").strip()

HORIZON_MIN = int(os.getenv("HORIZON_MINUTES", "5"))
TZ_NAME = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")
TZ = ZoneInfo(TZ_NAME)

SERVICES = [
    "api-gateway",
    "authentication-service",
    "order-service",
    "payment-service",
    "product-service",
]

# (optional) fallback theo tên Service của exporter
EXPORTER_SERVICE_NAME = {
    "api-gateway": "predictor-exporter-api-gateway",
    "authentication-service": "predictor-exporter-authentication",
    "order-service": "predictor-exporter-order",
    "payment-service": "predictor-exporter-payment",
    "product-service": "predictor-exporter-product",
}

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
    print(f"[INFO] MODEL_NAMESPACE={MODEL_NAMESPACE}, APPS_NAMESPACE={APPS_NAMESPACE}, HORIZON_MIN={HORIZON_MIN}")
    print(f"[INFO] PRED_JOB(fallback)={PRED_JOB}")
    print(f"[INFO] ALIGNMENT: predictor predicts t+{HORIZON_MIN}m, so we evaluate obs(t) vs pred(t-{HORIZON_MIN}m) using PromQL offset on PRED.")
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

def prom_query_range_first(queries, start_ts: int, end_ts: int, step: int):
    for q in queries:
        vals = prom_query_range(q, start_ts, end_ts, step)
        if vals:
            return vals, q
    return [], ""

def fmt_local(ts_epoch: int) -> str:
    return datetime.fromtimestamp(ts_epoch, tz=TZ).isoformat()

def safe_ape_pct(obs, pred):
    """
    APE% = 100 * |obs - pred| / |obs|
    Chỉ tránh chia cho 0 tuyệt đối.
    """
    if obs is None or pred is None:
        return None
    den = abs(float(obs))
    if den == 0.0:
        return None
    return 100.0 * abs(float(obs) - float(pred)) / den

def mean(xs):
    return (sum(xs) / len(xs)) if xs else None

def write_csv_timeseries(path: str, rows):
    fields = [
        "ts_epoch","ts_local","service",
        # obs(t)
        "obs_rps","obs_cpu_norm","obs_mem_norm",
        # pred(t-5m) meaning: prediction made 5m earlier for current t
        "pred_rps_tminus_horizon","pred_cpu_norm_tminus_horizon","pred_mem_norm_tminus_horizon",
        # errors
        "ape_rps_pct","ape_cpu_pct","ape_mem_pct",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)

def ts_bucket(ts: int, interval: int) -> int:
    return (ts // interval) * interval

# ============================================================
# MAIN
# ============================================================
def main():
    start_ts, end_ts = resolve_time_range()

    all_rows = []
    summary = []

    for svc in SERVICES:
        exporter_svc_name = EXPORTER_SERVICE_NAME.get(svc, "")

        # ============================================================
        # PRED: dùng offset HORIZON để lấy pred(t-H) (dự báo cho thời điểm t)
        # IMPORTANT: offset phải nằm ngay sau selector metric{...}
        # ============================================================
        pred_rps_qs = [
            f'avg(lstm_pred_rps{{namespace="{MODEL_NAMESPACE}",job="{svc}"}} offset {HORIZON_MIN}m)',
            f'avg(lstm_pred_rps{{namespace="{MODEL_NAMESPACE}",job="{PRED_JOB}",label_service="{svc}"}} offset {HORIZON_MIN}m)',
            f'avg(lstm_pred_rps{{namespace="{MODEL_NAMESPACE}",service="{exporter_svc_name}"}} offset {HORIZON_MIN}m)' if exporter_svc_name else "",
        ]
        pred_cpu_qs = [
            f'avg(lstm_pred_cpu{{namespace="{MODEL_NAMESPACE}",job="{svc}"}} offset {HORIZON_MIN}m)',
            f'avg(lstm_pred_cpu{{namespace="{MODEL_NAMESPACE}",job="{PRED_JOB}",label_service="{svc}"}} offset {HORIZON_MIN}m)',
            f'avg(lstm_pred_cpu{{namespace="{MODEL_NAMESPACE}",service="{exporter_svc_name}"}} offset {HORIZON_MIN}m)' if exporter_svc_name else "",
        ]
        pred_mem_qs = [
            f'avg(lstm_pred_mem{{namespace="{MODEL_NAMESPACE}",job="{svc}"}} offset {HORIZON_MIN}m)',
            f'avg(lstm_pred_mem{{namespace="{MODEL_NAMESPACE}",job="{PRED_JOB}",label_service="{svc}"}} offset {HORIZON_MIN}m)',
            f'avg(lstm_pred_mem{{namespace="{MODEL_NAMESPACE}",service="{exporter_svc_name}"}} offset {HORIZON_MIN}m)' if exporter_svc_name else "",
        ]

        pred_rps_qs = [q for q in pred_rps_qs if q]
        pred_cpu_qs = [q for q in pred_cpu_qs if q]
        pred_mem_qs = [q for q in pred_mem_qs if q]

        # ============================================================
        # OBS: lấy actual tại thời điểm t (KHÔNG offset)
        # ============================================================
        obs_rps_qs = [
            f'svc:qps:rate1m{{job="{svc}"}}',
        ]
        obs_cpu_norm_qs = [
            f'svc:cpu_norm{{job="{svc}"}}',  # nếu bạn có rule này
            f'(svc:cpu_usage_rate_1m{{job="{svc}"}}) / clamp_min((svc:cpu_limits{{job="{svc}"}}), 0.001)',
        ]
        obs_mem_norm_qs = [
            f'svc:mem_norm{{job="{svc}"}}',  # nếu bạn có rule này
            f'(svc:mem_usage{{job="{svc}"}}) / clamp_min((svc:mem_limits{{job="{svc}"}}), 1)',
        ]

        # ============================================================
        # QUERY (step=60s)
        # ============================================================
        pred_rps_vals, pred_rps_used = prom_query_range_first(pred_rps_qs, start_ts, end_ts, STEP)
        pred_cpu_vals, pred_cpu_used = prom_query_range_first(pred_cpu_qs, start_ts, end_ts, STEP)
        pred_mem_vals, pred_mem_used = prom_query_range_first(pred_mem_qs, start_ts, end_ts, STEP)

        obs_rps_vals, obs_rps_used = prom_query_range_first(obs_rps_qs, start_ts, end_ts, STEP)
        obs_cpu_vals, obs_cpu_used = prom_query_range_first(obs_cpu_norm_qs, start_ts, end_ts, STEP)
        obs_mem_vals, obs_mem_used = prom_query_range_first(obs_mem_norm_qs, start_ts, end_ts, STEP)

        print(f"[INFO] svc={svc}")
        print(f"       pred_rps_q={pred_rps_used or 'NONE'}")
        print(f"       pred_cpu_q={pred_cpu_used or 'NONE'}")
        print(f"       pred_mem_q={pred_mem_used or 'NONE'}")
        print(f"       obs_rps_q ={obs_rps_used or 'NONE'}")
        print(f"       obs_cpu_q ={obs_cpu_used or 'NONE'}")
        print(f"       obs_mem_q ={obs_mem_used or 'NONE'}")
        print(
            f"       points(raw pred_rps(t-{HORIZON_MIN}m)={len(pred_rps_vals)}, pred_cpu={len(pred_cpu_vals)}, pred_mem={len(pred_mem_vals)}, "
            f"obs(t) rps={len(obs_rps_vals)}, cpu_norm={len(obs_cpu_vals)}, mem_norm={len(obs_mem_vals)})"
        )

        # ============================================================
        # BUCKET về lưới 60s để tránh lệch 30s
        # ============================================================
        buckets = {}

        def ingest_bucketed(key, vals):
            for t, v in vals:
                ts = int(float(t))
                b = ts_bucket(ts, OUTPUT_INTERVAL)
                try:
                    cur = buckets.setdefault(b, {})
                    cur["_latest_ts_" + key] = max(cur.get("_latest_ts_" + key, -1), ts)
                    cur[key] = float(v)
                except Exception:
                    pass

        ingest_bucketed("pred_rps_tminus", pred_rps_vals)
        ingest_bucketed("pred_cpu_tminus", pred_cpu_vals)
        ingest_bucketed("pred_mem_tminus", pred_mem_vals)

        ingest_bucketed("obs_rps", obs_rps_vals)
        ingest_bucketed("obs_cpu_norm", obs_cpu_vals)
        ingest_bucketed("obs_mem_norm", obs_mem_vals)

        ape_rps_list, ape_cpu_list, ape_mem_list = [], [], []

        for bts in sorted(buckets.keys()):
            d = buckets[bts]

            obs_rps = d.get("obs_rps")
            pred_rps = d.get("pred_rps_tminus")

            obs_cpu = d.get("obs_cpu_norm")
            pred_cpu = d.get("pred_cpu_tminus")

            obs_mem = d.get("obs_mem_norm")
            pred_mem = d.get("pred_mem_tminus")

            ape_rps = safe_ape_pct(obs_rps, pred_rps)
            ape_cpu = safe_ape_pct(obs_cpu, pred_cpu)
            ape_mem = safe_ape_pct(obs_mem, pred_mem)

            if ape_rps is not None: ape_rps_list.append(ape_rps)
            if ape_cpu is not None: ape_cpu_list.append(ape_cpu)
            if ape_mem is not None: ape_mem_list.append(ape_mem)

            all_rows.append({
                "ts_epoch": bts,
                "ts_local": fmt_local(bts),
                "service": svc,

                "obs_rps": obs_rps,
                "obs_cpu_norm": obs_cpu,
                "obs_mem_norm": obs_mem,

                "pred_rps_tminus_horizon": pred_rps,
                "pred_cpu_norm_tminus_horizon": pred_cpu,
                "pred_mem_norm_tminus_horizon": pred_mem,

                "ape_rps_pct": ape_rps,
                "ape_cpu_pct": ape_cpu,
                "ape_mem_pct": ape_mem,
            })

        mape_rps = mean(ape_rps_list)
        mape_cpu = mean(ape_cpu_list)
        mape_mem = mean(ape_mem_list)

        summary.append({
            "service": svc,
            "mape_rps_pct": mape_rps,
            "mape_cpu_pct": mape_cpu,
            "mape_mem_pct": mape_mem,
            "n_points_rps": len(ape_rps_list),
            "n_points_cpu": len(ape_cpu_list),
            "n_points_mem": len(ape_mem_list),
        })

        print(
            f"[SUMMARY] svc={svc} | "
            f"MAPE_RPS%={mape_rps if mape_rps is not None else 'n/a'} (n={len(ape_rps_list)}), "
            f"MAPE_CPU%={mape_cpu if mape_cpu is not None else 'n/a'} (n={len(ape_cpu_list)}), "
            f"MAPE_MEM%={mape_mem if mape_mem is not None else 'n/a'} (n={len(ape_mem_list)})"
        )

    # ============================================================
    # WRITE CSV
    # ============================================================
    write_csv_timeseries("forecast_eval_timeseries.csv", all_rows)

    with open("forecast_eval_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "service","mape_rps_pct","mape_cpu_pct","mape_mem_pct",
                "n_points_rps","n_points_cpu","n_points_mem",
            ],
        )
        w.writeheader()
        for s in summary:
            w.writerow(s)

    print("[OK] Wrote forecast_eval_timeseries.csv and forecast_eval_summary.csv")

if __name__ == "__main__":
    main()

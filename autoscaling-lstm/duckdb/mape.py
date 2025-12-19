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
START_ISO = os.getenv("START_ISO", "2025-12-18T10:59:02Z")
DURATION_MINUTES = int(os.getenv("DURATION_MINUTES", "30"))
STEP = int(os.getenv("STEP_SECONDS", "30"))

# ============================================================
# CONSTANTS
# ============================================================
APPS_NAMESPACE = os.getenv("APPS_NAMESPACE", "apps")
MODEL_NAMESPACE = os.getenv("MODEL_NAMESPACE", "model")

# Prometheus job label của predictor-exporter (ServiceMonitor: jobLabel: app)
PRED_JOB = os.getenv("PRED_JOB", "predictor-exporter").strip()

HORIZON_MIN = int(os.getenv("HORIZON_MINUTES", "5"))
TZ_NAME = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")
TZ = ZoneInfo(TZ_NAME)

MEM_LIMIT_BYTES = float(os.getenv("MEM_LIMIT_BYTES", "1073741824"))

CPU_LIMIT_MAP = {
    "api-gateway": 1.0,
    "authentication-service": 0.5,
    "order-service": 0.5,
    "payment-service": 0.5,
    "product-service": 1.0,
}

SERVICES = [
    "api-gateway",
    "authentication-service",
    "order-service",
    "payment-service",
    "product-service",
]

# K8s Service name của exporter -> label `service` trong Prometheus thường = Service name
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
    print(f"[INFO] STEP_SECONDS={STEP}")
    print(f"[INFO] PRED_JOB={PRED_JOB}, MODEL_NAMESPACE={MODEL_NAMESPACE}, HORIZON_MIN={HORIZON_MIN}")
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
    """
    Thử nhiều query theo thứ tự; query nào có data thì dùng query đó.
    """
    for q in queries:
        vals = prom_query_range(q, start_ts, end_ts, step)
        if vals:
            return vals
    return []

def write_csv_timeseries(path: str, rows):
    fields = [
        "ts_epoch","ts_local","service",
        "obs_rps","pred_rps","ape_rps",
        "obs_cpu_norm","pred_cpu_norm","ape_cpu",
        "obs_mem_norm","pred_mem_norm","ape_mem",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)

def safe_ape(obs, pred, eps):
    if obs is None or pred is None:
        return None
    den = abs(obs)
    if den < eps:
        return None
    return abs(obs - pred) / den

def fmt_local(ts_epoch: int) -> str:
    return datetime.fromtimestamp(ts_epoch, tz=TZ).isoformat()

# ============================================================
# MAIN
# ============================================================
def main():
    start_ts, end_ts = resolve_time_range()

    all_rows = []
    summary = []

    for svc in SERVICES:
        cpu_limit = CPU_LIMIT_MAP[svc]
        exporter_svc_name = EXPORTER_SERVICE_NAME.get(svc)

        if not exporter_svc_name:
            print(f"[WARN] No exporter service name mapping for svc={svc}, skip pred metrics.")
            exporter_svc_name = ""

        # ---- Predicted: FIX label match để có data ----
        # Primary: match theo job + namespace + service(ServiceName)
        # Fallback: match theo job + namespace + label_service(k8s label `service: <svc>`)
        pred_rps_qs = [
            f'avg(lstm_pred_rps{{job="{PRED_JOB}",namespace="{MODEL_NAMESPACE}",service="{exporter_svc_name}"}} offset {HORIZON_MIN}m)',
            f'avg(lstm_pred_rps{{job="{PRED_JOB}",namespace="{MODEL_NAMESPACE}",label_service="{svc}"}} offset {HORIZON_MIN}m)',
        ]
        pred_cpu_qs = [
            f'avg(lstm_pred_cpu{{job="{PRED_JOB}",namespace="{MODEL_NAMESPACE}",service="{exporter_svc_name}"}} offset {HORIZON_MIN}m)',
            f'avg(lstm_pred_cpu{{job="{PRED_JOB}",namespace="{MODEL_NAMESPACE}",label_service="{svc}"}} offset {HORIZON_MIN}m)',
        ]
        pred_mem_qs = [
            f'avg(lstm_pred_mem{{job="{PRED_JOB}",namespace="{MODEL_NAMESPACE}",service="{exporter_svc_name}"}} offset {HORIZON_MIN}m)',
            f'avg(lstm_pred_mem{{job="{PRED_JOB}",namespace="{MODEL_NAMESPACE}",label_service="{svc}"}} offset {HORIZON_MIN}m)',
        ]

        # ---- Observed ----
        obs_rps_q = f'svc:qps:rate1m{{job="{svc}"}}'
        obs_cpu_q = f'avg(pod:cpu:usage1m{{namespace="{APPS_NAMESPACE}",pod=~"{svc}-.*"}}) / {cpu_limit}'
        obs_mem_q = f'avg(pod:mem:usage{{namespace="{APPS_NAMESPACE}",pod=~"{svc}-.*"}}) / {MEM_LIMIT_BYTES}'

        series = {
            "pred_rps": prom_query_range_first(pred_rps_qs, start_ts, end_ts, STEP),
            "pred_cpu": prom_query_range_first(pred_cpu_qs, start_ts, end_ts, STEP),
            "pred_mem": prom_query_range_first(pred_mem_qs, start_ts, end_ts, STEP),
            "obs_rps":  prom_query_range(obs_rps_q,  start_ts, end_ts, STEP),
            "obs_cpu":  prom_query_range(obs_cpu_q,  start_ts, end_ts, STEP),
            "obs_mem":  prom_query_range(obs_mem_q,  start_ts, end_ts, STEP),
        }

        print(
            f"[INFO] svc={svc} exporter_service={exporter_svc_name} "
            f"points(pred_rps={len(series['pred_rps'])}, pred_cpu={len(series['pred_cpu'])}, pred_mem={len(series['pred_mem'])}, "
            f"obs_rps={len(series['obs_rps'])}, obs_cpu={len(series['obs_cpu'])}, obs_mem={len(series['obs_mem'])})"
        )

        by_ts = {}
        for k, vals in series.items():
            for t, v in vals:
                ts = int(float(t))
                try:
                    by_ts.setdefault(ts, {})[k] = float(v)
                except Exception:
                    # bỏ qua nếu parse fail
                    pass

        ape_rps_list, ape_cpu_list, ape_mem_list = [], [], []

        for ts in sorted(by_ts.keys()):
            d = by_ts[ts]
            obs_rps = d.get("obs_rps");  pred_rps = d.get("pred_rps")
            obs_cpu = d.get("obs_cpu");  pred_cpu = d.get("pred_cpu")
            obs_mem = d.get("obs_mem");  pred_mem = d.get("pred_mem")

            ape_rps = safe_ape(obs_rps, pred_rps, 1e-3)
            ape_cpu = safe_ape(obs_cpu, pred_cpu, 1e-4)
            ape_mem = safe_ape(obs_mem, pred_mem, 1e-4)

            if ape_rps is not None: ape_rps_list.append(ape_rps)
            if ape_cpu is not None: ape_cpu_list.append(ape_cpu)
            if ape_mem is not None: ape_mem_list.append(ape_mem)

            all_rows.append({
                "ts_epoch": ts,
                "ts_local": fmt_local(ts),
                "service": svc,
                "obs_rps": obs_rps, "pred_rps": pred_rps, "ape_rps": ape_rps,
                "obs_cpu_norm": obs_cpu, "pred_cpu_norm": pred_cpu, "ape_cpu": ape_cpu,
                "obs_mem_norm": obs_mem, "pred_mem_norm": pred_mem, "ape_mem": ape_mem,
            })

        def mean(xs): return (sum(xs) / len(xs)) if xs else None
        summary.append({
            "service": svc,
            "mape_rps": mean(ape_rps_list),
            "mape_cpu": mean(ape_cpu_list),
            "mape_mem": mean(ape_mem_list),
            "n_points_rps": len(ape_rps_list),
            "n_points_cpu": len(ape_cpu_list),
            "n_points_mem": len(ape_mem_list),
        })

    write_csv_timeseries("forecast_eval_timeseries.csv", all_rows)

    with open("forecast_eval_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "service","mape_rps","mape_cpu","mape_mem",
                "n_points_rps","n_points_cpu","n_points_mem"
            ],
        )
        w.writeheader()
        for s in summary:
            w.writerow(s)

    print("[OK] Wrote forecast_eval_timeseries.csv and forecast_eval_summary.csv")

if __name__ == "__main__":
    main()

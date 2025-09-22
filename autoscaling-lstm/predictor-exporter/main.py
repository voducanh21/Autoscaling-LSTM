import os, math, time, datetime as dt, requests
from fastapi import FastAPI
from starlette.responses import Response
from prometheus_client import Gauge, Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

PROM_URL=os.getenv("PROM_URL","http://monitoring-kube-prometheus-prometheus.monitoring.svc:9090")
NAMESPACE=os.getenv("NAMESPACE","apps")
DEPLOYMENT=os.getenv("DEPLOYMENT","api-gateway")
APP_LABEL=os.getenv("APP_LABEL","API-GATEWAY")
STEP=int(os.getenv("STEP_SECONDS","60"))
LOOKBACK=int(os.getenv("LOOKBACK_POINTS","60"))
MODEL_URL=os.getenv("MODEL_URL","http://model-api.apps.svc:9000/predict")
HORIZON=int(os.getenv("HORIZON_SECONDS","600"))
CAPACITY_PER_POD=float(os.getenv("CAPACITY_PER_POD","60"))  # RPS/pod mục tiêu
CPU_TARGET=float(os.getenv("CPU_TARGET","0.7"))              # 70% guardrail

RPS_Q=f'sum(rate(http_server_requests_seconds_count{{application="{APP_LABEL}",uri!~".*actuator.*"}}[1m]))'
CPU_Q=f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NAMESPACE}",pod=~"{DEPLOYMENT}-.*",container!=""}}[1m]))'
MEM_Q=f'sum(container_memory_working_set_bytes{{namespace="{NAMESPACE}",pod=~"{DEPLOYMENT}-.*",container!=""}})'
REPLICAS_Q=f'max(kube_deployment_status_replicas{{namespace="{NAMESPACE}",deployment="{DEPLOYMENT}"}})'

app=FastAPI(title="predictor-exporter", version="0.1.0")
g_pred_rps=Gauge("forecast_predicted_rps","Predicted RPS (5-10m)",["deployment"])
g_desired =Gauge("forecast_desired_replicas","Desired replicas by forecast",["deployment"])
m_loop=Histogram("forecast_loop_seconds","Loop duration")
m_err =Counter("forecast_errors_total","Errors",["stage"])

def q_range(query, start, end, step):
    try:
        r=requests.get(f"{PROM_URL}/api/v1/query_range", params={
            "query":query,"start":start,"end":end,"step":step
        }, timeout=15); r.raise_for_status(); res=r.json()["data"]["result"]
        return res[0]["values"] if res else []
    except Exception as e:
        m_err.labels("prom").inc(); return []

def q_instant(query):
    try:
        r=requests.get(f"{PROM_URL}/api/v1/query", params={"query":query}, timeout=10)
        r.raise_for_status(); res=r.json()["data"]["result"]
        if not res: return 0.0
        v=res[0]["value"][1]; return float(v)
    except Exception:
        m_err.labels("prom").inc(); return 0.0

def tail(vals, n):
    arr=[float(v) for _,v in vals]
    if not arr: return [0.0]*n
    return (arr if len(arr)>=n else [arr[0]]*(n-len(arr))+arr)[-n:]

def call_model(rps, cpu, mem, hour, dow):
    try:
        payload={"rps":rps,"cpu":cpu,"mem":mem,"features":{"hour":hour,"dow":dow},"horizon_seconds":HORIZON}
        r=requests.post(MODEL_URL, json=payload, timeout=3.0); r.raise_for_status()
        return float(r.json()["predicted_rps"])
    except Exception:
        m_err.labels("model").inc(); return None

@app.get("/healthz")
def healthz(): return {"ok":True}

@app.get("/metrics")
def metrics(): return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# vòng lặp: tự tick (đơn giản bằng endpoint /tick hoặc background task)
@app.on_event("startup")
def start_loop():
    import threading
    def loop():
        while True:
            t=dt.datetime.utcnow(); hour=t.hour; dow=t.weekday()
            end=int(t.timestamp()); start=end-LOOKBACK*STEP
            with m_loop.time():
                rps_vals=q_range(RPS_Q,start,end,STEP)
                cpu_vals=q_range(CPU_Q,start,end,STEP)
                mem_vals=q_range(MEM_Q,start,end,STEP)
                rps=tail(rps_vals,LOOKBACK); cpu=tail(cpu_vals,LOOKBACK); mem=tail(mem_vals,LOOKBACK)

                yhat=call_model(rps,cpu,mem,hour,dow)
                if yhat is None:
                    # fallback: EMA đơn giản
                    ema=None
                    for x in rps: ema = x if ema is None else 0.4*x+(1-0.4)*ema
                    yhat = max(0.0, ema if ema is not None else 0.0)

                # desired by RPS
                desired_rps = max(1, math.ceil(yhat / max(1e-6,CAPACITY_PER_POD)))
                # guardrail CPU: giữ dưới CPU_TARGET
                replicas_now = int(q_instant(REPLICAS_Q)) or 1
                cpu_now = (cpu_vals[-1][1] if cpu_vals else 0.0)
                cpu_per_pod = float(cpu_now)/max(1,replicas_now)
                desired_cpu = max(1, math.ceil(replicas_now * (cpu_per_pod / max(1e-6,CPU_TARGET))))
                desired = max(desired_rps, desired_cpu)

                g_pred_rps.labels(DEPLOYMENT).set(yhat)
                g_desired.labels(DEPLOYMENT).set(desired)
            time.sleep(STEP)
    threading.Thread(target=loop, daemon=True).start()

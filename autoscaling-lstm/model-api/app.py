import os, json, math, time
from typing import List, Optional, Dict, Any, Tuple
import numpy as np, torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, conlist
from prometheus_client import Histogram, Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from datetime import datetime

# ================= Config =================
MODEL_PATH = os.getenv("MODEL_PATH", "/models/lstm_ts.pt")
SCALER_PATH = os.getenv("SCALER_PATH", "/models/scaler.json")
DEFAULT_HORIZON = int(os.getenv("DEFAULT_HORIZON_SECONDS", "600"))  # 10 phút
STEP_SECONDS = int(os.getenv("STEP_SECONDS", "60"))

# (khuyến nghị cho pod nhỏ)
torch.set_num_threads(int(os.getenv("TORCH_NUM_THREADS", "1")))
torch.set_num_interop_threads(int(os.getenv("TORCH_NUM_INTEROP_THREADS", "1")))

# ================= Metrics =================
m_lat = Histogram("model_infer_latency_seconds", "Latency /predict")
m_req = Counter("model_infer_requests_total", "Requests", ["status"])
m_pred = Gauge("model_last_predicted_rps", "Last predicted RPS")

# ================= API =================
app = FastAPI(title="Model API (LSTM multivariate)", version="0.2.1")

class PredictRequest(BaseModel):
    rps: conlist(float, min_items=1)
    cpu: conlist(float, min_items=1)    # cores
    mem: conlist(float, min_items=1)    # bytes
    # Tùy chọn: series thời gian để time-features chính xác theo từng bước
    # features.hours: [0..23]; features.dows: [0..6]; hoặc features.ts: ISO8601
    features: Optional[Dict[str, Any]] = None  # hour, dow, hours, dows, ts
    horizon_seconds: Optional[int] = None
    step_seconds: Optional[int] = None   # nếu client muốn override STEP_SECONDS

class PredictResponse(BaseModel):
    predicted_rps: float
    horizon_seconds: int
    method: str

lstm = None
scaler: Dict[str, Any] = {}

# ============== Helpers ==============
def _tail_to_len(x: List[float], L: int) -> List[float]:
    """Lấy đuôi độ dài L; nếu thiếu thì pad trái bằng giá trị đầu tiên."""
    if len(x) >= L:
        return list(x[-L:])
    if not x:
        return [0.0] * L
    need = L - len(x)
    return [x[0]] * need + list(x)

def _safe_scale(arr: List[float], med: float, mad: float) -> List[float]:
    m = mad if (mad is not None and mad != 0) else 1.0
    return [(float(v) - float(med)) / float(m) for v in arr]

def _feat_from_series(hours: List[float], dows: List[float]) -> np.ndarray:
    """hours & dows đã cắt đúng lookback; trả mảng [lookback, 4] (hr_s, hr_c, dw_s, dw_c)."""
    hr = np.deg2rad(np.array(hours, dtype=np.float32) * 15.0)  # 24h -> 360° -> 15°/h
    dw = (np.array(dows, dtype=np.float32) / 7.0) * (2 * math.pi)
    hr_s, hr_c = np.sin(hr), np.cos(hr)
    dw_s, dw_c = np.sin(dw), np.cos(dw)
    return np.stack([hr_s, hr_c, dw_s, dw_c], axis=1)

def _parse_ts_series(ts_list: List[str]) -> Tuple[List[float], List[float]]:
    """Từ mảng timestamp ISO -> hours, dows."""
    hours, dows = [], []
    for t in ts_list:
        try:
            dt = datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone()
            hours.append(float(dt.hour))
            dows.append(float(dt.weekday()))  # Mon=0..Sun=6
        except Exception:
            now = datetime.now()
            hours.append(float(now.hour))
            dows.append(float(now.weekday()))
    return hours, dows

def _build_time_features(lookback: int, step_s: int, features: Optional[Dict[str, Any]]) -> np.ndarray:
    """Trả mảng [lookback, 4] theo thứ tự (hr_s, hr_c, dw_s, dw_c)."""
    if features:
        # 1) ts mảng
        ts = features.get("ts")
        if isinstance(ts, list) and len(ts) > 0:
            hours, dows = _parse_ts_series(ts)
            hours = _tail_to_len(hours, lookback)
            dows  = _tail_to_len(dows,  lookback)
            return _feat_from_series(hours, dows)
        # 2) hours/dows mảng
        hours = features.get("hours")
        dows  = features.get("dows")
        if isinstance(hours, list) and isinstance(dows, list) and len(hours) > 0 and len(dows) > 0:
            hours = _tail_to_len([float(h) for h in hours], lookback)
            dows  = _tail_to_len([float(d) for d in dows],  lookback)
            return _feat_from_series(hours, dows)
        # 3) chỉ có hour/dow hiện tại
        if "hour" in features or "dow" in features:
            now_hour = float(features.get("hour", datetime.now().hour))
            now_dow  = float(features.get("dow",  datetime.now().weekday()))
            hours = [now_hour] * lookback
            dows  = [now_dow]  * lookback
            return _feat_from_series(hours, dows)
    # 4) Không có gì: dùng localtime
    now = datetime.now()
    hours = [float(now.hour)] * lookback
    dows  = [float(now.weekday())] * lookback
    return _feat_from_series(hours, dows)

def _prep_tensor(req: PredictRequest, lookback: int) -> torch.Tensor:
    # Lấy step seconds từ request nếu có (hiện chưa sinh chuỗi theo step_s; không bắt buộc cho POC)
    step_s = int(req.step_seconds or STEP_SECONDS)

    # Cắt/pad 3 chuỗi đầu vào
    rps = _tail_to_len(req.rps, lookback)
    cpu = _tail_to_len(req.cpu, lookback)
    mem = _tail_to_len(req.mem, lookback)

    # Chuẩn hoá robust theo scaler
    med, mad = scaler["med"], scaler["mad"]
    rps_n = _safe_scale(rps, med.get("rps", 0.0), mad.get("rps", 1.0))
    cpu_n = _safe_scale(cpu, med.get("cpu", 0.0), mad.get("cpu", 1.0))
    mem_n = _safe_scale(mem, med.get("mem", 0.0), mad.get("mem", 1.0))

    # Time-features theo từng bước
    tf = _build_time_features(lookback, step_s, req.features or {})  # [L,4]

    # Ghép thành [lookback, 7]
    X = np.stack([
        np.array(rps_n, dtype=np.float32),
        np.array(cpu_n, dtype=np.float32),
        np.array(mem_n, dtype=np.float32),
        tf[:, 0], tf[:, 1], tf[:, 2], tf[:, 3]
    ], axis=1)
    return torch.tensor([X], dtype=torch.float32)  # [1, L, 7]

# ============== Lifecycle ==============
def load():
    global lstm, scaler
    # Load TorchScript model
    try:
        lstm = torch.jit.load(MODEL_PATH, map_location="cpu").eval()
    except Exception as e:
        raise RuntimeError(
            f"Failed to load TorchScript model at {MODEL_PATH}: {e}. "
            "Đảm bảo file .pt là TorchScript (torch.jit.script/trace)."
        )
    # Load scaler
    with open(SCALER_PATH, "r") as f:
        scaler = json.load(f)
    # Validate scaler keys
    for k in ["lookback", "med", "mad"]:
        if k not in scaler:
            raise RuntimeError(f"Invalid scaler.json: missing key '{k}'")
    # Validate feature keys in med/mad
    for feat in ["rps", "cpu", "mem"]:
        if feat not in scaler["med"] or feat not in scaler["mad"]:
            raise RuntimeError(f"Invalid scaler.json: missing med/mad for '{feat}'")
    print(f"[INFO] Loaded model: {MODEL_PATH}")
    print(f"[INFO] Loaded scaler: lookback={scaler['lookback']} horizon={scaler.get('horizon')}")

@app.on_event("startup")
def on_start():
    load()

# ============== Endpoints ==============
@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/readyz")
def readyz():
    return {"ready": bool(lstm is not None and scaler is not None)}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    t0 = time.time()
    try:
        lookback = int(scaler.get("lookback", 60))
        x = _prep_tensor(req, lookback)
        with torch.no_grad():
            y = float(lstm(x).item())
        y = max(0.0, y)  # không để âm
        m_pred.set(y)
        m_req.labels("ok").inc()
        horizon = int(req.horizon_seconds or DEFAULT_HORIZON)
        return PredictResponse(predicted_rps=y, horizon_seconds=horizon, method="lstm-mv@v2")
    except Exception as ex:
        m_req.labels("error").inc()
        raise HTTPException(500, f"predict failed: {ex}")
    finally:
        m_lat.observe(time.time() - t0)

import argparse, json, glob, os
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader

# ================== Hyperparams ==================
LOOKBACK = 60
HORIZON  = 5
BATCH    = 128
EPOCHS   = 20
LR       = 1e-3
DEVICE   = "cuda" if torch.cuda.is_available() else "cpu"
SEED     = 42
MIN_LOOKBACK = 16        # lookback tối thiểu khi phải tự co
RESAMPLE_STEP_S = 60     # lưới thời gian cố định (giây)

# ============== Utils & Robust Helpers ==============
def _median_abs_dev(series: pd.Series) -> float:
    arr = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    med = np.nanmedian(arr)
    mad = np.nanmedian(np.abs(arr - med))
    if np.isnan(mad) or mad == 0:
        mad = 1.0
    return float(mad)

def _safe_read_concat(paths):
    dfs = []
    for p in paths:
        d = pd.read_csv(p)
        if d is None or d.empty or d.dropna(how="all").empty:
            print(f"[WARN] Skip empty/NA-only file: {p}")
            continue
        dfs.append(d)
    if not dfs:
        raise RuntimeError("No valid CSVs found. All input files are empty/NA-only.")
    df = pd.concat(dfs, ignore_index=True)
    if "ts" not in df.columns:
        raise RuntimeError('Missing required column: "ts"')
    return df.sort_values("ts")

def _ensure_time_features(df: pd.DataFrame) -> pd.DataFrame:
    need_hour = "hour" not in df.columns
    need_dow  = "dow"  not in df.columns
    ts_parsed = pd.to_datetime(df["ts"], errors="coerce", utc=False)
    if ts_parsed.isna().all():
        raise RuntimeError('Failed to parse "ts" to datetime; cannot derive hour/dow.')
    if need_hour:
        df["hour"] = ts_parsed.dt.hour
    if need_dow:
        df["dow"] = ts_parsed.dt.dayofweek  # Mon=0..Sun=6
    return df

def _infer_step_s(idx: pd.DatetimeIndex) -> int:
    """Suy luận step (giây) từ chênh lệch timestamp phổ biến nhất; fallback = RESAMPLE_STEP_S."""
    if len(idx) < 3:
        return RESAMPLE_STEP_S
    diffs = np.diff(idx.view("int64")) / 1e9  # ns -> s
    diffs = diffs[diffs > 0]
    if diffs.size == 0:
        return RESAMPLE_STEP_S
    # làm tròn về bội số 1 giây
    diffs_rounded = np.clip(np.round(diffs), 1, None)
    # lấy mode
    values, counts = np.unique(diffs_rounded, return_counts=True)
    step = int(values[np.argmax(counts)])
    # ép về các bội phổ biến (30/60/300s) nếu sai biệt nhỏ
    for cand in (60, 30, 300):
        if abs(step - cand) <= 2:
            return cand
    return step

def _resample_uniform(df: pd.DataFrame, step_s=60) -> pd.DataFrame:
    """
    Resample về lưới đều theo 'step_s' giây.
      - rps: dùng mean khi gộp và interpolate('time') cho khoảng trống ngắn (không đổ 0 bừa bãi)
      - cpu/mem: ffill/bfill
    Hàng nào vẫn NaN sau xử lý sẽ bị drop ở bước sau (tránh kéo median về 0).
    """
    idx = pd.to_datetime(df["ts"], errors="coerce")
    df = df.assign(ts_parsed=idx).dropna(subset=["ts_parsed"])
    if df.empty:
        return df
    df = df.sort_values("ts_parsed").set_index("ts_parsed")

    # Suy luận step nếu người dùng đổi RESAMPLE_STEP_S
    inferred = _infer_step_s(df.index)
    if step_s is None:
        step_s = inferred
    print(f"[INFO] Resample step_s={step_s}s (inferred from data: {inferred}s)")

    # Gộp trùng timestamp bằng mean numeric
    df = df.groupby(level=0).mean(numeric_only=True)

    # Resample đều
    rule = f"{step_s}s"
    agg = {"rps": "mean", "cpu": "mean", "mem": "mean"}
    have_cols = [c for c in ["rps","cpu","mem"] if c in df.columns]
    df = df.resample(rule).agg({c: agg[c] for c in have_cols})

    # Xử lý missing
    if "rps" in df.columns:
        # nội suy theo thời gian cho khoảng trống ngắn; giữ NaN nếu gap dài để bị drop
        df["rps"] = df["rps"].interpolate("time", limit=3, limit_direction="both")
    for c in ["cpu", "mem"]:
        if c in df.columns:
            df[c] = df[c].ffill().bfill()

    # Gắn lại đặc trưng thời gian
    df["hour"] = df.index.hour
    df["dow"]  = df.index.dayofweek

    df = df.reset_index().rename(columns={"index": "ts", "ts_parsed": "ts"})
    return df

# ================== Dataset ==================
class SeqDS(Dataset):
    def __init__(self, paths, lookback=LOOKBACK, horizon=HORIZON):
        if len(paths) == 0:
            raise ValueError("No CSV files found for training!")

        df = _safe_read_concat(paths)
        df = _ensure_time_features(df)
        df = _resample_uniform(df, step_s=RESAMPLE_STEP_S)

        # Cột bắt buộc
        required = ["rps", "cpu", "mem", "hour", "dow"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise RuntimeError(f"Missing required columns after resample: {missing}")

        # Ép numeric
        for c in required:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        # Loại hàng còn NaN (đặc biệt RPS sau interpolate chưa lấp được)
        before = len(df)
        df = df.dropna(subset=["rps", "cpu", "mem", "hour", "dow"])
        after = len(df)
        if after < before:
            print(f"[INFO] Dropped {before - after} rows with NaN after resample/interpolate.")

        # Robust scale theo Median & MAD (giữ tương thích runtime)
        self.med = {k: float(np.nanmedian(df[k].to_numpy(dtype=float))) for k in ["rps","cpu","mem"]}
        self.mad = {k: _median_abs_dev(df[k]) for k in ["rps","cpu","mem"]}

        for k in ["rps","cpu","mem"]:
            df[f"{k}_n"] = (df[k] - self.med[k]) / self.mad[k]

        # Cyclic features
        hr_ang = (df["hour"] / 24.0) * (2 * np.pi)
        df["hr_sin"], df["hr_cos"] = np.sin(hr_ang), np.cos(hr_ang)
        dow_ang = (df["dow"] / 7.0) * (2 * np.pi)
        df["dow_sin"], df["dow_cos"] = np.sin(dow_ang), np.cos(dow_ang)

        feats = ["rps_n", "cpu_n", "mem_n", "hr_sin", "hr_cos", "dow_sin", "dow_cos"]

        # Tự co LOOKBACK nếu dữ liệu chưa đủ
        total = len(df)
        need = lookback + horizon
        if total <= need:
            new_lb = max(MIN_LOOKBACK, total - horizon - 1)
            if new_lb < MIN_LOOKBACK:
                raise RuntimeError(f"Not enough rows even for min lookback: total={total}, horizon={horizon}, min_lb={MIN_LOOKBACK}")
            print(f"[INFO] Auto-shrink LOOKBACK from {lookback} → {new_lb} due to limited data (total={total}).")
            lookback = new_lb
        self.lookback = lookback
        self.horizon = horizon

        # Xây chuỗi lookback và target = mean của HORIZON bước tiếp theo
        X, y, times = [], [], []
        vals = df[feats].to_numpy(np.float32)
        tgt  = df["rps"].to_numpy(np.float32)
        time_arr = pd.to_datetime(df["ts"]).to_numpy()
        limit = total - lookback - horizon
        for i in range(limit):
            X.append(vals[i:i+lookback])
            y.append(tgt[i+lookback:i+lookback+horizon].mean())
            # thời điểm dự báo bắt đầu (điểm ngay sau cửa sổ lookback)
            times.append(time_arr[i+lookback])

        self.X = np.stack(X).astype(np.float32)
        self.y = np.array(y, dtype=np.float32)
        self.times = np.array(times)

        # Log chẩn đoán
        zero_ratio = float(np.mean(self.y == 0.0)) if len(self.y) else 0.0
        print(f"[INFO] Dataset built: X={self.X.shape}, y={self.y.shape}, lookback={self.lookback}, horizon={self.horizon}")
        print(f"[INFO] Median: {self.med}")
        print(f"[INFO] MAD:    {self.mad}")
        print(f"[INFO] y stats: zero_ratio={zero_ratio:.3f}, min={self.y.min() if len(self.y) else 'NA'},"
              f" max={self.y.max() if len(self.y) else 'NA'}, mean={self.y.mean() if len(self.y) else 'NA'}")

    def __len__(self): return len(self.X)
    def __getitem__(self, i):
        return torch.from_numpy(self.X[i]), torch.tensor(self.y[i])

# ================== Model ==================
class LSTM(nn.Module):
    def __init__(self, input_size=7, hidden=64, layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden, num_layers=layers,
                            dropout=dropout, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(hidden, 64), nn.ReLU(), nn.Linear(64, 1)
        )

    def forward(self, x):
        o, _ = self.lstm(x)
        o = o[:, -1, :]
        return self.head(o).squeeze(1)

# ================== Train ==================
def train(paths, outdir="/models"):
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    ds = SeqDS(paths, lookback=LOOKBACK, horizon=HORIZON)
    N = len(ds)
    if N < 2:
        raise RuntimeError(f"Not enough samples after preprocessing: N={N}")

    # === Time-based split (tránh leakage) ===
    order = np.argsort(ds.times)
    ntr = int(N * 0.8)
    tr_idx = order[:ntr]
    va_idx = order[ntr:]

    class _IdxDS(Dataset):
        def __init__(self, base, idxs):
            self.base, self.idxs = base, idxs
        def __len__(self): return len(self.idxs)
        def __getitem__(self, k):
            i = self.idxs[k]
            return torch.from_numpy(self.base.X[i]), torch.tensor(self.base.y[i])

    tr_set = _IdxDS(ds, tr_idx)
    va_set = _IdxDS(ds, va_idx)

    tr = DataLoader(tr_set, batch_size=BATCH, shuffle=True,
                    drop_last=False, pin_memory=(DEVICE=="cuda"))
    va = DataLoader(va_set, batch_size=BATCH, shuffle=False,
                    drop_last=False, pin_memory=(DEVICE=="cuda"))

    print(f"[INFO] Split: train={len(tr_set)} samples, val={len(va_set)} samples. "
          f"Train range: {pd.to_datetime(ds.times[tr_idx[0]])} → {pd.to_datetime(ds.times[tr_idx[-1]])}; "
          f"Val range: {pd.to_datetime(ds.times[va_idx[0]])} → {pd.to_datetime(ds.times[va_idx[-1]])}")

    model = LSTM().to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    lossf = nn.L1Loss()
    best = (1e9, None)

    for ep in range(1, EPOCHS + 1):
        model.train()
        for xb, yb in tr:
            xb = xb.to(DEVICE, non_blocking=True)
            yb = yb.to(DEVICE, non_blocking=True)
            pred = model(xb)
            loss = lossf(pred, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()

        model.eval()
        preds, gts = [], []
        with torch.no_grad():
            for xb, yb in va:
                xb = xb.to(DEVICE, non_blocking=True)
                p = model(xb).cpu().numpy()
                preds.append(p)
                gts.append(yb.numpy())
        preds = np.concatenate(preds) if preds else np.array([])
        gts   = np.concatenate(gts) if gts else np.array([])
        mae = float(np.mean(np.abs(preds - gts))) if len(preds) else float("inf")
        print(f"Epoch {ep:02d} val_MAE={mae:.3f}")
        if mae < best[0]:
            best = (mae, {k: v.clone().detach().cpu() for k, v in model.state_dict().items()})

    os.makedirs(outdir, exist_ok=True)
    model.load_state_dict(best[1])
    model.eval()
    model_cpu = model.to("cpu").eval()
    example = torch.zeros(1, ds.lookback, 7, dtype=torch.float32)
    ts = torch.jit.trace(model_cpu, example)
    ts.save(os.path.join(outdir, "lstm_ts.pt"))

    with open(os.path.join(outdir, "scaler.json"), "w") as f:
        json.dump({
            "lookback": ds.lookback,      # lưu lookback thực tế
            "horizon":  ds.horizon,
            "med": {k: float(v) for k, v in ds.med.items()},
            "mad": {k: float(v) for k, v in ds.mad.items()}
        }, f)

    print(f"✅ Training done. Best val_MAE={best[0]:.3f}. Saved to {outdir}")

# ================== Main ==================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_glob", default="/data/*.csv")
    parser.add_argument("--outdir",    default="/models")
    args = parser.parse_args()

    paths = glob.glob(args.data_glob)
    print(f"[INFO] Found {len(paths)} files from pattern: {args.data_glob}")
    for p in paths[:5]:
        print(f" - {p}")
    if len(paths) > 5:
        print(f" ... (+{len(paths)-5} more)")

    train(paths, args.outdir)

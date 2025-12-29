import numpy as np
import pandas as pd

np.random.seed(42)

# ===================================================================
# 0) HỆ SỐ FROM MERGED (GIỮ NGUYÊN)
# ===================================================================

A_CPU = 0.00239373
B_CPU = 0.00376831

A_P95 = 3361.62893
B_P95 = 10.05448

A_MEM = 1_848_221.16
B_MEM = 2.62684763e8

# ===================================================================
# 1) LOAD RPS (KHÔNG CHỈNH)
# ===================================================================

IN_PATH = "payment-service.csv"
OUT_PATH = "payment-service_filled_from_rps.csv"

df = pd.read_csv(IN_PATH)
if "rps_1m" not in df.columns:
    raise ValueError("File payment-service.csv cần có cột 'rps_1m'")

rps = df["rps_1m"].astype(float).to_numpy()
rps = np.clip(rps, 0.0, None)
n = len(rps)

# ===================================================================
# 2) CPU: LINEAR + RELATIVE NOISE + CLIP TO POSITIVE (GIỮ LOGIC)
# ===================================================================

cpu_mean = A_CPU * rps + B_CPU
cpu_sigma = 0.54 * cpu_mean
cpu_noise = np.random.normal(0.0, cpu_sigma, size=n)
cpu = cpu_mean + cpu_noise
cpu = np.clip(cpu, 0.0, None)

df["cpu_cores_1m"] = cpu

# ===================================================================
# 3) P95: BASE FROM CPU + RELATIVE NOISE (GIỮ LOGIC)
# ===================================================================

p95_base = A_P95 * cpu + B_P95
p95_sigma = 0.76 * p95_base
p95_noise = np.random.normal(0.0, p95_sigma, size=n)
p95 = p95_base + p95_noise
p95 = np.clip(p95, 1.0, 4000.0)

df["latency_p95_ms"] = p95

# ===================================================================
# 4) MEMORY: YÊU CẦU MỚI -> mem_norm dao động 0.2407..0.247
# - mem_bytes = mem_norm * MEM_LIMIT_BYTES (match silver default 1GiB)
# - vẫn giữ thêm cột mem_bytes để pipeline downstream dùng như cũ
# ===================================================================

MEM_LIMIT_BYTES = 1024 * 1024 * 1024  # 1GiB (match silver default)

LOW_NORM = 0.2407
HIGH_NORM = 0.2470
BASE_NORM = LOW_NORM  # không tải ~ LOW_NORM

LOAD_RPS_THRESHOLD = 1.0  # rps >= 1 coi là có tải
IDLE_SIGMA = 0.0004
LOAD_SIGMA = 0.0005

mem_norm = np.empty(n, dtype=np.float64)

idle_mask = rps < LOAD_RPS_THRESHOLD
load_mask = ~idle_mask

# idle: quanh LOW_NORM
mem_norm[idle_mask] = BASE_NORM + np.random.normal(0.0, IDLE_SIGMA, size=int(idle_mask.sum()))
mem_norm[idle_mask] = np.clip(mem_norm[idle_mask], LOW_NORM, HIGH_NORM)

# load: tăng nhẹ theo rps, bão hòa nhanh để nằm trong [LOW..HIGH]
if np.any(load_mask):
    r = rps[load_mask]
    ramp = (1.0 - np.exp(-r / 80.0))  # 0..~1
    # tăng tối đa đến HIGH_NORM
    load_mean = LOW_NORM + (HIGH_NORM - LOW_NORM) * ramp
    mem_norm[load_mask] = load_mean + np.random.normal(0.0, LOAD_SIGMA, size=len(r))
    mem_norm[load_mask] = np.clip(mem_norm[load_mask], LOW_NORM, HIGH_NORM)

mem_bytes = mem_norm * MEM_LIMIT_BYTES

# giữ cột debug mem_norm + cột mem_bytes
df["mem_norm"] = mem_norm.astype(np.float32)
df["mem_bytes"] = mem_bytes.astype(np.float64)

# ===================================================================
# 5) SAVE
# ===================================================================

df.to_csv(OUT_PATH, index=False)
print(f"[OK] Saved {OUT_PATH}")

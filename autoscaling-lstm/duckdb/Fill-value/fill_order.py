import numpy as np
import pandas as pd

# Reproducible
np.random.seed(42)

# =========================================================
# 0) INPUT/OUTPUT
# =========================================================
IN_PATH = "order-service.csv"
OUT_PATH = "order-service_filled_from_rps.csv"

df = pd.read_csv(IN_PATH)
if "rps_1m" not in df.columns:
    raise ValueError("File order-service.csv cần có cột 'rps_1m'")

rps = df["rps_1m"].astype(float).to_numpy()
rps = np.clip(rps, 0.0, None)
n = len(rps)

# =========================================================
# 1) CPU model (giữ logic cũ)
# cpu_cores_1m ≈ A_CPU * rps_1m + B_CPU + noise
# =========================================================
A_CPU = 0.001617
B_CPU = 0.003981
CPU_SIGMA_FACTOR = 0.41

cpu_mean = A_CPU * rps + B_CPU
cpu_sigma = CPU_SIGMA_FACTOR * cpu_mean
cpu_sigma = np.maximum(cpu_sigma, 0.002)

cpu = cpu_mean + np.random.normal(0.0, cpu_sigma, size=n)

MIN_CPU = 0.005
MAX_CPU = 0.5
low_mask = cpu < MIN_CPU
if np.any(low_mask):
    cpu[low_mask] = np.random.uniform(MIN_CPU, 2 * MIN_CPU, size=low_mask.sum())
cpu = np.clip(cpu, None, MAX_CPU)

df["cpu_cores_1m"] = cpu

# =========================================================
# 2) P95 model (giữ logic cũ)
# latency_p95_ms ≈ A_P95 * cpu + B_P95 + noise
# =========================================================
A_P95 = 519.438
B_P95 = 6.200
P95_SIGMA_FACTOR = 0.52

p95_base = A_P95 * cpu + B_P95
p95_sigma = P95_SIGMA_FACTOR * p95_base
p95_sigma = np.maximum(p95_sigma, 2.0)

p95 = p95_base + np.random.normal(0.0, p95_sigma, size=n)
p95 = np.clip(p95, 1.0, 2000.0)

df["latency_p95_ms"] = p95

# =========================================================
# 3) MEMORY theo yêu cầu mới: dao động xung quanh 0.2285 (norm)
# - tạo mem_norm quanh baseline, có thể tăng rất nhẹ theo rps nhưng vẫn kẹp biên.
# - đổi ra bytes bằng MEM_LIMIT_BYTES (match silver default = 1GiB)
# =========================================================
MEM_LIMIT_BYTES = 1024 * 1024 * 1024  # 1GiB (match silver default)

BASE_NORM = 0.2285
LOW_NORM  = 0.2240   # biên dưới "dao động quanh" (có thể chỉnh)
HIGH_NORM = 0.2340   # biên trên "dao động quanh" (có thể chỉnh)

# ngưỡng coi là "có tải" (để tăng nhẹ khi rps > threshold)
LOAD_RPS_THRESHOLD = 1.0

# noise
IDLE_SIGMA = 0.0015
LOAD_SIGMA = 0.0010

mem_norm = np.empty(n, dtype=np.float64)

idle_mask = rps < LOAD_RPS_THRESHOLD
load_mask = ~idle_mask

# idle: quanh baseline
mem_norm[idle_mask] = BASE_NORM + np.random.normal(0.0, IDLE_SIGMA, size=int(idle_mask.sum()))
mem_norm[idle_mask] = np.clip(mem_norm[idle_mask], LOW_NORM, HIGH_NORM)

# load: tăng nhẹ theo rps, nhưng vẫn kẹp biên
if np.any(load_mask):
    r = rps[load_mask]
    ramp = (1.0 - np.exp(-r / 80.0))  # 0..~1 bão hòa nhanh
    load_mean = BASE_NORM + 0.0020 * ramp  # tăng tối đa ~+0.002
    mem_norm[load_mask] = load_mean + np.random.normal(0.0, LOAD_SIGMA, size=len(r))
    mem_norm[load_mask] = np.clip(mem_norm[load_mask], LOW_NORM, HIGH_NORM)

mem_bytes = mem_norm * MEM_LIMIT_BYTES

# giữ thêm mem_norm để debug/đối chiếu Prometheus/silver
df["mem_norm"] = mem_norm.astype(np.float32)
df["mem_bytes"] = mem_bytes.astype(np.float64)

# =========================================================
# 4) SAVE
# =========================================================
df.to_csv(OUT_PATH, index=False)
print(f"OK -> wrote {OUT_PATH}")

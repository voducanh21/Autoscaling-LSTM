import numpy as np
import pandas as pd

# Reproducible
np.random.seed(42)

# =========================================================
# 0) INPUT
# =========================================================
IN_PATH = "api-gateway.csv"
OUT_PATH = "api-gateway_filled_from_rps.csv"

df = pd.read_csv(IN_PATH)
if "rps_1m" not in df.columns:
    raise ValueError("File api-gateway.csv phải có cột 'rps_1m'")

rps = df["rps_1m"].astype(float).to_numpy()
rps = np.clip(rps, 0.0, None)
n = len(rps)

# =========================================================
# 1) CPU model (giữ logic cũ)
# cpu_cores_1m ≈ A_CPU * rps_1m + B_CPU + noise
# =========================================================
A_CPU = 0.00094813
B_CPU = 0.00156761
CPU_SIGMA_FACTOR = 0.30

cpu_mean = A_CPU * rps + B_CPU
cpu_sigma = CPU_SIGMA_FACTOR * cpu_mean
cpu_sigma = np.maximum(cpu_sigma, 0.003)  # min noise

cpu = cpu_mean + np.random.normal(0.0, cpu_sigma, size=n)

MIN_CPU = 0.01   # 10 millicores
MAX_CPU = 1.0    # 1 core
low_mask = cpu < MIN_CPU
if np.any(low_mask):
    cpu[low_mask] = np.random.uniform(MIN_CPU, 2 * MIN_CPU, size=low_mask.sum())
cpu = np.clip(cpu, None, MAX_CPU)

df["cpu_cores_1m"] = cpu

# =========================================================
# 2) P95 model (giữ logic cũ)
# latency_p95_ms ≈ A_P95 * cpu + B_P95 + noise
# =========================================================
A_P95 = 144.48300765
B_P95 = 5.39080915
P95_SIGMA_FACTOR = 0.35

p95_base = A_P95 * cpu + B_P95
p95_sigma = P95_SIGMA_FACTOR * p95_base
p95_sigma = np.maximum(p95_sigma, 2.0)

p95 = p95_base + np.random.normal(0.0, p95_sigma, size=n)
p95 = np.clip(p95, 1.0, 250.0)

df["latency_p95_ms"] = p95

# =========================================================
# 3) MEMORY theo yêu cầu mới (dùng mem_norm rồi đổi ra bytes)
# - idle (rps=0): mem_norm = 0.4812
# - có tải 100..500: mem_norm trong khoảng ~0.50..0.52
# - "có tải nhẹ đã tăng nhanh": dùng hàm bão hòa 1-exp(-rps/K)
# =========================================================
MEM_LIMIT_BYTES = 1024 * 1024 * 1024  # 1GiB (match silver default)

BASE_MEM_NORM = 0.4812   # không tải
MAX_MEM_NORM = 0.52      # bão hòa khi tải cao
LOADED_MIN_NORM = 0.50   # khi rps >= 100 thì tối thiểu 0.50

# Điều chỉnh độ "nhảy nhanh":
# K nhỏ -> nhảy nhanh hơn; K lớn -> nhảy chậm hơn
K_RPS = 150.0

# Noise nhỏ để dao động trong biên
MEM_NORM_SIGMA = 0.0025

mem_norm_mean = BASE_MEM_NORM + (MAX_MEM_NORM - BASE_MEM_NORM) * (1.0 - np.exp(-rps / K_RPS))
mem_norm = mem_norm_mean + np.random.normal(0.0, MEM_NORM_SIGMA, size=n)

# rps=0: giữ đúng baseline
zero_mask = rps <= 0.0
mem_norm[zero_mask] = BASE_MEM_NORM

# rps>=100: ép vào [0.50, 0.52]
loaded_mask = rps >= 100.0
mem_norm[loaded_mask] = np.clip(mem_norm[loaded_mask], LOADED_MIN_NORM, MAX_MEM_NORM)

# 0 < rps < 100: ép vào [0.4812, 0.52]
mid_mask = (~zero_mask) & (~loaded_mask)
mem_norm[mid_mask] = np.clip(mem_norm[mid_mask], BASE_MEM_NORM, MAX_MEM_NORM)

mem_bytes = mem_norm * MEM_LIMIT_BYTES

df["mem_norm"] = mem_norm.astype(np.float32)     # thêm để bạn check nhanh
df["mem_bytes"] = mem_bytes.astype(np.float64)   # cột cần để build bronze/silver

# =========================================================
# 4) SAVE
# =========================================================
df.to_csv(OUT_PATH, index=False)
print(f"OK -> wrote {OUT_PATH}")


import numpy as np
import pandas as pd

# Reproducible
np.random.seed(42)

# =========================================================
# 0) INPUT/OUTPUT
# =========================================================
IN_PATH = "authentication-service.csv"
OUT_PATH = "authentication-service_filled_from_rps.csv"

df = pd.read_csv(IN_PATH)
if "rps_1m" not in df.columns:
    raise ValueError("File authentication-service.csv cần có cột 'rps_1m'")

rps = df["rps_1m"].astype(float).to_numpy()
rps = np.clip(rps, 0.0, None)
n = len(rps)

# =========================================================
# 1) CPU model (giữ logic cũ)
# cpu_cores_1m ≈ A_CPU * rps_1m + B_CPU + noise
# =========================================================
A_CPU = 0.03813
B_CPU = 0.00227
CPU_SIGMA_FACTOR = 0.63

cpu_mean = A_CPU * rps + B_CPU
cpu_sigma = CPU_SIGMA_FACTOR * cpu_mean
cpu_sigma = np.maximum(cpu_sigma, 0.0005)

cpu = cpu_mean + np.random.normal(0.0, cpu_sigma, size=n)

MIN_CPU = 0.003
MAX_CPU = 0.25
low_mask = cpu < MIN_CPU
if np.any(low_mask):
    cpu[low_mask] = np.random.uniform(MIN_CPU, 2 * MIN_CPU, size=low_mask.sum())
cpu = np.clip(cpu, None, MAX_CPU)

df["cpu_cores_1m"] = cpu

# =========================================================
# 2) P95 model (giữ logic cũ)
# latency_p95_ms ≈ A_P95 * cpu + B_P95 + noise
# =========================================================
A_P95 = 6046.56
B_P95 = 29.83
P95_SIGMA_FACTOR = 0.79

p95_base = A_P95 * cpu + B_P95
p95_sigma = P95_SIGMA_FACTOR * p95_base
p95_sigma = np.maximum(p95_sigma, 1.0)

p95 = p95_base + np.random.normal(0.0, p95_sigma, size=n)
p95 = np.clip(p95, 1.0, 4000.0)

df["latency_p95_ms"] = p95

# =========================================================
# 3) MEMORY theo yêu cầu mới (dùng mem_norm rồi đổi ra bytes)
# - idle (rps=0): mem_norm = 0.3645, và "không tải" nằm 0.3645..0.37
# - có tải: mem_norm giao động 0.371..0.374
#
# Lưu ý:
# - Nếu bạn dùng MEM_LIMIT_BYTES=1GiB trong silver, dùng đúng 1GiB để ra bytes.
# =========================================================
MEM_LIMIT_BYTES = 1024 * 1024 * 1024  # 1GiB (match silver default)

IDLE_BASE_NORM = 0.3645
IDLE_MAX_NORM  = 0.3700

LOAD_MIN_NORM  = 0.3710
LOAD_MAX_NORM  = 0.3740

# "có tải" định nghĩa theo ngưỡng rps; nếu muốn nhạy hơn/ít hơn thì chỉnh ngưỡng này
LOAD_RPS_THRESHOLD = 1.0

# Noise nhỏ để tạo dao động tự nhiên
IDLE_SIGMA = 0.0012
LOAD_SIGMA = 0.0006

mem_norm = np.empty(n, dtype=np.float64)

idle_mask = rps < LOAD_RPS_THRESHOLD
load_mask = ~idle_mask

# --- idle: quanh baseline nhưng bị kẹp trong [0.3645..0.37] ---
idle_mean = IDLE_BASE_NORM
mem_norm[idle_mask] = idle_mean + np.random.normal(0.0, IDLE_SIGMA, size=int(idle_mask.sum()))
mem_norm[idle_mask] = np.clip(mem_norm[idle_mask], IDLE_BASE_NORM, IDLE_MAX_NORM)

# --- load: dao động trong [0.371..0.374] ---
# có thể cho hơi "tăng dần" theo rps một chút, nhưng vẫn kẹp trong biên
# scale nhỏ để không vượt range
if np.any(load_mask):
    r = rps[load_mask]
    # tăng nhẹ theo rps, bão hòa nhanh
    ramp = (1.0 - np.exp(-r / 50.0))  # 0..~1
    load_mean = LOAD_MIN_NORM + (LOAD_MAX_NORM - LOAD_MIN_NORM) * 0.6 * ramp  # vẫn gần đáy
    mem_norm[load_mask] = load_mean + np.random.normal(0.0, LOAD_SIGMA, size=len(r))
    mem_norm[load_mask] = np.clip(mem_norm[load_mask], LOAD_MIN_NORM, LOAD_MAX_NORM)

mem_bytes = mem_norm * MEM_LIMIT_BYTES

# bạn có thể giữ thêm cột mem_norm để debug/so sánh
df["mem_norm"] = mem_norm.astype(np.float32)
df["mem_bytes"] = mem_bytes.astype(np.float64)

# =========================================================
# 4) SAVE
# =========================================================
df.to_csv(OUT_PATH, index=False)
print(f"OK -> wrote {OUT_PATH}")

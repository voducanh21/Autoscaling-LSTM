import numpy as np
import pandas as pd

# ===================================================================
# 0. CONFIG
# ===================================================================

np.random.seed(42)

# Hệ số tuyến tính đã học từ dữ liệu thực (GIỮ NGUYÊN)
A_CPU = 0.00090405
B_CPU = 0.00216404

A_P95 = 92.21782
B_P95 = 1.56912

A_MEM = 78217.13
B_MEM = 2.81343989e8   # ≈ 281MB baseline (giữ để tham chiếu)

# Noise cũ (giữ cho CPU/P95)
CPU_NOISE_FACTOR = 0.4
P95_NOISE_FACTOR = 0.6

# Giới hạn hợp lý (giữ)
MIN_CPU = 0.01
MIN_P95 = 1.0
MIN_MEM = 200 * 1024**2
MAX_MEM = 512 * 1024**2

# ===================================================================
# 1. LOAD DATA
# ===================================================================

IN_PATH = "product-service.csv"
OUT_PATH = "product-service_filled_from_rps.csv"

df = pd.read_csv(IN_PATH)
if "rps_1m" not in df.columns:
    raise ValueError("File cần có cột 'rps_1m'")

rps = df["rps_1m"].astype(float).to_numpy()
rps = np.clip(rps, 0.0, None)
n = len(rps)

# ===================================================================
# 2. CPU (linear + gaussian noise + lower bound)
# ===================================================================

cpu_mean = A_CPU * rps + B_CPU
cpu_noise = np.random.normal(loc=0.0, scale=CPU_NOISE_FACTOR * cpu_mean, size=n)
cpu = cpu_mean + cpu_noise
cpu = np.clip(cpu, MIN_CPU, 1.0)

df["cpu_cores_1m"] = cpu

# ===================================================================
# 3. P95 (dựa trên CPU + noise)
# ===================================================================

p95_base = A_P95 * cpu + B_P95
p95_noise = np.random.normal(loc=0.0, scale=P95_NOISE_FACTOR * p95_base, size=n)
p95 = p95_base + p95_noise
p95 = np.clip(p95, MIN_P95, 250.0)

df["latency_p95_ms"] = p95

# ===================================================================
# 4. MEMORY (YÊU CẦU MỚI)
# - mem_norm: không tải ~ 0.3718
# - có tải ~ 0.3798 (dao động quanh mốc này)
# - mem_bytes = mem_norm * MEM_LIMIT_BYTES (match silver default 1GiB)
# ===================================================================

MEM_LIMIT_BYTES = 1024 * 1024 * 1024  # 1GiB (match silver default)

IDLE_NORM = 0.3718
LOAD_NORM = 0.3798

LOAD_RPS_THRESHOLD = 1.0  # rps >= 1 coi là có tải

IDLE_SIGMA = 0.00045
LOAD_SIGMA = 0.00055

# optional clamp band để không vượt quá xa (có thể nới nếu muốn)
IDLE_BAND = 0.0015   # idle ~ [IDLE_NORM-.., IDLE_NORM+..]
LOAD_BAND = 0.0015   # load ~ [LOAD_NORM-.., LOAD_NORM+..]

mem_norm = np.empty(n, dtype=np.float64)

idle_mask = rps < LOAD_RPS_THRESHOLD
load_mask = ~idle_mask

# idle: quanh 0.3718
mem_norm[idle_mask] = IDLE_NORM + np.random.normal(0.0, IDLE_SIGMA, size=int(idle_mask.sum()))
mem_norm[idle_mask] = np.clip(mem_norm[idle_mask], IDLE_NORM - IDLE_BAND, IDLE_NORM + IDLE_BAND)

# load: quanh 0.3798 (không cần tăng theo rps vì bạn muốn "chỉ cần có tải nhẹ đã lên mức này")
mem_norm[load_mask] = LOAD_NORM + np.random.normal(0.0, LOAD_SIGMA, size=int(load_mask.sum()))
mem_norm[load_mask] = np.clip(mem_norm[load_mask], LOAD_NORM - LOAD_BAND, LOAD_NORM + LOAD_BAND)

mem_bytes = mem_norm * MEM_LIMIT_BYTES
mem_bytes = np.clip(mem_bytes, MIN_MEM, MAX_MEM)  # giữ safe bounds

df["mem_norm"] = mem_norm.astype(np.float32)
df["mem_bytes"] = mem_bytes.astype(np.float64)

# ===================================================================
# 5. SAVE RESULT
# ===================================================================

df.to_csv(OUT_PATH, index=False)
print(f"[OK] Saved {OUT_PATH}")

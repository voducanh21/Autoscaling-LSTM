import numpy as np
import pandas as pd

# ===================================================================
# 0. CONFIG
# ===================================================================

np.random.seed(42)

# Hệ số tuyến tính đã học từ dữ liệu thực
A_CPU = 0.00090405
B_CPU =  0.00216404

A_P95 = 92.21782
B_P95 = 1.56912

A_MEM = 78217.13
B_MEM = 2.81343989e8   # ≈ 281MB baseline

# Biên độ dao động noise (tỉ lệ với giá trị gốc)
CPU_NOISE_FACTOR = 0.4    # 40%
P95_NOISE_FACTOR = 0.6    # 60%
MEM_NOISE_FACTOR = 0.04   # 4%

# Giới hạn hợp lý
MIN_CPU = 0.01            # 1% core
MIN_P95 = 1.0             # ms
MIN_MEM = 200*1024**2     # 200MB
MAX_MEM = 512*1024**2     # 512MB

# ===================================================================
# 1. LOAD DATA
# ===================================================================

df = pd.read_csv("product-service.csv")

if "rps_1m" not in df.columns:
    raise ValueError("File cần có cột 'rps_1m'")

rps = df["rps_1m"].astype(float).values
n = len(rps)

# ===================================================================
# 2. CPU (linear + gaussian noise + lower bound)
# ===================================================================

cpu_mean = A_CPU * rps + B_CPU

cpu_noise = np.random.normal(
    loc=0.0,
    scale=CPU_NOISE_FACTOR * cpu_mean,
    size=n
)

cpu = cpu_mean + cpu_noise

cpu = np.clip(cpu, MIN_CPU, 1.0)
df["cpu_cores_1m"] = cpu

# ===================================================================
# 3. P95 (dựa trên CPU + noise)
# ===================================================================

p95_base = A_P95 * cpu + B_P95

p95_noise = np.random.normal(
    loc=0.0,
    scale=P95_NOISE_FACTOR * p95_base,
    size=n
)

p95 = p95_base + p95_noise

p95 = np.clip(p95, MIN_P95, 250.0)
df["latency_p95_ms"] = p95

# ===================================================================
# 4. MEMORY (linear + noise + clip)
# ===================================================================

mem_mean = A_MEM * rps + B_MEM

mem_noise = np.random.normal(
    loc=0.0,
    scale=MEM_NOISE_FACTOR * mem_mean,
    size=n
)

mem = mem_mean + mem_noise

mem = np.clip(mem, MIN_MEM, MAX_MEM)
df["mem_bytes"] = mem

# ===================================================================
# 5. SAVE RESULT
# ===================================================================

df.to_csv("product-service_filled_from_rps.csv", index=False)
print("[OK] Saved product-service_filled.csv with synthetic CPU, P95, MEM")

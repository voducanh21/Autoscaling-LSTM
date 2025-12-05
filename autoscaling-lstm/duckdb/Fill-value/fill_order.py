import numpy as np
import pandas as pd

# Cho reproducible, có thể đổi seed nếu muốn
np.random.seed(42)

# ===== 1. Hệ số fit từ merged_order-service_2025-12-01 =====

# cpu_cores_1m ≈ A_CPU * rps_1m + B_CPU
A_CPU = 0.001617
B_CPU = 0.003981
CPU_SIGMA_FACTOR = 0.41       # ~41% quanh cpu_mean

# latency_p95_ms ≈ A_P95 * cpu + B_P95
A_P95 = 519.438
B_P95 = 6.200
P95_SIGMA_FACTOR = 0.52       # ~52% quanh p95_base

# mem_bytes ≈ A_MEM * rps_1m + B_MEM
A_MEM = 1_045_241.0
B_MEM = 2.246848e8            # ~224.68 MB
MEM_SIGMA_FACTOR = 0.034      # ~3.4% quanh mem_target

# Baseline & limit cho memory
MEM_MIN = 1.8e8               # ~180MB
POD_MEM_LIMIT = 512 * 1024**2 # 512Mi ≈ 536,870,912 bytes


# ===== 2. Đọc file chỉ có RPS =====

df = pd.read_csv("order-service.csv")

if "rps_1m" not in df.columns:
    raise ValueError("File order-service.csv cần có cột 'rps_1m'")

rps = df["rps_1m"].astype(float).values
n = len(df)


# ======================================================================
# 3. CPU: dao động quanh cpu_mean(rps) nhưng KHÔNG bao giờ về 0
# ======================================================================

# CPU mean tuyến tính theo rps
cpu_mean = A_CPU * rps + B_CPU

# sigma = 0.41 * mean, nhưng không nhỏ hơn 0.002
cpu_sigma = CPU_SIGMA_FACTOR * cpu_mean
cpu_sigma = np.maximum(cpu_sigma, 0.002)

# noise Gaussian
cpu_noise = np.random.normal(loc=0.0, scale=cpu_sigma, size=n)
cpu = cpu_mean + cpu_noise

# ----- FIX LOW VALUES (QUAN TRỌNG) -----
# Nếu cpu < MIN_CPU → fill bằng giá trị nhỏ realistic (random)
MIN_CPU = 0.005     # ~5m cores, idle realistic
MAX_CPU = 0.5       # upper bound thực tế

low_mask = cpu < MIN_CPU
if np.any(low_mask):
    # random nhỏ để tránh pattern giả
    cpu[low_mask] = np.random.uniform(MIN_CPU, 2*MIN_CPU, size=low_mask.sum())

# clip upper bound
cpu = np.clip(cpu, None, MAX_CPU)

df["cpu_cores_1m"] = cpu


# ======================================================================
# 4. P95: từ CPU + noise
# ======================================================================

p95_base = A_P95 * cpu + B_P95

# σ_P95 = 0.52 * p95_base, tối thiểu 2ms
p95_sigma = P95_SIGMA_FACTOR * p95_base
p95_sigma = np.maximum(p95_sigma, 2.0)

p95_noise = np.random.normal(loc=0.0, scale=p95_sigma, size=n)
p95 = p95_base + p95_noise

# clip thực tế
p95 = np.clip(p95, 1.0, 2000.0)
df["latency_p95_ms"] = p95


# ======================================================================
# 5. Memory: mem_target(rps) + noise, clip theo 512Mi
# ======================================================================

mem_target = A_MEM * rps + B_MEM

mem_sigma = MEM_SIGMA_FACTOR * mem_target
mem_sigma = np.maximum(mem_sigma, 5e5)   # ~0.5MB

mem_noise = np.random.normal(loc=0.0, scale=mem_sigma, size=n)
mem = mem_target + mem_noise

# giữ mem trong range realistic
mem = np.clip(mem, MEM_MIN, POD_MEM_LIMIT)
df["mem_bytes"] = mem


# ======================================================================
# 6. Lưu ra file mới
# ======================================================================

df.to_csv("order-service_filled_from_rps.csv", index=False)
print("Đã tạo order-service_filled_from_rps.csv với CPU, P95, mem từ RPS (profile merged_order-service + limit 512Mi).")

import numpy as np
import pandas as pd

# Cho reproducible (có thể đổi seed tuỳ ý)
np.random.seed(42)

# ===== 1. Hệ số fit từ merged_authentication-service_2025-12-01 =====

# cpu_cores_1m ≈ A_CPU * rps_1m + B_CPU
A_CPU = 0.03813
B_CPU = 0.00227
CPU_SIGMA_FACTOR = 0.63       # dao động ~63% quanh cpu_mean (từ residual thực tế)

# latency_p95_ms ≈ A_P95 * cpu + B_P95
A_P95 = 6046.56
B_P95 = 29.83
P95_SIGMA_FACTOR = 0.79       # dao động ~79% quanh p95_base

# mem_bytes ≈ A_MEM * rps_1m + B_MEM
A_MEM = 4_982_311.16
B_MEM = 271_442_138.90        # ~271 MB
MEM_SIGMA_FACTOR = 0.028      # dao động ~2.8% quanh mem_target

# Baseline & limit cho memory
MEM_MIN = 2.48e8              # ~248MB, gần min trong 1 ngày sample
POD_MEM_LIMIT = 512 * 1024**2 # 512Mi ≈ 536,870,912 bytes


# ===== 2. Đọc file chỉ có RPS =====

df = pd.read_csv("authentication-service.csv")

if "rps_1m" not in df.columns:
    raise ValueError("File authentication-service.csv cần có cột 'rps_1m'")

rps = df["rps_1m"].astype(float).values
n = len(df)


# ======================================================================
# 3. CPU: dao động quanh cpu_mean(rps) nhưng KHÔNG bao giờ về 0
# ======================================================================

cpu_mean = A_CPU * rps + B_CPU

# sigma = 0.63 * mean, nhưng không nhỏ hơn 0.0005 core
cpu_sigma = CPU_SIGMA_FACTOR * cpu_mean
cpu_sigma = np.maximum(cpu_sigma, 0.0005)

# noise Gaussian
cpu_noise = np.random.normal(loc=0.0, scale=cpu_sigma, size=n)
cpu = cpu_mean + cpu_noise

# --------- FIX LOW VALUES (QUAN TRỌNG) ---------
# Auth-service idle rất nhẹ, nhưng không bằng 0
MIN_CPU = 0.003      # ~3m cores
MAX_CPU = 0.25       # trần được quan sát thực tế

low_mask = cpu < MIN_CPU
if np.any(low_mask):
    # random nhỏ để tránh pattern cứng & tạo variability tự nhiên
    cpu[low_mask] = np.random.uniform(MIN_CPU, 2*MIN_CPU, size=low_mask.sum())

# clip upper bound
cpu = np.clip(cpu, None, MAX_CPU)

df["cpu_cores_1m"] = cpu


# ======================================================================
# 4. P95: từ CPU + noise
# ======================================================================

p95_base = A_P95 * cpu + B_P95

# σ_P95 = 0.79 * p95_base, tối thiểu 1ms
p95_sigma = P95_SIGMA_FACTOR * p95_base
p95_sigma = np.maximum(p95_sigma, 1.0)

p95_noise = np.random.normal(loc=0.0, scale=p95_sigma, size=n)
p95 = p95_base + p95_noise

# clip realistic
p95 = np.clip(p95, 1.0, 4000.0)
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
# 6. Lưu file mới
# ======================================================================

df.to_csv("authentication-service_filled_from_rps.csv", index=False)
print("Đã tạo authentication-service_filled_from_rps.csv với CPU, P95, mem từ RPS (profile merged_authentication-service + limit 512Mi).")

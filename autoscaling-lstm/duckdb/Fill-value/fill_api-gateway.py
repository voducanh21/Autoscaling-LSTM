import numpy as np
import pandas as pd

# Để chạy lại nhiều lần ra cùng kết quả (có thể đổi seed)
np.random.seed(42)

# ===== 1. Hệ số học được từ merged_api-gateway =====

# cpu_cores_1m ≈ A_CPU * rps_1m + B_CPU
A_CPU = 0.00094813
B_CPU = 0.00156761
CPU_SIGMA_FACTOR = 0.30   # dao động ≈ 30% quanh cpu_mean

# latency_p95_ms ≈ A_P95 * cpu + B_P95
A_P95 = 144.48300765
B_P95 = 5.39080915
P95_SIGMA_FACTOR = 0.35   # dao động ≈ 35% quanh p95_base

# mem_bytes ≈ A_MEM * rps_1m + B_MEM
A_MEM = 48264.21
B_MEM = 2.90193775e8      # ≈ 290.19 MB
MEM_SIGMA_FACTOR = 0.02   # dao động ≈ 2% quanh mem_target

# Baseline và limit cho memory
MEM_MIN = 2.6e8                    # ~260MB
POD_MEM_LIMIT = 512 * 1024**2      # 512Mi ≈ 536,870,912 bytes


# ===== 2. Đọc file chỉ có RPS =====

df = pd.read_csv("api-gateway.csv")

if "rps_1m" not in df.columns:
    raise ValueError("File api-gateway.csv cần có cột 'rps_1m'")

rps = df["rps_1m"].astype(float).values
n = len(df)


# ======================================================================
# 3. CPU: dao động quanh cpu_mean(rps) nhưng KHÔNG bao giờ về 0
# ======================================================================

cpu_mean = A_CPU * rps + B_CPU

# σ_CPU = 0.30 * cpu_mean, nhưng không nhỏ hơn 0.003 core
cpu_sigma = CPU_SIGMA_FACTOR * cpu_mean
cpu_sigma = np.maximum(cpu_sigma, 0.003)

# noise Gaussian
cpu_noise = np.random.normal(loc=0.0, scale=cpu_sigma, size=n)
cpu = cpu_mean + cpu_noise

# --------- FIX LOW VALUES (QUAN TRỌNG) ---------
# API Gateway idle không bằng 0, thường ~0.01 – 0.03
MIN_CPU = 0.01     # ~10 millicores
MAX_CPU = 1.0      # một pod ~1 core

low_mask = cpu < MIN_CPU
if np.any(low_mask):
    cpu[low_mask] = np.random.uniform(MIN_CPU, 2*MIN_CPU, size=low_mask.sum())

# clip upper bound
cpu = np.clip(cpu, None, MAX_CPU)

df["cpu_cores_1m"] = cpu


# ======================================================================
# 4. P95: từ CPU + noise
# ======================================================================

p95_base = A_P95 * cpu + B_P95

# σ_P95 = 0.35 * p95_base, tối thiểu 2ms
p95_sigma = P95_SIGMA_FACTOR * p95_base
p95_sigma = np.maximum(p95_sigma, 2.0)

p95_noise = np.random.normal(loc=0.0, scale=p95_sigma, size=n)
p95 = p95_base + p95_noise

# P95 tối thiểu 1ms, tối đa 250ms
p95 = np.clip(p95, 1.0, 250.0)
df["latency_p95_ms"] = p95


# ======================================================================
# 5. Memory: bám mem_target(rps) + noise, clip theo limit 512Mi
# ======================================================================

mem_target = A_MEM * rps + B_MEM

mem_sigma = MEM_SIGMA_FACTOR * mem_target
mem_sigma = np.maximum(mem_sigma, 1e6)   # ~1MB

mem_noise = np.random.normal(loc=0.0, scale=mem_sigma, size=n)
mem = mem_target + mem_noise

# giữ mem trong [MEM_MIN, POD_MEM_LIMIT]
mem = np.clip(mem, MEM_MIN, POD_MEM_LIMIT)
df["mem_bytes"] = mem


# ======================================================================
# 6. Lưu file mới
# ======================================================================

df.to_csv("api-gateway_filled_from_rps.csv", index=False)
print("Đã tạo file api-gateway_filled_from_rps.csv với CPU, P95, mem từ RPS (theo profile merged_api-gateway + limit 512Mi).")

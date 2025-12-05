import numpy as np
import pandas as pd

np.random.seed(42)

# ===================================================================
# 0. HỆ SỐ FROM MERGED (ĐÚNG THỰC TẾ)
# ===================================================================

# cpu_cores_1m ≈ A_CPU * rps_1m + B_CPU
A_CPU = 0.00239373
B_CPU =  0.00376831

# latency_p95_ms ≈ A_P95 * cpu + B_P95
A_P95 = 3361.62893
B_P95 = 10.05448

# mem_bytes ≈ A_MEM * rps_1m + B_MEM
A_MEM = 1_848_221.16
B_MEM = 2.62684763e8

# ===================================================================
# 1. LOAD RPS (KHÔNG ĐƯỢC CHỈNH SỬA)
# ===================================================================

df = pd.read_csv("payment-service.csv")
rps = df["rps_1m"].astype(float).values
n = len(rps)

# ===================================================================
# 2. CPU: LINEAR + RELATIVE NOISE + CLIP TO POSITIVE
# ===================================================================

cpu_mean = A_CPU * rps + B_CPU

# Noise tương đối theo magnitude
cpu_sigma = 0.54 * cpu_mean

# Noise tự nhiên (multi-modal behavior)
cpu_noise = np.random.normal(0, cpu_sigma, size=n)

cpu = cpu_mean + cpu_noise

# Không clip cứng floor → tránh giá trị lặp
# Nhưng không để <0
cpu = np.clip(cpu, 0, None)

df["cpu_cores_1m"] = cpu

# ===================================================================
# 3. P95: BASE FROM CPU + RELATIVE NOISE
# ===================================================================

p95_base = A_P95 * cpu + B_P95

p95_sigma = 0.76 * p95_base
p95_noise = np.random.normal(0, p95_sigma, size=n)

p95 = p95_base + p95_noise
p95 = np.clip(p95, 1.0, 4000.0)

df["latency_p95_ms"] = p95

# ===================================================================
# 4. MEMORY: BASE FROM RPS + RELATIVE NOISE
# ===================================================================

mem_mean = A_MEM * rps + B_MEM
mem_sigma = 0.027 * mem_mean

mem_noise = np.random.normal(0, mem_sigma, size=n)

mem = mem_mean + mem_noise
mem = np.clip(mem, 2.45e8, 512 * 1024**2)

df["mem_bytes"] = mem

# ===================================================================
# 5. SAVE
# ===================================================================

df.to_csv("payment-service_filled_from_rps.csv", index=False)
print("[OK] Saved payment-service_filled.csv")

import os
import json
import s3fs

# =========================
# CONFIG
# =========================
BUCKET = os.getenv("S3_BUCKET", "datalake")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "https://minio.voducanh.id.vn")

MODEL_NAME = os.getenv("MODEL_NAME", "lstm_forecast")
PSI_PREFIX = os.getenv("PSI_PREFIX", "drift/psi")

# Nếu muốn đọc theo run cụ thể: export RUN_TAG=20260103T124245Z và USE_LATEST=false
RUN_TAG = os.getenv("RUN_TAG", "")  # ví dụ "20260103T124245Z"
USE_LATEST = os.getenv("USE_LATEST", "true").lower() == "true"

fs = s3fs.S3FileSystem(
    key="H7TLSw9YlDtC88KDjzMN",
    secret="6thNYmyTFH1HZdl1DIw4mSx8Z6Eu8p2lIg50yizL",
    client_kwargs={"endpoint_url": S3_ENDPOINT},
)

# =========================
# READ PSI JSON
# =========================
if USE_LATEST:
    key = f"{PSI_PREFIX}/model={MODEL_NAME}/latest.json"
else:
    if not RUN_TAG:
        raise SystemExit("Missing RUN_TAG. Example: RUN_TAG=20260103T124245Z and USE_LATEST=false")
    key = f"{PSI_PREFIX}/model={MODEL_NAME}/run={RUN_TAG}/psi.json"

path = f"{BUCKET}/{key}"

with fs.open(path, "rb") as f:
    data = json.loads(f.read().decode("utf-8"))

print("[INFO] read:", f"s3://{path}")
print("[INFO] method:", data.get("method"))
print("[INFO] model_name:", data.get("model_name"))
print("[INFO] run_tag:", data.get("run_tag"))
print("[INFO] created_at_utc:", data.get("created_at_utc"))
print()

print("[INFO] aggregate:", data.get("aggregate"))
print("[INFO] features:", data.get("features"))
print()

per = data.get("per_service", {}) or {}
for svc, v in per.items():
    print("===", svc, "===")
    print("ref_rows_used:", v.get("ref_rows_used"))
    print("cur_rows_used:", v.get("cur_rows_used"))
    print("psi_overall_mean:", v.get("psi_overall_mean"))
    print("psi:", v.get("psi"))
    print()

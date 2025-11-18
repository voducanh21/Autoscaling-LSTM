FROM python:3.11-slim

# Hạn chế size và tăng ổn định cài đặt
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates tzdata && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài dependencies
COPY requirements.txt /app/requirements.txt
# Nếu mạng cho phép, dùng extra index của PyTorch để có bản CPU tối ưu:
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt \
        --extra-index-url https://download.pytorch.org/whl/cpu

# Copy app (KHÔNG copy models vì sẽ mount PVC vào /models)
COPY app.py /app/app.py

# Chạy non-root cho an toàn
RUN useradd -m -u 10001 appuser
USER appuser

# Env khớp app.py
ENV MODEL_PATH=/models/lstm_ts.pt \
    SCALER_PATH=/models/scaler.json \
    DEFAULT_HORIZON_SECONDS=600 \
    STEP_SECONDS=60 \
    TORCH_NUM_THREADS=1 \
    TORCH_NUM_INTEROP_THREADS=1

EXPOSE 9000

# Healthcheck đơn giản
HEALTHCHECK --interval=30s --timeout=2s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

# Chạy server
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","9000"]

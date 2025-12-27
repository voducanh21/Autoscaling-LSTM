FROM python:3.11-slim

# (khuyến nghị) tránh warning/đảm bảo log không bị buffer
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Cài đặt các thư viện cần thiết cho việc huấn luyện + drift (Evidently)
# Việc này chỉ diễn ra MỘT LẦN khi xây dựng image
RUN pip install --no-cache-dir \
    pandas pyarrow s3fs fsspec \
    tensorflow==2.16.1 \
    scikit-learn mlflow tzdata joblib boto3 \
    evidently==0.7.17

# Tạo thư mục làm việc
WORKDIR /app

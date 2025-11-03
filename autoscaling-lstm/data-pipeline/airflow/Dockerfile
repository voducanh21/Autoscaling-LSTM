FROM python:3.11-slim

# Cài đặt các thư viện cần thiết cho việc huấn luyện
# Việc này chỉ diễn ra MỘT LẦN khi xây dựng image
RUN pip install --no-cache-dir \
    pandas pyarrow s3fs fsspec \
    tensorflow==2.16.1 \
    scikit-learn mlflow tzdata joblib boto3

# Tạo thư mục làm việc và sao chép script
WORKDIR /app
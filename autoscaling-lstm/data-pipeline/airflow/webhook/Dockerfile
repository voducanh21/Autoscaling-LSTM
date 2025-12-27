FROM python:3.11-slim

WORKDIR /app

# chỉ cài dependencies
RUN pip install --no-cache-dir fastapi uvicorn[standard] requests

# code sẽ được mount từ ConfigMap vào /app/app.py
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]

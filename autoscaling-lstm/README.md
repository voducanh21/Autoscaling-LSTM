# Predictive Autoscaling Pipeline

This module explores forecast-driven scaling for the commerce services. It connects telemetry preparation, time-series model training and serving, Prometheus metrics, and KEDA `ScaledObject` policies.

## Pipeline

```text
Locust load tests ──> service telemetry ──> MinIO / DuckDB analysis
                                              │
Airflow DAGs and CronJobs ──> LSTM / CNN-LSTM / TCN training ──> MLflow
                                                                  │
                    Kubernetes workloads <── KEDA <── Prometheus <── predictor exporter
                                                                  ▲
                                               FastAPI model serving
```

- **Data and training:** Airflow workflows and Kubernetes CronJobs build bronze/silver metric datasets and train model variants.
- **Analysis and storage:** DuckDB scripts analyze service metrics and read object data through S3-compatible storage; MinIO is the configured object store.
- **Model operations:** MLflow supports model tracking; a FastAPI/Uvicorn service hosts inference. Drift-analysis manifests include PSI-oriented checks.
- **Scaling:** predictor-exporter resources publish `lstm_desired_replicas`; the KEDA Prometheus triggers consume that metric for the five commerce Deployments.
- **Load generation:** Locust manifests replay the included traffic dataset from a Kubernetes PVC.

## Quick deploy

Prerequisites: a Kubernetes cluster, the `apps` and `monitoring` namespaces, KEDA, Prometheus serving the configured metric, and access to the required model/data services.

Apply the model-serving resource, then the required service-specific predictor-exporter YAMLs, and finally the KEDA policies:

```bash
kubectl create namespace model --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f autoscaling-lstm/model-serving/lstm-serving.yaml
kubectl apply -f autoscaling-lstm/predictor-exporter/cm-predictor-exporter-new.yaml
for service in api-gateway authentication order payment product; do
  kubectl apply -f "autoscaling-lstm/predictor-exporter/pre-deploy-${service}.yaml"
done
kubectl apply -f autoscaling-lstm/keda/
```

The serving manifest references `ducanhvo/cnn-lstm-serving:latest`. Ensure that image is available to the cluster and that the predictor exporter is publishing the metric before enabling KEDA. The policies expect Prometheus at `prometheus-operated.monitoring.svc.cluster.local:9090`.

### Airflow and MLflow (optional pipeline services)

Configure the required values through Replit Secrets or the environment used for deployment; do not commit them.

```bash
kubectl create namespace airflow --dry-run=client -o yaml | kubectl apply -f -
cd autoscaling-lstm/data-pipeline/my-airflow
bash create-secret.sh
helm upgrade --install airflow . --namespace airflow --create-namespace -f our-values.yaml
```

For the custom MLflow/PostgreSQL manifests:

```bash
# Run from the repository root.
kubectl create namespace mlflow --dry-run=client -o yaml | kubectl apply -f -
cd autoscaling-lstm/data-pipeline/my-mlflow
bash create-secrets.sh
kubectl apply -f mlflow-postgres.yaml
kubectl apply -f mlflow-deployment.yaml
```

The helper scripts read secret values from the current process environment and create Kubernetes Secrets; they require a working `kubectl` context. The Airflow chart helper expects `AIRFLOW_MYSQL_ROOT_PASSWORD` and `AIRFLOW_MYSQL_PASSWORD`; the MLflow helper expects `MLFLOW_DATABASE_PASSWORD` and the MinIO/S3 key pair.

## Related modules

- [`keda/`](keda/) — Prometheus-based `ScaledObject` policies
- [`locust/`](locust/) — traffic replay and PVC setup
- [`model-serving/`](model-serving/) — FastAPI serving image and Kubernetes resource
- [`data-pipeline/`](data-pipeline/) — Airflow DAGs, training jobs, and MLflow resources

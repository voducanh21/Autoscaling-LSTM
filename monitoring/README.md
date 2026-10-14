# Monitoring Configuration

This directory contains Helm value overrides for Prometheus. The settings tune Prometheus and its operator resources, probe timings, and WAL compression; the file is intended to be used with the Prometheus Community `kube-prometheus-stack` chart.

## Install or upgrade

Requirements: Helm, a reachable Kubernetes cluster, and the Prometheus Community chart repository.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --values monitoring/values-prom-pvc.yaml
```

Check the rollout:

```bash
kubectl get pods -n monitoring
kubectl get services -n monitoring
```

The values file does not itself declare a Prometheus PVC. Add the chart's storage settings if the Prometheus time-series database must persist across pod replacement. The KEDA manifests expect a Prometheus endpoint in the `monitoring` namespace; update their `serverAddress` if your release exposes a different service.

## Local observability

For local development, the Compose stack in `backend/docker-compose.yml` provides Prometheus, Grafana, Loki, and Tempo:

```bash
docker compose -f backend/docker-compose.yml up -d prometheus grafana loki tempo
```

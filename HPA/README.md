# CPU-based Kubernetes Autoscaling

This directory contains five `autoscaling/v2` HorizontalPodAutoscaler manifests for the API Gateway, authentication, product, order, and payment Deployments in the `apps` namespace.

## Scaling policy

- Target: average CPU utilization of 80%
- Range: 1–5 replicas per service
- Scale-up and scale-down stabilization policies are defined in each manifest

## Apply

The `apps` namespace and target Deployments must already exist, and the cluster must expose resource metrics through Metrics Server.

```bash
kubectl apply -f HPA/
kubectl get hpa -n apps
kubectl describe hpa api-gateway-hpa -n apps
```

To remove these policies:

```bash
kubectl delete -f HPA/
```

## HPA or KEDA

These policies use CPU utilization and do not require the predictive model pipeline. The [`autoscaling-lstm/keda/`](../autoscaling-lstm/keda/) manifests use Prometheus metrics instead. Do not enable both controllers for the same Deployment at the same time.

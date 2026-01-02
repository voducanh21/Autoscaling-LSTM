kubectl delete scaledobject -n apps --all

kubectl get hpa -n apps

kubectl -n keda scale deploy keda-operator-metrics-apiserver --replicas=0

kubectl delete apiservice v1beta1.external.metrics.k8s.io

kubectl get apiservices | egrep 'external.metrics.k8s.io|custom.metrics.k8s.io'

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install prometheus-adapter prometheus-community/prometheus-adapter \
-n monitoring --create-namespace \
-f adapter-values.yaml \
--version 5.2.0

kubectl -n monitoring scale deploy prometheus-adapter --replicas=0


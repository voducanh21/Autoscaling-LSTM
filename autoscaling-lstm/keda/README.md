kubectl delete hpa -n apps \
api-gateway-hpa-rps product-hpa-rps authentication-hpa-rps order-hpa-rps payment-hpa-rps

kubectl -n monitoring scale deploy prometheus-adapter --replicas=0

kubectl delete apiservice v1beta1.external.metrics.k8s.io

kubectl get apiservices | egrep 'external.metrics.k8s.io|custom.metrics.k8s.io'

kubectl -n keda scale deploy keda-operator-metrics-apiserver --replicas=1

cat <<EOF | kubectl apply -f -
apiVersion: apiregistration.k8s.io/v1
kind: APIService
metadata:
name: v1beta1.external.metrics.k8s.io
spec:
group: external.metrics.k8s.io
version: v1beta1
groupPriorityMinimum: 100
versionPriority: 100
service:
name: keda-operator-metrics-apiserver
namespace: keda
port: 443
caBundle: ${CA_BUNDLE}
EOF

kubectl get apiservice v1beta1.external.metrics.k8s.io -o wide
kubectl -n keda get pods

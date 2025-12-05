# 1️⃣ Deploy PVC
kubectl apply -f pvc-traffic.yaml

# 2️⃣ Kiểm tra xem pod tạm pvc-copy đã chạy chưa và copy CSV từ local vào pod tạm (PVC)
kubectl get pods -n loadtest -> pvc-copy cần ở trạng thái Running
kubectl cp elogs_week_02Dec_09Dec_2019.csv loadtest/pvc-copy:/mnt/traffic/traffic.csv -c busybox

# 3️⃣ Kiểm tra file đã vào PVC chưa
kubectl exec -n loadtest -it pvc-copy -- ls -l /mnt/traffic

# 4️⃣ Xóa pod tạm
kubectl delete pod pvc-copy -n loadtest

# 5️⃣ Deploy ConfigMap locustfile.py và CronJob Locust
kubectl apply -f cronjob_locust_with_logs.yaml

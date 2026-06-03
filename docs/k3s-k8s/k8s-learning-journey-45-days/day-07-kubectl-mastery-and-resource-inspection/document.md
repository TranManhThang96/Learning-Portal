# Document - Day 07: kubectl Cheatsheet

## Context và namespace

```bash
kubectl config get-contexts
kubectl config current-context
kubectl config use-context <context-name>
kubectl config set-context --current --namespace=<namespace>
kubectl get ns
kubectl create namespace <namespace>
```

K3s:

```bash
sudo k3s kubectl get nodes
kubectl --kubeconfig /etc/rancher/k3s/k3s.yaml get pods -A
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

PowerShell:

```powershell
$env:KUBECONFIG='/etc/rancher/k3s/k3s.yaml'
kubectl api-resources | Select-Object -First 10
```

## Resource discovery

```bash
kubectl api-resources
kubectl api-resources --namespaced=true
kubectl api-resources --namespaced=false
kubectl api-versions
kubectl explain pod
kubectl explain pod.spec.containers
kubectl explain deployment.spec.strategy
```

## Get output patterns

```bash
kubectl get pods
kubectl get pods -A
kubectl get pods -o wide
kubectl get pods -o name
kubectl get pod <pod> -o yaml
kubectl get deployment <deployment> -o json
```

Custom columns:

```bash
kubectl get pods -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,PHASE:.status.phase,IP:.status.podIP
kubectl get nodes -o custom-columns=NAME:.metadata.name,KERNEL:.status.nodeInfo.kernelVersion,RUNTIME:.status.nodeInfo.containerRuntimeVersion
```

JSONPath:

```bash
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\n"}{end}'
kubectl get pod <pod> -o jsonpath='{.spec.nodeName}{"\n"}'
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[*].restartCount}{"\n"}'
kubectl get svc <svc> -o jsonpath='{.spec.clusterIP}{"\n"}'
```

## Labels và selectors

```bash
kubectl get pods --show-labels
kubectl get pods -l app=web
kubectl get pods -l 'app in (web,api)'
kubectl label pod <pod> debug=true
kubectl label pod <pod> debug-
kubectl get svc <svc> -o yaml
kubectl describe svc <svc>
```

Field selectors:

```bash
kubectl get pods --field-selector=status.phase=Running
kubectl get pods --field-selector=spec.nodeName=<node-name>
kubectl get events --field-selector type=Warning --sort-by=.lastTimestamp
```

Endpoint inspection:

```bash
kubectl get endpoints
kubectl get endpointslice
kubectl get endpointslice -l kubernetes.io/service-name=<svc>
```

## Events và describe

```bash
kubectl describe pod <pod>
kubectl describe deployment <deployment>
kubectl get events --sort-by=.lastTimestamp
kubectl get events -A --sort-by=.lastTimestamp
kubectl events --all-namespaces
kubectl events --for pod/<pod-name> --watch
kubectl events --types=Warning
```

## Logs, exec và temporary debug Pod

```bash
kubectl logs <pod>
kubectl logs <pod> -c <container>
kubectl logs <pod> --previous
kubectl logs deployment/<deployment> --all-containers=true --tail=100
kubectl exec -it <pod> -- sh
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- sh
kubectl run netshoot --rm -it --image=nicolaka/netshoot -- bash
```

Với image có ENTRYPOINT như `curlimages/curl`, dùng `--command --` để command sau `--` không bị hiểu thành args của entrypoint:

```bash
kubectl run curl-debug --rm -it --restart=Never --image=curlimages/curl:8.10.1 --command -- curl -sS http://web.default.svc.cluster.local
```

## Rollout commands

```bash
kubectl rollout status deployment/<deployment>
kubectl rollout history deployment/<deployment>
kubectl rollout undo deployment/<deployment>
kubectl rollout undo deployment/<deployment> --to-revision=<revision>
kubectl rollout pause deployment/<deployment>
kubectl rollout resume deployment/<deployment>
kubectl set image deployment/<deployment> <container>=<image>
kubectl scale deployment/<deployment> --replicas=3
```

## Patch/apply/delete patterns

```bash
kubectl apply -f manifest.yaml
kubectl apply --dry-run=server -f manifest.yaml
kubectl diff -f manifest.yaml
kubectl delete -f manifest.yaml
kubectl delete namespace <namespace>
kubectl patch deployment <deployment> --type=merge -p '{"spec":{"replicas":3}}'
kubectl patch deployment <deployment> --type=merge --patch-file patch.json
kubectl annotate deployment <deployment> kubernetes.io/change-cause="update image"
```

## Wait và RBAC checks

```bash
kubectl wait --for=condition=Available deployment/<deployment> --timeout=60s
kubectl wait --for=condition=Ready pod/<pod> --timeout=60s
kubectl auth can-i get pods -n <namespace>
kubectl auth can-i create deployments.apps -n <namespace>
kubectl auth can-i get pods --as=system:serviceaccount:<namespace>:<serviceaccount> -n <namespace>
```

## Incident quick flow

```text
1. current-context và namespace có đúng không?
2. get resource -o wide để thấy state nhanh.
3. describe resource để đọc events gần nhất.
4. get resource -o yaml/json để đọc spec/status chi tiết.
5. Kiểm tra labels/selectors/ownerReferences.
6. Dùng logs/exec/debug Pod nếu cần xác minh runtime/network.
7. Sửa manifest hoặc rollback, sau đó wait/rollout status.
```

## Answer key ngắn

| Câu hỏi | Đáp án ngắn |
|---|---|
| `apply` khác Pod `Ready` thế nào? | `apply` chỉ ghi desired state; `Ready` là observed state do kubelet/probe/controller cập nhật sau reconcile |
| Service no endpoint kiểm tra gì? | `spec.selector`, Pod labels, readiness, namespace và EndpointSlice |
| Vì sao dùng `logs --previous`? | Container hiện tại có thể đã restart; lỗi crash nằm ở instance trước |
| Khi nào dùng JSONPath? | Khi cần lấy field cụ thể; dùng `-o yaml` để khám phá cấu trúc hoặc debug output rỗng |
| K3s kubeconfig ở đâu? | Thường là `/etc/rancher/k3s/k3s.yaml` trên server node |

## Common mistakes

| Mistake | Hậu quả | Cách tránh |
|---|---|---|
| Quên context | Sửa nhầm cluster | `kubectl config current-context` trước thao tác lớn |
| Quên namespace | Không thấy object hoặc tạo sai namespace | Set context namespace hoặc dùng `-n` rõ ràng |
| Chỉ nhìn `get pods` | Bỏ qua events/root cause | Luôn đọc `describe` khi lỗi |
| Xóa Pod thuộc Deployment | Pod bị tạo lại | Sửa Deployment/ReplicaSet owner |
| Service no endpoint nhưng debug kube-proxy | Mất thời gian | Kiểm tra selector/labels/readiness trước |

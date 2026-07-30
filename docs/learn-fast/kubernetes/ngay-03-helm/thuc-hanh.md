# Ngày 3: Thực hành Helm

## Chuẩn bị

1. Cài Helm (Linux):
   ```bash
   curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
   chmod +x get_helm.sh
   ./get_helm.sh
   ```
2. Verify:
   ```bash
   helm version
   ```
3. Đảm bảo Minikube đang chạy:
   ```bash
   minikube status
   # nếu chưa chạy:
   minikube start
   ```

---

## Phần 1 - Beginner: Chart đầu tiên

**Mục tiêu**: Tạo, xem, render và cài một chart mẫu bằng `helm create`.

**Yêu cầu**: Helm đã cài, cluster Minikube đang chạy.

**Các bước**:

1. Tạo chart mẫu:
   ```bash
   helm create myapp
   cd myapp
   ```

2. Xem cấu trúc thư mục:
   ```bash
   tree . -L 2
   # hoặc
   find . -maxdepth 2
   ```
   Quan sát: `Chart.yaml`, `values.yaml`, `templates/`, `templates/_helpers.tpl`.

3. Kiểm tra chart bằng lint:
   ```bash
   helm lint .
   ```
   Kết quả mong đợi: `0 chart(s) linted, 0 chart(s) failed`.

4. Render manifest để xem trước (không apply lên cluster):
   ```bash
   helm template myapp .
   ```
   Kết quả mong đợi: in ra toàn bộ YAML Deployment, Service, ServiceAccount đã render sẵn giá trị từ `values.yaml`.

5. Cài chart vào cluster:
   ```bash
   helm install myapp .
   ```

6. Xem release vừa cài:
   ```bash
   helm list
   kubectl get pods,svc
   ```

7. Truy cập app (chart mẫu mặc định dùng nginx, ClusterIP):
   ```bash
   kubectl port-forward svc/myapp 8080:80
   ```
   Mở `http://localhost:8080` để thấy trang chào mừng nginx.

**Kết quả mong đợi**: release `myapp` chạy trên cluster, `helm list` hiển thị revision 1, truy cập được qua port-forward.

**Kiến thức luyện tập**: `helm create`, cấu trúc chart, `helm lint`, `helm template`, `helm install`, `helm list`.

- [ ] Tạo chart bằng `helm create`
- [ ] Chạy `helm lint` không lỗi
- [ ] Chạy `helm template` xem manifest render
- [ ] Cài chart, xác nhận `helm list` thấy release
- [ ] Truy cập app qua port-forward

---

## Phần 2 - Practical: Override values và upgrade/rollback

**Mục tiêu**: Tùy biến chart theo environment, tạo thay đổi, upgrade và rollback.

**Yêu cầu**: Đã hoàn thành Phần 1, đang ở trong thư mục `myapp/`.

**Các bước**:

1. Mở `values.yaml`, sửa các giá trị cơ bản:
   ```yaml
   replicaCount: 2

   image:
     repository: nginx
     tag: "1.25"

   service:
     type: NodePort
     port: 80
   ```

2. Tạo file override riêng cho prod, `values-prod.yaml`:
   ```yaml
   replicaCount: 3

   image:
     tag: "1.27"

   resources:
     limits:
       cpu: 200m
       memory: 256Mi
     requests:
       cpu: 100m
       memory: 128Mi
   ```

3. Template hóa thêm field `env` trong `templates/deployment.yaml`. Mở file, tìm khối `containers:` và thêm:
   ```yaml
           {{- if .Values.env }}
           env:
             {{- range $key, $value := .Values.env }}
             - name: {{ $key }}
               value: {{ $value | quote }}
             {{- end }}
           {{- end }}
   ```
   Thêm vào `values.yaml`:
   ```yaml
   env:
     APP_ENV: "development"
   ```
   Và vào `values-prod.yaml`:
   ```yaml
   env:
     APP_ENV: "production"
   ```

4. Kiểm tra render với values prod trước khi apply:
   ```bash
   helm template myapp . -f values-prod.yaml
   ```
   Xác nhận `APP_ENV: "production"` xuất hiện trong output.

5. Upgrade release hiện tại với values mới:
   ```bash
   helm upgrade myapp . -f values-prod.yaml
   ```

6. Xem lịch sử revision:
   ```bash
   helm history myapp
   ```
   Kết quả mong đợi: thấy revision 1 (install) và revision 2 (upgrade).

7. Giả lập cần rollback (ví dụ nghi ngờ bản mới có lỗi):
   ```bash
   helm rollback myapp 1
   helm history myapp
   ```
   Kết quả mong đợi: revision 3 xuất hiện, mang cấu hình giống revision 1.

**Kết quả mong đợi**: chart có thể chạy khác nhau giữa dev (values.yaml mặc định) và prod (values-prod.yaml), upgrade tăng revision, rollback khôi phục lại cấu hình cũ.

**Kiến thức luyện tập**: sửa `values.yaml`, tạo file override theo env, template hóa field mới, `helm upgrade`, `helm history`, `helm rollback`.

- [ ] Sửa values.yaml (image, replicas, service type)
- [ ] Tạo values-prod.yaml override
- [ ] Template hóa field `env` trong Deployment
- [ ] `helm template` kiểm tra trước khi upgrade
- [ ] `helm upgrade` thành công, revision tăng
- [ ] `helm rollback` về revision cũ thành công

---

## Phần 3 - Advanced: Đóng gói app + Redis, label chung qua _helpers.tpl

**Mục tiêu**: Đóng gói app Ngày 2 (Deployment + Service + ConfigMap + Ingress + probes + resources) kèm Redis làm dependency subchart, dùng `_helpers.tpl` cho label chung, cài lại toàn bộ bằng 1 lệnh.

**Yêu cầu**: Đã hoàn thành Phần 1-2. Có kiến thức Deployment/probes/resources/Ingress từ Ngày 1-2.

**Các bước**:

1. Mở `templates/_helpers.tpl`, xác nhận helper `myapp.labels` có sẵn (do `helm create` sinh ra) hoặc thêm nếu chưa có:
   ```yaml
   {{- define "myapp.labels" -}}
   app.kubernetes.io/name: {{ include "myapp.name" . }}
   app.kubernetes.io/instance: {{ .Release.Name }}
   app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
   app.kubernetes.io/managed-by: {{ .Release.Service }}
   {{- end -}}

   {{- define "myapp.name" -}}
   {{- .Chart.Name -}}
   {{- end -}}
   ```

2. Sửa `templates/deployment.yaml` để dùng label chung và thêm probes + resources đầy đủ:
   ```yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: {{ .Release.Name }}-myapp
     labels:
       {{- include "myapp.labels" . | nindent 4 }}
   spec:
     replicas: {{ .Values.replicaCount | default 1 }}
     selector:
       matchLabels:
         app.kubernetes.io/name: {{ include "myapp.name" . }}
         app.kubernetes.io/instance: {{ .Release.Name }}
     template:
       metadata:
         labels:
           {{- include "myapp.labels" . | nindent 8 }}
       spec:
         containers:
           - name: myapp
             image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
             ports:
               - containerPort: {{ .Values.service.port }}
             readinessProbe:
               httpGet:
                 path: /healthz
                 port: {{ .Values.service.port }}
               initialDelaySeconds: 5
               periodSeconds: 10
             livenessProbe:
               httpGet:
                 path: /healthz
                 port: {{ .Values.service.port }}
               initialDelaySeconds: 10
               periodSeconds: 20
             resources:
               {{- toYaml .Values.resources | nindent 14 }}
             {{- if .Values.env }}
             env:
               {{- range $key, $value := .Values.env }}
               - name: {{ $key }}
                 value: {{ $value | quote }}
               {{- end }}
             {{- end }}
   ```

3. Thêm ConfigMap `templates/configmap.yaml`:
   ```yaml
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: {{ .Release.Name }}-myapp-config
     labels:
       {{- include "myapp.labels" . | nindent 4 }}
   data:
     APP_MODE: {{ .Values.appMode | default "standard" | quote }}
   ```

4. Thêm Ingress `templates/ingress.yaml` (điều kiện theo `.Values.ingress.enabled`):
   ```yaml
   {{- if .Values.ingress.enabled }}
   apiVersion: networking.k8s.io/v1
   kind: Ingress
   metadata:
     name: {{ .Release.Name }}-myapp
     labels:
       {{- include "myapp.labels" . | nindent 4 }}
   spec:
     ingressClassName: {{ .Values.ingress.className | default "nginx" }}
     rules:
       - host: {{ .Values.ingress.host | quote }}
         http:
           paths:
             - path: /
               pathType: Prefix
               backend:
                 service:
                   name: {{ .Release.Name }}-myapp
                   port:
                     number: {{ .Values.service.port }}
   {{- end }}
   ```
   Thêm vào `values.yaml`:
   ```yaml
   ingress:
     enabled: false
     className: nginx
     host: myapp.local
   ```

5. Khai báo Redis làm dependency trong `Chart.yaml`:
   ```yaml
   dependencies:
     - name: redis
       version: "19.6.4"
       repository: "https://charts.bitnami.com/bitnami"
       condition: redis.enabled
   ```

6. Add repo Bitnami và tải dependency:
   ```bash
   helm repo add bitnami https://charts.bitnami.com/bitnami
   helm repo update
   helm dependency update .
   ```
   Kết quả mong đợi: thư mục `charts/redis-*.tgz` xuất hiện, file `Chart.lock` được tạo.

7. Bật Redis và cấu hình trong `values.yaml`:
   ```yaml
   redis:
     enabled: true
     auth:
       enabled: false
   ```

8. Cài lại toàn bộ chart (app + Redis) bằng 1 lệnh:
   ```bash
   helm upgrade -i myapp . -f values.yaml
   ```

9. Xác nhận cả app và Redis đã chạy:
   ```bash
   kubectl get pods
   kubectl get pods -l app.kubernetes.io/name=myapp
   ```
   Kết quả mong đợi: pod `myapp` và pod `myapp-redis-master` (hoặc tên tương tự) đều Running.

10. Kiểm tra label chung áp dụng đúng:
    ```bash
    kubectl get deploy -l app.kubernetes.io/managed-by=Helm
    ```

**Kết quả mong đợi**: 1 chart duy nhất triển khai được Deployment (có probes, resources, env), Service, ConfigMap, Ingress (tùy chọn) và Redis subchart, tất cả có label chuẩn nhất quán, cài đặt bằng đúng 1 lệnh `helm upgrade -i`.

**Kiến thức luyện tập**: `_helpers.tpl`/`include`, dependencies subchart, `helm dependency update`, `toYaml`/`nindent`, điều kiện `if` cho Ingress, tích hợp nhiều resource trong 1 chart.

- [ ] `_helpers.tpl` có label chung, dùng `include` ở mọi template
- [ ] Deployment có probes và resources đầy đủ
- [ ] ConfigMap được template hóa
- [ ] Ingress điều kiện theo `ingress.enabled`
- [ ] Redis khai báo trong `Chart.yaml` dependencies
- [ ] `helm dependency update` tải Redis vào `charts/`
- [ ] `helm upgrade -i` cài toàn bộ app + Redis bằng 1 lệnh
- [ ] Xác nhận pod app và Redis đều Running với label chuẩn

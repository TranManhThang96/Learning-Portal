# Bài thực hành - Day 31: Distributed Tracing

## Prerequisites

- K3s hoặc Kubernetes cluster đang chạy.
- `kubectl` trỏ đúng context.
- Cluster pull được image `jaegertracing/all-in-one:1.57`, `otel/opentelemetry-collector-contrib:0.108.0`, `python:3.12-alpine` và `curlimages/curl:8.10.1`.
- Port local `16686` còn trống nếu muốn mở Jaeger UI.

## Lab Scenario

Bạn sẽ deploy Jaeger all-in-one, gửi một trace thủ công qua Zipkin API để hiểu trace/span shape, sau đó thêm OpenTelemetry Collector làm lớp pipeline trung gian. Phần chính của lab là deploy hai service Python nhỏ: `service-a` nhận request, inject `traceparent`, gọi `service-b`, cả hai ghi log có `trace_id` và export span về Collector.

Core path khoảng 110 phút. Phần trace thủ công sâu hơn được đưa xuống `Stretch Goals`.

## Task 1: Tạo namespace (5 phút)

```bash
kubectl create namespace day31
kubectl config set-context --current --namespace=day31
```

## Task 2: Deploy Jaeger all-in-one (15 phút)

Tạo file `jaeger.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger
  labels:
    app: jaeger
spec:
  replicas: 1
  selector:
    matchLabels:
      app: jaeger
  template:
    metadata:
      labels:
        app: jaeger
    spec:
      containers:
      - name: jaeger
        image: jaegertracing/all-in-one:1.57
        env:
        - name: COLLECTOR_ZIPKIN_HOST_PORT
          value: ":9411"
        - name: COLLECTOR_OTLP_ENABLED
          value: "true"
        ports:
        - name: query
          containerPort: 16686
        - name: zipkin
          containerPort: 9411
        - name: otlp-grpc
          containerPort: 4317
        - name: otlp-http
          containerPort: 4318
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            memory: 512Mi
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger
spec:
  selector:
    app: jaeger
  ports:
  - name: query
    port: 16686
    targetPort: query
  - name: zipkin
    port: 9411
    targetPort: zipkin
  - name: otlp-grpc
    port: 4317
    targetPort: otlp-grpc
  - name: otlp-http
    port: 4318
    targetPort: otlp-http
```

Apply:

```bash
kubectl apply -f jaeger.yaml
kubectl rollout status deploy/jaeger
kubectl get pod,svc
```

Mở UI:

```bash
kubectl port-forward svc/jaeger 16686:16686
```

Truy cập `http://localhost:16686`.

## Task 3: Gửi một trace thủ công qua Zipkin API (15 phút)

Tạo Pod curl:

```bash
kubectl run curl --image=curlimages/curl:8.10.1 --restart=Never --command -- sleep 3600
kubectl wait --for=condition=Ready pod/curl --timeout=120s
```

Gửi span:

```bash
kubectl exec curl -- curl -sS \
  -X POST http://jaeger:9411/api/v2/spans \
  -H 'Content-Type: application/json' \
  -d '[
    {
      "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
      "id": "00f067aa0ba902b7",
      "kind": "SERVER",
      "name": "GET /orders/{id}",
      "localEndpoint": {
        "serviceName": "order-service"
      },
      "duration": 25000,
      "tags": {
        "http.method": "GET",
        "http.route": "/orders/{id}",
        "http.status_code": "200",
        "k8s.namespace.name": "day31",
        "service.version": "v1"
      }
    }
  ]'
```

Kiểm tra Jaeger API:

```bash
kubectl exec curl -- curl -s http://jaeger:16686/api/services
kubectl exec curl -- curl -s 'http://jaeger:16686/api/traces?service=order-service&limit=5'
```

Trong UI, chọn service `order-service` và bấm Find Traces.

### Expected output

- Jaeger có service `order-service`.
- Trace có một span `GET /orders/{id}`.
- Tags hiển thị method, route, status code, namespace và version.

## Task 4: Thêm OpenTelemetry Collector pipeline (25 phút)

Tạo file `otel-collector.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-collector-config
data:
  config.yaml: |
    receivers:
      zipkin:
        endpoint: 0.0.0.0:9411

    processors:
      memory_limiter:
        check_interval: 1s
        limit_mib: 128
      batch: {}

    exporters:
      debug:
        verbosity: detailed
      otlp/jaeger:
        endpoint: jaeger:4317
        tls:
          insecure: true

    service:
      pipelines:
        traces:
          receivers: [zipkin]
          processors: [memory_limiter, batch]
          exporters: [debug, otlp/jaeger]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otel-collector
spec:
  replicas: 1
  selector:
    matchLabels:
      app: otel-collector
  template:
    metadata:
      labels:
        app: otel-collector
    spec:
      containers:
      - name: otel-collector
        image: otel/opentelemetry-collector-contrib:0.108.0
        args:
        - --config=/conf/config.yaml
        ports:
        - name: zipkin
          containerPort: 9411
        volumeMounts:
        - name: config
          mountPath: /conf
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            memory: 256Mi
      volumes:
      - name: config
        configMap:
          name: otel-collector-config
---
apiVersion: v1
kind: Service
metadata:
  name: otel-collector
spec:
  selector:
    app: otel-collector
  ports:
  - name: zipkin
    port: 9411
    targetPort: zipkin
```

Apply:

```bash
kubectl apply -f otel-collector.yaml
kubectl rollout status deploy/otel-collector
kubectl logs deploy/otel-collector --tail=80
```

Gửi trace qua collector thay vì gửi thẳng Jaeger:

```bash
kubectl exec curl -- curl -sS \
  -X POST http://otel-collector:9411/api/v2/spans \
  -H 'Content-Type: application/json' \
  -d '[
    {
      "traceId": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "id": "bbbbbbbbbbbbbbbb",
      "kind": "SERVER",
      "name": "GET /inventory/{sku}",
      "localEndpoint": {"serviceName": "inventory-service"},
      "duration": 42000,
      "tags": {
        "http.route": "/inventory/{sku}",
        "http.status_code": "200"
      }
    }
  ]'
```

Kiểm tra:

```bash
kubectl logs deploy/otel-collector --tail=120
kubectl exec curl -- curl -s http://jaeger:16686/api/services
```

### Expected output

- Collector log có span ở debug exporter.
- Jaeger có service `inventory-service`.
- Bạn thấy pipeline `Zipkin receiver -> memory_limiter -> batch -> debug + OTLP exporter`.

## Task 5: Deploy service A -> B có propagation thật (35 phút)

Tạo file `trace-demo.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: trace-demo-scripts
data:
  service_a.py: |
    import http.server
    import json
    import os
    import secrets
    import time
    import urllib.request

    ZIPKIN = os.getenv("ZIPKIN_ENDPOINT", "http://otel-collector:9411/api/v2/spans")
    DOWNSTREAM = os.getenv("DOWNSTREAM_URL", "http://service-b:8080/work")

    def now_us():
        return int(time.time() * 1_000_000)

    def parse_traceparent(value):
        parts = (value or "").split("-")
        if len(parts) == 4 and len(parts[1]) == 32 and len(parts[2]) == 16:
            return parts[1], parts[2]
        return secrets.token_hex(16), None

    def emit(spans):
        data = json.dumps(spans).encode()
        req = urllib.request.Request(ZIPKIN, data=data, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=2).read()
        except Exception as exc:
            print(json.dumps({"service": "service-a", "event": "zipkin_export_failed", "error": str(exc)}), flush=True)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            incoming = self.headers.get("traceparent")
            trace_id, incoming_parent = parse_traceparent(incoming)
            server_span = secrets.token_hex(8)
            client_span = secrets.token_hex(8)
            downstream_traceparent = f"00-{trace_id}-{client_span}-01"

            status = 200
            try:
                req = urllib.request.Request(DOWNSTREAM, headers={"traceparent": downstream_traceparent})
                with urllib.request.urlopen(req, timeout=5) as response:
                    body = response.read()
                    downstream_status = response.status
            except Exception as exc:
                body = str(exc).encode()
                downstream_status = 502
                status = 502

            log = {
                "service": "service-a",
                "path": self.path,
                "trace_id": trace_id,
                "span_id": server_span,
                "incoming_traceparent": incoming,
                "downstream_traceparent": downstream_traceparent,
                "downstream_status": downstream_status,
            }
            print(json.dumps(log), flush=True)

            root = {
                "traceId": trace_id,
                "id": server_span,
                "kind": "SERVER",
                "name": "GET /checkout",
                "timestamp": now_us(),
                "duration": 50000,
                "localEndpoint": {"serviceName": "service-a"},
                "tags": {"http.route": "/checkout", "http.status_code": str(status)},
            }
            if incoming_parent:
                root["parentId"] = incoming_parent
            emit([
                root,
                {
                    "traceId": trace_id,
                    "parentId": server_span,
                    "id": client_span,
                    "kind": "CLIENT",
                    "name": "GET service-b /work",
                    "timestamp": now_us(),
                    "duration": 30000,
                    "localEndpoint": {"serviceName": "service-a"},
                    "tags": {"peer.service": "service-b", "http.status_code": str(downstream_status)},
                },
            ])

            self.send_response(status)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            return

    http.server.HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
  service_b.py: |
    import http.server
    import json
    import os
    import secrets
    import time
    import urllib.request

    ZIPKIN = os.getenv("ZIPKIN_ENDPOINT", "http://otel-collector:9411/api/v2/spans")

    def now_us():
        return int(time.time() * 1_000_000)

    def parse_traceparent(value):
        parts = (value or "").split("-")
        if len(parts) == 4 and len(parts[1]) == 32 and len(parts[2]) == 16:
            return parts[1], parts[2]
        return secrets.token_hex(16), None

    def emit(spans):
        data = json.dumps(spans).encode()
        req = urllib.request.Request(ZIPKIN, data=data, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=2).read()
        except Exception as exc:
            print(json.dumps({"service": "service-b", "event": "zipkin_export_failed", "error": str(exc)}), flush=True)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            incoming = self.headers.get("traceparent")
            trace_id, parent_span = parse_traceparent(incoming)
            span_id = secrets.token_hex(8)
            print(json.dumps({
                "service": "service-b",
                "path": self.path,
                "trace_id": trace_id,
                "span_id": span_id,
                "incoming_traceparent": incoming,
            }), flush=True)

            span = {
                "traceId": trace_id,
                "id": span_id,
                "kind": "SERVER",
                "name": "GET /work",
                "timestamp": now_us(),
                "duration": 12000,
                "localEndpoint": {"serviceName": "service-b"},
                "tags": {"http.route": "/work", "http.status_code": "200"},
            }
            if parent_span:
                span["parentId"] = parent_span
            emit([span])

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"service-b ok\n")

        def log_message(self, *_):
            return

    http.server.HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: service-b
spec:
  replicas: 1
  selector:
    matchLabels:
      app: service-b
  template:
    metadata:
      labels:
        app: service-b
    spec:
      containers:
      - name: app
        image: python:3.12-alpine
        command: ["python", "/app/service_b.py"]
        ports:
        - name: http
          containerPort: 8080
        volumeMounts:
        - name: scripts
          mountPath: /app
        resources:
          requests:
            cpu: 20m
            memory: 64Mi
          limits:
            memory: 128Mi
      volumes:
      - name: scripts
        configMap:
          name: trace-demo-scripts
---
apiVersion: v1
kind: Service
metadata:
  name: service-b
spec:
  selector:
    app: service-b
  ports:
  - name: http
    port: 8080
    targetPort: http
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: service-a
spec:
  replicas: 1
  selector:
    matchLabels:
      app: service-a
  template:
    metadata:
      labels:
        app: service-a
    spec:
      containers:
      - name: app
        image: python:3.12-alpine
        command: ["python", "/app/service_a.py"]
        env:
        - name: DOWNSTREAM_URL
          value: http://service-b:8080/work
        - name: ZIPKIN_ENDPOINT
          value: http://otel-collector:9411/api/v2/spans
        ports:
        - name: http
          containerPort: 8080
        volumeMounts:
        - name: scripts
          mountPath: /app
        resources:
          requests:
            cpu: 20m
            memory: 64Mi
          limits:
            memory: 128Mi
      volumes:
      - name: scripts
        configMap:
          name: trace-demo-scripts
---
apiVersion: v1
kind: Service
metadata:
  name: service-a
spec:
  selector:
    app: service-a
  ports:
  - name: http
    port: 8080
    targetPort: http
```

Apply và gọi service A:

```bash
kubectl apply -f trace-demo.yaml
kubectl rollout status deploy/service-a
kubectl rollout status deploy/service-b
kubectl exec curl -- curl -sS \
  -H 'traceparent: 00-1234567890abcdef1234567890abcdef-1111111111111111-01' \
  http://service-a:8080/checkout
```

Kiểm tra logs:

```bash
kubectl logs deploy/service-a --tail=20
kubectl logs deploy/service-b --tail=20
kubectl logs deploy/otel-collector --tail=120
```

### Expected output

- `service-a` log có `trace_id=1234567890abcdef1234567890abcdef`.
- `service-a` log có `downstream_traceparent`.
- `service-b` log có cùng `trace_id` và `incoming_traceparent` bằng header mà `service-a` gửi xuống.
- Collector log có spans từ `service-a` và `service-b`.
- Jaeger UI/API có service `service-a` và `service-b`.

## Task 6: Verification, correlation và cleanup note (15 phút)

Query Jaeger API:

```bash
kubectl exec curl -- curl -s http://jaeger:16686/api/services
kubectl exec curl -- curl -s 'http://jaeger:16686/api/traces?service=service-a&limit=5'
```

Viết câu trả lời:

| Hop | Evidence cần có |
|---|---|
| Client -> service-a | `traceparent` trong curl command hoặc service-a tự tạo trace mới |
| service-a -> service-b | `downstream_traceparent` trong service-a log |
| service-b receive | `incoming_traceparent` trong service-b log |
| Logs -> Trace | Cùng `trace_id` xuất hiện trong log và Jaeger |
| Collector -> Jaeger | Collector debug log và Jaeger API đều thấy span |

### Câu hỏi

- Nếu `service-b` log có `trace_id` khác `service-a`, code/layer nào có lỗi?
- Nếu logs có `trace_id` nhưng Jaeger không có trace, bạn kiểm tra Collector, sampling hay exporter trước?
- Nếu backend trace quá đắt, bạn sampling thế nào để vẫn giữ trace lỗi?

## Stretch Goals

- Gửi trace parent-child thủ công qua Zipkin API để so sánh với trace do service A -> B tạo.
- Thêm `service.version` vào span tags và log để debug rollout.
- Thử bỏ header `traceparent` khi `service-a` gọi `service-b` và quan sát trace bị đứt.

## Task 7: Cleanup

```bash
kubectl delete namespace day31
```

## Checklist hoàn thành

- [ ] Deploy được Jaeger all-in-one.
- [ ] Gửi được trace thủ công và xem trong Jaeger UI.
- [ ] Hiểu trace, span, parent span và service name.
- [ ] Deploy được OpenTelemetry Collector pipeline cơ bản.
- [ ] Deploy được service A -> B và thấy `traceparent` được propagate thật.
- [ ] Correlate được logs và traces bằng cùng `trace_id`.
- [ ] Viết được sampling và propagation checklist.

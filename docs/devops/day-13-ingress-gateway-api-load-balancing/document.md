# Day 13: Ingress & Gateway API — Cheat Sheet & Reference

## Ingress vs Gateway API Comparison

| Feature | Ingress | Gateway API |
|---------|---------|-------------|
| **API Version** | `networking.k8s.io/v1` | `gateway.networking.k8s.io/v1` |
| **Status** | Stable, legacy | GA v1.0+, future |
| **Resources** | Ingress (single) | GatewayClass → Gateway → *Route |
| **Role separation** | ❌ Single resource | ✅ Infra team / App team |
| **Protocols** | HTTP/HTTPS only | HTTP, gRPC, TCP, UDP, TLS |
| **Config method** | Annotations (vendor-specific) | Typed fields (portable) |
| **Traffic splitting** | Annotations only | Native weight-based |
| **Header matching** | Annotations only | Native |
| **Migration** | N/A | Can coexist with Ingress |

> Ingress API vẫn stable, nhưng community-maintained `kubernetes/ingress-nginx` controller đã retired/archived từ 03/2026. Đừng nhầm Ingress resource với một controller cụ thể.

## NGINX Ingress Annotations Cheat Sheet

### Routing & Rewrite

```yaml
# Rewrite target (strip path prefix)
nginx.ingress.kubernetes.io/rewrite-target: /

# Regex path matching
nginx.ingress.kubernetes.io/use-regex: "true"

# App root redirect
nginx.ingress.kubernetes.io/app-root: /dashboard

# Permanent redirect
nginx.ingress.kubernetes.io/permanent-redirect: https://new.example.com
```

### TLS & Security

```yaml
# Force HTTPS redirect
nginx.ingress.kubernetes.io/ssl-redirect: "true"
nginx.ingress.kubernetes.io/force-ssl-redirect: "true"

# Rate limiting
nginx.ingress.kubernetes.io/limit-rps: "10"
nginx.ingress.kubernetes.io/limit-rpm: "300"
nginx.ingress.kubernetes.io/limit-burst-multiplier: "3"
nginx.ingress.kubernetes.io/limit-connections: "5"

# IP whitelist
nginx.ingress.kubernetes.io/whitelist-source-range: "10.0.0.0/8,192.168.0.0/16"

# CORS
nginx.ingress.kubernetes.io/enable-cors: "true"
nginx.ingress.kubernetes.io/cors-allow-origin: "https://app.example.com"
nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, PUT, DELETE"
nginx.ingress.kubernetes.io/cors-allow-headers: "Authorization, Content-Type"

# Basic auth
nginx.ingress.kubernetes.io/auth-type: basic
nginx.ingress.kubernetes.io/auth-secret: basic-auth-secret
nginx.ingress.kubernetes.io/auth-realm: "Authentication Required"

# Custom headers
nginx.ingress.kubernetes.io/configuration-snippet: |
  more_set_headers "X-Frame-Options: DENY";
  more_set_headers "X-Content-Type-Options: nosniff";
```

### Performance & Timeouts

```yaml
# Proxy timeouts
nginx.ingress.kubernetes.io/proxy-connect-timeout: "5"
nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
nginx.ingress.kubernetes.io/proxy-send-timeout: "60"

# Buffer sizes
nginx.ingress.kubernetes.io/proxy-buffer-size: "8k"
nginx.ingress.kubernetes.io/proxy-body-size: "10m"

# Connection keep-alive
nginx.ingress.kubernetes.io/upstream-keepalive-connections: "32"
nginx.ingress.kubernetes.io/upstream-keepalive-timeout: "60"

# Sticky sessions
nginx.ingress.kubernetes.io/affinity: "cookie"
nginx.ingress.kubernetes.io/session-cookie-name: "SERVERID"
```

## TLS Configuration Checklist

### Self-signed Certificate (Dev/Test)

```bash
# Generate
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout tls.key \
  -out tls.crt \
  -subj "/CN=app.example.com/O=MyOrg" \
  -addext "subjectAltName=DNS:app.example.com"

# Create secret
kubectl create secret tls app-tls --cert=tls.crt --key=tls.key

# Verify
kubectl get secret app-tls -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -text -noout

# Verify local Ingress với đúng SNI
curl -kv --resolve app.example.com:443:127.0.0.1 --noproxy app.example.com https://app.example.com 2>&1 | grep "subject:"
```

### Production TLS Checklist

- [ ] Use cert-manager for auto cert management
- [ ] TLS 1.2+ only (disable TLS 1.0/1.1)
- [ ] ECDSA certificates preferred over RSA
- [ ] Certificate auto-renewal configured
- [ ] SSL redirect enabled (HTTP → HTTPS)
- [ ] HSTS header enabled
- [ ] Certificate monitoring/alerting set up

## AWS Load Balancer Mapping

| Kubernetes | AWS Service | Layer | Use Case |
|-----------|-------------|-------|----------|
| Service type: LoadBalancer | NLB | L4 | TCP/UDP, high perf, static IP |
| Ingress (ALB controller) | ALB | L7 | HTTP routing, path/host-based |
| External DNS controller | Route 53 | DNS | Auto DNS record management |
| cert-manager + ACME | ACM | TLS | Free TLS certificates |
| Ingress + WAF annotation | AWS WAF | L7 | Web Application Firewall |

### ALB Ingress Annotations (AWS)

```yaml
# ALB specific
kubernetes.io/ingress.class: alb
alb.ingress.kubernetes.io/scheme: internet-facing  # or internal
alb.ingress.kubernetes.io/target-type: ip           # or instance
alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:...
alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
alb.ingress.kubernetes.io/ssl-redirect: "443"
alb.ingress.kubernetes.io/healthcheck-path: /healthz
```

## Debugging Quick Reference

### Ingress không hoạt động

```bash
# 1. Check IC pods
kubectl get pods -n ingress-nginx

# 2. Check Ingress resource
kubectl describe ingress <name>
kubectl get ingress <name> -o yaml

# 3. Check IC logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller --tail=100

# 4. Check backend service/endpoints
kubectl get svc <backend>
kubectl get endpoints <backend>

# 5. Test from inside cluster
kubectl run curl-test --rm -it --image=curlimages/curl --restart=Never -- curl -v http://<service>
```

### Common HTTP Errors

| Error | Likely Cause | Debug |
|-------|-------------|-------|
| 404 | Path/host not matching rules | Check Ingress rules, pathType |
| 502 | Backend pod not reachable | Check pod status, targetPort |
| 503 | No backend endpoints | Check endpoints, readiness |
| 504 | Backend timeout | Check proxy-read-timeout, backend health |
| 413 | Request body too large | Set proxy-body-size annotation |
| 429 | Rate limited | Check limit-rps annotation |

## Production Checklist

### Ingress Controller
- [ ] Không dùng retired `kubernetes/ingress-nginx` cho platform production mới; nếu đang dùng, có migration plan sang Gateway API hoặc controller còn maintained
- [ ] Multiple IC replicas (≥ 2)
- [ ] PodAntiAffinity across nodes
- [ ] PodDisruptionBudget configured
- [ ] Resource requests/limits set
- [ ] HPA for auto-scaling
- [ ] Prometheus metrics enabled
- [ ] Access logs enabled

### Ingress Resource
- [ ] ingressClassName explicitly set
- [ ] TLS configured for all hosts
- [ ] SSL redirect enabled
- [ ] Rate limiting on public endpoints
- [ ] Appropriate timeouts set
- [ ] CORS configured if needed
- [ ] Security headers set
- [ ] Health check paths excluded from auth


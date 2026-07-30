# Kubernetes hướng Production — 7 ngày từ nền tảng đến hệ thống thực chiến

Khóa học nhanh 7 ngày giúp bạn đi từ "biết chạy container" đến "thiết kế và vận hành được một hệ thống production-grade trên Kubernetes". Mỗi ngày học theo dạng: bài học → thực hành → tài liệu tham khảo.

**Giả định:** bạn đã biết Docker/container cơ bản, có nền lập trình backend, học trên máy cá nhân bằng **Minikube** và **Floci** để giả lập AWS.

## Roadmap 7 ngày

| Ngày | Trọng tâm | Deliverable cuối ngày |
|---|---|---|
| **1** | K8s core: Pod, Deployment, Service, Ingress, ConfigMap, Secret + Minikube | Deploy app đầu tiên, truy cập được qua trình duyệt |
| **2** | Production-readiness: probes, resource limits, HPA, API Gateway, Redis | App tự phục hồi, tự co giãn, có cache |
| **3** | Helm: chart, template, values, release | Đóng gói app + Redis thành 1 Helm chart cài lại được |
| **4** | GitOps + Argo CD + Jenkins | Đẩy Git → Argo CD tự sync lên cluster |
| **5** | Terraform + Floci: IaC, giả lập AWS/EKS | Provision hạ tầng bằng `terraform apply` |
| **6** | Observability: Prometheus + Grafana + ELK | Dashboard metrics + log tập trung xem được |
| **7** | Capstone: thiết kế hệ thống production | Sơ đồ kiến trúc + mini hệ thống chạy được |

## Mục tiêu học nhanh (3 cấp độ)

**Cấp độ 1 — Biết dùng cơ bản:**
- Dựng được cluster Minikube, deploy 1 app, `kubectl get pods` thấy Running.
- Hiểu Pod/Deployment/Service/Ingress/ConfigMap/Secret khác nhau ra sao.

**Cấp độ 2 — Làm được việc thực tế:**
- Deploy app + Redis, expose qua Ingress, cấu hình probes + resource limits + HPA.
- Dựng pipeline GitOps: đẩy Git → Argo CD tự deploy.
- Xem được metrics trên Grafana và log trên Kibana.

**Cấp độ 3 — Đi sâu / chuyên nghiệp:**
- Thiết kế hệ thống production nhiều thành phần và giải thích trade-off.
- Xử lý sự cố: CrashLoopBackOff, OOMKilled, pod pending, drift trong GitOps.

## Tài liệu tham khảo

- [Giới thiệu & Roadmap chi tiết](./00-gioi-thieu)
- [Tổng hợp & ôn tập](./99-tong-hop)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs)
- [Argo CD Documentation](https://argo-cd.readthedocs.io/)
- [Terraform Documentation](https://developer.hashicorp.com/terraform)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

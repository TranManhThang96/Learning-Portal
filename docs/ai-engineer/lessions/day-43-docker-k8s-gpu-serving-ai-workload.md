# Day 43: Docker/K8s/GPU Serving Cho AI Workload

Day 43 chuyển RAG/LLM service từ trạng thái "chạy được trên máy mình" sang trạng thái có thể đóng gói, chạy local bằng Docker Compose và có đường nâng cấp lên Kubernetes/GPU serving.

## Nội dung

1. [Lession: Docker/K8s/GPU Serving cho AI workload](./day-43-docker-k8s-gpu-serving-ai-workload/lession.md)
   - Docker image cho ML/AI service, Dockerfile CPU/GPU, `.dockerignore`, healthcheck và runtime config.
   - Docker Compose cho RAG app gồm API, vector DB, optional UI/model server và `.env.example`.
   - Kubernetes manifests cho API/vector DB/model server, GPU scheduling, `nodeSelector`, taints/tolerations và `nvidia-device-plugin`.
   - Tổng quan Helm, KServe, Ray Serve, trade-off, best solution theo context/performance và production readiness answer.

2. [Document: Template cấu hình, manifest và runbook](./day-43-docker-k8s-gpu-serving-ai-workload/document.md)
   - Project structure, Dockerfile, Compose, `.env.example`, Kubernetes manifests và GPU node setup checklist.
   - Template Helm values, KServe/Ray Serve skeleton, smoke test, rollback plan và deployment note.
   - Checklist production readiness cho Docker, Kubernetes, GPU, security, observability và cost.

3. [Exercise: Lab Dockerize và deploy RAG/LLM service](./day-43-docker-k8s-gpu-serving-ai-workload/exercise.md)
   - Dockerize FastAPI RAG backend từ Day 40.
   - Chạy local bằng Docker Compose, thêm health/readiness endpoint và smoke test.
   - Viết Kubernetes manifests, optional GPU deployment, benchmark latency/resource và trả lời production readiness.

## Mục tiêu sau bài học

- Build được Docker image repeatable cho AI backend mà không leak secret hoặc đóng gói dữ liệu/model cache quá lớn.
- Chạy được RAG stack local bằng Docker Compose với API, vector DB, volume, env file và healthcheck rõ ràng.
- Viết được Kubernetes manifests đủ tốt cho learning/portfolio: `Deployment`, `Service`, `ConfigMap`, `Secret`, resource requests/limits, probes và rollout/rollback.
- Hiểu NVIDIA GPU stack trong container/Kubernetes: host driver, `nvidia-container-toolkit`, container runtime, `nvidia-device-plugin`, `nvidia.com/gpu`.
- Biết khi nào dùng Docker Compose, raw Kubernetes manifests, Helm chart, KServe, Ray Serve, managed LLM hoặc self-host GPU.
- Trả lời được: "Dùng được trong production không? Nếu có thì cần điều kiện gì?"

# Day 30: Quantization & Deploy Local Model API

Bài này đã được tách thành folder riêng để dễ học, dễ review và dễ mở rộng:

- [Lession: kiến thức chính](day-30-quantization-deploy-local-model-api/lession.md)
- [Document: production reference](day-30-quantization-deploy-local-model-api/document.md)
- [Exercise: bài thực hành](day-30-quantization-deploy-local-model-api/exercise.md)

Gợi ý học trong 2 giờ:

1. Đọc `lession.md` để hiểu FP32/FP16/BF16, INT8/INT4, GGUF, AWQ, GPTQ, KV cache, VRAM estimation và trade-off throughput vs quality.
2. Mở `document.md` khi cần công thức, checklist production, FastAPI gateway template, logging, readiness, concurrency và benchmark.
3. Làm `exercise.md` để chạy local model API, đo latency, memory usage và quyết định quantization có đủ điều kiện production không.

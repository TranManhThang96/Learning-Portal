# Day 29: Local LLM - Ollama, llama.cpp, vLLM

Bài này đã được tách thành thư mục riêng để dễ học và thực hành.

## Nội dung

- [lession.md](./day-29-local-llm-ollama-llama-cpp-vllm/lession.md): bài học chính, giải thích step by step về local LLM, runtime, trade-off, performance và production decision.
- [document.md](./day-29-local-llm-ollama-llama-cpp-vllm/document.md): tài liệu triển khai gần production, gồm OpenAI-compatible client abstraction, FastAPI proxy, health check, logging, timeout/retry, config và benchmark.
- [exercise.md](./day-29-local-llm-ollama-llama-cpp-vllm/exercise.md): bài tập thực hành, checklist, quiz và decision note.

## Mục tiêu nhanh

Sau Day 29, bạn cần trả lời được:

- Vì sao dùng local LLM: privacy, cost, latency, offline, control và compliance.
- Khi nào chọn Ollama, llama.cpp, vLLM, TGI hoặc LM Studio.
- Local LLM dùng được trong production không, nếu có thì cần điều kiện gì.
- Làm sao thiết kế model serving API để app không bị lock-in vào một runtime.

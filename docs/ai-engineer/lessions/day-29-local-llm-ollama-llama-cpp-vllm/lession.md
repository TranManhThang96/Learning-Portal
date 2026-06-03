# Day 29: Local LLM - Ollama, llama.cpp, vLLM

## Mục Tiêu

Sau bài này, bạn cần làm được các việc sau:

- Hiểu vì sao team chọn local/self-host LLM thay vì luôn gọi cloud LLM API.
- Phân biệt đúng vai trò của Ollama, llama.cpp, vLLM, TGI và LM Studio.
- Hiểu các biến ảnh hưởng serving: model size, tokenizer, context window, quantization, KV cache, batching, concurrency, RAM/VRAM.
- Gọi được local model qua HTTP API và OpenAI-compatible client.
- Thiết kế được LLM gateway để business code không phụ thuộc trực tiếp vào một runtime.
- Biết benchmark latency, throughput, memory và chất lượng ở mức đủ để ra production decision.
- Trả lời rõ: dùng được trong production không, nếu có thì cần điều kiện gì.

## TL;DR

Local LLM không chỉ là "tải model về máy". Nó là một serving stack gồm model weights, tokenizer, runtime inference, quantization kernels, API server, scheduler, hardware, observability, security policy và deployment process.

Ollama phù hợp nhất cho local development, prototype và internal tool vì setup nhanh. llama.cpp mạnh ở GGUF, CPU, Apple Silicon, edge và môi trường hạn chế memory. vLLM phù hợp GPU serving có concurrency cao nhờ scheduler, batching và OpenAI-compatible server. TGI phù hợp team đã dùng Hugging Face ecosystem và muốn containerized serving. LM Studio rất tốt cho học, demo, manual evaluation nhưng không nên là production backend mặc định.

Production answer ngắn: local LLM dùng được trong production, nhưng chỉ khi bạn kiểm soát được model license, eval quality, hardware capacity, API gateway, timeout/retry, observability, security, fallback, rollout và vận hành GPU/CPU như một service thật.

## 1. Bài Này Nằm Ở Đâu Trong Phase 4

Phase 4 đi từ quyết định fine-tuning tới local deployment:

```text
Day 25: Khi nào dùng RAG, fine-tuning, distillation
Day 26: Chuẩn bị dataset instruction tuning
Day 27: LoRA/QLoRA hands-on
Day 28: Evaluation trước/sau fine-tune
Day 29: Local LLM runtime và model serving API
Day 30: Quantization và deploy local model API
```

Day 29 không tập trung vào train model. Trọng tâm là inference/runtime: sau khi có base model hoặc fine-tuned model, bạn phục vụ nó cho app như thế nào, đo hiệu năng ra sao, và chọn runtime nào theo context.

## 2. Vì Sao Dùng Local LLM

### Privacy

Local LLM giúp dữ liệu không phải rời khỏi network bạn kiểm soát. Điều này quan trọng khi prompt chứa source code private, tài liệu nội bộ, dữ liệu khách hàng, thông tin pháp lý, dữ liệu y tế, dữ liệu tài chính hoặc policy nội bộ.

Nhưng local không tự động an toàn. Nếu bạn log prompt thô chứa PII, mount volume sai quyền, expose endpoint không auth, hoặc lưu KV cache/debug dump không kiểm soát, dữ liệu vẫn có thể leak. Privacy là property của toàn bộ system, không phải chỉ của model.

### Cost

Cloud API tính tiền theo token. Local LLM tốn GPU/CPU, RAM/VRAM, điện, storage, ops, monitoring và thời gian engineer. Local có thể rẻ hơn khi workload ổn định, traffic lớn, model vừa đủ nhỏ, hardware được tận dụng tốt và team có năng lực vận hành.

Nếu traffic thấp, yêu cầu chất lượng cao, hoặc team chưa có GPU ops, cloud API thường rẻ hơn về total cost of ownership.

### Latency

Local LLM có thể giảm network latency nếu service nằm gần app hoặc user. Với internal app trong cùng datacenter, request không phải đi qua internet. Tuy nhiên inference latency vẫn phụ thuộc model size, context length, quantization, hardware, batching và số request đồng thời.

Local nhỏ hơn không luôn nhanh hơn theo cách hữu ích. Model quá nhỏ có thể trả lời sai, khiến phải retry, fallback hoặc human review, làm latency end-to-end tăng.

### Offline

Local LLM hữu ích cho air-gapped environment, factory, lab, field device, laptop dev khi mất mạng, hoặc nơi không được gọi external API. Use case offline thường cần artifact management chặt: model file, tokenizer, config, container image, eval set và rollback bundle phải đi cùng nhau.

### Control và Compliance

Local giúp bạn pin model version, pin runtime version, chọn quantization, giới hạn log retention, enforce data residency, audit request path và thử nghiệm model nội bộ. Đổi lại, bạn sở hữu trách nhiệm security patch, model upgrade, incident response và capacity planning.

## 3. Mental Model Của Local Serving

```text
Client/App
  -> LLM Gateway hoặc Provider Adapter
  -> Runtime API Server
      -> Request validation
      -> Tokenizer
      -> Model weights
      -> Quantization kernels
      -> KV cache
      -> Scheduler / batching
  -> Stream hoặc JSON response
```

Map về tư duy Senior Software Engineer:

| AI serving concept | SE analogy | Cần quan tâm |
|---|---|---|
| Model weights | Build artifact | Version, checksum, license, storage |
| Tokenizer | Parser/input contract | Token count, special tokens, chat template |
| Runtime | Application server | Performance, compatibility, observability |
| Quantization | Compression/optimized binary | Quality loss, memory, kernel support |
| KV cache | Runtime memory state | VRAM tăng theo context và concurrency |
| Context window | Request payload budget | Prompt dài làm chậm và tốn memory |
| Chat template | Serialization contract | Sai template làm model trả lời kém |
| Model serving API | Internal service contract | Timeout, retry, streaming, auth, schema |

## 4. Các Biến Quyết Định Hiệu Năng

### Model size

Model càng nhiều parameters thì thường chất lượng tốt hơn nhưng cần nhiều RAM/VRAM hơn và decode chậm hơn. Model 7B quantized có thể chạy trên laptop mạnh; model 70B cần GPU server nghiêm túc nếu muốn latency tốt.

### Dtype và quantization

FP16/BF16 thường dùng cho GPU serving chất lượng cao. INT8/INT4, GGUF, AWQ, GPTQ giúp giảm memory. Trade-off là chất lượng có thể giảm, kernel có thể không tối ưu cho mọi runtime, và một số quantization phù hợp runtime này nhưng không phù hợp runtime khác.

### Context window và KV cache

Prompt dài làm prefill chậm. Mỗi token trong context sinh thêm KV cache. Khi batch/concurrency tăng, KV cache có thể trở thành nguyên nhân hết VRAM trước cả model weights.

Rule thực tế: luôn benchmark với prompt dài đúng production, không chỉ prompt "hello".

### Throughput và latency

- Latency: thời gian một request hoàn thành.
- Time-to-first-token: thời gian tới token đầu tiên khi streaming.
- Throughput: token/second tổng hoặc request/second.
- p95/p99: tail latency, quan trọng hơn average với user-facing app.

Batching tăng throughput nhưng có thể tăng latency cho request đơn lẻ. Runtime phục vụ chatbot realtime và runtime phục vụ batch summarization có tuning khác nhau.

## 5. Runtime Options

### Ollama

Ollama là lựa chọn nhanh nhất để bắt đầu local LLM. Nó quản lý pull model, run model, local API và có OpenAI-compatible endpoint.

Ví dụ:

```bash
ollama pull llama3.2
ollama run llama3.2
```

Native API:

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "llama3.2",
  "messages": [
    {"role": "user", "content": "Giải thích local LLM trong 3 bullet"}
  ],
  "stream": false
}'
```

OpenAI-compatible endpoint thường dùng dạng:

```text
http://localhost:11434/v1
```

Dùng Ollama khi:

- Cần setup nhanh trên laptop.
- Cần test prompt, RAG, tool calling local.
- Cần internal demo hoặc dev offline.
- Muốn app dùng OpenAI-compatible client để giảm lock-in.

Không nên mặc định dùng Ollama khi:

- Cần throughput GPU cao với nhiều user đồng thời.
- Cần autoscaling, multi-replica, metrics production đầy đủ.
- Cần tuning sâu scheduler/batching.

### llama.cpp

llama.cpp là runtime C/C++ inference, nổi bật với GGUF, CPU inference, Apple Silicon, GPU offload và edge deployment.

Ví dụ server:

```bash
./build/bin/llama-server \
  -m ./models/model-q4_k_m.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  -c 4096 \
  -ngl 99
```

Dùng llama.cpp khi:

- Cần chạy CPU hoặc edge.
- Cần artifact GGUF nhỏ, dễ ship.
- Cần kiểm soát memory tốt.
- Cần runtime ít dependency.
- Cần Apple Silicon hoặc máy dev không có NVIDIA GPU.

Trade-off:

- Throughput scale lớn cần tự thiết kế thêm gateway, queue, metrics, replica và load balancing.
- Chọn GGUF quantization sai có thể làm chất lượng giảm rõ.
- Với model lớn, CPU latency có thể không đáp ứng realtime chat.

### vLLM

vLLM là inference engine/server tối ưu cho GPU throughput, OpenAI-compatible serving, scheduler và batching.

Ví dụ:

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct \
  --host 0.0.0.0 \
  --port 8000
```

Dùng vLLM khi:

- Có GPU server và traffic đồng thời.
- Cần throughput cao.
- Cần OpenAI-compatible endpoint cho app.
- Cần serving controls, metrics và production deployment rõ hơn dev tool.
- Cần phục vụ chat/completions nhiều request.

Trade-off:

- Cần hiểu GPU memory, tensor parallel, max model len, batch sizing và rollout.
- Setup phức tạp hơn Ollama.
- Không phải model/quantization nào cũng chạy tốt như nhau.

### TGI

TGI, Text Generation Inference, phù hợp khi team đã dùng Hugging Face ecosystem, model registry, container deployment và muốn serving stack có production orientation.

Dùng TGI khi:

- Model nằm trong Hugging Face workflow.
- Team quen Docker/Kubernetes.
- Cần containerized serving và monitoring.
- Muốn tiêu chuẩn hóa deployment nhiều model HF.

Trade-off:

- Ops phức tạp hơn Ollama.
- Cần kiểm tra compatibility từng model, dtype, quantization và GPU.

### LM Studio

LM Studio là desktop UX tốt để tải model, chat thử, so sánh model và expose local API trong lúc học hoặc demo.

Dùng LM Studio khi:

- Người học muốn nhìn thấy model chạy ngay.
- Product/PM/engineer cần manual evaluation nhanh.
- Cần thử nhiều GGUF model trên desktop.

Không nên coi LM Studio là production backend mặc định vì deployment, security, observability, scaling và automation không phải trọng tâm chính của nó.

## 6. Runtime Matrix

| Runtime | Mạnh ở đâu | Hạn chế | Hardware thường gặp | API | Production fit |
|---|---|---|---|---|---|
| Ollama | Setup nhanh, dev UX tốt, pull/run đơn giản | Throughput cao và ops production cần bổ sung | Laptop, workstation, single server | Native + OpenAI-compatible | Internal tool nhỏ, dev, prototype; production nhỏ nếu bọc gateway/monitoring |
| llama.cpp | GGUF, CPU, Apple Silicon, edge, memory thấp | Scale lớn cần tự xây nhiều phần | CPU, Apple Silicon, GPU offload | Server API/OpenAI-compatible tùy build | Edge, offline, embedded, workload nhỏ/vừa |
| vLLM | GPU throughput, batching, OpenAI-compatible serving | Cần GPU ops và tuning | NVIDIA GPU server | OpenAI-compatible | Production GPU serving mạnh |
| TGI | Hugging Face ecosystem, container serving | Setup/ops nặng hơn dev tools | NVIDIA GPU server | HTTP/generation API | Production nếu team dùng HF stack |
| LM Studio | Desktop UX, manual eval, học nhanh | Không phải backend production chuẩn | Laptop/desktop | Local API | Dev/manual evaluation |
| Cloud LLM API | Quality/SLA/time-to-market | Cost/token, data boundary, provider lock-in | Provider-managed | Provider API | Production nhanh nếu compliance cho phép |

## 7. Best Solution Theo Context

| Context | Lựa chọn nên bắt đầu | Vì sao |
|---|---|---|
| Học local LLM trong 1 giờ | Ollama hoặc LM Studio | Setup nhanh, ít ops |
| Dev RAG app offline | Ollama | Dễ chạy OpenAI-compatible endpoint |
| Laptop Apple Silicon | llama.cpp hoặc Ollama | GGUF/Metal/local UX tốt |
| Edge device không có GPU mạnh | llama.cpp + GGUF quantized | Memory thấp, artifact dễ đóng gói |
| Internal assistant traffic thấp | Ollama sau LLM gateway | Đơn giản, đủ dùng nếu benchmark đạt |
| Chat API nhiều user đồng thời | vLLM | Scheduler/batching tốt cho GPU throughput |
| Team đã chuẩn HF/K8s | TGI hoặc vLLM | Dễ đưa vào platform hiện có |
| Batch summarization traffic ổn định | vLLM/TGI với batching | Tối ưu cost/token và throughput |
| Data không được rời khỏi VPC | Self-host vLLM/TGI/llama.cpp | Kiểm soát network và data residency |
| Cần model chất lượng cao nhất ngay | Cloud LLM API hoặc hybrid | Local model nhỏ có thể chưa đạt quality |

## 8. Model Serving API Nên Thiết Kế Thế Nào

Không hardcode Ollama, vLLM hoặc llama.cpp vào business logic. App nên gọi một interface nội bộ:

```text
Product App
  -> LLM Gateway
      -> policy: model, runtime, timeout, max_tokens, fallback
      -> ProviderAdapter: OpenAI cloud
      -> ProviderAdapter: Ollama
      -> ProviderAdapter: vLLM
      -> ProviderAdapter: llama.cpp
  -> Response + trace
```

Contract tối thiểu:

```python
class ChatRequest(BaseModel):
    messages: list[dict[str, str]]
    model_policy: str = "default"
    temperature: float = 0.2
    max_tokens: int = 512
    timeout_s: float = 30.0


class ChatResponse(BaseModel):
    text: str
    model: str
    runtime: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    trace_id: str
```

Gateway chịu trách nhiệm:

- Validate input và giới hạn max prompt size.
- Chọn runtime/model theo policy.
- Timeout và retry có kiểm soát.
- Streaming nếu UX cần.
- Logging không leak PII.
- Rate limit, auth, tenant isolation.
- Fallback sang model khác hoặc cloud provider.
- Chuẩn hóa response schema.
- Ghi metric latency, token, error, memory signal.

## 9. Performance, Throughput, Latency Và VRAM Concern

### Những metric cần đo

| Metric | Ý nghĩa |
|---|---|
| Time-to-first-token | User cảm thấy model bắt đầu trả lời nhanh hay chậm |
| Total latency | Request hoàn thành mất bao lâu |
| Output tokens/second | Decode speed |
| Requests/second | Service capacity |
| p50/p95/p99 latency | Tail latency |
| RAM/VRAM used | Có còn headroom không |
| Error rate | Timeout, OOM, 5xx, invalid response |
| Quality score | Golden eval, human rating, task success |

### Các nguyên nhân latency cao

- Model quá lớn so với hardware.
- Prompt quá dài làm prefill chậm.
- `max_tokens` quá rộng khiến decode dài.
- Concurrency vượt capacity, queue tăng.
- KV cache đầy VRAM.
- Quantization format không tối ưu cho runtime.
- Cold start hoặc model unload/reload.
- Không streaming nên user phải chờ toàn bộ output.

### VRAM estimation ở mức trực giác

VRAM không chỉ chứa model weights. Nó còn chứa KV cache, activation workspace, runtime overhead và fragmentation. Với production, đừng dùng 100% VRAM lý thuyết. Cần headroom để tránh OOM khi prompt dài hoặc concurrency tăng.

Checklist capacity:

- Model weights fit vào VRAM với dtype/quantization đã chọn.
- Context length production không vượt ngân sách KV cache.
- Batch/concurrency benchmark đúng traffic thật.
- Có guardrail `max_tokens`, `max_context`, request timeout.
- Có canary và rollback khi đổi model/runtime.

## 10. Production Answer

### Dùng được trong production không?

Có, local LLM dùng được trong production. Nhiều use case production hợp lý gồm internal assistant, private RAG, code assistant nội bộ, batch summarization, document extraction, offline assistant và domain workflow có data boundary nghiêm ngặt.

### Nếu có thì cần điều kiện gì?

Cần tối thiểu các điều kiện sau:

- Model license cho phép use case hiện tại, đặc biệt commercial/internal distribution.
- Có golden eval để chứng minh chất lượng đủ tốt so với cloud baseline hoặc human baseline.
- Có runtime phù hợp context: Ollama cho internal nhỏ/dev, llama.cpp cho edge/CPU/GGUF, vLLM/TGI cho GPU production.
- Có LLM gateway với auth, timeout, retry, max token, logging, policy routing và fallback.
- Có observability: latency p50/p95/p99, throughput, token count, error rate, RAM/VRAM, OOM, queue time, quality sample.
- Có security policy: không log PII thô, tenant isolation, network boundary, secret management, audit log.
- Có deployment process: pin model revision, runtime version, container image, config, canary, rollback.
- Có capacity planning: benchmark theo prompt thật, concurrency thật, context thật và output length thật.
- Có response validation nếu output đi vào downstream automation.

Không nên production nếu:

- Chỉ mới chạy được demo trên laptop.
- Chưa đọc license model.
- Chưa có eval dataset.
- Chưa đo p95 latency và memory.
- Endpoint không auth hoặc log prompt nhạy cảm.
- Không có fallback khi model timeout/OOM.
- Team không có năng lực vận hành hardware/runtime đã chọn.

## 11. Checklist Học Xong

- [ ] Giải thích được local LLM khác gì cloud LLM API.
- [ ] Nêu được privacy benefit và privacy risk còn lại.
- [ ] Phân biệt được Ollama, llama.cpp, vLLM, TGI, LM Studio.
- [ ] Biết vì sao OpenAI-compatible API giúp giảm lock-in.
- [ ] Biết KV cache ảnh hưởng memory và latency như thế nào.
- [ ] Biết đo latency, throughput, p95 và RAM/VRAM.
- [ ] Có decision note chọn runtime theo context.
- [ ] Trả lời được điều kiện để dùng local LLM trong production.

## 12. Câu Hỏi Tự Kiểm Tra

1. Local LLM giải quyết privacy theo cách nào, và không giải quyết phần nào?
2. Vì sao traffic thấp thường chưa nên self-host LLM?
3. Ollama khác vLLM ở mục tiêu thiết kế nào?
4. GGUF liên quan gì tới llama.cpp?
5. Vì sao prompt dài làm prefill chậm và KV cache lớn?
6. Khi nào chọn TGI thay vì vLLM?
7. Vì sao LM Studio tốt cho learning nhưng không phải production backend mặc định?
8. OpenAI-compatible API giúp app architecture như thế nào?
9. Nếu local model trả lời kém hơn cloud model, bạn đo và quyết định ra sao?
10. Điều kiện tối thiểu để đưa local LLM vào production là gì?

## 13. Tài Liệu Liên Quan Trong Folder

- `document.md`: code và cấu hình triển khai.
- `exercise.md`: bài tập 60-120 phút, benchmark và decision note.

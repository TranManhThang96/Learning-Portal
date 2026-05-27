# Tài Liệu Tham Khảo — Ngày 19: Prompt Engineering

## 📚 Official Docs

- **OpenAI Prompt Engineering Guide** — https://platform.openai.com/docs/guides/prompt-engineering — Official guide từ OpenAI, cover 6 strategies chính
- **OpenAI Safety Best Practices** — https://platform.openai.com/docs/guides/safety-best-practices — Prompt injection defense, moderation
- **OpenAI Moderation API** — https://platform.openai.com/docs/guides/moderation — Built-in content moderation, free to use
- **Jinja2 Documentation** — https://jinja.palletsprojects.com/en/3.1.x/ — Template syntax đầy đủ, filters, tests, extensions
- **Jinja2 Template Designer Guide** — https://jinja.palletsprojects.com/en/3.1.x/templates/ — Chỉ đọc phần này là đủ cho prompt templating

## 🎥 Video / Courses

- **ChatGPT Prompt Engineering for Developers** — https://www.deeplearning.ai/short-courses/chatgpt-prompt-engineering-for-developers/ — Free course từ DeepLearning.AI + OpenAI, do Isa Fulford và Andrew Ng dạy. **Bắt buộc xem** nếu chưa xem.
- **Building Systems with the ChatGPT API** — https://www.deeplearning.ai/short-courses/building-systems-with-chatgpt/ — Follow-up course, cover chain of prompts, evaluation
- **LangChain for LLM Application Development** — https://www.deeplearning.ai/short-courses/langchain-for-llm-application-development/ — Ecosystem rộng hơn
- **Prompt Engineering Playlist (LearnLM)** — https://www.youtube.com/playlist?list=PLrmY8197EITj6B5o5v3lO-PdUMBpMtyeO — Kỹ thuật advanced
- **AI Red-Teaming & Prompt Injection (Simon Willison)** — https://www.youtube.com/watch?v=Sv5OLj2nVAQ — Security-focused, quan trọng cho production

## 📝 Articles / Blog Posts

- **"Prompt Engineering Guide" (DAIR.AI)** — https://www.promptingguide.ai/ — Comprehensive guide, cover CoT, ToT, ReAct, RAG. Reference tốt nhất hiện tại.
- **"Chain-of-Thought Prompting" (Google Brain)** — https://arxiv.org/abs/2201.11903 — Paper gốc về CoT, nên đọc abstract và key results
- **"Large Language Models are Zero-Shot Reasoners"** — https://arxiv.org/abs/2205.11916 — Paper về "Let's think step by step"
- **"Prompt Injection Attacks Against GPT-3"** — https://research.nccgroup.com/2022/12/05/exploring-prompt-injection-attacks/ — Security perspective
- **"Defending Against Prompt Injection"** — https://simonwillison.net/2023/Apr/25/dual-llm-pattern/ — Simon Willison's dual-LLM pattern, một trong những defense approaches tốt nhất
- **"Evaluating LLMs"** — https://hamel.dev/blog/posts/evals/ — Hamel Husain's comprehensive guide về LLM evaluation
- **"The Illustrated Transformer"** — http://jalammar.github.io/illustrated-transformer/ — Hiểu internals giúp hiểu tại sao prompts work
- **"OpenAI Cookbook — Techniques to improve reliability"** — https://cookbook.openai.com/articles/techniques_to_improve_reliability — Official tips với benchmarks

## 🔧 Tools / Libraries

- **Jinja2** — `uv add jinja2` — Template engine, dùng trong bài học
- **promptwatch** — `uv add promptwatch` — https://github.com/blip-solutions/promptwatch-client — Track, version, và evaluate prompts
- **promptflow** — `uv add promptflow` — https://microsoft.github.io/promptflow/ — Microsoft's framework cho LLM application development, có built-in eval
- **LangSmith** — https://smith.langchain.com — Observability platform cho LLM apps, tracing prompts trong production
- **Braintrust** — https://www.braintrustdata.com — Eval platform, A/B testing prompts với metrics
- **Promptfoo** — https://promptfoo.dev — CLI tool cho prompt testing, open source
- **guidance** — `uv add guidance` — https://github.com/guidance-ai/guidance — Structured generation, constrained prompts
- **outlines** — `uv add outlines` — https://github.com/outlines-dev/outlines — Constrained text generation, alternative to Pydantic structured output

## 💡 Ghi chú thêm

**Prompt Engineering Mental Models cho NodeJS devs:**

1. **System prompt = Constructor + Class definition:** Giống như `class MyService { constructor() { this.role = "..."; this.constraints = [...] } }`. Một lần set, áp dụng cho toàn bộ conversation.

2. **Few-shot = Unit test examples (inverted):** Trong unit tests, bạn provide input → assert output. Trong few-shot, bạn provide input + desired output → model learns pattern.

3. **Reasoning summary = Debug notes:** Khi debug NodeJS, bạn add logs vừa đủ để audit state. Với LLM, yêu cầu assumptions/calculation steps ngắn gọn; không cần yêu cầu model tiết lộ toàn bộ hidden reasoning.

4. **Prompt injection = XSS/SQL injection:** Cùng attack pattern — untrusted user input thay đổi behavior của system. Defense cũng tương tự — sanitize, escape, separate data from instructions.

5. **Eval suite = Integration tests:** Prompt thay đổi = code change → cần test suite để ensure không bị regression.

**Jinja2 Quick Reference cho Prompt Templates:**
```jinja2
{# Comment #}
{{ variable }}               {# Print variable #}
{{ variable | upper }}       {# Filter: upper/lower/trim/default/truncate #}
{{ variable | default("N/A") }}  {# Default nếu variable undefined #}

{% if condition %}           {# If/elif/else #}
  ...
{% elif other_condition %}
  ...
{% else %}
  ...
{% endif %}

{% for item in items %}      {# Loop #}
  {{ loop.index }}: {{ item }}  {# loop.index bắt đầu từ 1 #}
{% endfor %}

{% set my_var = "value" %}   {# Set variable #}

{# Multi-line string trong variable #}
{{ long_text | wordwrap(80) }}   {# Wrap tại 80 chars #}
{{ code | indent(4) }}           {# Indent mỗi dòng 4 spaces #}
```

**Prompt Engineering Anti-patterns cần tránh:**

1. **The Kitchen Sink**: Nhét quá nhiều instructions vào 1 prompt. Model "forgets" instructions ở giữa khi context dài.
   - Fix: Tách thành multiple focused prompts (prompt chaining)

2. **The Wishful Thinking**: "Return a perfect, comprehensive, accurate answer". Vô nghĩa với model.
   - Fix: Specify cụ thể: format, length, what to include/exclude

3. **The Inconsistent Few-shot**: Examples không consistent về format hoặc style.
   - Fix: Ensure tất cả examples follow exactly cùng format

4. **The Secret System Prompt Syndrome**: Nghĩ rằng system prompt là "bí mật" an toàn.
   - Fix: Assume users luôn có thể extract system prompt. Đừng put secrets vào prompt — dùng server-side business logic.

5. **The God Prompt**: Một prompt làm mọi thứ.
   - Fix: Decompose thành specialized prompts, orchestrate với code

**Model config / snapshot pinning — rất quan trọng:**
```python
# Iteration nhanh — alias/current model, dễ upgrade nhưng behavior có thể đổi
model = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5")

# Reproducibility cao — nếu model catalog cung cấp snapshot phù hợp, pin snapshot đó trong config
model = os.getenv("OPENAI_PINNED_MODEL", "gpt-5")

# Cách check available model versions:
# client.models.list() → filter theo family bạn dùng
```

**Monitoring prompts trong production:**
```python
# Minimal logging wrapper — add vào mọi LLM call
import uuid, logging, hashlib, os

def logged_response(input_items, model, **kwargs):
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"LLM_REQUEST id={request_id} model={model} "
                f"item_count={len(input_items)} "
                f"first_item_hash={hashlib.md5(input_items[0]['content'].encode()).hexdigest()[:8]}")

    response = client.responses.create(model=model, input=input_items, **kwargs)

    logger.info(f"LLM_RESPONSE id={request_id} "
                f"tokens={response.usage.total_tokens} "
                f"response_id={response.id}")
    return response

# Với request_id, bạn có thể trace toàn bộ pipeline khi debug production issues
```

# Tài Liệu Tham Khảo — Ngày 28

## 📚 Official Docs

- **Anthropic Python SDK** — https://github.com/anthropics/anthropic-sdk-python — Source code và examples đầy đủ
- **Anthropic API Docs** — https://docs.anthropic.com/en/api — Reference đầy đủ, bao gồm tool use, vision
- **Anthropic Tool Use Guide** — https://docs.anthropic.com/en/docs/build-with-claude/tool-use — Hướng dẫn function calling với Claude
- **Google GenAI SDK** — https://ai.google.dev/gemini-api/docs/libraries — SDK hiện hành cho Gemini (`google-genai`)
- **Google GenAI migration** — https://ai.google.dev/gemini-api/docs/migrate — Chuyển từ `google-generativeai` sang `google-genai`
- **Gemini API Docs** — https://ai.google.dev/gemini-api/docs — Reference đầy đủ
- **OpenAI Responses API** — https://platform.openai.com/docs/guides/responses-vs-chat-completions — Responses API là default path mới; Chat Completions là compatibility
- **OpenAI Function Calling** — https://platform.openai.com/docs/guides/function-calling — Tool-calling flow với Responses API
- **OpenAI Whisper** — https://github.com/openai/whisper — Repository chính thức, model sizes, supported languages
- **OpenAI Audio API** — https://platform.openai.com/docs/api-reference/audio — Whisper API reference

## 🎥 Video / Courses

- **Claude Tool Use Deep Dive** — https://www.youtube.com/watch?v=4h2NM_qWbcc — Official Anthropic video
- **Building AI Agents with Function Calling** — https://www.deeplearning.ai/short-courses/building-systems-with-the-chatgpt-api/ — DeepLearning.AI short course (miễn phí)
- **Gemini API Tutorial** — https://www.youtube.com/playlist?list=PLIivdWyY5sqJio5vkSCaFOBEVZBHRE7b3 — Official Google playlist
- **Whisper Tutorial** — https://www.youtube.com/watch?v=ABFqbY_rmEk — Hands-on local Whisper

## 📝 Articles / Blog Posts

- **Anthropic Claude Models Overview** — https://docs.anthropic.com/en/docs/about-claude/models — Danh sách models hiện tại với capabilities
- **Prompt Caching with Claude** — https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching — Có thể giảm cost/latency cho repeated long prompts; mức lợi ích phụ thuộc model và cache hit
- **Gemini Models** — https://ai.google.dev/gemini-api/docs/models — Danh sách model/context/capabilities hiện hành; đọc trước khi chọn model production
- **OpenAI Whisper Blog Post** — https://openai.com/research/whisper — Technical explanation
- **Building Reliable AI Agents** — https://www.anthropic.com/research/building-effective-agents — Anthropic research blog

## 🔧 Tools / Libraries

- **anthropic** — `uv add anthropic` — Claude Python SDK
- **google-genai** — `uv add google-genai` — Gemini Python SDK hiện hành
- **openai** — `uv add openai` — OpenAI SDK (cũng dùng cho Whisper API)
- **openai-whisper** — `uv add openai-whisper` — Local Whisper model
- **pytz** — `uv add pytz` — Timezone handling
- **Pillow** — `uv add Pillow` — Image processing (cần cho Gemini vision)
- **ffmpeg-python** — `uv add ffmpeg-python` — Audio processing wrapper (cần cho Whisper)
- **litellm** — `uv add litellm` — Unified API cho 100+ LLM providers (Claude, Gemini, OpenAI, etc.)

## 💡 Ghi chú thêm

**Setup environment variables:**
```bash
# Thêm vào ~/.zshrc hoặc ~/.bashrc
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="AI..."  # google-genai cũng đọc GOOGLE_API_KEY nếu team đã dùng tên đó
export OPENAI_API_KEY="sk-..."
export CLAUDE_MODEL="<current-claude-model-from-docs>"
export GEMINI_MODEL="<current-gemini-model-from-docs>"
export OPENAI_MODEL="<current-openai-model-from-docs>"

# Hoặc dùng .env file với python-dotenv
uv add python-dotenv
```

```python
# Load .env trong Python
from dotenv import load_dotenv
load_dotenv()  # đọc từ .env file trong current directory
```

**Pricing workflow (không hardcode vào bài):**
| Provider | Xem ở đâu | Cách dùng trong lab |
|----------|-----------|---------------------|
| Anthropic | https://docs.anthropic.com/en/docs/about-claude/pricing | Lưu giá snapshot vào config/README của project thật, kèm ngày kiểm tra |
| Google Gemini | https://ai.google.dev/gemini-api/docs/pricing | Lấy model từ `GEMINI_MODEL`, không assume Flash/Pro cố định |
| OpenAI | https://platform.openai.com/docs/pricing | Dùng pricing page hiện hành cho Responses/Audio, không copy số vào code |

**LiteLLM — provider abstraction một dòng:**
```python
# uv add litellm
import os
from litellm import completion

# Cùng API cho tất cả providers
response = completion(
    model=os.environ["LITELLM_MODEL"],  # ví dụ: anthropic/<model>, gemini/<model>, openai/<model>
    messages=[{"role": "user", "content": "Hello"}]
)
```

**Retry với tenacity:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential
import anthropic
import os

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def call_claude_with_retry(prompt: str) -> str:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

**FFmpeg cài đặt:**
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows: download từ https://ffmpeg.org/download.html
```

from __future__ import annotations

import asyncio
import hashlib
import random
import time
import uuid
from dataclasses import dataclass
from typing import Literal, Protocol

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


TaskType = Literal["chat", "extract", "reasoning"]
TenantTier = Literal["free", "pro", "enterprise"]


app = FastAPI(title="Day 20 LLM Orchestrator Skeleton")


class ChatRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=128)
    task: TaskType = "chat"
    message: str = Field(min_length=1, max_length=4000)
    prompt_id: str = "assistant"
    prompt_version: str = "v1"
    schema_version: str = "text.v1"
    max_output_tokens: int = Field(default=256, ge=16, le=1024)


class ChatResponse(BaseModel):
    trace_id: str
    answer: str
    provider: str
    model: str
    cache_hit: bool
    fallback_used: bool
    retry_count: int
    latency_ms: float
    prompt_id: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class DebugProviderRequest(BaseModel):
    fail: bool


class ProviderRequest(BaseModel):
    trace_id: str
    prompt: str
    max_output_tokens: int
    temperature: float = 0.2


class ProviderResponse(BaseModel):
    text: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class PromptTemplate:
    prompt_id: str
    version: str
    owner: str
    schema_version: str
    template: str


@dataclass(frozen=True)
class TenantPolicy:
    tier: TenantTier
    request_quota: int
    daily_budget_usd: float
    allowed_models: set[str]


class ProviderError(Exception):
    retryable: bool = True


class ProviderUnavailable(ProviderError):
    pass


class ProviderTimeout(ProviderError):
    pass


class LLMProvider(Protocol):
    name: str
    model: str
    cost_per_1k_tokens_usd: float

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        ...


class MockProvider:
    def __init__(
        self,
        *,
        name: str,
        model: str,
        delay_ms: int,
        cost_per_1k_tokens_usd: float,
        fail: bool = False,
    ) -> None:
        self.name = name
        self.model = model
        self.delay_ms = delay_ms
        self.cost_per_1k_tokens_usd = cost_per_1k_tokens_usd
        self.fail = fail

    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        await asyncio.sleep(self.delay_ms / 1000)
        if self.fail:
            raise ProviderUnavailable(f"{self.name} is unavailable")

        input_tokens = estimate_tokens(request.prompt)
        output_tokens = min(request.max_output_tokens, 80 + len(request.prompt) // 20)
        text = (
            f"[{self.model}] task completed. "
            f"trace_id={request.trace_id}. "
            f"summary={request.prompt[-180:]}"
        )
        return ProviderResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


PROMPTS: dict[tuple[str, str], PromptTemplate] = {
    ("assistant", "v1"): PromptTemplate(
        prompt_id="assistant",
        version="v1",
        owner="ai-platform",
        schema_version="text.v1",
        template=(
            "Bạn là AI assistant nội bộ. Trả lời ngắn gọn, đúng ngữ cảnh, "
            "không tự ý gọi tool.\nTask: {task}\nUser message: {message}"
        ),
    ),
    ("support_triage", "v1"): PromptTemplate(
        prompt_id="support_triage",
        version="v1",
        owner="support-platform",
        schema_version="ticket_triage.v1",
        template=(
            "Phân loại ticket support. Trả về hướng xử lý rõ ràng, nêu priority "
            "và lý do.\nTask: {task}\nTicket: {message}"
        ),
    ),
}


PROVIDERS: dict[str, MockProvider] = {
    "mock-fast": MockProvider(
        name="mock-fast",
        model="fast-extract-v1",
        delay_ms=120,
        cost_per_1k_tokens_usd=0.0002,
    ),
    "mock-balanced": MockProvider(
        name="mock-balanced",
        model="balanced-chat-v1",
        delay_ms=320,
        cost_per_1k_tokens_usd=0.0010,
    ),
    "mock-strong": MockProvider(
        name="mock-strong",
        model="strong-reason-v1",
        delay_ms=850,
        cost_per_1k_tokens_usd=0.0030,
    ),
}


TENANT_POLICIES: dict[str, TenantPolicy] = {
    "tenant_free": TenantPolicy(
        tier="free",
        request_quota=20,
        daily_budget_usd=1.0,
        allowed_models={"fast-extract-v1"},
    ),
    "tenant_pro": TenantPolicy(
        tier="pro",
        request_quota=200,
        daily_budget_usd=20.0,
        allowed_models={"fast-extract-v1", "balanced-chat-v1"},
    ),
    "tenant_enterprise": TenantPolicy(
        tier="enterprise",
        request_quota=1000,
        daily_budget_usd=500.0,
        allowed_models={"fast-extract-v1", "balanced-chat-v1", "strong-reason-v1"},
    ),
}


cache: dict[str, ChatResponse] = {}
audit_events: list[dict] = []
tenant_request_count: dict[str, int] = {}
tenant_cost_usd: dict[str, float] = {}
metrics = {
    "requests_total": 0,
    "cache_hits_total": 0,
    "fallbacks_total": 0,
    "retries_total": 0,
    "provider_errors_total": 0,
}


def get_tenant_policy(tenant_id: str) -> TenantPolicy:
    return TENANT_POLICIES.get(
        tenant_id,
        TenantPolicy(
            tier="free",
            request_quota=10,
            daily_budget_usd=0.25,
            allowed_models={"fast-extract-v1"},
        ),
    )


def enforce_quota(tenant_id: str, policy: TenantPolicy) -> None:
    used = tenant_request_count.get(tenant_id, 0)
    spent = tenant_cost_usd.get(tenant_id, 0.0)
    if used >= policy.request_quota:
        raise HTTPException(status_code=429, detail="tenant request quota exceeded")
    if spent >= policy.daily_budget_usd:
        raise HTTPException(status_code=429, detail="tenant cost budget exceeded")
    tenant_request_count[tenant_id] = used + 1


def get_prompt(prompt_id: str, prompt_version: str) -> PromptTemplate:
    prompt = PROMPTS.get((prompt_id, prompt_version))
    if prompt is None:
        raise HTTPException(status_code=400, detail="unknown prompt_id or prompt_version")
    return prompt


def build_prompt(req: ChatRequest, prompt: PromptTemplate) -> str:
    return prompt.template.format(task=req.task, message=req.message)


def permission_hash(req: ChatRequest) -> str:
    raw = f"{req.tenant_id}:{req.user_id}:{req.task}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_cache_key(req: ChatRequest, prompt: PromptTemplate, provider: LLMProvider, rendered_prompt: str) -> str:
    raw = "|".join(
        [
            req.tenant_id,
            permission_hash(req),
            prompt.prompt_id,
            prompt.version,
            prompt.schema_version,
            provider.model,
            req.task,
            normalize_text(rendered_prompt),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def route_models(req: ChatRequest, policy: TenantPolicy) -> list[LLMProvider]:
    if req.task == "extract":
        candidates = [PROVIDERS["mock-fast"], PROVIDERS["mock-balanced"]]
    elif req.task == "reasoning":
        candidates = [PROVIDERS["mock-strong"], PROVIDERS["mock-balanced"], PROVIDERS["mock-fast"]]
    else:
        candidates = [PROVIDERS["mock-balanced"], PROVIDERS["mock-fast"]]

    allowed = [provider for provider in candidates if provider.model in policy.allowed_models]
    if not allowed:
        raise HTTPException(status_code=403, detail="tenant tier has no allowed model for this task")
    return allowed


async def call_provider_with_timeout(provider: LLMProvider, request: ProviderRequest) -> ProviderResponse:
    try:
        return await asyncio.wait_for(provider.generate(request), timeout=1.2)
    except asyncio.TimeoutError as exc:
        raise ProviderTimeout(f"{provider.name} timed out") from exc


async def generate_with_retry_and_fallback(
    *,
    req: ChatRequest,
    trace_id: str,
    rendered_prompt: str,
    providers: list[LLMProvider],
) -> tuple[ProviderResponse, LLMProvider, bool, int]:
    retry_count = 0
    last_error = "unknown"

    for provider_index, provider in enumerate(providers):
        max_attempts = 2 if provider_index == 0 else 1
        for attempt in range(max_attempts):
            try:
                provider_request = ProviderRequest(
                    trace_id=trace_id,
                    prompt=rendered_prompt,
                    max_output_tokens=req.max_output_tokens,
                )
                response = await call_provider_with_timeout(provider, provider_request)
                return response, provider, provider_index > 0, retry_count
            except ProviderError as exc:
                metrics["provider_errors_total"] += 1
                last_error = str(exc)
                if attempt < max_attempts - 1:
                    retry_count += 1
                    metrics["retries_total"] += 1
                    await asyncio.sleep(backoff_seconds(attempt))

    raise HTTPException(
        status_code=503,
        detail={"error": "all_models_failed", "last_error": last_error},
    )


def backoff_seconds(attempt: int) -> float:
    return 0.1 * (2**attempt) + random.uniform(0, 0.05)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_cost(provider: LLMProvider, input_tokens: int, output_tokens: int) -> float:
    return round(((input_tokens + output_tokens) / 1000) * provider.cost_per_1k_tokens_usd, 8)


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]


def append_audit_event(
    *,
    req: ChatRequest,
    trace_id: str,
    response: ChatResponse | None,
    status: str,
    error_code: str | None = None,
) -> None:
    audit_events.append(
        {
            "event_type": "llm_request_completed",
            "trace_id": trace_id,
            "tenant_id": req.tenant_id,
            "user_id_hash": hash_user_id(req.user_id),
            "task": req.task,
            "prompt_id": req.prompt_id,
            "prompt_version": req.prompt_version,
            "schema_version": req.schema_version,
            "provider": response.provider if response else None,
            "model": response.model if response else None,
            "cache_hit": response.cache_hit if response else False,
            "retry_count": response.retry_count if response else 0,
            "fallback_used": response.fallback_used if response else False,
            "input_tokens": response.input_tokens if response else 0,
            "output_tokens": response.output_tokens if response else 0,
            "estimated_cost_usd": response.estimated_cost_usd if response else 0,
            "latency_ms": response.latency_ms if response else 0,
            "status": status,
            "error_code": error_code,
        }
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    start = time.perf_counter()
    trace_id = str(uuid.uuid4())
    metrics["requests_total"] += 1

    policy = get_tenant_policy(req.tenant_id)
    enforce_quota(req.tenant_id, policy)
    prompt = get_prompt(req.prompt_id, req.prompt_version)
    rendered_prompt = build_prompt(req, prompt)
    providers = route_models(req, policy)
    primary = providers[0]
    key = build_cache_key(req, prompt, primary, rendered_prompt)

    if key in cache:
        metrics["cache_hits_total"] += 1
        cached = cache[key].copy(
            update={
                "trace_id": trace_id,
                "cache_hit": True,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            }
        )
        append_audit_event(req=req, trace_id=trace_id, response=cached, status="success")
        return cached

    try:
        provider_response, provider, fallback_used, retry_count = await generate_with_retry_and_fallback(
            req=req,
            trace_id=trace_id,
            rendered_prompt=rendered_prompt,
            providers=providers,
        )
        if fallback_used:
            metrics["fallbacks_total"] += 1

        cost = estimate_cost(provider, provider_response.input_tokens, provider_response.output_tokens)
        tenant_cost_usd[req.tenant_id] = tenant_cost_usd.get(req.tenant_id, 0.0) + cost
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        response = ChatResponse(
            trace_id=trace_id,
            answer=provider_response.text,
            provider=provider.name,
            model=provider.model,
            cache_hit=False,
            fallback_used=fallback_used,
            retry_count=retry_count,
            latency_ms=latency_ms,
            prompt_id=req.prompt_id,
            prompt_version=req.prompt_version,
            input_tokens=provider_response.input_tokens,
            output_tokens=provider_response.output_tokens,
            estimated_cost_usd=cost,
        )
        cache[key] = response
        append_audit_event(req=req, trace_id=trace_id, response=response, status="success")
        return response
    except HTTPException as exc:
        append_audit_event(req=req, trace_id=trace_id, response=None, status="error", error_code=str(exc.status_code))
        raise


@app.get("/audit")
async def audit() -> list[dict]:
    return audit_events[-100:]


@app.get("/metrics")
async def read_metrics() -> dict:
    return {
        **metrics,
        "cache_size": len(cache),
        "audit_events": len(audit_events),
        "tenant_request_count": tenant_request_count,
        "tenant_cost_usd": tenant_cost_usd,
    }


@app.post("/debug/provider/{provider_name}/fail")
async def set_provider_failure(provider_name: str, req: DebugProviderRequest) -> dict:
    provider = PROVIDERS.get(provider_name)
    if provider is None:
        raise HTTPException(status_code=404, detail="provider not found")
    provider.fail = req.fail
    return {"provider": provider_name, "fail": provider.fail}

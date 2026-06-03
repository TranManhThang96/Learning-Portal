from __future__ import annotations

import math

import torch
from torch import nn


def make_causal_mask(seq_len: int, device: torch.device) -> torch.Tensor:
    if seq_len <= 0:
        raise ValueError("seq_len must be positive")
    return torch.tril(torch.ones(seq_len, seq_len, dtype=torch.bool, device=device))


class MultiHeadSelfAttention(nn.Module):
    def __init__(self, embed_dim: int, num_heads: int, dropout_p: float = 0.1) -> None:
        super().__init__()
        if embed_dim <= 0 or num_heads <= 0:
            raise ValueError("embed_dim and num_heads must be positive")
        if embed_dim % num_heads != 0:
            raise ValueError("embed_dim must be divisible by num_heads")

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.qkv = nn.Linear(embed_dim, 3 * embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)
        self.dropout = nn.Dropout(dropout_p)

    def _normalize_mask(
        self,
        attention_mask: torch.Tensor,
        batch_size: int,
        seq_len: int,
        device: torch.device,
    ) -> torch.Tensor:
        if attention_mask.dtype != torch.bool:
            raise TypeError("attention_mask must be boolean, where True means allowed")

        attention_mask = attention_mask.to(device=device)
        if attention_mask.shape == (batch_size, seq_len):
            return attention_mask[:, None, None, :]
        if attention_mask.shape == (batch_size, 1, 1, seq_len):
            return attention_mask
        if attention_mask.shape == (batch_size, self.num_heads, seq_len, seq_len):
            return attention_mask

        raise ValueError(f"unsupported attention_mask shape: {tuple(attention_mask.shape)}")

    def forward(
        self,
        x: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        causal: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if x.ndim != 3:
            raise ValueError("x must have shape [batch, seq_len, embed_dim]")

        batch_size, seq_len, embed_dim = x.shape
        if embed_dim != self.embed_dim:
            raise ValueError(f"expected embed_dim={self.embed_dim}, got {embed_dim}")

        qkv = self.qkv(x).view(batch_size, seq_len, 3, self.num_heads, self.head_dim)
        q, k, v = qkv.permute(2, 0, 3, 1, 4).unbind(0)

        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)

        allowed = None
        if attention_mask is not None:
            allowed = self._normalize_mask(attention_mask, batch_size, seq_len, x.device)
        if causal:
            causal_allowed = make_causal_mask(seq_len, x.device)[None, None, :, :]
            allowed = causal_allowed if allowed is None else allowed & causal_allowed
        if allowed is not None:
            if not allowed.any(dim=-1).all():
                raise ValueError("each query must be allowed to attend to at least one key")
            scores = scores.masked_fill(~allowed, torch.finfo(scores.dtype).min)

        weights = torch.softmax(scores, dim=-1)
        weights = self.dropout(weights)
        context = torch.matmul(weights, v)
        context = context.transpose(1, 2).contiguous().view(batch_size, seq_len, embed_dim)
        return self.out_proj(context), weights


def run_tests() -> None:
    torch.manual_seed(13)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float32

    model = MultiHeadSelfAttention(embed_dim=32, num_heads=4, dropout_p=0.2).to(device=device, dtype=dtype)
    x = torch.randn(2, 5, 32, device=device, dtype=dtype)
    padding_mask = torch.tensor(
        [
            [True, True, True, False, False],
            [True, True, True, True, True],
        ],
        dtype=torch.bool,
        device=device,
    )

    model.eval()
    output, weights = model(x, attention_mask=padding_mask, causal=True)
    assert output.shape == (2, 5, 32)
    assert weights.shape == (2, 4, 5, 5)
    assert output.device == x.device
    assert output.dtype == x.dtype
    assert torch.allclose(weights[0, :, :, 3:], torch.zeros_like(weights[0, :, :, 3:]), atol=1e-6)
    assert torch.allclose(weights[:, :, 1, 2:], torch.zeros_like(weights[:, :, 1, 2:]), atol=1e-6)

    eval_a, _ = model(x, attention_mask=padding_mask)
    eval_b, _ = model(x, attention_mask=padding_mask)
    assert torch.allclose(eval_a, eval_b)

    model.train()
    train_a, _ = model(x, attention_mask=padding_mask)
    train_b, _ = model(x, attention_mask=padding_mask)
    assert not torch.allclose(train_a, train_b)

    try:
        model(x, attention_mask=padding_mask.to(dtype=torch.float32))
    except TypeError:
        pass
    else:
        raise AssertionError("float attention_mask should fail fast")

    print("All tests passed")
    print(f"device={device}, dtype={dtype}")
    print(f"output.shape={tuple(output.shape)}")
    print(f"weights.shape={tuple(weights.shape)}")
    print("batch0/head0 attention weights with padding + causal mask:")
    rounded_weights = (weights[0, 0].detach().cpu() * 1000).round() / 1000
    print(rounded_weights)


if __name__ == "__main__":
    run_tests()

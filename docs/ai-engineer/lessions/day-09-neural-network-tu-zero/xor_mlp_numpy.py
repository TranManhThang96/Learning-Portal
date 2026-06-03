from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray


Array = NDArray[np.floating]
ActivationName = Literal["tanh", "relu", "sigmoid", "gelu"]


def sigmoid(x: Array) -> Array:
    clipped = np.clip(x, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def binary_cross_entropy(y_true: Array, y_pred: Array, eps: float = 1e-7) -> float:
    y_pred = np.clip(y_pred, eps, 1.0 - eps)
    loss = -(y_true * np.log(y_pred) + (1.0 - y_true) * np.log(1.0 - y_pred))
    return float(np.mean(loss))


def activation_forward(name: ActivationName, z: Array) -> Array:
    if name == "tanh":
        return np.tanh(z)
    if name == "relu":
        return np.maximum(z, 0.0)
    if name == "sigmoid":
        return sigmoid(z)
    if name == "gelu":
        c = np.sqrt(2.0 / np.pi)
        return 0.5 * z * (1.0 + np.tanh(c * (z + 0.044715 * np.power(z, 3))))
    raise ValueError(f"Unsupported activation: {name}")


def activation_backward(name: ActivationName, z: Array, a: Array) -> Array:
    if name == "tanh":
        return 1.0 - np.square(a)
    if name == "relu":
        return (z > 0.0).astype(z.dtype)
    if name == "sigmoid":
        return a * (1.0 - a)
    if name == "gelu":
        c = np.sqrt(2.0 / np.pi)
        u = c * (z + 0.044715 * np.power(z, 3))
        tanh_u = np.tanh(u)
        du = c * (1.0 + 3.0 * 0.044715 * np.square(z))
        return 0.5 * (1.0 + tanh_u) + 0.5 * z * (1.0 - np.square(tanh_u)) * du
    raise ValueError(f"Unsupported activation: {name}")


def _check_2d(name: str, value: Array, expected_cols: int | None = None) -> None:
    if value.ndim != 2:
        raise ValueError(f"{name} must be 2D, got shape={value.shape}")
    if expected_cols is not None and value.shape[1] != expected_cols:
        raise ValueError(
            f"{name} must have {expected_cols} columns, got shape={value.shape}"
        )


def _init_scale(fan_in: int, activation: ActivationName) -> float:
    if activation in {"relu", "gelu"}:
        return float(np.sqrt(2.0 / fan_in))
    return float(np.sqrt(1.0 / fan_in))


@dataclass(frozen=True)
class MLPConfig:
    input_dim: int = 2
    hidden_dim: int = 4
    output_dim: int = 1
    learning_rate: float = 0.5
    epochs: int = 8_000
    seed: int = 42
    activation: ActivationName = "tanh"
    dtype: np.dtype = np.dtype("float32")
    clip_grad_norm: float | None = None


class TwoLayerMLP:
    def __init__(self, config: MLPConfig) -> None:
        if config.input_dim <= 0 or config.hidden_dim <= 0 or config.output_dim <= 0:
            raise ValueError("input_dim, hidden_dim and output_dim must be positive")
        if config.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if config.clip_grad_norm is not None and config.clip_grad_norm <= 0:
            raise ValueError("clip_grad_norm must be positive when provided")

        self.config = config
        self.rng = np.random.default_rng(config.seed)

        scale1 = _init_scale(config.input_dim, config.activation)
        scale2 = np.sqrt(1.0 / config.hidden_dim)

        self.W1 = self.rng.normal(
            loc=0.0, scale=scale1, size=(config.input_dim, config.hidden_dim)
        ).astype(config.dtype)
        self.b1 = np.zeros((1, config.hidden_dim), dtype=config.dtype)
        self.W2 = self.rng.normal(
            loc=0.0, scale=scale2, size=(config.hidden_dim, config.output_dim)
        ).astype(config.dtype)
        self.b2 = np.zeros((1, config.output_dim), dtype=config.dtype)

    def forward(self, X: Array) -> tuple[Array, dict[str, Array]]:
        X = np.asarray(X, dtype=self.config.dtype)
        _check_2d("X", X, self.config.input_dim)

        Z1 = X @ self.W1 + self.b1
        A1 = activation_forward(self.config.activation, Z1)
        Z2 = A1 @ self.W2 + self.b2
        P = sigmoid(Z2)

        if P.shape != (X.shape[0], self.config.output_dim):
            raise RuntimeError(f"Invalid output shape: {P.shape}")

        cache = {"X": X, "Z1": Z1, "A1": A1, "Z2": Z2, "P": P}
        return P, cache

    def train_step(self, X: Array, Y: Array) -> tuple[float, float]:
        Y = np.asarray(Y, dtype=self.config.dtype)
        _check_2d("Y", Y, self.config.output_dim)

        P, cache = self.forward(X)
        if Y.shape[0] != P.shape[0]:
            raise ValueError(f"X and Y batch sizes differ: {P.shape[0]} != {Y.shape[0]}")

        batch_size = Y.shape[0]
        loss = binary_cross_entropy(Y, P)
        if not np.isfinite(loss):
            raise FloatingPointError(f"Loss is not finite: {loss}")

        dZ2 = (P - Y) / batch_size
        dW2 = cache["A1"].T @ dZ2
        db2 = np.sum(dZ2, axis=0, keepdims=True)

        dA1 = dZ2 @ self.W2.T
        dZ1 = dA1 * activation_backward(self.config.activation, cache["Z1"], cache["A1"])
        dW1 = cache["X"].T @ dZ1
        db1 = np.sum(dZ1, axis=0, keepdims=True)

        grads = {"W1": dW1, "b1": db1, "W2": dW2, "b2": db2}
        self._check_gradient_shapes(grads)
        grad_norm = self._clip_gradients_if_needed(grads)

        self.W2 -= self.config.learning_rate * grads["W2"]
        self.b2 -= self.config.learning_rate * grads["b2"]
        self.W1 -= self.config.learning_rate * grads["W1"]
        self.b1 -= self.config.learning_rate * grads["b1"]

        return loss, grad_norm

    def fit(self, X: Array, Y: Array, log_every: int = 1_000) -> list[float]:
        if log_every <= 0:
            raise ValueError("log_every must be positive")

        history: list[float] = []
        for epoch in range(1, self.config.epochs + 1):
            loss, grad_norm = self.train_step(X, Y)
            history.append(loss)

            if epoch == 1 or epoch % log_every == 0 or epoch == self.config.epochs:
                logging.info(
                    "epoch=%d loss=%.6f grad_norm=%.6f",
                    epoch,
                    loss,
                    grad_norm,
                )

        return history

    def predict_proba(self, X: Array) -> Array:
        P, _ = self.forward(X)
        return P

    def predict(self, X: Array, threshold: float = 0.5) -> NDArray[np.int64]:
        if not 0.0 < threshold < 1.0:
            raise ValueError("threshold must be between 0 and 1")
        return (self.predict_proba(X) >= threshold).astype(np.int64)

    def _check_gradient_shapes(self, grads: dict[str, Array]) -> None:
        expected = {
            "W1": self.W1.shape,
            "b1": self.b1.shape,
            "W2": self.W2.shape,
            "b2": self.b2.shape,
        }
        for name, shape in expected.items():
            if grads[name].shape != shape:
                raise RuntimeError(
                    f"Gradient {name} shape mismatch: expected={shape}, got={grads[name].shape}"
                )

    def _clip_gradients_if_needed(self, grads: dict[str, Array]) -> float:
        total_norm = float(
            np.sqrt(sum(float(np.sum(np.square(grad))) for grad in grads.values()))
        )
        max_norm = self.config.clip_grad_norm
        if max_norm is not None and total_norm > max_norm:
            scale = max_norm / (total_norm + 1e-12)
            for name in grads:
                grads[name] *= scale
        return total_norm


def make_xor(
    *,
    dtype: np.dtype,
    noise_std: float = 0.0,
    seed: int = 42,
) -> tuple[Array, Array]:
    if noise_std < 0:
        raise ValueError("noise_std must be non-negative")

    X = np.array(
        [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]],
        dtype=dtype,
    )
    Y = np.array([[0.0], [1.0], [1.0], [0.0]], dtype=dtype)

    if noise_std > 0:
        rng = np.random.default_rng(seed + 10_000)
        noise = rng.normal(loc=0.0, scale=noise_std, size=X.shape).astype(dtype)
        X = X + noise

    return X, Y


def maybe_plot(history: list[float], *, enabled: bool, path: str | None) -> None:
    if not enabled:
        return

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logging.warning("matplotlib is not installed; skipping loss plot")
        return

    epochs = np.arange(1, len(history) + 1)
    plt.figure(figsize=(8, 4))
    plt.plot(epochs, history)
    plt.title("XOR MLP loss")
    plt.xlabel("epoch")
    plt.ylabel("binary cross entropy")
    plt.grid(True, alpha=0.3)

    if path:
        plt.savefig(path, dpi=160, bbox_inches="tight")
        logging.info("saved loss plot to %s", path)
    else:
        plt.show()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a 2-layer NumPy MLP on XOR.")
    parser.add_argument("--hidden-dim", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=0.5)
    parser.add_argument("--epochs", type=int, default=8_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--activation",
        choices=["tanh", "relu", "sigmoid", "gelu"],
        default="tanh",
    )
    parser.add_argument("--dtype", choices=["float32", "float64"], default="float32")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--noise-std", type=float, default=0.0)
    parser.add_argument("--log-every", type=int, default=1_000)
    parser.add_argument("--clip-grad-norm", type=float, default=None)
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--plot-path", default=None)
    parser.add_argument("--assert-xor", action="store_true")
    parser.add_argument("--max-final-loss", type=float, default=0.05)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(message)s",
    )

    dtype = np.dtype(args.dtype)
    X, Y = make_xor(dtype=dtype, noise_std=args.noise_std, seed=args.seed)
    config = MLPConfig(
        hidden_dim=args.hidden_dim,
        learning_rate=args.learning_rate,
        epochs=args.epochs,
        seed=args.seed,
        activation=args.activation,
        dtype=dtype,
        clip_grad_norm=args.clip_grad_norm,
    )

    model = TwoLayerMLP(config)
    history = model.fit(X, Y, log_every=args.log_every)

    probabilities = model.predict_proba(X)
    predictions = model.predict(X, threshold=args.threshold)
    expected = Y.astype(np.int64)
    accuracy = float(np.mean(predictions == expected))

    print(f"final_loss={history[-1]:.6f}")
    print(f"accuracy={accuracy:.3f}")
    print("probabilities=")
    print(np.round(probabilities, 4))
    print("predictions=")
    print(predictions)
    print("expected=")
    print(expected)

    if args.assert_xor:
        if not np.array_equal(predictions, expected):
            raise SystemExit("XOR assertion failed: predictions do not match labels")
        if history[-1] > args.max_final_loss:
            raise SystemExit(
                f"XOR assertion failed: final_loss={history[-1]:.6f} > {args.max_final_loss}"
            )

    maybe_plot(history, enabled=args.plot, path=args.plot_path)


if __name__ == "__main__":
    main()

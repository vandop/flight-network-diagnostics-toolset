"""Delay strategy helpers shared by the server and clients."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


class DelayConfigurationError(Exception):
    """Raised when delay configuration is invalid."""


@dataclass
class DelayStrategy:
    strategy: str
    initial_ms: float
    linear_increment_ms: float = 0.0
    multiplier: float = 1.0
    exponential_base: float = 2.0
    max_ms: Optional[float] = None
    _current_ms: float = field(init=False)

    def __post_init__(self) -> None:
        if self.initial_ms < 0:
            raise DelayConfigurationError("initial_ms must be non-negative")
        self._current_ms = self.initial_ms

    def override(self, *, initial_ms: Optional[float] = None, strategy: Optional[str] = None,
                 linear_increment_ms: Optional[float] = None, multiplier: Optional[float] = None,
                 exponential_base: Optional[float] = None, max_ms: Optional[float] = None) -> "DelayStrategy":
        params = {
            "strategy": strategy or self.strategy,
            "initial_ms": self.initial_ms if initial_ms is None else initial_ms,
            "linear_increment_ms": self.linear_increment_ms if linear_increment_ms is None else linear_increment_ms,
            "multiplier": self.multiplier if multiplier is None else multiplier,
            "exponential_base": self.exponential_base if exponential_base is None else exponential_base,
            "max_ms": self.max_ms if max_ms is None else max_ms,
        }
        return DelayStrategy(**params)

    def next_delay(self) -> float:
        delay_ms = self._current_ms
        if self.strategy == "fixed":
            pass
        elif self.strategy == "linear":
            self._current_ms += self.linear_increment_ms
        elif self.strategy == "multiplier":
            self._current_ms *= self.multiplier
        elif self.strategy == "exponential":
            self._current_ms = self.exponential_base ** (self._current_ms / 1000.0)
            delay_ms = self._current_ms
        else:
            raise DelayConfigurationError(f"Unsupported delay strategy: {self.strategy}")

        if self.max_ms is not None:
            self._current_ms = min(self._current_ms, self.max_ms)
            delay_ms = min(delay_ms, self.max_ms)

        return max(delay_ms, 0.0) / 1000.0

    def reset(self) -> None:
        self._current_ms = self.initial_ms

"""LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Minimal interface used by analysis and research modules."""

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.2) -> str:
        """Return a model response for chat messages."""

    @abstractmethod
    def structured_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Return parsed JSON from a model response."""

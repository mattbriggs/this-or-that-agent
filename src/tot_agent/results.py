"""
results.py — Structured action results shared by browser and tool layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ActionResult:
    """Serializable result for browser actions and tool dispatch."""

    ok: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    recoverable: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert the result to a plain dict for API/tool transport."""
        payload: dict[str, Any] = {
            "ok": self.ok,
            "message": self.message,
        }
        if self.data:
            payload["data"] = self.data
        if self.error:
            payload["error"] = self.error
        if self.recoverable:
            payload["recoverable"] = True
        return payload


def success_result(message: str, **data: Any) -> dict[str, Any]:
    """Build a successful structured result."""
    return ActionResult(ok=True, message=message, data=data).to_dict()


def failure_result(
    message: str,
    *,
    error: str | None = None,
    recoverable: bool = False,
    **data: Any,
) -> dict[str, Any]:
    """Build a failed structured result."""
    return ActionResult(
        ok=False,
        message=message,
        data=data,
        error=error,
        recoverable=recoverable,
    ).to_dict()


def is_failure_result(result: Any) -> bool:
    """Return True when *result* is a structured failure payload."""
    return isinstance(result, dict) and result.get("ok") is False

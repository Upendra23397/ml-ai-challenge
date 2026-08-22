"""Versioned in-memory context store."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
import uuid


VALID_SCOPES = {"category", "merchant", "customer", "trigger"}


class ContextStore:
  def __init__(self) -> None:
    self._data: dict[tuple[str, str], dict[str, Any]] = {}

  def put(self, scope: str, context_id: str, version: int, payload: dict) -> dict:
    if scope not in VALID_SCOPES:
      return {"accepted": False, "reason": "invalid_scope", "details": f"Unknown scope: {scope}"}

    key = (scope, context_id)
    current = self._data.get(key)
    if current and current["version"] > version:
      return {"accepted": False, "reason": "stale_version", "current_version": current["version"]}
    if current and current["version"] == version:
      return {
        "accepted": True,
        "ack_id": f"ack_{context_id}_v{version}",
        "stored_at": current["stored_at"],
      }

    stored_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    self._data[key] = {"version": version, "payload": payload, "stored_at": stored_at}
    return {
      "accepted": True,
      "ack_id": f"ack_{context_id}_v{version}",
      "stored_at": stored_at,
    }

  def get(self, scope: str, context_id: str) -> Optional[dict]:
    entry = self._data.get((scope, context_id))
    return entry["payload"] if entry else None

  def get_version(self, scope: str, context_id: str) -> Optional[int]:
    entry = self._data.get((scope, context_id))
    return entry["version"] if entry else None

  def counts(self) -> dict[str, int]:
    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    for (scope, _), _ in self._data.items():
      if scope in counts:
        counts[scope] += 1
    return counts

  def clear(self) -> None:
    self._data.clear()

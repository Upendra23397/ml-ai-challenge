"""Per-conversation state: turns, auto-reply detection, 24h session window."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ConversationState:
  conversation_id: str
  merchant_id: Optional[str] = None
  customer_id: Optional[str] = None
  trigger_id: Optional[str] = None
  turns: list[dict] = field(default_factory=list)
  sent_bodies: list[str] = field(default_factory=list)
  merchant_replies: list[str] = field(default_factory=list)
  unanswered_nudges: int = 0
  auto_reply_redirect_attempted: bool = False
  last_merchant_reply_at: Optional[str] = None
  session_open: bool = False
  ended: bool = False
  pending_action: Optional[str] = None

  def record_bot_send(self, body: str, received_at: str | None = None) -> None:
    self.sent_bodies.append(body)
    self.turns.append({"from": "vera", "body": body, "ts": received_at})
    self.unanswered_nudges += 1

  def record_merchant_reply(self, message: str, received_at: str) -> None:
    self.merchant_replies.append(message)
    self.turns.append({"from": "merchant", "body": message, "ts": received_at})
    self.last_merchant_reply_at = received_at
    self.session_open = True
    self.unanswered_nudges = 0

  def is_auto_reply_pattern(self) -> bool:
    if len(self.merchant_replies) < 3:
      return False
    last_three = self.merchant_replies[-3:]
    return len(set(last_three)) == 1

  def has_repeat_body(self, body: str) -> bool:
    normalized = body.strip().lower()
    return any(s.strip().lower() == normalized for s in self.sent_bodies)


class ConversationManager:
  def __init__(self) -> None:
    self._conversations: dict[str, ConversationState] = {}

  def get_or_create(
    self,
    conversation_id: str,
    merchant_id: str | None = None,
    customer_id: str | None = None,
    trigger_id: str | None = None,
  ) -> ConversationState:
    if conversation_id not in self._conversations:
      self._conversations[conversation_id] = ConversationState(
        conversation_id=conversation_id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        trigger_id=trigger_id,
      )
    return self._conversations[conversation_id]

  def clear(self) -> None:
    self._conversations.clear()

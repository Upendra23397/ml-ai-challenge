"""Multi-turn reply composer."""

from __future__ import annotations

import re
from typing import Any, Optional

from bot.composer import compose
from bot.conversation_state import ConversationState


AFFIRMATIVE_PATTERNS = [
  r"\b(yes|yeah|yep|ok|okay|sure|go ahead|let'?s do it|lets do it|sounds good)\b",
  r"\b(kar do|kar doon|bhej do|theek hai|chalo|haan|ha|ji)\b",
  r"\b(i want to join|sign me up|proceed|confirm)\b",
]

DECLINE_PATTERNS = [
  r"\b(no thanks|not interested|stop|unsubscribe|leave me|don'?t message)\b",
  r"\b(mat bhejo|band karo|nahi chahiye)\b",
  r"\b(spam|useless|stop messaging)\b",
]

HOSTILE_PATTERNS = [
  r"\b(stupid|idiot|useless|spam|hate|shut up|fuck|damn)\b",
  r"\b(bakwas|bekar|chup)\b",
]

OFF_TOPIC_PATTERNS = [
  r"\b(gst|tax|accounting|legal advice|court)\b",
  r"\b(weather forecast|cricket score|movie)\b",
]

AUTO_REPLY_PATTERNS = [
  r"thank you for contacting",
  r"our team will respond",
  r"automated assistant",
  r"bahut shukriya.*team tak",
]


def respond(
  state: ConversationState,
  merchant_message: str,
  category: Optional[dict] = None,
  merchant: Optional[dict] = None,
  trigger: Optional[dict] = None,
  customer: Optional[dict] = None,
) -> dict:
  """Given conversation state + merchant message, produce next action."""
  msg_lower = merchant_message.strip().lower()

  if state.ended:
    return {"action": "end", "rationale": "Conversation already ended."}

  if _matches_any(msg_lower, DECLINE_PATTERNS) or _matches_any(msg_lower, HOSTILE_PATTERNS):
    return {
      "action": "end",
      "rationale": "Merchant declined or was hostile — graceful exit.",
    }

  if _is_auto_reply(merchant_message):
    if state.is_auto_reply_pattern():
      if state.auto_reply_redirect_attempted:
        return {
          "action": "end",
          "rationale": "Auto-reply detected 3+ times; exiting after one redirect attempt.",
        }
      state.auto_reply_redirect_attempted = True
      return {
        "action": "send",
        "body": (
          "Samajh gayi — looks like an auto-reply. Kya aap khud 2 min mein dekhna chahenge "
          "ki exactly kya pending hai? Chalega, ya main owner se connect karun?"
        ),
        "cta": "open_ended",
        "rationale": "One redirect attempt after detecting auto-reply pattern.",
      }

  if _matches_any(msg_lower, OFF_TOPIC_PATTERNS):
    return {
      "action": "send",
      "body": (
        "That's outside what I can help with — I focus on your Google profile, campaigns, "
        "and customer outreach. Want me to pick up where we left off on your listing?"
      ),
      "cta": "open_ended",
      "rationale": "Polite redirect for off-topic request without fabricating help.",
    }

  if _matches_any(msg_lower, AFFIRMATIVE_PATTERNS):
    return _action_mode_response(state, merchant, category)

  if "time" in msg_lower or "later" in msg_lower or "busy" in msg_lower:
    return {
      "action": "wait",
      "wait_seconds": 1800,
      "rationale": "Merchant asked for time; backing off 30 minutes.",
    }

  if state.unanswered_nudges >= 3:
    return {
      "action": "end",
      "rationale": "Three unanswered nudges — graceful exit.",
    }

  if category and merchant and trigger:
    composed = compose(category, merchant, trigger, customer, state.sent_bodies)
    body = composed["body"]
    if state.has_repeat_body(body):
      body = _vary_body(body, merchant_message)
    return {
      "action": "send",
      "body": body,
      "cta": composed.get("cta", "open_ended"),
      "rationale": composed.get("rationale", "Follow-up composed from context."),
    }

  return {
    "action": "send",
    "body": "Got it. I've noted that — anything specific you'd like me to action on your profile or campaigns?",
    "cta": "open_ended",
    "rationale": "Generic acknowledgment when full context unavailable.",
  }


def _action_mode_response(state: ConversationState, merchant: Optional[dict], category: Optional[dict]) -> dict:
  name = ""
  if merchant:
    name = merchant.get("identity", {}).get("owner_first_name", "")
  sal = f"{name}, " if name else ""
  pending = state.pending_action or "your request"

  return {
    "action": "send",
    "body": (
      f"{sal}done — proceeding with {pending}. "
      f"I'll send a draft in the next message for your review. Confirm when ready?"
    ),
    "cta": "open_ended",
    "rationale": "Intent transition — merchant committed; switching to action mode immediately.",
  }


def _is_auto_reply(message: str) -> bool:
  msg_lower = message.lower()
  return any(re.search(p, msg_lower) for p in AUTO_REPLY_PATTERNS)


def _matches_any(text: str, patterns: list[str]) -> bool:
  return any(re.search(p, text) for p in patterns)


def _vary_body(body: str, merchant_message: str) -> str:
  if body.endswith("?"):
    return body[:-1] + f" (re: your note: \"{merchant_message[:40]}...\")?"
  return body + f" Also noted: \"{merchant_message[:50]}\"."

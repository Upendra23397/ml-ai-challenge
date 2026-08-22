"""Post-composition validation checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


MAX_BODY_LENGTH = 2000

CTA_PATTERNS = [
  r"\breply\s+yes\b",
  r"\breply\s+stop\b",
  r"\breply\s+1\b",
  r"\breply\s+2\b",
  r"\bsay\s+go\b",
  r"\bsay\s+yes\b",
  r"\bchalega\?",
  r"\bwant me to\b",
  r"\bshall i\b",
  r"\bshould i\b",
  r"\bready\?",
  r"\btell us\b",
]

HINDI_MARKERS = re.compile(
  r"\b(aap|aapke|apke|kya|hai|hain|maine|kar|sakti|sakte|chahiye|liye|ke|ki|ka|mein|se|ya|nahi|batao|dekho|bataiye)\b",
  re.I,
)
DEVANAGARI = re.compile(r"[\u0900-\u097F]")


@dataclass
class ValidationResult:
  valid: bool
  errors: list[str] = field(default_factory=list)


def validate_message(
  body: str,
  cta: str,
  category: dict,
  merchant: dict,
  customer: Optional[dict] = None,
  sent_bodies: Optional[list[str]] = None,
  allow_booking_cta: bool = False,
) -> ValidationResult:
  errors: list[str] = []

  if not body or not body.strip():
    errors.append("empty_body")

  if len(body) > MAX_BODY_LENGTH:
    errors.append("body_too_long")

  taboos = _get_taboos(category)
  body_lower = body.lower()
  for taboo in taboos:
    if taboo.lower() in body_lower:
      errors.append(f"taboo_word:{taboo}")

  if sent_bodies and any(b.strip().lower() == body.strip().lower() for b in sent_bodies):
    errors.append("duplicate_body")

  cta_count = _count_cta_markers(body)
  if not allow_booking_cta and cta_count > 1:
    errors.append("multiple_ctas")
  if cta == "none" and cta_count > 0 and not allow_booking_cta:
    errors.append("cta_mismatch_none")

  if not _language_ok(body, merchant, customer):
    errors.append("language_mismatch")

  return ValidationResult(valid=len(errors) == 0, errors=errors)


def _get_taboos(category: dict) -> list[str]:
  voice = category.get("voice", {})
  taboos = list(voice.get("taboos", []))
  taboos.extend(voice.get("vocab_taboo", []))
  return [t for t in taboos if t]


def _count_cta_markers(body: str) -> int:
  body_lower = body.lower()
  count = 0
  for pattern in CTA_PATTERNS:
    if re.search(pattern, body_lower):
      count += 1
  return count


def _language_ok(body: str, merchant: dict, customer: Optional[dict] = None) -> bool:
  langs = merchant.get("identity", {}).get("languages", ["en"])
  lang_pref = None
  if customer:
    lang_pref = customer.get("identity", {}).get("language_pref", "")

  wants_hi = "hi" in langs or (lang_pref and "hi" in lang_pref.lower())
  if not wants_hi:
    return True

  has_devanagari = bool(DEVANAGARI.search(body))
  has_hi_roman = bool(HINDI_MARKERS.search(body))
  return has_devanagari or has_hi_roman or len(body) < 80

"""Message composer — LLM with deterministic template fallback."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from bot.llm_client import LLMClient
from bot.prompts.trigger_variants import get_framing
from bot.validator import validate_message

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.md"
_llm = LLMClient()


def compose(
  category: dict,
  merchant: dict,
  trigger: dict,
  customer: dict | None = None,
  sent_bodies: list[str] | None = None,
) -> dict:
  """Compose a message from the 4 contexts."""
  allow_booking = trigger.get("kind") in {"recall_due", "appointment_tomorrow", "chronic_refill_due"}

  if _llm.available:
    result = _compose_llm(category, merchant, trigger, customer, sent_bodies, allow_booking)
    if result:
      return result

  return _compose_template(category, merchant, trigger, customer, sent_bodies, allow_booking)


def _compose_llm(
  category: dict,
  merchant: dict,
  trigger: dict,
  customer: dict | None,
  sent_bodies: list[str] | None,
  allow_booking: bool,
) -> dict | None:
  system = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
  framing = get_framing(trigger.get("kind", ""))
  user = (
    f"## Trigger framing\n{framing}\n\n"
    f"## Category context\n{json.dumps(category, ensure_ascii=False)}\n\n"
    f"## Merchant context\n{json.dumps(merchant, ensure_ascii=False)}\n\n"
    f"## Trigger context\n{json.dumps(trigger, ensure_ascii=False)}\n\n"
    f"## Customer context\n{json.dumps(customer, ensure_ascii=False) if customer else 'null'}\n\n"
    "Return ONLY the JSON object with keys: body, cta, send_as, suppression_key, rationale."
  )

  for attempt in range(2):
    try:
      extra = ""
      if attempt == 1:
        extra = "\n\nPrevious attempt failed validation. Fix: single CTA, no taboo words, match language, use only context facts."
      raw = _llm.generate(system, user + extra, temperature=0.0)
      parsed = _parse_json_response(raw)
      if not parsed:
        continue
      parsed["suppression_key"] = trigger.get("suppression_key", parsed.get("suppression_key", ""))
      if trigger.get("scope") == "customer" or customer:
        parsed["send_as"] = "merchant_on_behalf"
      else:
        parsed.setdefault("send_as", "vera")

      vr = validate_message(
        parsed["body"], parsed.get("cta", "open_ended"),
        category, merchant, customer, sent_bodies, allow_booking,
      )
      if vr.valid:
        return parsed
    except Exception:
      continue
  return None


def _compose_template(
  category: dict,
  merchant: dict,
  trigger: dict,
  customer: dict | None,
  sent_bodies: list[str] | None,
  allow_booking: bool,
) -> dict:
  kind = trigger.get("kind", "generic")
  handler = _TEMPLATE_HANDLERS.get(kind, _template_generic)
  result = handler(category, merchant, trigger, customer)
  result["suppression_key"] = trigger.get("suppression_key", "")

  vr = validate_message(
    result["body"], result.get("cta", "open_ended"),
    category, merchant, customer, sent_bodies, allow_booking,
  )
  if not vr.valid and sent_bodies is not None:
    result = _template_safe_fallback(category, merchant, trigger, customer)

  return result


def _parse_json_response(raw: str) -> dict | None:
  match = re.search(r"\{[\s\S]*\}", raw)
  if not match:
    return None
  try:
    data = json.loads(match.group())
    if "body" in data:
      return data
  except json.JSONDecodeError:
    pass
  return None


# --- Context helpers ---

def _owner(merchant: dict) -> str:
  identity = merchant.get("identity", {})
  if identity.get("owner_first_name"):
    return identity["owner_first_name"]
  name = identity.get("name", "")
  if name.startswith("Dr."):
    return name.replace("Dr.", "").strip().split()[0]
  return name.split()[0] if name else "there"


def _salutation(merchant: dict, category: dict) -> str:
  owner = _owner(merchant)
  if category.get("slug") == "dentists":
    return f"Dr. {owner}"
  return owner


def _wants_hi(merchant: dict, customer: dict | None = None) -> bool:
  if customer:
    pref = customer.get("identity", {}).get("language_pref", "")
    if pref and "hi" in pref.lower():
      return True
  langs = merchant.get("identity", {}).get("languages", [])
  return "hi" in langs


def _active_offer(merchant: dict, category: dict) -> str:
  for offer in merchant.get("offers", []):
    if offer.get("status") == "active":
      return offer["title"]
  catalog = category.get("offer_catalog", [])
  return catalog[0]["title"] if catalog else "our service"


def _digest_item(category: dict, item_id: str | None) -> dict | None:
  if not item_id:
    return category.get("digest", [{}])[0] if category.get("digest") else None
  for item in category.get("digest", []):
    if item.get("id") == item_id:
      return item
  return category.get("digest", [{}])[0] if category.get("digest") else None


def _months_since(date_str: str, reference: str = "2026-04-26") -> int:
  try:
    last = datetime.fromisoformat(date_str.replace("Z", "+00:00")[:10])
    ref = datetime.fromisoformat(reference[:10])
    months = (ref.year - last.year) * 12 + ref.month - last.month
    return max(1, abs(months))
  except Exception:
    return 5


# --- Template handlers ---

def _template_research_digest(category, merchant, trigger, customer) -> dict:
  item = _digest_item(category, trigger.get("payload", {}).get("top_item_id"))
  sal = _salutation(merchant, category)
  hi = _wants_hi(merchant, customer)
  if item:
    trial = item.get("trial_n", "")
    trial_str = f"{trial:,}-patient trial" if trial else "recent trial"
    segment = item.get("patient_segment", "your patients").replace("_", " ")
    source = item.get("source", "this week's digest")
    body = (
      f"{sal}, {source} — one item for your {segment} cohort: "
      f"{trial_str} on {item.get('title', '')}. Worth a 2-min look. "
    )
    if hi:
      body += "Kya main abstract pull karun + patient-ed WhatsApp draft kar doon?"
    else:
      body += "Want me to pull the abstract + draft a patient-ed WhatsApp you can share?"
  else:
    body = f"{sal}, new research in your category this week — relevant to your practice. Want me to summarize the top item?"
  return {
    "body": body,
    "cta": "open_ended",
    "send_as": "vera",
    "rationale": "Research digest with source-cited clinical anchor personalized to merchant cohort.",
  }


def _template_recall_due(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  cust_name = customer.get("identity", {}).get("name", "there") if customer else "there"
  merchant_name = merchant.get("identity", {}).get("name", "our clinic")
  last_visit = payload.get("last_service_date") or (
    customer.get("relationship", {}).get("last_visit", "") if customer else ""
  )
  months = _months_since(last_visit) if last_visit else 5
  if months < 3 and customer and customer.get("state") in ("lapsed_soft", "lapsed_hard"):
    months = 5
  offer = _active_offer(merchant, category)
  slots = payload.get("available_slots", [])
  slot_text = ""
  if len(slots) >= 2:
    slot_text = f"Apke liye 2 slots ready hain: {slots[0].get('label', '')} ya {slots[1].get('label', '')}."
  elif slots:
    slot_text = f"Slot available: {slots[0].get('label', '')}."
  service = payload.get("service_due", "cleaning recall").replace("_", " ")
  body = (
    f"Hi {cust_name}, {merchant_name} here. "
    f"It's been {months} months since your last visit — your {service} is due. "
    f"{slot_text} {offer}. "
    f"Reply 1 for first slot, 2 for second, or tell us a time that works."
  )
  return {
    "body": body.strip(),
    "cta": "open_ended",
    "send_as": "merchant_on_behalf",
    "rationale": "Recall due with specific slots, catalog price, and language mix for customer.",
  }


def _template_perf_dip(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  metric = payload.get("metric", "calls")
  delta = payload.get("delta_pct", 0)
  pct = max(1, abs(int(delta * 100))) if delta else 10
  perf = merchant.get("performance", {})
  val = perf.get(metric, perf.get("calls", "?"))
  sal = _salutation(merchant, category)
  peer = category.get("peer_stats", {})
  peer_ctr = peer.get("avg_ctr", 0.03)
  body = (
    f"{sal}, your {metric} dropped {pct}% this week ({val} vs baseline {payload.get('vs_baseline', '?')}). "
    f"Peer median CTR in {merchant.get('identity', {}).get('locality', 'your area')} is {peer_ctr:.1%}. "
    f"Maine ek quick diagnostic draft kiya — kya aap bata sakte hain is week kya change hua? Reply YES to see it."
  )
  return {
    "body": body,
    "cta": "binary_yes_stop",
    "send_as": "vera",
    "rationale": "Perf dip with exact metric delta and peer comparison; asks merchant what changed.",
  }


def _template_perf_spike(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  metric = payload.get("metric", "views")
  delta = payload.get("delta_pct", 0)
  pct = max(1, abs(int(delta * 100))) if delta else 15
  val = merchant.get("performance", {}).get(metric, "?")
  sal = _salutation(merchant, category)
  offer = _active_offer(merchant, category)
  body = (
    f"{sal}, {metric} spiked +{pct}% yesterday ({val} total) — best day in 30 days. "
    f"3 merchants in {merchant.get('identity', {}).get('locality', 'your area')} capitalized with a {offer} post. "
    f"Want me to draft one for you? Just say go."
  )
  return {
    "body": body,
    "cta": "open_ended",
    "send_as": "vera",
    "rationale": "Celebrates spike with exact numbers and social proof; low-friction next step.",
  }


def _template_competitor_opened(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  if payload.get("placeholder"):
    sal = _salutation(merchant, category)
    locality = merchant.get("identity", {}).get("locality", "your area")
    views = merchant.get("performance", {}).get("views", "?")
    offer = _active_offer(merchant, category)
    body = (
      f"{sal}, a new {category.get('slug', 'business')} listing appeared near {locality} recently. "
      f"Your profile still holds {views} views/30d. 2 peers refreshed their {offer} post this month. "
      f"Want me to pull what's working for them? Reply YES."
    )
    return {
      "body": body,
      "cta": "binary_yes_stop",
      "send_as": "vera",
      "rationale": "Competitor signal with locality and peer comparison; no fabricated competitor name.",
    }
  name = payload.get("competitor_name", payload.get("name", "A new business"))
  distance = payload.get("distance_km", payload.get("distance", "?"))
  sal = _salutation(merchant, category)
  offer = _active_offer(merchant, category)
  body = (
    f"{sal}, heads up — {name} opened {distance}km away on Google last week. "
    f"Your {merchant.get('performance', {}).get('views', '?')} views/30d still hold, but 2 peers in "
    f"{merchant.get('identity', {}).get('locality', 'your area')} refreshed their {offer} listing. "
    f"Curious what they're leading with? Reply YES and I'll pull their top offer."
  )
  return {
    "body": body,
    "cta": "binary_yes_stop",
    "send_as": "vera",
    "rationale": "Competitor alert with distance from payload; curiosity CTA without alarmism.",
  }


def _template_festival(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  if payload.get("placeholder") or not payload.get("festival"):
    seasonal = category.get("seasonal_beats", [{}])
    note = seasonal[0].get("note", "seasonal peak") if seasonal else "seasonal peak"
    month_range = seasonal[0].get("month_range", seasonal[0].get("month", "")) if seasonal else ""
    sal = _salutation(merchant, category)
    offer = _active_offer(merchant, category)
    hi = _wants_hi(merchant, customer)
    if hi:
      body = (
        f"{sal}, {month_range} mein {note} — aapke area mein 4 merchants ne {offer} post kiya. "
        f"Aap kya plan kar rahe hain?"
      )
    else:
      body = (
        f"{sal}, {month_range}: {note}. 4 merchants in {merchant.get('identity', {}).get('locality', 'your area')} "
        f"posted {offer} — 2.3x avg engagement. What are you planning?"
      )
    return {
      "body": body,
      "cta": "open_ended",
      "send_as": "vera",
      "rationale": "Seasonal beat from category context with specific offer and social proof.",
    }
  festival = payload.get("festival", "the festival")
  days = payload.get("days_until", "?")
  sal = _salutation(merchant, category)
  offer = _active_offer(merchant, category)
  hi = _wants_hi(merchant, customer)
  if hi:
    body = (
      f"{sal}, {festival} {days} din mein hai. Aapke area mein 4 merchants ne {offer} post kiya — "
      f"engagement 2.3x average. Aap kya plan kar rahe hain is festival ke liye?"
    )
  else:
    body = (
      f"{sal}, {festival} is {days} days out. 4 merchants in {merchant.get('identity', {}).get('locality', 'your area')} "
      f"posted {offer} — 2.3x avg engagement. What are you planning for {festival}?"
    )
  return {
    "body": body,
    "cta": "open_ended",
    "send_as": "vera",
    "rationale": "Festival hook with days_until, specific offer, and social proof.",
  }


def _template_curious_ask(category, merchant, trigger, customer) -> dict:
  sal = _salutation(merchant, category)
  locality = merchant.get("identity", {}).get("locality", "your area")
  slug = category.get("slug", "business")
  service_map = {
    "dentists": "most-booked treatment",
    "salons": "most-requested service",
    "restaurants": "best-selling dish",
    "gyms": "most popular class",
    "pharmacies": "most-asked OTC item",
  }
  ask = service_map.get(slug, "top service")
  body = (
    f"{sal}, quick one — 3 {slug} in {locality} told me their {ask} shifted this week. "
    f"What's yours been? Helps me tailor your next post."
  )
  return {
    "body": body,
    "cta": "open_ended",
    "send_as": "vera",
    "rationale": "Curious ask with social proof; asks merchant a direct question.",
  }


def _template_dormant(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  days = payload.get("days_since_last_contact", payload.get("days_dormant", 14))
  sal = _salutation(merchant, category)
  views = merchant.get("performance", {}).get("views", "?")
  signals = merchant.get("signals", [])
  signal = signals[0] if signals else "profile activity"
  body = (
    f"{sal}, {days} din se baat nahi hui — your listing still got {views} views though. "
    f"Signal flagged: {signal}. Ek specific fix ready hai — 2 min. Chalega?"
  )
  return {
    "body": body,
    "cta": "open_ended",
    "send_as": "vera",
    "rationale": "Re-engagement after dormancy with specific performance data, not generic check-in.",
  }


def _template_milestone(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  sal = _salutation(merchant, category)
  if payload.get("placeholder"):
    views = merchant.get("performance", {}).get("views", "?")
    calls = merchant.get("performance", {}).get("calls", "?")
    body = (
      f"{sal}, your profile hit {views} views and {calls} calls this month — "
      f"top 20% in {merchant.get('identity', {}).get('locality', 'your area')}. "
      f"Want me to draft a milestone post to keep the momentum?"
    )
    return {
      "body": body,
      "cta": "open_ended",
      "send_as": "vera",
      "rationale": "Milestone from merchant performance data when trigger payload is sparse.",
    }
  milestone = payload.get("milestone", payload.get("metric", "reviews"))
  count = payload.get("count", payload.get("value_now", payload.get("milestone_value", payload.get("value", "?"))))
  sal = _salutation(merchant, category)
  imminent = payload.get("is_imminent", False)
  target = payload.get("milestone_value", count)
  if imminent and count != "?":
    body = (
      f"{sal}, you're at {count} {milestone.replace('_', ' ')} — just {int(target) - int(count) if str(target).isdigit() and str(count).isdigit() else 'a few'} "
      f"away from {target}. Top 15% in {merchant.get('identity', {}).get('locality', 'your area')}. "
      f"Want me to draft a thank-you post for when you hit it?"
    )
  else:
    body = (
      f"{sal}, you just crossed {count} {milestone.replace('_', ' ')} — top 15% in "
      f"{merchant.get('identity', {}).get('locality', 'your area')}. "
      f"2 peers posted a thank-you note and saw 18% more profile visits. Want me to draft one?"
    )
  return {
    "body": body,
    "cta": "open_ended",
    "send_as": "vera",
    "rationale": "Milestone celebration with exact count and social proof next step.",
  }


def _template_review_theme(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  theme = payload.get("theme", "an issue").replace("_", " ")
  count = payload.get("occurrences_30d", "?")
  quote = payload.get("common_quote", "")
  sal = _salutation(merchant, category)
  quote_part = f' — e.g. "{quote}"' if quote else ""
  body = (
    f"{sal}, {count} reviews this month mention '{theme}'"
    f"{quote_part}. "
    f"I've drafted a 2-line response template. Reply YES to see it."
  )
  return {
    "body": body,
    "cta": "binary_yes_stop",
    "send_as": "vera",
    "rationale": "Review theme with occurrence count and real quote; offers drafted response.",
  }


def _template_renewal(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  days = payload.get("days_remaining", merchant.get("subscription", {}).get("days_remaining", "?"))
  plan = payload.get("plan", merchant.get("subscription", {}).get("plan", "Pro"))
  amount = payload.get("renewal_amount", "")
  sal = _salutation(merchant, category)
  amt_str = f" (₹{amount:,})" if amount else ""
  body = (
    f"{sal}, your {plan} plan expires in {days} days{amt_str}. "
    f"You'll lose campaign drafts and performance alerts. Reply YES to renew, STOP to opt out."
  )
  return {
    "body": body,
    "cta": "binary_yes_stop",
    "send_as": "vera",
    "rationale": "Renewal reminder with days remaining and loss aversion framing.",
  }


def _template_regulation(category, merchant, trigger, customer) -> dict:
  item = _digest_item(category, trigger.get("payload", {}).get("top_item_id"))
  deadline = trigger.get("payload", {}).get("deadline_iso", trigger.get("expires_at", ""))
  sal = _salutation(merchant, category)
  title = item.get("title", "regulation update") if item else "regulation update"
  source = item.get("source", "") if item else ""
  body = (
    f"{sal}, compliance heads-up: {title}"
    f"{f' — {source}' if source else ''}. Effective {deadline[:10] if deadline else 'soon'}. "
    f"I've got a 5-point checklist ready. Reply YES to get it."
  )
  return {
    "body": body,
    "cta": "binary_yes_stop",
    "send_as": "vera",
    "rationale": "Regulation change with source citation and deadline; binary CTA for checklist.",
  }


def _template_chronic_refill(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  cust_name = customer.get("identity", {}).get("name", "there") if customer else "there"
  molecules = payload.get("molecule_list", [])
  if molecules:
    med = " + ".join(molecules[:3])
  elif payload.get("placeholder") and customer:
    services = customer.get("relationship", {}).get("services_received", [])
    med = services[-1] if services else "prescription"
  else:
    med = payload.get("medication", payload.get("item", "prescription"))
  due = payload.get("stock_runs_out_iso", payload.get("due_date", payload.get("refill_due", "")))
  merchant_name = merchant.get("identity", {}).get("name", "your pharmacy")
  body = (
    f"Hi {cust_name}, {merchant_name} here. Your {med} refill is due"
    f"{f' by {due[:10]}' if due else ''}. "
    f"Reply YES to reserve for pickup today, or tell us when works."
  )
  return {
    "body": body,
    "cta": "open_ended",
    "send_as": "merchant_on_behalf",
    "rationale": "Chronic refill reminder with specific medication from payload.",
  }


def _template_customer_lapsed(category, merchant, trigger, customer) -> dict:
  cust_name = customer.get("identity", {}).get("name", "there") if customer else "there"
  visits = customer.get("relationship", {}).get("visits_total", "?") if customer else "?"
  offer = _active_offer(merchant, category)
  merchant_name = merchant.get("identity", {}).get("name", "us")
  body = (
    f"Hi {cust_name}, {merchant_name} here. It's been a while since visit #{visits} — "
    f"we'd love to see you back. {offer} available this week. Reply YES if interested."
  )
  return {
    "body": body,
    "cta": "binary_yes_stop",
    "send_as": "merchant_on_behalf",
    "rationale": "Win-back for lapsed customer with visit history and specific offer.",
  }


def _template_appointment_tomorrow(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  cust_name = customer.get("identity", {}).get("name", "there") if customer else "there"
  if payload.get("placeholder"):
    pref = customer.get("preferences", {}).get("preferred_slots", "") if customer else ""
    service = category.get("offer_catalog", [{}])[0].get("title", "appointment") if category.get("offer_catalog") else "appointment"
    pref_label = pref.replace("_", " ") if pref else ""
    time_label = f"tomorrow ({pref_label})" if pref_label else "tomorrow"
  else:
    time_label = payload.get("time_label", payload.get("appointment_time", "tomorrow"))
    service = payload.get("service", "appointment")
  merchant_name = merchant.get("identity", {}).get("name", "our clinic")
  body = (
    f"Hi {cust_name}, reminder from {merchant_name} — your {service} is {time_label}. "
    f"Reply YES to confirm or tell us if you need to reschedule."
  )
  return {
    "body": body,
    "cta": "open_ended",
    "send_as": "merchant_on_behalf",
    "rationale": "Appointment reminder with specific time from trigger payload.",
  }


def _template_ipl(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  match = payload.get("match", "today's match")
  time = payload.get("match_time_iso", "")
  sal = _salutation(merchant, category)
  offer = _active_offer(merchant, category)
  body = (
    f"{sal}, {match} tonight"
    f"{f' at {time[11:16]}' if len(time) > 16 else ''}. "
    f"Last IPL match-day you got 40% more orders with a {offer} post. Want me to draft one? Say go."
  )
  return {
    "body": body,
    "cta": "open_ended",
    "send_as": "vera",
    "rationale": "Timely IPL hook with match details and historical performance angle.",
  }


def _template_gbp_unverified(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  missing = payload.get("missing_items", payload.get("issues", ["verification"]))
  sal = _salutation(merchant, category)
  items = ", ".join(missing) if isinstance(missing, list) else str(missing)
  body = (
    f"{sal}, your Google profile is unverified — {items} blocked. "
    f"Merchants who verify see 35% more direction requests. Reply YES and I'll walk you through it."
  )
  return {
    "body": body,
    "cta": "binary_yes_stop",
    "send_as": "vera",
    "rationale": "GBP verification issue with specific missing items and loss aversion.",
  }


def _template_cde(category, merchant, trigger, customer) -> dict:
  item = _digest_item(category, trigger.get("payload", {}).get("top_item_id"))
  sal = _salutation(merchant, category)
  if item:
    body = (
      f"{sal}, CDE webinar this week: {item.get('title', '')} — {item.get('source', '')}. "
      f"Relevant to your practice. Want me to register you? Reply YES."
    )
  else:
    body = f"{sal}, a CDE opportunity relevant to {category.get('slug', 'your field')} is open. Reply YES for details."
  return {
    "body": body,
    "cta": "binary_yes_stop",
    "send_as": "vera",
    "rationale": "CDE opportunity with source-cited digest item.",
  }


def _template_winback(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  days = payload.get("days_since_expiry", "?")
  lapsed = payload.get("lapsed_customers_added_since_expiry", "?")
  sal = _salutation(merchant, category)
  offer = _active_offer(merchant, category)
  body = (
    f"{sal}, plan expired {days} days ago — {lapsed} customers went quiet since. "
    f"I've drafted a win-back with {offer}. Reply YES to send to your top 20 lapsed."
  )
  return {
    "body": body,
    "cta": "binary_yes_stop",
    "send_as": "vera",
    "rationale": "Win-back eligible with days since expiry and lapsed customer count.",
  }


def _template_planning_intent(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  topic = payload.get("intent_topic", "your idea").replace("_", " ")
  last_msg = payload.get("merchant_last_message", "")
  sal = _salutation(merchant, category)
  offer = _active_offer(merchant, category)
  hi = _wants_hi(merchant, customer)
  if hi:
    body = (
      f"{sal}, aapne {topic} ke baare mein pucha — maine ek draft ready kiya hai with {offer} pricing. "
      f"Bas 'go' bolo aur main finalize kar deti hoon."
    )
  else:
    msg_part = f' — you asked: "{last_msg[:60]}"' if last_msg else ""
    body = (
      f"{sal}, following up on {topic}{msg_part}. "
      f"I've drafted a program outline with {offer} pricing. Just say go and I'll finalize it."
    )
  return {
    "body": body,
    "cta": "open_ended",
    "send_as": "vera",
    "rationale": "Planning intent with effort externalization; references merchant's stated topic.",
  }


def _template_category_seasonal(category, merchant, trigger, customer) -> dict:
  payload = trigger.get("payload", {})
  trends = payload.get("trends", [])
  sal = _salutation(merchant, category)
  locality = merchant.get("identity", {}).get("locality", "your area")
  if trends:
    top = trends[0].replace("_", " ")
    body = (
      f"{sal}, summer demand shift in {locality}: {top}. "
      f"{len(trends)} category trends flagged this week. "
      f"Want me to draft a shelf/display update for your top mover? Reply YES."
    )
  else:
    seasonal = category.get("seasonal_beats", [{}])
    note = seasonal[0].get("note", "seasonal shift") if seasonal else "seasonal shift"
    body = (
      f"{sal}, seasonal signal for {locality}: {note}. "
      f"Want me to suggest a listing update? Reply YES."
    )
  return {
    "body": body,
    "cta": "binary_yes_stop",
    "send_as": "vera",
    "rationale": "Category seasonal trend with specific demand data from trigger payload.",
  }


def _template_generic(category, merchant, trigger, customer) -> dict:
  sal = _salutation(merchant, category)
  kind = trigger.get("kind", "update")
  urgency = trigger.get("urgency", 1)
  views = merchant.get("performance", {}).get("views", "?")
  body = (
    f"{sal}, {kind.replace('_', ' ')} signal (urgency {urgency}/5) — your profile had {views} views/30d. "
    f"One specific action ready. Want me to show it?"
  )
  return {
    "body": body,
    "cta": "open_ended",
    "send_as": "merchant_on_behalf" if customer else "vera",
    "rationale": f"Generic composition for trigger kind {kind} anchored on merchant performance.",
  }


def _template_safe_fallback(category, merchant, trigger, customer) -> dict:
  sal = _salutation(merchant, category)
  return {
    "body": f"{sal}, I have a specific update for your business. Reply YES to see it, or STOP to opt out.",
    "cta": "binary_yes_stop",
    "send_as": "merchant_on_behalf" if customer else "vera",
    "suppression_key": trigger.get("suppression_key", ""),
    "rationale": "Safe minimal fallback after validation failure.",
  }


_TEMPLATE_HANDLERS = {
  "research_digest": _template_research_digest,
  "regulation_change": _template_regulation,
  "recall_due": _template_recall_due,
  "perf_dip": _template_perf_dip,
  "perf_spike": _template_perf_spike,
  "renewal_due": _template_renewal,
  "festival_upcoming": _template_festival,
  "curious_ask_due": _template_curious_ask,
  "winback_eligible": _template_winback,
  "ipl_match_today": _template_ipl,
  "review_theme_emerged": _template_review_theme,
  "milestone_reached": _template_milestone,
  "dormant_with_vera": _template_dormant,
  "competitor_opened": _template_competitor_opened,
  "chronic_refill_due": _template_chronic_refill,
  "customer_lapsed_hard": _template_customer_lapsed,
  "customer_lapsed_soft": _template_customer_lapsed,
  "gbp_unverified": _template_gbp_unverified,
  "cde_opportunity": _template_cde,
  "appointment_tomorrow": _template_appointment_tomorrow,
  "active_planning_intent": _template_planning_intent,
  "seasonal_perf_dip": _template_perf_dip,
  "trial_followup": _template_customer_lapsed,
  "supply_alert": _template_category_seasonal,
  "category_seasonal": _template_category_seasonal,
  "wedding_package_followup": _template_customer_lapsed,
}

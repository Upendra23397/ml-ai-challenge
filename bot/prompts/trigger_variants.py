"""Per-trigger-kind prompt framing variants."""

from __future__ import annotations

TRIGGER_VARIANTS: dict[str, str] = {
  "research_digest": (
    "Frame as a peer sharing a source-cited digest item relevant to this merchant's patient/customer cohort. "
    "Cite the exact source from category.digest. Offer to pull the abstract or draft patient-ed content. "
    "Use clinical vocabulary for dentists. End with a low-friction open CTA."
  ),
  "regulation_change": (
    "Frame as a compliance heads-up with deadline from trigger payload. "
    "Reference the exact regulation item from category.digest. Non-alarmist, actionable. "
    "Binary YES/STOP CTA to get a checklist."
  ),
  "recall_due": (
    "Customer-facing message sent as merchant_on_behalf. Name the customer, reference last visit date "
    "and service due from trigger. Offer specific slots from payload.available_slots. "
    "Use active offer price from merchant.offers. Hi-en mix if customer prefers. "
    "Booking flow: multi-choice slot reply is allowed."
  ),
  "perf_dip": (
    "Diagnostic, non-alarmist framing. Reference exact metric and delta from trigger.payload. "
    "Compare to merchant's actual performance numbers. Suggest one concrete fix. "
    "Ask merchant what changed this week (social proof angle)."
  ),
  "perf_spike": (
    "Celebrate the spike with exact numbers from trigger and merchant performance. "
    "Suggest capitalizing with a specific offer from catalog. Curiosity about what drove it."
  ),
  "renewal_due": (
    "Direct but respectful renewal reminder with days_remaining and plan from payload. "
    "Reference what they'll lose (loss aversion). Binary YES/STOP CTA."
  ),
  "festival_upcoming": (
    "Timely festival hook with exact festival name and days_until. "
    "Suggest a specific service+price offer from catalog, not generic discount. "
    "Ask what they're planning for the festival."
  ),
  "curious_ask_due": (
    "Light conversational ask — use social proof ('3 salons in {locality} told me…'). "
    "Ask the merchant an open question about their business this week. Open-ended CTA."
  ),
  "winback_eligible": (
    "Acknowledge lapse since expiry with exact days. Reference lapsed customers added. "
    "Offer to draft a win-back campaign with specific service+price."
  ),
  "ipl_match_today": (
    "Timely event hook with match details from payload. Suggest a specific offer for match day. "
    "Reference locality. Low-friction CTA to post or activate."
  ),
  "review_theme_emerged": (
    "Surface the review theme with occurrence count and a real quote from payload. "
    "Non-defensive, solution-oriented. Offer to draft a response or fix."
  ),
  "milestone_reached": (
    "Celebrate milestone with exact number from payload. Social proof angle. "
    "Suggest next step to capitalize."
  ),
  "active_planning_intent": (
    "Merchant showed planning intent — offer concrete help with specific numbers from payload. "
    "Effort externalization: 'I've drafted X, just say go'."
  ),
  "seasonal_perf_dip": (
    "Seasonal context from payload + performance dip. Suggest seasonal offer from catalog."
  ),
  "customer_lapsed_hard": (
    "Customer-facing win-back on behalf of merchant. Reference visit history. "
    "Specific offer with price. Personal tone matching language_pref."
  ),
  "trial_followup": (
    "Customer-facing follow-up after trial. Reference trial date and next step from payload."
  ),
  "supply_alert": (
    "Utility-first alert about supply/demand shift. Specific product or category from payload."
  ),
  "chronic_refill_due": (
    "Customer-facing refill reminder. Reference medication/service from payload. "
    "Pharmacy: precise, trustworthy tone. Offer pickup slot if available."
  ),
  "category_seasonal": (
    "Seasonal trend from category.seasonal_beats or trigger payload. "
    "Suggest relevant offer from catalog."
  ),
  "gbp_unverified": (
    "Profile issue with specific missing items from payload. Loss aversion framing. "
    "Offer to fix — binary CTA."
  ),
  "cde_opportunity": (
    "Continuing education opportunity from digest. Cite source. "
    "Relevant to merchant's specialty."
  ),
  "competitor_opened": (
    "New competitor alert with distance/name from payload only. Curiosity framing, not alarmist. "
    "Suggest differentiation with specific offer or strength."
  ),
  "dormant_with_vera": (
    "Re-engagement after dormancy. Reference days since last contact. "
    "Lead with one high-value insight from their data, not a generic check-in."
  ),
  "wedding_package_followup": (
    "Customer-facing bridal follow-up. Reference wedding date and trial completed. "
    "Suggest next step program from payload."
  ),
  "appointment_tomorrow": (
    "Customer-facing appointment reminder for tomorrow. Reference time from payload. "
    "Confirm or reschedule option."
  ),
}


def get_framing(trigger_kind: str) -> str:
  return TRIGGER_VARIANTS.get(
    trigger_kind,
    "Compose a specific, timely message anchored on the trigger payload and merchant state. "
    "Use one compulsion lever. Single CTA in the last sentence.",
  )

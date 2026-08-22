"""Pydantic models mirroring challenge-testing-brief.md §3."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# --- Category context ---

class OfferTemplate(BaseModel):
    id: Optional[str] = None
    title: str
    value: Optional[str] = None
    audience: Optional[str] = None
    type: Optional[str] = None


class VoiceProfile(BaseModel):
    tone: Optional[str] = None
    register: Optional[str] = None
    code_mix: Optional[str] = None
    vocab_allowed: list[str] = Field(default_factory=list)
    vocab_taboo: list[str] = Field(default_factory=list)
    taboos: list[str] = Field(default_factory=list)
    salutation_examples: list[str] = Field(default_factory=list)
    tone_examples: list[str] = Field(default_factory=list)


class PeerStats(BaseModel):
    scope: Optional[str] = None
    avg_rating: Optional[float] = None
    avg_review_count: Optional[int] = None
    avg_reviews: Optional[int] = None
    avg_views_30d: Optional[int] = None
    avg_calls_30d: Optional[int] = None
    avg_directions_30d: Optional[int] = None
    avg_ctr: Optional[float] = None
    avg_photos: Optional[int] = None
    avg_post_freq_days: Optional[int] = None
    retention_6mo_pct: Optional[float] = None


class DigestItem(BaseModel):
    id: str
    kind: Optional[str] = None
    title: str
    source: Optional[str] = None
    trial_n: Optional[int] = None
    patient_segment: Optional[str] = None
    summary: Optional[str] = None
    actionable: Optional[str] = None


class ContentItem(BaseModel):
    id: str
    title: str
    channel: Optional[str] = None
    body: Optional[str] = None


class SeasonalBeat(BaseModel):
    month_range: Optional[str] = None
    month: Optional[str] = None
    note: str


class TrendSignal(BaseModel):
    query: str
    delta_yoy: Optional[float] = None
    segment_age: Optional[str] = None


class CategoryContext(BaseModel):
    slug: str
    display_name: Optional[str] = None
    offer_catalog: list[OfferTemplate] = Field(default_factory=list)
    voice: VoiceProfile = Field(default_factory=VoiceProfile)
    peer_stats: PeerStats = Field(default_factory=PeerStats)
    digest: list[DigestItem] = Field(default_factory=list)
    patient_content_library: list[ContentItem] = Field(default_factory=list)
    seasonal_beats: list[SeasonalBeat] = Field(default_factory=list)
    trend_signals: list[TrendSignal] = Field(default_factory=list)


# --- Merchant context ---

class MerchantIdentity(BaseModel):
    name: str
    city: Optional[str] = None
    locality: Optional[str] = None
    place_id: Optional[str] = None
    verified: Optional[bool] = None
    languages: list[str] = Field(default_factory=lambda: ["en"])
    owner_first_name: Optional[str] = None
    established_year: Optional[int] = None


class Subscription(BaseModel):
    status: Optional[str] = None
    plan: Optional[str] = None
    days_remaining: Optional[int] = None
    renewed_at: Optional[str] = None


class PerformanceDelta(BaseModel):
    views_pct: Optional[float] = None
    calls_pct: Optional[float] = None
    ctr_pct: Optional[float] = None


class PerformanceSnapshot(BaseModel):
    window_days: Optional[int] = None
    views: Optional[int] = None
    calls: Optional[int] = None
    directions: Optional[int] = None
    ctr: Optional[float] = None
    leads: Optional[int] = None
    delta_7d: PerformanceDelta = Field(default_factory=PerformanceDelta)


class MerchantOffer(BaseModel):
    id: str
    title: str
    status: str
    started: Optional[str] = None
    ended: Optional[str] = None


class ConversationTurn(BaseModel):
    ts: Optional[str] = None
    from_: Optional[str] = Field(None, alias="from")
    body: str
    engagement: Optional[str] = None

    model_config = {"populate_by_name": True}


class CustomerAggregate(BaseModel):
    total_unique_ytd: Optional[int] = None
    lapsed_180d_plus: Optional[int] = None
    retention_6mo_pct: Optional[float] = None
    high_risk_adult_count: Optional[int] = None


class ReviewTheme(BaseModel):
    theme: Optional[str] = None
    sentiment: Optional[str] = None
    occurrences_30d: Optional[int] = None
    common_quote: Optional[str] = None


class MerchantContext(BaseModel):
    merchant_id: str
    category_slug: str
    identity: MerchantIdentity
    subscription: Subscription = Field(default_factory=Subscription)
    performance: PerformanceSnapshot = Field(default_factory=PerformanceSnapshot)
    offers: list[MerchantOffer] = Field(default_factory=list)
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    customer_aggregate: CustomerAggregate = Field(default_factory=CustomerAggregate)
    signals: list[str] = Field(default_factory=list)
    review_themes: list[ReviewTheme] = Field(default_factory=list)


# --- Customer context ---

class CustomerIdentity(BaseModel):
    name: str
    phone_redacted: Optional[str] = None
    language_pref: Optional[str] = None


class Relationship(BaseModel):
    first_visit: Optional[str] = None
    last_visit: Optional[str] = None
    visits_total: Optional[int] = None
    services_received: list[str] = Field(default_factory=list)


class Preferences(BaseModel):
    preferred_slots: Optional[str] = None
    preferred_time: Optional[str] = None
    channel: Optional[str] = None


class Consent(BaseModel):
    opted_in_at: Optional[str] = None
    scope: list[str] = Field(default_factory=list)


class CustomerContext(BaseModel):
    customer_id: str
    merchant_id: str
    identity: CustomerIdentity
    relationship: Relationship = Field(default_factory=Relationship)
    state: Literal["new", "active", "lapsed_soft", "lapsed_hard", "churned"] = "active"
    preferences: Preferences = Field(default_factory=Preferences)
    consent: Consent = Field(default_factory=Consent)


# --- Trigger context ---

class TriggerContext(BaseModel):
    id: str
    scope: Literal["merchant", "customer"]
    kind: str
    source: Literal["external", "internal"]
    merchant_id: str
    customer_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    urgency: int = 1
    suppression_key: str = ""
    expires_at: Optional[str] = None


# --- API request/response models ---

class ContextPushRequest(BaseModel):
    scope: Literal["category", "merchant", "customer", "trigger"]
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: str


class ContextPushResponse(BaseModel):
    accepted: bool
    ack_id: Optional[str] = None
    stored_at: Optional[str] = None
    reason: Optional[str] = None
    current_version: Optional[int] = None
    details: Optional[str] = None


class TickRequest(BaseModel):
    now: str
    available_triggers: list[str] = Field(default_factory=list)


class TickAction(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: Literal["vera", "merchant_on_behalf"]
    trigger_id: str
    template_name: str
    template_params: list[str]
    body: str
    cta: Literal["binary_yes_stop", "open_ended", "none"]
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: list[TickAction] = Field(default_factory=list)


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int


class ReplyResponse(BaseModel):
    action: Literal["send", "wait", "end"]
    body: Optional[str] = None
    cta: Optional[Literal["binary_yes_stop", "open_ended", "none"]] = None
    wait_seconds: Optional[int] = None
    rationale: str = ""


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: int
    contexts_loaded: dict[str, int]


class MetadataResponse(BaseModel):
    team_name: str
    team_members: list[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str


class ComposedMessage(BaseModel):
    body: str
    cta: Literal["binary_yes_stop", "open_ended", "none"]
    send_as: Literal["vera", "merchant_on_behalf"]
    suppression_key: str
    rationale: str

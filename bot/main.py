"""FastAPI app — Vera challenge bot endpoints."""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

from bot.composer import compose
from bot.conversation_state import ConversationManager
from bot.models import (
  ContextPushRequest,
  ReplyRequest,
  TickRequest,
)
from bot.reply_composer import respond
from bot.store import ContextStore

app = FastAPI(title="Vera Challenge Bot", version="1.0.0")
START = time.time()

store = ContextStore()
conversations = ConversationManager()

TEAM_METADATA = {
  "team_name": "Vera Builders",
  "team_members": ["Challenge Participant"],
  "model": os.getenv("LLM_MODEL", "gemini-1.5-flash (template fallback)"),
  "approach": "LLM composer with trigger-variant framing, post-LLM validation, and deterministic template fallback",
  "contact_email": "vera-challenge@example.com",
  "version": "1.0.0",
  "submitted_at": "2026-04-26T08:00:00Z",
}


@app.get("/")
async def root():
  return {
    "service": "Vera Challenge Bot",
    "status": "running",
    "docs": "/docs",
    "endpoints": {
      "health": "/v1/healthz",
      "metadata": "/v1/metadata",
      "context": "POST /v1/context",
      "tick": "POST /v1/tick",
      "reply": "POST /v1/reply",
    },
  }


@app.get("/v1/healthz")
async def healthz():
  return {
    "status": "ok",
    "uptime_seconds": int(time.time() - START),
    "contexts_loaded": store.counts(),
  }


@app.get("/v1/metadata")
async def metadata():
  return TEAM_METADATA


@app.post("/v1/context")
async def push_context(body: ContextPushRequest):
  result = store.put(body.scope, body.context_id, body.version, body.payload)
  if not result.get("accepted"):
    status = 409 if result.get("reason") == "stale_version" else 400
    return JSONResponse(status_code=status, content=result)
  return result


@app.post("/v1/tick")
async def tick(body: TickRequest):
  actions = []
  seen_pairs: set[tuple[str, str]] = set()

  for trg_id in body.available_triggers[:20]:
    trg = store.get("trigger", trg_id)
    if not trg:
      continue

    merchant_id = trg.get("merchant_id")
    merchant = store.get("merchant", merchant_id) if merchant_id else None
    if not merchant:
      continue

    category_slug = merchant.get("category_slug")
    category = store.get("category", category_slug) if category_slug else None
    if not category:
      continue

    customer_id = trg.get("customer_id")
    customer = store.get("customer", customer_id) if customer_id else None

    conv_id = f"conv_{merchant_id}_{trg_id}"
    pair = (merchant_id, conv_id)
    if pair in seen_pairs:
      continue
    seen_pairs.add(pair)

    state = conversations.get_or_create(conv_id, merchant_id, customer_id, trg_id)
    composed = compose(category, merchant, trg, customer, state.sent_bodies)

    owner = merchant.get("identity", {}).get("owner_first_name", merchant.get("identity", {}).get("name", ""))
    template_name = f"vera_{trg.get('kind', 'generic')}_v1"
    template_params = [owner, trg.get("kind", ""), composed["body"][:50]]

    state.record_bot_send(composed["body"], body.now)
    state.pending_action = trg.get("kind", "update")

    actions.append({
      "conversation_id": conv_id,
      "merchant_id": merchant_id,
      "customer_id": customer_id,
      "send_as": composed.get("send_as", "vera"),
      "trigger_id": trg_id,
      "template_name": template_name,
      "template_params": template_params,
      "body": composed["body"],
      "cta": composed.get("cta", "open_ended"),
      "suppression_key": composed.get("suppression_key", trg.get("suppression_key", "")),
      "rationale": composed.get("rationale", ""),
    })

  return {"actions": actions}


@app.post("/v1/reply")
async def reply(body: ReplyRequest):
  state = conversations.get_or_create(
    body.conversation_id, body.merchant_id, body.customer_id,
  )
  state.record_merchant_reply(body.message, body.received_at)

  category = None
  merchant = None
  trigger = None
  customer = None

  if body.merchant_id:
    merchant = store.get("merchant", body.merchant_id)
    if merchant:
      category = store.get("category", merchant.get("category_slug", ""))

  if body.customer_id:
    customer = store.get("customer", body.customer_id)

  if state.trigger_id:
    trigger = store.get("trigger", state.trigger_id)

  result = respond(state, body.message, category, merchant, trigger, customer)

  if result["action"] == "send":
    state.record_bot_send(result.get("body", ""), body.received_at)
  elif result["action"] == "end":
    state.ended = True

  return result


@app.post("/v1/teardown")
async def teardown():
  store.clear()
  conversations.clear()
  return {"status": "ok", "message": "All context wiped."}

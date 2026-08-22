Vera Challenge Bot
Approach
Single-prompt LLM composer (Gemini 1.5 Flash) with trigger-kind framing variants, post-LLM validation, and a deterministic template fallback when no API key is set.

Architecture:

compose() takes 4 contexts → returns {body, cta, send_as, suppression_key, rationale}
Trigger variants (prompts/trigger_variants.py) tailor framing per kind (research_digest, recall_due, perf_dip, etc.)
validator.py enforces single CTA, language match, taboo words, anti-repetition
reply_composer.py handles auto-reply detection, intent transition, graceful exit, hostile/off-topic
In-memory ContextStore with versioned idempotent /v1/context pushes
Prompting strategy
System prompt encodes hard constraints verbatim. Per-trigger framing is injected in the user turn alongside serialized JSON contexts. Temperature=0 for determinism. One re-prompt on validation failure, then template fallback.

Tradeoffs
Template fallback over pure LLM: ensures the bot works without API keys and stays under 30s; templates extract real facts from context programmatically
In-memory state: simple and sufficient for the 60-min test window; no Redis dependency
Heuristic language check: Devanagari + common Hindi roman tokens rather than full NLP
What would have helped
Real merchant reply corpus for fine-tuning auto-reply detection
Historical campaign performance per trigger kind (which CTAs convert)
Slot/booking integration schemas for richer customer-facing messages
Run locally
cd magicpin-ai-challenge
pip install -r bot/requirements.txt
uvicorn bot.main:app --host 0.0.0.0 --port 8080
Generate submission
python bot/scripts/generate_submission.py
Docker
docker build -f bot/Dockerfile -t vera-bot .
docker run -p 8080:8080 -e LLM_API_KEY=your_key vera-bot

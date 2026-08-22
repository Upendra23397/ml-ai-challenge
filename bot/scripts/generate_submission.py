"""Generate submission.jsonl from canonical test pairs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHALLENGE_ROOT = ROOT.parent
sys.path.insert(0, str(CHALLENGE_ROOT))

from bot.composer import compose  # noqa: E402


def load_json(path: Path) -> dict:
  return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
  expanded = CHALLENGE_ROOT / "expanded"
  pairs_data = load_json(expanded / "test_pairs.json")
  out_path = ROOT / "submission.jsonl"

  lines = []
  for pair in pairs_data["pairs"]:
    test_id = pair["test_id"]
    merchant = load_json(expanded / "merchants" / f"{pair['merchant_id']}.json")
    trigger = load_json(expanded / "triggers" / f"{pair['trigger_id']}.json")
    category = load_json(expanded / "categories" / f"{merchant['category_slug']}.json")

    customer = None
    if pair.get("customer_id"):
      customer = load_json(expanded / "customers" / f"{pair['customer_id']}.json")

    result = compose(category, merchant, trigger, customer)
    line = {
      "test_id": test_id,
      "body": result["body"],
      "cta": result["cta"],
      "send_as": result["send_as"],
      "suppression_key": result["suppression_key"],
      "rationale": result["rationale"],
    }
    lines.append(line)
    print(f"  {test_id}: {result['body'][:60]}...")

  with out_path.open("w", encoding="utf-8") as f:
    for line in lines:
      f.write(json.dumps(line, ensure_ascii=False) + "\n")

  print(f"\nWrote {len(lines)} lines to {out_path}")


if __name__ == "__main__":
  main()

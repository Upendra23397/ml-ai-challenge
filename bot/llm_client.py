"""Provider-agnostic LLM client."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


TIMEOUT_SECONDS = 18


class LLMClient:
  def __init__(
    self,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
  ) -> None:
    self.provider = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower()
    self.api_key = api_key or os.getenv("LLM_API_KEY", "")
    self.model = model or os.getenv("LLM_MODEL", "")

  @property
  def available(self) -> bool:
    if self.provider == "ollama":
      return True
    return bool(self.api_key)

  def generate(self, system: str, user: str, temperature: float = 0.0) -> str:
    if not self.available:
      raise RuntimeError("LLM API key not configured")

    if self.provider == "openai":
      return self._openai(system, user, temperature)
    if self.provider == "anthropic":
      return self._anthropic(system, user, temperature)
    if self.provider == "gemini":
      return self._gemini(system, user, temperature)
    if self.provider == "deepseek":
      return self._deepseek(system, user, temperature)
    if self.provider == "groq":
      return self._groq(system, user, temperature)
    if self.provider == "ollama":
      return self._ollama(system, user, temperature)
    raise ValueError(f"Unknown LLM provider: {self.provider}")

  def _openai(self, system: str, user: str, temperature: float) -> str:
    model = self.model or "gpt-4o-mini"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature}).encode()
    req = urllib.request.Request(
      "https://api.openai.com/v1/chat/completions",
      data=body,
      headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
    )
    return self._read_json(req)["choices"][0]["message"]["content"]

  def _anthropic(self, system: str, user: str, temperature: float) -> str:
    model = self.model or "claude-3-5-sonnet-20241022"
    body = json.dumps({
      "model": model,
      "max_tokens": 1500,
      "temperature": temperature,
      "system": system,
      "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
      "https://api.anthropic.com/v1/messages",
      data=body,
      headers={
        "x-api-key": self.api_key,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
      },
    )
    return self._read_json(req)["content"][0]["text"]

  def _gemini(self, system: str, user: str, temperature: float) -> str:
    model = self.model or "gemini-1.5-flash"
    full_prompt = f"{system}\n\n{user}"
    body = json.dumps({
      "contents": [{"parts": [{"text": full_prompt}]}],
      "generationConfig": {"temperature": temperature, "maxOutputTokens": 1500},
    }).encode()
    url = (
      f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
      f"?key={self.api_key}"
    )
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    data = self._read_json(req)
    return data["candidates"][0]["content"]["parts"][0]["text"]

  def _deepseek(self, system: str, user: str, temperature: float) -> str:
    model = self.model or "deepseek-chat"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature}).encode()
    req = urllib.request.Request(
      "https://api.deepseek.com/v1/chat/completions",
      data=body,
      headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
    )
    return self._read_json(req)["choices"][0]["message"]["content"]

  def _groq(self, system: str, user: str, temperature: float) -> str:
    model = self.model or "llama-3.1-70b-versatile"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    body = json.dumps({"model": model, "messages": messages, "temperature": temperature}).encode()
    req = urllib.request.Request(
      "https://api.groq.com/openai/v1/chat/completions",
      data=body,
      headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
    )
    return self._read_json(req)["choices"][0]["message"]["content"]

  def _ollama(self, system: str, user: str, temperature: float) -> str:
    model = self.model or "llama3"
    url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    body = json.dumps({
      "model": model,
      "prompt": f"{system}\n\n{user}",
      "stream": False,
      "options": {"temperature": temperature},
    }).encode()
    req = urllib.request.Request(f"{url}/api/generate", data=body, headers={"Content-Type": "application/json"})
    return self._read_json(req)["response"]

  def _read_json(self, req: urllib.request.Request) -> dict:
    try:
      with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
      detail = e.read().decode("utf-8", errors="replace")
      raise RuntimeError(f"LLM HTTP {e.code}: {detail}") from e

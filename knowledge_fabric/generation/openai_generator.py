"""OpenAI-compatible generation backend with usage telemetry."""
from __future__ import annotations
import os, requests


class OpenAIGenerator:
    def __init__(self, model_id="gpt-4.1-mini", api_key_env="OPENAI_API_KEY", base_url="https://api.openai.com/v1/chat/completions"):
        self.model_id = model_id
        self.api_key_env = api_key_env
        self.api_key = os.getenv(api_key_env)
        self.base_url = base_url
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}
        self.last_error = None
        if not self.api_key:
            raise RuntimeError(f"{api_key_env} is not set; enable local mode or configure an OpenAI-compatible API key")

    def generate(self, system_prompt, user_prompt, max_tokens=800):
        try:
            r = requests.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model_id, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.1, "max_tokens": max_tokens},
                timeout=90,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            self.last_error = str(exc)
            raise
        usage = data.get("usage") or {}
        self.last_usage = {"input_tokens": int(usage.get("prompt_tokens", 0) or 0), "output_tokens": int(usage.get("completion_tokens", 0) or 0)}
        text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        if not text:
            raise RuntimeError("OpenAI-compatible endpoint returned an empty response")
        self.last_error = None
        return text

    def health(self):
        return bool(self.api_key and self.base_url)

    def health_details(self):
        return {
            "ready": bool(self.api_key and self.base_url),
            "credentials": bool(self.api_key),
            "endpoint": self.base_url,
            "model": self.model_id,
            "error": None if self.api_key and self.base_url else "API key or endpoint is not configured.",
        }

    def probe(self):
        try:
            text = self.generate("Reply with OK only.", "OK", max_tokens=8)
            return bool(text.strip())
        except Exception as exc:
            self.last_error = str(exc)
            return False

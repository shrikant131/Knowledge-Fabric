"""Local LLM generation via an OpenAI-compatible HTTP endpoint.

Ollama is the default local runtime, but any local server exposing
POST /api/chat can be used. No cloud credentials are required.
"""
from __future__ import annotations
import requests

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL_ID = "llama3.2:3b"


class LocalLLMUnavailable(RuntimeError):
    pass


class LocalGenerator:
    def __init__(self, model_id=DEFAULT_MODEL_ID, base_url=DEFAULT_BASE_URL, timeout=120):
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}
        self.last_error = None

    def health(self):
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.ok
        except requests.RequestException:
            return False

    def models(self):
        r = requests.get(f"{self.base_url}/api/tags", timeout=10)
        r.raise_for_status()
        return [m.get("name") for m in r.json().get("models", []) if m.get("name")]

    def health_details(self):
        try:
            models = self.models()
            model_ready = self.model_id in models or any(
                str(name).split(":", 1)[0] == self.model_id.split(":", 1)[0] for name in models
            )
            return {
                "ready": model_ready,
                "service": True,
                "model": self.model_id,
                "models": models,
                "error": None if model_ready else f"Model '{self.model_id}' is not installed.",
            }
        except Exception as exc:
            return {"ready": False, "service": False, "model": self.model_id,
                    "models": [], "error": str(exc)}

    def probe(self):
        try:
            return bool(self.generate("Reply with OK only.", "OK", max_tokens=8).strip())
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def generate(self, system_prompt, user_prompt, max_tokens=800):
        payload = {
            "model": self.model_id,
            "stream": False,
            "options": {"num_predict": max_tokens},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            r = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            r.raise_for_status()
        except requests.RequestException as exc:
            self.last_error = str(exc)
            raise LocalLLMUnavailable(
                f"Local LLM is unavailable at {self.base_url}. Start Ollama and pull '{self.model_id}'."
            ) from exc
        data = r.json()
        usage = data.get("prompt_eval_count", 0), data.get("eval_count", 0)
        self.last_usage = {"input_tokens": int(usage[0] or 0), "output_tokens": int(usage[1] or 0)}
        text = ((data.get("message") or {}).get("content") or "").strip()
        if not text:
            self.last_error = "Local LLM returned an empty response"
            raise LocalLLMUnavailable(self.last_error)
        self.last_error = None
        return text

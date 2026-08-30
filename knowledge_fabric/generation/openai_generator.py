"""OpenAI-compatible generation backend with usage telemetry."""
from __future__ import annotations
import os, requests

class OpenAIGenerator:
    def __init__(self, model_id="gpt-4.1-mini", api_key_env="OPENAI_API_KEY", base_url="https://api.openai.com/v1/chat/completions"):
        self.model_id=model_id; self.api_key=os.getenv(api_key_env); self.base_url=base_url
        self.last_usage={"input_tokens":0,"output_tokens":0}
        if not self.api_key: raise RuntimeError(f"{api_key_env} is not set; enable local mode or configure an OpenAI API key")
    def generate(self,system_prompt,user_prompt,max_tokens=800):
        r=requests.post(self.base_url,headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"},
                        json={"model":self.model_id,"messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],"temperature":0.1,"max_tokens":max_tokens},timeout=90)
        r.raise_for_status(); data=r.json()
        usage=data.get("usage") or {}
        self.last_usage={"input_tokens":int(usage.get("prompt_tokens",0) or 0),"output_tokens":int(usage.get("completion_tokens",0) or 0)}
        return data["choices"][0]["message"]["content"]
    def health(self): return bool(self.api_key)
    def probe(self):
        text=self.generate("Reply with OK only.","OK",max_tokens=8)
        return bool(text.strip())

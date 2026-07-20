"""AIProvider abstraction (§3/§7): one interface, pluggable backends.

Backends: Anthropic, Google (Gemini), DeepSeek, OpenAI, Local/Ollama (BETA).
Each returns an AIResponse with token counts so every call can be logged as an
AIRun and priced. Providers are thin: no business logic, no prompt text —
prompts live versioned in backend/prompts/ and are supplied by the agent
runner.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class AIResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    provider: str = ""
    raw: dict = field(default_factory=dict)

    def json(self) -> dict:
        """Parse a JSON body out of the response, tolerating code fences."""
        t = self.text.strip()
        if t.startswith("```"):
            t = t.split("```", 2)[1]
            t = t.split("\n", 1)[1] if "\n" in t else t
        start, end = t.find("{"), t.rfind("}")
        if start == -1:
            start, end = t.find("["), t.rfind("]")
        return json.loads(t[start:end + 1])


class AIProvider(Protocol):
    name: str

    def generate_text(self, *, system: str, user: str, model: str,
                      max_tokens: int = 4096, temperature: float = 0.7) -> AIResponse: ...

    def classify_image(self, *, system: str, image_path: Path, model: str,
                       max_tokens: int = 1024) -> AIResponse: ...


def _img_b64(path: Path) -> tuple[str, str]:
    media = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return base64.standard_b64encode(path.read_bytes()).decode(), media


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def _client(self):
        import anthropic

        return anthropic.Anthropic(api_key=self.api_key)

    def generate_text(self, *, system, user, model, max_tokens=4096, temperature=0.7) -> AIResponse:
        msg = self._client().messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return AIResponse(text=msg.content[0].text, input_tokens=msg.usage.input_tokens,
                          output_tokens=msg.usage.output_tokens, model=model, provider=self.name)

    def classify_image(self, *, system, image_path, model, max_tokens=1024) -> AIResponse:
        b64, media = _img_b64(image_path)
        msg = self._client().messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media, "data": b64}},
                {"type": "text", "text": "Classify this photo per your instructions. JSON only."},
            ]}],
        )
        return AIResponse(text=msg.content[0].text, input_tokens=msg.usage.input_tokens,
                          output_tokens=msg.usage.output_tokens, model=model, provider=self.name)


class OpenAICompatProvider:
    """OpenAI-compatible chat API — used directly for OpenAI and DeepSeek
    (which speaks the same protocol at a different base URL)."""

    def __init__(self, name: str, base_url: str, api_key_env: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = os.environ.get(api_key_env, "")

    def _post(self, payload: dict) -> dict:
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())

    def generate_text(self, *, system, user, model, max_tokens=4096, temperature=0.7) -> AIResponse:
        data = self._post({"model": model, "max_tokens": max_tokens, "temperature": temperature,
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": user}]})
        usage = data.get("usage", {})
        return AIResponse(text=data["choices"][0]["message"]["content"],
                          input_tokens=usage.get("prompt_tokens", 0),
                          output_tokens=usage.get("completion_tokens", 0),
                          model=model, provider=self.name, raw=data)

    def classify_image(self, *, system, image_path, model, max_tokens=1024) -> AIResponse:
        b64, media = _img_b64(image_path)
        data = self._post({"model": model, "max_tokens": max_tokens, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media};base64,{b64}"}},
                {"type": "text", "text": "Classify this photo per your instructions. JSON only."},
            ]},
        ]})
        usage = data.get("usage", {})
        return AIResponse(text=data["choices"][0]["message"]["content"],
                          input_tokens=usage.get("prompt_tokens", 0),
                          output_tokens=usage.get("completion_tokens", 0),
                          model=model, provider=self.name, raw=data)


class GoogleProvider:
    name = "google"

    def generate_text(self, *, system, user, model, max_tokens=4096, temperature=0.7) -> AIResponse:
        import google.generativeai as genai

        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
        m = genai.GenerativeModel(model, system_instruction=system)
        resp = m.generate_content(user, generation_config={"max_output_tokens": max_tokens,
                                                           "temperature": temperature})
        um = getattr(resp, "usage_metadata", None)
        return AIResponse(text=resp.text,
                          input_tokens=getattr(um, "prompt_token_count", 0),
                          output_tokens=getattr(um, "candidates_token_count", 0),
                          model=model, provider=self.name)

    def classify_image(self, *, system, image_path, model, max_tokens=1024) -> AIResponse:
        import google.generativeai as genai
        from PIL import Image

        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
        m = genai.GenerativeModel(model, system_instruction=system)
        resp = m.generate_content(
            [Image.open(image_path), "Classify this photo per your instructions. JSON only."],
            generation_config={"max_output_tokens": max_tokens},
        )
        um = getattr(resp, "usage_metadata", None)
        return AIResponse(text=resp.text,
                          input_tokens=getattr(um, "prompt_token_count", 0),
                          output_tokens=getattr(um, "candidates_token_count", 0),
                          model=model, provider=self.name)


class OllamaProvider:
    """Local models (BETA in the UI): zero token cost, slower, lower quality."""

    name = "local"

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def _post(self, endpoint: str, payload: dict) -> dict:
        req = urllib.request.Request(f"{self.base_url}{endpoint}",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read())

    def generate_text(self, *, system, user, model, max_tokens=4096, temperature=0.7) -> AIResponse:
        data = self._post("/api/chat", {"model": model, "stream": False,
                                        "options": {"num_predict": max_tokens, "temperature": temperature},
                                        "messages": [{"role": "system", "content": system},
                                                     {"role": "user", "content": user}]})
        return AIResponse(text=data["message"]["content"],
                          input_tokens=data.get("prompt_eval_count", 0),
                          output_tokens=data.get("eval_count", 0),
                          model=model, provider=self.name)

    def classify_image(self, *, system, image_path, model, max_tokens=1024) -> AIResponse:
        b64, _ = _img_b64(image_path)
        data = self._post("/api/chat", {"model": model, "stream": False,
                                        "messages": [{"role": "system", "content": system},
                                                     {"role": "user",
                                                      "content": "Classify this photo. JSON only.",
                                                      "images": [b64]}]})
        return AIResponse(text=data["message"]["content"],
                          input_tokens=data.get("prompt_eval_count", 0),
                          output_tokens=data.get("eval_count", 0),
                          model=model, provider=self.name)


PROVIDERS: dict[str, AIProvider] = {}


def get_provider(name: str) -> AIProvider:
    if name not in PROVIDERS:
        if name == "anthropic":
            PROVIDERS[name] = AnthropicProvider()
        elif name == "openai":
            PROVIDERS[name] = OpenAICompatProvider("openai", "https://api.openai.com/v1", "OPENAI_API_KEY")
        elif name == "deepseek":
            PROVIDERS[name] = OpenAICompatProvider("deepseek", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY")
        elif name == "google":
            PROVIDERS[name] = GoogleProvider()
        elif name == "local":
            PROVIDERS[name] = OllamaProvider()
        else:
            raise ValueError(f"Unknown AI provider: {name}")
    return PROVIDERS[name]

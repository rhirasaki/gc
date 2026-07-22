"""Regression tests for two bugs found only by a live Anthropic API call
against a real key:

1. Some models (extended-thinking-capable) reject `temperature` outright with
   a 400 error ("temperature is deprecated for this model"). The provider
   must retry once without it and remember the model for next time.
2. Those same models put a ThinkingBlock at content[0], not the answer text —
   content[0].text silently grabs reasoning instead of the JSON payload.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.ai.provider import AnthropicProvider, _text_from_message


class _FakeBadRequest(Exception):
    pass


def _msg(blocks, in_tok=10, out_tok=5):
    return SimpleNamespace(content=blocks, usage=SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok))


def _text_block(t):
    return SimpleNamespace(type="text", text=t)


def _thinking_block(t="reasoning..."):
    return SimpleNamespace(type="thinking", thinking=t)


def test_text_from_message_skips_thinking_block():
    msg = _msg([_thinking_block(), _text_block("the real answer")])
    assert _text_from_message(msg) == "the real answer"


def test_text_from_message_plain_response():
    msg = _msg([_text_block("hello")])
    assert _text_from_message(msg) == "hello"


def test_text_from_message_raises_if_no_text_block():
    msg = _msg([_thinking_block()])
    with pytest.raises(ValueError):
        _text_from_message(msg)


def test_generate_text_retries_without_temperature_on_400(monkeypatch):
    import anthropic

    calls = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            if "temperature" in kwargs:
                # Mimic the real SDK's error shape closely enough for our
                # except clause (str(exc) must contain "temperature").
                raise anthropic.BadRequestError(
                    "Error code: 400 - temperature is deprecated for this model",
                    response=SimpleNamespace(status_code=400, headers={}, request=SimpleNamespace()),
                    body=None,
                )
            return _msg([_text_block('{"ok": true}')])

    class FakeClient:
        messages = FakeMessages()

    provider = AnthropicProvider(api_key="test")
    provider._no_temperature_models = set()  # isolate from other tests
    monkeypatch.setattr(provider, "_client", lambda: FakeClient())

    resp = provider.generate_text(system="sys", user="hi", model="weird-model", temperature=0.5)
    assert resp.text == '{"ok": true}'
    assert len(calls) == 2  # first with temperature (fails), retry without
    assert "temperature" in calls[0] and "temperature" not in calls[1]
    assert "weird-model" in provider._no_temperature_models

    # Second call for the same model skips straight to no-temperature — one call only.
    calls.clear()
    provider.generate_text(system="sys", user="hi again", model="weird-model", temperature=0.9)
    assert len(calls) == 1 and "temperature" not in calls[0]


def test_generate_text_normal_model_unaffected(monkeypatch):
    calls = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return _msg([_text_block("fine")])

    class FakeClient:
        messages = FakeMessages()

    provider = AnthropicProvider(api_key="test")
    provider._no_temperature_models = set()
    monkeypatch.setattr(provider, "_client", lambda: FakeClient())

    resp = provider.generate_text(system="sys", user="hi", model="normal-model", temperature=0.5)
    assert resp.text == "fine"
    assert len(calls) == 1 and calls[0]["temperature"] == 0.5

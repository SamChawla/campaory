import json

import httpx
import pytest
import respx

from app.core.config import Settings
from app.llm.base import LLMUnavailable
from app.llm.euri import EuriProvider

BASE = "https://api.euron.one/api/v1/euri"
URL = f"{BASE}/chat/completions"


def completion(text: str, *, model: str = "gemma-test", usage: bool = True) -> dict:
    body: dict = {
        "id": "cmpl-1",
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}}],
    }
    if usage:
        body["usage"] = {"prompt_tokens": 120, "completion_tokens": 45, "total_tokens": 165}
    return body


async def no_sleep(_: float) -> None:
    return None


@pytest.fixture
def provider() -> EuriProvider:
    return EuriProvider(
        api_key="sk-test", model="gemma-test", base_url=BASE, timeout=5, sleep=no_sleep
    )


@respx.mock
async def test_posts_openai_chat_request(provider):
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=completion('{"a":1}')))

    await provider.complete(system="Be precise.", prompt="Extract facts.", temperature=0.2)

    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer sk-test"
    body = json.loads(request.content)
    assert body["model"] == "gemma-test"
    assert body["temperature"] == 0.2
    assert body["max_tokens"] == 2048
    assert "response_format" not in body


@respx.mock
async def test_system_text_goes_at_start_of_user_message(provider):
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=completion("{}")))

    await provider.complete(system="SYSTEM RULES", prompt="USER TASK")

    messages = json.loads(route.calls.last.request.content)["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"].startswith("SYSTEM RULES")
    assert messages[0]["content"].endswith("USER TASK")


@respx.mock
async def test_returns_text_model_and_token_counts(provider):
    respx.post(URL).mock(return_value=httpx.Response(200, json=completion('{"facts":[]}')))

    result = await provider.complete(system="s", prompt="p")

    assert result.text == '{"facts":[]}'
    assert result.provider == "euri"
    assert result.model == "gemma-test"
    assert result.input_tokens == 120
    assert result.output_tokens == 45
    assert result.latency_ms >= 0


@respx.mock
async def test_missing_usage_gives_none_tokens(provider):
    respx.post(URL).mock(return_value=httpx.Response(200, json=completion("{}", usage=False)))

    result = await provider.complete(system="s", prompt="p")

    assert result.input_tokens is None
    assert result.output_tokens is None


@respx.mock
async def test_retries_once_on_5xx(provider):
    route = respx.post(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=completion("{}"))]
    )

    result = await provider.complete(system="s", prompt="p")

    assert result.text == "{}"
    assert route.call_count == 2


@respx.mock
async def test_retries_once_on_network_error(provider):
    route = respx.post(URL).mock(
        side_effect=[httpx.ConnectError("down"), httpx.Response(200, json=completion("{}"))]
    )

    await provider.complete(system="s", prompt="p")

    assert route.call_count == 2


@respx.mock
async def test_second_5xx_raises_unavailable(provider):
    route = respx.post(URL).mock(return_value=httpx.Response(502))

    with pytest.raises(LLMUnavailable) as exc:
        await provider.complete(system="s", prompt="p")

    assert route.call_count == 2
    assert exc.value.status == 502
    assert exc.value.code == "llm_unavailable"


@respx.mock
@pytest.mark.parametrize("status", [400, 401, 429])
async def test_4xx_is_not_retried(provider, status):
    route = respx.post(URL).mock(return_value=httpx.Response(status))

    with pytest.raises(LLMUnavailable):
        await provider.complete(system="s", prompt="p")

    assert route.call_count == 1


@respx.mock
async def test_timeout_is_retried_then_raises(provider):
    route = respx.post(URL).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(LLMUnavailable):
        await provider.complete(system="s", prompt="p")

    assert route.call_count == 2


@respx.mock
@pytest.mark.parametrize(
    "body",
    [{}, {"choices": []}, {"choices": [{"message": {"content": None}}]}, "not json"],
)
async def test_malformed_response_raises_unavailable(provider, body):
    response = (
        httpx.Response(200, text=body) if isinstance(body, str) else httpx.Response(200, json=body)
    )
    respx.post(URL).mock(return_value=response)

    with pytest.raises(LLMUnavailable):
        await provider.complete(system="s", prompt="p")


@respx.mock
async def test_error_message_does_not_leak_key_or_prompt(provider):
    respx.post(URL).mock(return_value=httpx.Response(401, text="bad key sk-test"))

    with pytest.raises(LLMUnavailable) as exc:
        await provider.complete(system="s", prompt="SECRET CAMPAIGN TEXT")

    assert "sk-test" not in exc.value.message
    assert "SECRET CAMPAIGN TEXT" not in exc.value.message


@respx.mock
async def test_trailing_slash_in_base_url_is_tolerated():
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=completion("{}")))
    provider = EuriProvider(api_key="k", model="m", base_url=BASE + "/", sleep=no_sleep)

    await provider.complete(system="s", prompt="p")

    assert route.called


def test_from_settings_reads_euri_config():
    settings = Settings(_env_file=None, llm_provider="euri", euri_api_key="k", euri_model="gemma-x")

    provider = EuriProvider.from_settings(settings)

    assert provider.name == "euri"
    assert provider.model == "gemma-x"


@pytest.mark.parametrize("missing", ["euri_api_key", "euri_model"])
def test_from_settings_requires_key_and_model(missing):
    values = {"euri_api_key": "k", "euri_model": "gemma-x", missing: ""}
    settings = Settings(_env_file=None, llm_provider="euri", **values)

    with pytest.raises(ValueError, match=missing.upper()):
        EuriProvider.from_settings(settings)

import httpx
import pytest
import respx

from app.core.config import Settings
from app.llm.base import Completion, LLMUnavailable
from app.llm.euri import EuriProvider
from app.llm.factory import FallbackProvider, get_provider
from app.llm.mock import MockProvider

EURI = {"llm_provider": "euri", "euri_api_key": "k", "euri_model": "google/gemma-4"}


def test_mock_settings_give_mock_provider():
    assert isinstance(get_provider(Settings(_env_file=None)), MockProvider)


def test_euri_settings_give_euri_provider():
    provider = get_provider(Settings(_env_file=None, **EURI))

    assert isinstance(provider, EuriProvider)
    assert provider.model == "google/gemma-4"


def test_fallback_wraps_euri_when_enabled():
    provider = get_provider(Settings(_env_file=None, llm_fallback_to_mock=True, **EURI))

    assert isinstance(provider, FallbackProvider)
    assert provider.name == "euri"
    assert provider.model == "google/gemma-4"


def test_fallback_flag_is_ignored_for_mock():
    provider = get_provider(Settings(_env_file=None, llm_fallback_to_mock=True))

    assert isinstance(provider, MockProvider)


class Down:
    name = "euri"
    model = "gemma"

    async def complete(self, **kwargs):
        raise LLMUnavailable()


class Up:
    name = "euri"
    model = "gemma"

    async def complete(self, **kwargs):
        return Completion("{}", "euri", "gemma", 5, 1, 1)


async def test_fallback_uses_mock_when_primary_is_unavailable():
    provider = FallbackProvider(Down(), MockProvider())

    done = await provider.complete(system="s", prompt="p")

    assert done.provider == "mock"


async def test_fallback_keeps_primary_result_when_it_works():
    provider = FallbackProvider(Up(), MockProvider())

    done = await provider.complete(system="s", prompt="p")

    assert done.provider == "euri"


async def test_without_fallback_unavailable_propagates():
    provider = get_provider(Settings(_env_file=None, **EURI))

    with respx.mock:
        respx.post(url__regex=r".*/chat/completions").mock(return_value=httpx.Response(401))
        with pytest.raises(LLMUnavailable):
            await provider.complete(system="s", prompt="p")

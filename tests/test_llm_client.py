import asyncio
from types import SimpleNamespace

import pytest
from litellm.exceptions import RateLimitError, Timeout

import app.services.llm_client as llm_module
from app.core.errors import LLMProviderAppError, LLMTimeoutAppError
from app.services.llm_client import LLMClient


def build_client() -> LLMClient:
    return LLMClient(
        model="openai/test-model",
        api_key="test-api-key",
        timeout_seconds=12,
    )


def test_generate_returns_trimmed_provider_content(monkeypatch) -> None:
    async def fake_acompletion(**kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="  valid response  ")
                )
            ]
        )

    monkeypatch.setattr(llm_module, "acompletion", fake_acompletion)

    result = asyncio.run(build_client().generate(prompt="test prompt"))

    assert result == "valid response"


def test_generate_maps_provider_timeout(monkeypatch) -> None:
    async def raise_timeout(**kwargs):
        raise Timeout(
            message="provider timed out",
            model="openai/test-model",
            llm_provider="openai",
        )

    monkeypatch.setattr(llm_module, "acompletion", raise_timeout)

    with pytest.raises(LLMTimeoutAppError) as exc_info:
        asyncio.run(build_client().generate(prompt="test prompt"))

    assert exc_info.value.status_code == 504
    assert exc_info.value.metadata["timeout_seconds"] == 12


def test_generate_maps_provider_rate_limit(monkeypatch) -> None:
    async def raise_rate_limit(**kwargs):
        raise RateLimitError(
            message="quota exhausted",
            model="openai/test-model",
            llm_provider="openai",
        )

    monkeypatch.setattr(llm_module, "acompletion", raise_rate_limit)

    with pytest.raises(LLMProviderAppError) as exc_info:
        asyncio.run(build_client().generate(prompt="test prompt"))

    assert exc_info.value.status_code == 502
    assert exc_info.value.metadata["model"] == "openai/test-model"


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(choices=[]),
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="   "))]
        ),
    ],
)
def test_generate_rejects_invalid_provider_response(
    monkeypatch,
    response,
) -> None:
    async def fake_acompletion(**kwargs):
        return response

    monkeypatch.setattr(llm_module, "acompletion", fake_acompletion)

    with pytest.raises(LLMProviderAppError):
        asyncio.run(build_client().generate(prompt="test prompt"))

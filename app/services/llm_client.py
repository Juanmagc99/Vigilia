from litellm import acompletion
from litellm.exceptions import APIError, RateLimitError, Timeout

from app.core.errors import LLMProviderAppError, LLMTimeoutAppError


class LLMClient:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        timeout_seconds: float = 35.0,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    async def generate(self, *, prompt: str) -> str:
        try:
            response = await acompletion(
                model=self._model,
                api_key=self._api_key,
                timeout=self._timeout_seconds,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
        except Timeout as exc:
            raise LLMTimeoutAppError(
                metadata={
                    "operation": "generate_llm_response",
                    "model": self._model,
                    "timeout_seconds": self._timeout_seconds,
                },
            ) from exc
        except (APIError, RateLimitError) as exc:
            raise LLMProviderAppError(
                metadata={
                    "operation": "generate_llm_response",
                    "model": self._model,
                },
            ) from exc

        try:
            content = response.choices[0].message.content # type: ignore
        except (AttributeError, IndexError, TypeError) as exc:
            raise LLMProviderAppError(
                metadata={
                    "operation": "read_llm_response",
                    "model": self._model,
                    "reason": "invalid_response_structure",
                },
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMProviderAppError(
                metadata={
                    "operation": "read_llm_response",
                    "model": self._model,
                    "reason": "empty_response",
                },
            )

        return content.strip()

import math

from litellm import aembedding

from vigilia.application.errors import TransientInvestigationError
from vigilia.application.ports import EmbeddingProvider


class LiteLLMEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        api_base: str | None,
        timeout_seconds: float,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._api_base = api_base
        self._timeout_seconds = timeout_seconds

    async def embed(self, texts: list[str]) -> list[tuple[float, ...]]:
        if not texts:
            return []
        try:
            response = await aembedding(
                model=self.model,
                input=texts,
                api_key=self._api_key,
                api_base=self._api_base,
                timeout=self._timeout_seconds,
            )
            data = response.get("data") if isinstance(response, dict) else response.data
            ordered = []
            for fallback_index, item in enumerate(data):
                if isinstance(item, dict):
                    index = item.get("index", fallback_index)
                    vector = item.get("embedding")
                else:
                    index = getattr(item, "index", fallback_index)
                    vector = getattr(item, "embedding", None)
                if vector is None:
                    raise ValueError("Embedding response did not contain a vector")
                ordered.append((int(index), tuple(float(value) for value in vector)))
            vectors = [
                vector for _, vector in sorted(ordered, key=lambda item: item[0])
            ]
            if len(vectors) != len(texts) or any(not vector for vector in vectors):
                raise ValueError("Embedding response count did not match input count")
            if len({len(vector) for vector in vectors}) != 1:
                raise ValueError("Embedding response dimensions were inconsistent")
            if any(not math.isfinite(value) for vector in vectors for value in vector):
                raise ValueError("Embedding response contained a non-finite value")
            return vectors
        except Exception as exc:
            raise TransientInvestigationError(
                message="Embedding provider is temporarily unavailable",
                code="knowledge_embedding_unavailable",
                metadata={"model": self.model},
            ) from exc

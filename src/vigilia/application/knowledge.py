import hashlib
import math
import re
from uuid import UUID

from vigilia.application.errors import NotFoundAppError, ValidationAppError
from vigilia.application.ports import (
    EmbeddingProvider,
    KnowledgeRetriever,
    UnitOfWorkFactory,
)
from vigilia.domain.models import (
    IncidentSnapshot,
    KnowledgeChunkRecord,
    KnowledgeEvidence,
)

_SECRET_PATTERNS = (
    re.compile(r"(?i)(\bauthorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(
        r"(?i)(\b(?:password|passwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*)"
        r"[^\s,;]+"
    ),
)


def _sanitize_content(content: str) -> str:
    sanitized = content
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
    return sanitized.strip()


def _split_content(content: str, chunk_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(content):
        end = min(start + chunk_size, len(content))
        if end < len(content):
            boundary = content.rfind("\n", start + chunk_size // 2, end)
            if boundary < 0:
                boundary = content.rfind(" ", start + chunk_size // 2, end)
            if boundary > start:
                end = boundary
        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(content):
            break
        start = max(end - overlap, start + 1)
    return chunks


class IngestKnowledgeDocument:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        embedder: EmbeddingProvider,
        *,
        environment: str,
        chunk_size: int,
        chunk_overlap: int,
        embedding_batch_size: int,
        max_document_characters: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._embedder = embedder
        self._environment = environment
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._embedding_batch_size = embedding_batch_size
        self._max_document_characters = max_document_characters

    async def execute(
        self,
        *,
        service: str,
        source: str,
        title: str,
        version: str,
        content: str,
    ) -> tuple[UUID, int]:
        sanitized = _sanitize_content(content)
        if not sanitized:
            raise ValidationAppError(
                message="Knowledge document content is empty after sanitization",
                code="empty_knowledge_document",
            )
        if len(sanitized) > self._max_document_characters:
            raise ValidationAppError(
                message="Knowledge document exceeds the configured size limit",
                code="knowledge_document_too_large",
                metadata={"max_characters": self._max_document_characters},
            )
        parts = _split_content(sanitized, self._chunk_size, self._chunk_overlap)
        embeddings: list[tuple[float, ...]] = []
        for offset in range(0, len(parts), self._embedding_batch_size):
            embeddings.extend(
                await self._embedder.embed(
                    parts[offset : offset + self._embedding_batch_size]
                )
            )
        if len(embeddings) != len(parts) or any(
            not embedding for embedding in embeddings
        ):
            raise ValidationAppError(
                message="Embedding provider returned an invalid result",
                code="invalid_embedding_response",
            )
        dimensions = {len(embedding) for embedding in embeddings}
        if len(dimensions) != 1:
            raise ValidationAppError(
                message="Embedding provider returned inconsistent vector dimensions",
                code="inconsistent_embedding_dimensions",
            )
        if any(
            not math.isfinite(value) for embedding in embeddings for value in embedding
        ):
            raise ValidationAppError(
                message="Embedding provider returned a non-finite vector value",
                code="invalid_embedding_value",
            )
        chunk_records = tuple(
            KnowledgeChunkRecord(index=index, content=part, embedding=embedding)
            for index, (part, embedding) in enumerate(
                zip(parts, embeddings, strict=True)
            )
        )
        async with self._uow_factory() as uow:
            return await uow.upsert_knowledge_document(
                service=service,
                environment=self._environment,
                source=source,
                title=title,
                version=version,
                content_hash=hashlib.sha256(sanitized.encode("utf-8")).hexdigest(),
                embedding_model=self._embedder.model,
                embedding_dimensions=next(iter(dimensions)),
                chunks=chunk_records,
            )


class DeleteKnowledgeDocument:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, document_id: UUID) -> None:
        async with self._uow_factory() as uow:
            if not await uow.delete_knowledge_document(document_id):
                raise NotFoundAppError(
                    message="Knowledge document was not found",
                    code="knowledge_document_not_found",
                )


class IncidentKnowledgeRetriever(KnowledgeRetriever):
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        embedder: EmbeddingProvider,
        *,
        environment: str,
        top_k: int,
        max_context_characters: int,
    ) -> None:
        self._uow_factory = uow_factory
        self._embedder = embedder
        self._environment = environment
        self._top_k = top_k
        self._max_context_characters = max_context_characters

    async def retrieve(
        self, incident: IncidentSnapshot
    ) -> tuple[KnowledgeEvidence, ...]:
        query_parts = [
            f"Service: {incident.service}",
            f"Incident: {incident.title}",
            f"Severity: {incident.severity}",
        ]
        for alert in incident.alerts:
            query_parts.extend(
                part
                for part in (alert.alert_name, alert.summary, alert.description)
                if part
            )
        query = "\n".join(query_parts)[:8000]
        try:
            query_embeddings = await self._embedder.embed([query])
            query_embedding = query_embeddings[0]
        except Exception as exc:
            from vigilia.application.errors import TransientInvestigationError

            raise TransientInvestigationError(
                message="Knowledge retrieval is temporarily unavailable",
                code="knowledge_embedding_unavailable",
            ) from exc
        async with self._uow_factory() as uow:
            matches = await uow.search_knowledge_chunks(
                service=incident.service,
                environment=self._environment,
                embedding_model=self._embedder.model,
                embedding_dimensions=len(query_embedding),
                embedding=query_embedding,
                limit=self._top_k,
            )
        selected: list[KnowledgeEvidence] = []
        remaining = self._max_context_characters
        for item in matches:
            if remaining <= 0:
                break
            content = item.content[:remaining]
            selected.append(
                KnowledgeEvidence(
                    id=item.id,
                    document_id=item.document_id,
                    service=item.service,
                    title=item.title,
                    source=item.source,
                    content=content,
                    version=item.version,
                    similarity=item.similarity,
                )
            )
            remaining -= len(content)
        return tuple(selected)

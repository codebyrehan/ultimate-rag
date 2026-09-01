"""Query orchestration service.

Threads tenant scoping through the entire RAG loop: persistence of the
:class:`Query` and :class:`Evidence` records, retrieval, answer synthesis,
and latency tracking. Designed to be invoked synchronously from an API route
or asynchronously from the inline job worker.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from ultimate_rag.core.ids import new_id
from ultimate_rag.core.metrics import inc
from ultimate_rag.db.models import Conversation, Evidence, Message, Query
from ultimate_rag.db.repositories.conversations import ConversationRepository, MessageRepository
from ultimate_rag.db.repositories.evidence import EvidenceRepository
from ultimate_rag.db.repositories.queries import QueryRepository
from ultimate_rag.generation.answer_builder import AnswerBuilder
from ultimate_rag.generation.interface import Answer
from ultimate_rag.retrieval.pipeline import RetrievalPipeline, build_retrieval_pipeline
from ultimate_rag.retrieval.types import RetrievalContext
from ultimate_rag.verification.guard import VerificationGuard, VerificationReport

QueryID = str


class QueryService:
    """Orchestrates retrieval + generation + evidence persistence for one query."""

    def __init__(
        self,
        retrieval: RetrievalPipeline,
        answer_builder: AnswerBuilder,
        settings,
        guard: VerificationGuard | None = None,
    ) -> None:
        self.retrieval = retrieval
        self.answer_builder = answer_builder
        self.settings = settings
        self.guard = guard or VerificationGuard(settings)

    async def answer(
        self,
        query: str,
        tenant_id: str,
        session: AsyncSession,
        user_id: str | None = None,
        conversation_id: str | None = None,
        text_loader: Callable[[list[str]], Awaitable[dict[str, str]]] | None = None,
    ) -> tuple[Answer, QueryID, VerificationReport | None, str]:
        t0 = time.perf_counter()
        query_id = new_id()
        q_repo = QueryRepository(session)
        conv_repo = ConversationRepository(session)
        msg_repo = MessageRepository(session)

        conv_id = await self._resolve_conversation(conv_repo, tenant_id, user_id, conversation_id)

        history = await self._get_history(msg_repo, tenant_id, conv_id)

        await msg_repo.add(
            Message(
                id=new_id(),
                conversation_id=conv_id,
                tenant_id=tenant_id,
                role="user",
                content=query,
            )
        )

        await q_repo.add(
            Query(
                id=query_id,
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conv_id,
                query=query,
            )
        )
        await session.flush()

        ctx: RetrievalContext = await self.retrieval.retrieve(query, tenant_id, text_loader=text_loader)

        answer: Answer = await self.answer_builder.build_answer(
            ctx, text_loader=text_loader, history=history
        )

        await msg_repo.add(
            Message(
                id=new_id(),
                conversation_id=conv_id,
                tenant_id=tenant_id,
                role="assistant",
                content=answer.text,
                citations=[c.to_dict() for c in answer.citations],
            )
        )
        await session.flush()

        await self._persist_evidence(query_id, tenant_id, ctx, session)

        report: VerificationReport | None = None
        if self.settings.claim_extraction_enabled and self.settings.faithfulness_check_enabled:
            report = self.guard.verify(answer, ctx)
            answer.confidence = report.confidence

        latency_ms = int((time.perf_counter() - t0) * 1000)
        await q_repo.update_latency(tenant_id, query_id, latency_ms)
        inc("queries_answered")
        return answer, query_id, report, conv_id

    async def stream_answer(
        self,
        query: str,
        tenant_id: str,
        session: AsyncSession,
        user_id: str | None = None,
        conversation_id: str | None = None,
        text_loader: Callable[[list[str]], Awaitable[dict[str, str]]] | None = None,
    ):
        """Stream answer deltas; yields ``{"type": "token", "data": ...}`` then a done message.

        Also persists the user query and assistant answer as messages, and
        creates a conversation if one is not provided.
        """
        t0 = time.perf_counter()
        query_id = new_id()
        q_repo = QueryRepository(session)
        conv_repo = ConversationRepository(session)
        msg_repo = MessageRepository(session)

        conv_id = await self._resolve_conversation(conv_repo, tenant_id, user_id, conversation_id)

        history = await self._get_history(msg_repo, tenant_id, conv_id)

        await msg_repo.add(
            Message(
                id=new_id(),
                conversation_id=conv_id,
                tenant_id=tenant_id,
                role="user",
                content=query,
            )
        )

        await q_repo.add(
            Query(
                id=query_id,
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conv_id,
                query=query,
            )
        )
        await session.flush()

        ctx: RetrievalContext = await self.retrieval.retrieve(query, tenant_id, text_loader=text_loader)

        # hydrate chunks once so the done message has full citations
        if text_loader is not None and ctx.compressed:
            texts = await text_loader([c.chunk_id for c in ctx.compressed])
            for c in ctx.compressed:
                c.text = texts.get(c.chunk_id, c.text)

        done_msg: dict | None = None
        answer_text = ""
        async for event in self.answer_builder.build_answer_stream(ctx, text_loader=None, history=history):
            if event["type"] == "done":
                done_msg = event
            else:
                answer_text += event["data"]
                yield event

        await msg_repo.add(
            Message(
                id=new_id(),
                conversation_id=conv_id,
                tenant_id=tenant_id,
                role="assistant",
                content=answer_text,
            )
        )
        await session.flush()

        await self._persist_evidence(query_id, tenant_id, ctx, session)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        await q_repo.update_latency(tenant_id, query_id, latency_ms)
        inc("queries_streamed")

        report: VerificationReport | None = None
        if self.settings.claim_extraction_enabled and self.settings.faithfulness_check_enabled:
            answer_obj = Answer(text=answer_text, citations=[])
            report = self.guard.verify(answer_obj, ctx)

        if done_msg is None:
            done_msg = {
                "type": "done",
                "citations": [],
                "confidence": report.confidence if report else 0.0,
                "model": self.answer_builder.llm.name,
            }
        else:
            done_msg["confidence"] = report.confidence if report else done_msg.get("confidence", 0.0)
        done_msg["query_id"] = query_id
        done_msg["conversation_id"] = conv_id
        yield done_msg

    async def _persist_evidence(
        self, query_id: str, tenant_id: str, ctx: RetrievalContext, session: AsyncSession
    ) -> None:
        records: list[Evidence] = []
        for rank, chunk in enumerate(ctx.compressed):
            records.append(
                Evidence(
                    id=new_id(),
                    query_id=query_id,
                    chunk_id=chunk.chunk_id,
                    rank=rank,
                    score=chunk.score,
                )
            )
        if records:
            ev_repo = EvidenceRepository(session)
            await ev_repo.add_many(records)
        await session.flush()

    async def _resolve_conversation(
        self,
        conv_repo: ConversationRepository,
        tenant_id: str,
        user_id: str | None,
        conversation_id: str | None,
    ) -> str:
        """Return an existing conversation or create a new one."""
        if conversation_id:
            conv = await conv_repo.get(tenant_id, conversation_id)
            if conv is not None:
                return conv.id
        new_conv = Conversation(
            id=new_id(),
            tenant_id=tenant_id,
            user_id=user_id or "",
        )
        await conv_repo.add(new_conv)
        return new_conv.id

    async def _get_history(
        self, msg_repo: MessageRepository, tenant_id: str, conv_id: str
    ) -> list[dict[str, str]]:
        """Return prior messages as role/content dicts for LLM context."""
        msgs = await msg_repo.list_for_conversation(tenant_id, conv_id)
        return [{"role": m.role, "content": m.content} for m in msgs]


async def build_query_service(container) -> QueryService:
    settings = container.settings
    retrieval: RetrievalPipeline = await build_retrieval_pipeline(container)
    from ultimate_rag.generation.factory import build_answer_builder

    answer_builder = build_answer_builder(settings, container.get("llm"))
    return QueryService(retrieval=retrieval, answer_builder=answer_builder, settings=settings)

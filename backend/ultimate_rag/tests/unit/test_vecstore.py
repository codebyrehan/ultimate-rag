from __future__ import annotations

import pytest

from ultimate_rag.core.config import get_settings
from ultimate_rag.core.ids import new_id
from ultimate_rag.vecstore.interface import VectorPayload
from ultimate_rag.vecstore.providers.in_memory import InMemoryVectorStore


def _payload(tenant: str, cid: str = "") -> VectorPayload:
    return VectorPayload(
        chunk_id=cid or new_id(),
        document_id=new_id(),
        tenant_id=tenant,
        doc_filename="doc.pdf",
        page_number=1,
        section="Intro",
        chunk_type="child",
    )


@pytest.fixture
def store():
    return InMemoryVectorStore(get_settings())


async def test_inmemory_search_returns_top_k(store):
    await store.acreate_collection()
    a = new_id()
    b = new_id()
    await store.abatch_insert(
        [a, b],
        [[1.0, 0.0, 0.0], [0.9, 0.1, 0.0]],
        [_payload("t", a), _payload("t", b)],
    )
    res = await store.asearch([1.0, 0.0, 0.0], top_k=2, tenant_id="t")
    assert [r.chunk_id for r in res] == [a, b]
    assert res[0].score >= res[1].score


async def test_inmemory_tenant_isolation(store):
    await store.acreate_collection()
    v = new_id()
    await store.ainsert(v, [1.0, 0.0, 0.0], _payload("tenantA", v))
    res = await store.asearch([1.0, 0.0, 0.0], top_k=5, tenant_id="tenantB")
    assert res == []


async def test_inmemory_delete_document(store):
    await store.acreate_collection()
    doc_id = new_id()
    await store.ainsert(new_id(), [1.0, 0.0, 0.0], _payload("t"))
    await store.ainsert(
        new_id(),
        [0.1, 0.9, 0.0],
        VectorPayload(chunk_id=new_id(), document_id=doc_id, tenant_id="t", doc_filename="d.pdf"),
    )
    removed = await store.adelete_document(doc_id, "t")
    assert removed == 1


async def test_inmemory_health(store):
    assert await store.health_check() is True

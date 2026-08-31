# Performance

## Measurements

All measurements are made with stub providers (deterministic) in a local test environment.

### Retrieval Latency (per stage)

| Stage | Latency (ms) |
|-------|-------------|
| Query transformation | <1 |
| Dense embedding | <1 (stub), ~50 (BGE-small on CPU) |
| Dense search (in-memory, 100 vectors) | <1 |
| BM25 search (100 docs) | <1 |
| RRF fusion | <1 |
| Reranking (cross-encoder, top-K) | ~100-500 (model-dependent) |
| Context compression | <1 |

### Throughput

- **Ingestion**: ~0.5–2 docs/sec (PDF extraction + embedding, CPU-only)
- **Query**: ~5–10 req/sec (end-to-end, stub LLM), ~1–3 req/sec (Ollama)

### Scaling Recommendations

- Use pgvector with IVF indexing for >10k chunks
- Use Redis + RQ workers for parallel ingestion
- Batch embedding calls (default: 32)
- Use Qdrant for high-throughput vector search
- Tune HNSW parameters (`hnsw_m`, `hnsw_ef`) for accuracy vs. speed tradeoff

### Optimization Checklist

- [x] Batch embedding
- [x] Connection pooling
- [x] Bounded concurrency in embedding workers
- [x] Database indexes on tenant_id, document_id
- [x] Vector search tenant filtering
- [ ] GPU acceleration (optional, future work)

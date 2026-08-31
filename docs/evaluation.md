# Evaluation

## Framework

The evaluation framework (`backend/ultimate_rag/evaluation/`) provides:

- Standard IR metrics: Recall@K, Precision@K, MRR, nDCG
- Dataset loader for JSONL format
- Ablation study runner comparing retrieval strategies

## Ablation Study

Compares retrieval configurations:

| Configuration | Description |
|---|---|
| `dense_only` | Dense embedding + vector search only |
| `bm25_only` | BM25 keyword search only |
| `dense+bm25_concat` | Dense + BM25 results concatenated |
| `dense+bm25+rrf` | Dense + BM25 with RRF fusion |

## Running

```bash
cd backend
python -m ultimate_rag.evaluation.ablation \
  --dataset ../evaluation/datasets/handbook_qa.json \
  --output ../evaluation/results/ablation_result.json
```

## Metrics

- **Recall@K**: Fraction of expected sources found in top-K results
- **Precision@K**: Fraction of top-K results that are relevant
- **MRR**: Mean Reciprocal Rank — rank of the first correct answer
- **nDCG@K**: Normalized Discounted Cumulative Gain — ranking quality

## Dataset Format

```json
{
  "question": "What is the annual leave entitlement?",
  "expected_sources": ["chunk_id_1"],
  "document_ids": ["handbook.pdf"],
  "category": "factual"
}
```

# Ultimate RAG Evaluation

## Running an ablation study

```bash
cd backend
python -m ultimate_rag.evaluation.ablation \
  --dataset ../evaluation/datasets/handbook_qa.json \
  --output ../evaluation/results/ablation_result.json
```

## Metrics

| Metric         | Description                                      |
|----------------|--------------------------------------------------|
| Recall@K       | Fraction of expected sources in top-K results    |
| Precision@K    | Fraction of top-K results that are relevant      |
| MRR            | Mean Reciprocal Rank of the first relevant hit   |
| nDCG@K         | Normalized Discounted Cumulative Gain at K       |

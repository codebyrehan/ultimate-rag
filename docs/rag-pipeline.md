# RAG Pipeline

## Overview

The retrieval-augmented generation pipeline follows this flow:

```
Question
  → Query Transform (rewrite, expand, HyDE)
  → Hybrid Retrieval (Dense + BM25)
  → RRF Fusion
  → Deduplication
  → Reranking (cross-encoder)
  → Context Compression
  → Grounded Generation
  → Claim Extraction
  → Faithfulness Verification
  → Confidence Scoring
  → Final Response (with citations)
```

## Components

### Query Transformation (`retrieval/query_transform/`)

- **QueryRewriter**: Strips conversational prefixes, normalizes case, lowercases
- **QueryExpander**: Synonym-based query variants (deterministic)
- **MultiQueryExpander**: Template + synonym-based paraphrased queries
- **HydeGenerator**: Hypothetical answer generation for HyDE

### Hybrid Retrieval (`retrieval/`)

- **DenseRetriever**: Embeds query, searches vector store (cosine similarity)
- **BM25Retriever**: From-scratch Okapi BM25 with TF-IDF
- **RRFusioner**: Weighted Reciprocal Rank Fusion of dense + lexical
- **StubReranker**: No-op (for testing)
- **CrossEncoderReranker**: `thenlper/gte-reranker` or `cross-encoder/ms-marco-MiniLM-L-6-v2`

### Generation (`generation/`)

- **AnswerBuilder**: Constructs system prompt with numbered context, injects conversation history, calls LLM
- **QueryService**: Orchestrates retrieval → generation → verification → persistence

### Verification (`verification/`)

- **ClaimExtractor**: Splits answer into atomic claims
- **FaithfulnessChecker**: Token-overlap (Jaccard) between claims and evidence
- **ConfidenceScorer**: Combines faithfulness + retrieval scores
- **VerificationGuard**: Full pipeline guard with configurable confidence threshold

## Configuration

```env
# Retrieval
DENSE_RETRIEVAL_ENABLED=true
DENSE_TOP_K=20
DENSE_WEIGHT=0.6
LEXICAL_WEIGHT=0.4
RRF_K=60
FINAL_TOP_K=10

# Query transformation
QUERY_REWRITE_ENABLED=true
QUERY_EXPANSION_ENABLED=false
MULTI_QUERY_ENABLED=false
HYDE_ENABLED=false

# Verification
CLAIM_EXTRACTION_ENABLED=true
FAITHFULNESS_CHECK_ENABLED=true
NLI_SIMILARITY_THRESHOLD=0.65
```

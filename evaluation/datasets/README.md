Evaluation dataset documentation.

# Evaluation Datasets

## handbook_qa.json
A question-answering dataset derived from `sample_docs/handbook.md`, covering
topics: leave, sick days, remote work, performance, benefits, resignation.

## Dataset format (JSON array)

Each entry:
- `question`: the user query
- `expected_sources`: chunk identifiers expected to be retrieved
- `document_ids`: source document identifiers
- `category`: factual, semantic, paraphrase

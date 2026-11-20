# Enterprise AI Knowledge Assistant

A local-first document Q&A prototype with source citations, conservative abstention, and a repeatable retrieval benchmark.

## Run

Requires Python 3.11+.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[app,semantic,dev]"
Copy-Item .env.example .env
uvicorn knowledge_assistant.api:app --reload
```

The first semantic-model load may download model files. API docs are at `http://127.0.0.1:8000/docs`. Run the Streamlit interface separately with `streamlit run knowledge_assistant/ui.py`.

The sample corpus contains fictional policy documents for demonstration only; they are not real organizational rules.

## Retrieval and abstention

- **Keyword:** BM25 term retrieval. Its saturating score stays on an absolute scale and is not divided by the current query's top score.
- **Semantic:** Sentence Transformers cosine similarity. It returns an explicit unavailable error if the embedding package or model cannot load; it never silently substitutes keyword results.
- **Hybrid:** a fixed 50/50 blend of absolute BM25 and cosine scores. This is a hypothesis to measure, not an assumed winner.
- **Abstention:** method-specific score thresholds are configurable through environment variables. Current demo-corpus defaults are `0.60` for keyword, `0.50` for semantic, and `0.50` for hybrid. They were selected from the bundled synthetic benchmark's threshold sweep to reduce unsupported accepts; they are not calibrated probabilities and will overfit this tiny corpus. Tune on a separate validation set and report false accepts and false rejects.
- **Answers:** the prototype returns the best passage verbatim with its source and page, or abstains. Retrieved passages are available in the response for verification.

Scores are ranking/confidence proxies, not probabilities. Thresholds need recalibration when the corpus, chunking, embedding model, or retrieval blend changes.

## Evaluation

The benchmark contains 120 authored questions: 100 answerable questions across five documents and 20 deliberately unanswerable questions. Each answerable question has an expected source and exact evidence phrase. The questions are checked against this synthetic corpus, but have not been reviewed by an organization's policy owner. Replace or independently validate the set before making external quality claims.

```powershell
python eval\build_dataset.py
python -m knowledge_assistant.cli evaluate --retrieval compare --dataset eval/questions.jsonl --corpus data/approved --top-k 5 --chunk-size 350 --chunk-overlap 80
```

The comparison runs keyword, semantic, and hybrid retrieval on the same questions. It writes `eval/results/comparison.json` and `eval/results/failures.json`. If the semantic model cannot load, that method is explicitly marked unavailable rather than reporting keyword scores as semantic results.

Reported measures include Recall@K, Precision@K (denominator is K), citation accuracy (source and expected phrase support), exact answer phrase accuracy, abstention decision accuracy, unsupported answer rate, abstention rate, and warm-request latency. Review failure examples before selecting a configuration. This benchmark is small and synthetic; its results do not predict performance on a real enterprise corpus.

### Recorded comparison

Results below use 120 questions, 10 chunks, `K=5`, 350-character chunks, 80-character overlap, and the per-method thresholds listed above. Thresholds were swept on this same dataset, so the abstention figures are in-sample and optimistic.

| Retrieval | Recall@5 | Precision@5 | Citation accuracy | Exact answer phrase | Abstention decision accuracy | Unsupported answer rate | p95 latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Keyword | 0.920 | 0.202 | 0.683 | 0.630 | 0.858 | 0.050 | 0.09 ms |
| Semantic | 1.000 | 0.220 | 0.683 | 0.630 | 0.800 | 0.050 | 10.65 ms |
| Hybrid | 0.970 | 0.214 | 0.783 | 0.750 | 0.908 | 0.050 | 11.81 ms |

Hybrid had the strongest citation, exact-answer, and abstention-decision results in this run; semantic had the highest Recall@5. The small fixture corpus and in-sample threshold selection mean this is an engineering check, not evidence of production performance.

Run the automated suite with:

```powershell
pytest
```

## Design notes and limits

- **PDF extraction:** PyMuPDF extracts text page-by-page and preserves page numbers. Scanned PDFs need OCR, which is not included.
- **Tables:** text extraction can flatten columns and lose row/column relationships. Inspect table-heavy PDFs; add a layout-aware parser and table-specific tests before relying on them.
- **Chunking:** the prototype targets 350 characters with 80 characters overlap and prefers whitespace boundaries. Compare chunk sizes on a real labeled set.
- **Authorization:** the configured document directory is treated as approved. There is no user identity, document-level ACL, tenant isolation, or ingestion authorization; do not expose this prototype to multiple permission groups.
- **LLM generation:** no LLM is used. This avoids unsupported synthesis in the current prototype. If adding one, require citation-grounded output and evaluate claim-level support.

## API

- `POST /documents/ingest` — reload the configured local corpus (`APPROVED_DOCS_DIR`).
- `POST /ask` — `{ "question": "...", "retrieval": "hybrid", "top_k": 5 }`.
- `GET /health` — corpus count and semantic-model availability.

The API is intended for local use. Restrict ingestion and add authentication before deployment.

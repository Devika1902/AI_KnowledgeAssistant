# Enterprise AI Knowledge Assistant

A local-first prototype for answering questions from an approved document folder with page-level citations and conservative abstention.

## Prototype scope

- Extracts page text from PDFs with PyMuPDF and ingests Markdown/text files.
- Preserves page boundaries and reports source filename plus page number.
- Uses overlapping, heading-aware chunks; optional Sentence Transformers embeddings; keyword retrieval is always available.
- Combines normalized semantic and keyword scores (or runs either method alone).
- Grounds answers in retrieved passages. The included extractive answerer does not invent prose; an optional LLM adapter can be added behind the same interface.
- Refuses when evidence is weak or conflicting, and exposes retrieved evidence so users can verify it.
- Includes a command-line evaluation harness and a small, explicitly illustrative evaluation set. Expand it to at least 100 manually reviewed questions against your real approved documents before publishing quality claims.

This is a prototype, not a production authorization system. The document directory is treated as the approved corpus; access control, tenant isolation, audit retention, and identity integration must be added before deployment to multiple user groups.

## Run

Requires Python 3.11+.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[app,semantic]"
Copy-Item .env.example .env
python -m knowledge_assistant.cli ingest --source data/approved
uvicorn knowledge_assistant.api:app --reload
```

The API is at `http://127.0.0.1:8000`; OpenAPI docs are at `/docs`. To use the Streamlit interface, run `streamlit run knowledge_assistant/ui.py`.

Without the optional `semantic` extra, keyword retrieval still works. Semantic model downloads require network access on first use. PDF table extraction is not guaranteed by plain text extraction: table layouts may be flattened, so inspect extracted text and add table-aware extraction for documents where cell relationships matter.

## Evaluate

```powershell
python -m knowledge_assistant.cli evaluate --dataset eval/questions.jsonl --retrieval hybrid
```

The harness reports Recall@K, Precision@K, citation support rate, answer correctness (when labeled), abstention rate, and latency. The bundled examples are smoke-check fixtures only; they are not a 100-question manually verified benchmark. Record your human-reviewed benchmark, configuration, model version, and corpus version before comparing results.

## Design notes

- **PDF extraction:** read each page independently and retain its page index for citations. Scanned documents need OCR, which is not included.
- **Tables:** basic PDF text extraction can scramble columns and headers. Validate table-heavy sources and use a table-aware parser or OCR/layout model where needed.
- **Chunking:** chunks target about 700 characters with 100 characters overlap and split on paragraph boundaries where possible. Evaluate alternative sizes against your own questions.
- **Hybrid retrieval:** keyword matching helps exact names and identifiers; embeddings help paraphrases. Compare both separately as well as hybrid.
- **Unsupported answers:** do not call an LLM with no evidence. Return an abstention when the best score is below a configured threshold. Any future generative adapter must cite only supplied evidence and be tested for citation support.
- **Verification:** each answer includes quoted evidence, source filename, and page number.

## API

- `POST /documents/ingest` — ingest a local directory (configure `APPROVED_DOCS_DIR`).
- `POST /ask` — `{ "question": "...", "retrieval": "hybrid", "top_k": 5 }`.
- `GET /health` — readiness and corpus count.

Only administrators should be able to trigger ingestion in a deployed service. The prototype API is intended for local use.

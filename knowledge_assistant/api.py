import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .ingest import load_directory
from .qa import answer_question
from .retrieval import Retriever

load_dotenv()

DOCS = Path(os.getenv("APPROVED_DOCS_DIR", "data/approved"))
THRESHOLDS = {
    "keyword": float(os.getenv("KEYWORD_ABSTAIN_THRESHOLD", os.getenv("ABSTAIN_THRESHOLD", "0.60"))),
    "semantic": float(os.getenv("SEMANTIC_ABSTAIN_THRESHOLD", "0.50")),
    "hybrid": float(os.getenv("HYBRID_ABSTAIN_THRESHOLD", "0.50")),
}
SIZE = int(os.getenv("CHUNK_SIZE", "350"))
OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))
MODEL = os.getenv("EMBEDDING_MODEL", "")
chunks = load_directory(DOCS, SIZE, OVERLAP)
retriever = Retriever(chunks, MODEL or None)
app = FastAPI(title="Enterprise AI Knowledge Assistant", version="0.1.0")


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    retrieval: str = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)


@app.get("/health")
def health():
    return {"status": "ok", "chunks": len(chunks), "semantic_available": retriever.semantic_available,
            "semantic_error": retriever.semantic_error}


@app.post("/ask")
def ask(request: AskRequest):
    try:
        evidence = retriever.search(request.question, request.top_k, request.retrieval)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return answer_question(request.question, evidence, THRESHOLDS[request.retrieval])


@app.post("/documents/ingest")
def ingest():
    global chunks, retriever
    chunks = load_directory(DOCS, SIZE, OVERLAP)
    retriever = Retriever(chunks, MODEL or None)
    return {"ingested_chunks": len(chunks), "directory": str(DOCS)}

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .ingest import load_directory
from .qa import answer_question
from .retrieval import Retriever

DOCS = Path(os.getenv("APPROVED_DOCS_DIR", "data/approved"))
THRESHOLD = float(os.getenv("ABSTAIN_THRESHOLD", "0.12"))
SIZE = int(os.getenv("CHUNK_SIZE", "700"))
OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
chunks = load_directory(DOCS, SIZE, OVERLAP)
retriever = Retriever(chunks, MODEL)
app = FastAPI(title="Enterprise AI Knowledge Assistant", version="0.1.0")


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    retrieval: str = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)


@app.get("/health")
def health():
    return {"status": "ok", "chunks": len(chunks), "semantic_available": retriever.semantic_available}


@app.post("/ask")
def ask(request: AskRequest):
    try:
        evidence = retriever.search(request.question, request.top_k, request.retrieval)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return answer_question(request.question, evidence, THRESHOLD)


@app.post("/documents/ingest")
def ingest():
    global chunks, retriever
    chunks = load_directory(DOCS, SIZE, OVERLAP)
    retriever = Retriever(chunks, MODEL)
    return {"ingested_chunks": len(chunks), "directory": str(DOCS)}

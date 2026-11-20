from fastapi.testclient import TestClient
import json
from pathlib import Path

from knowledge_assistant import api
from knowledge_assistant.ingest import load_directory, split_text
from knowledge_assistant.models import Chunk, Evidence
from knowledge_assistant.qa import answer_question
from knowledge_assistant.retrieval import Retriever
from knowledge_assistant.cli import evaluate


def test_keyword_retrieval_uses_absolute_scores_and_ranks_relevant_chunk():
    chunks = [
        Chunk("policy", "security.md", None, "Report a security incident within 24 hours."),
        Chunk("travel", "travel.md", None, "Travel claims are reimbursed within 30 days."),
    ]
    retriever = Retriever(chunks)
    results = retriever.search("security incident report deadline", method="keyword")
    assert results[0].chunk_id == "policy"
    assert 0 < results[0].score <= 1
    assert retriever.search("quantum banana", method="keyword") == []


def test_semantic_does_not_silently_fall_back_to_keyword():
    retriever = Retriever([Chunk("x", "x.md", None, "security incident report")])
    try:
        retriever.search("security", method="semantic")
    except RuntimeError as exc:
        assert "Semantic retrieval is unavailable" in str(exc)
    else:
        assert False, "semantic retrieval must report unavailable instead of returning keyword results"


def test_unsupported_questions_abstain_without_citation():
    result = answer_question("What is the office lunch menu?", [])
    assert result["abstained"] is True
    assert result["citations"] == []


def test_grounded_answer_has_verifiable_citation():
    evidence = [Evidence("abc123", "security.md", 2, "Incidents must be reported within 24 hours.", 0.72)]
    result = answer_question("When do I report an incident?", evidence)
    assert result["abstained"] is False
    assert result["answer"] == evidence[0].text
    assert result["citations"] == [{"source": "security.md", "page": 2, "chunk_id": "abc123"}]


def test_chunking_preserves_long_content_and_validates_overlap():
    text = "A" * 1800
    parts = split_text(text, size=600, overlap=100)
    assert len(parts) >= 3
    assert all(part for part in parts)
    try:
        split_text("text", size=10, overlap=10)
    except ValueError:
        pass
    else:
        assert False, "overlap equal to chunk size must be rejected"


def test_load_directory_ignores_unsupported_files(tmp_path):
    (tmp_path / "doc.md").write_text("Approved policy text.", encoding="utf-8")
    (tmp_path / "ignore.csv").write_text("not ingested", encoding="utf-8")
    chunks = load_directory(tmp_path)
    assert len(chunks) == 1
    assert chunks[0].source == "doc.md"


def test_api_validation_and_abstention(monkeypatch):
    monkeypatch.setattr(api, "chunks", [])
    monkeypatch.setattr(api, "retriever", Retriever([]))
    client = TestClient(api.app)
    assert client.get("/health").json()["chunks"] == 0
    assert client.post("/ask", json={"question": "?"}).status_code == 422
    response = client.post("/ask", json={"question": "Which team won the moon race?", "retrieval": "keyword"})
    assert response.status_code == 200
    assert response.json()["abstained"] is True
    assert response.json()["citations"] == []


def test_api_reports_semantic_unavailable_as_503(monkeypatch):
    monkeypatch.setattr(api, "retriever", Retriever([]))
    response = TestClient(api.app).post("/ask", json={"question": "Any question?", "retrieval": "semantic"})
    assert response.status_code == 503


def test_benchmark_covers_multiple_documents_and_reports_failure_metrics():
    root = Path(__file__).resolve().parents[1]
    rows = [json.loads(line) for line in (root / "eval" / "questions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) >= 100
    assert len({source for row in rows for source in row["relevant_sources"]}) >= 5
    assert sum(row["answerable"] is False for row in rows) >= 10
    results = evaluate(root / "eval" / "questions.jsonl", root / "data" / "approved", "keyword", 5)
    assert results["questions"] == len(rows)
    assert results["corpus_chunks"] > 5
    assert "unsupported_answer_rate" in results
    assert results["threshold_sweep"]

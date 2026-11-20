import argparse
import json
import statistics
import time
from pathlib import Path

from .ingest import load_directory
from .qa import answer_question
from .retrieval import Retriever


def evaluate(dataset: Path, corpus: Path, method: str, top_k: int) -> dict:
    chunks = load_directory(corpus)
    retriever = Retriever(chunks)
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    recall, precision, citation, correctness, abstentions, abstained_results, latencies = [], [], [], [], [], [], []
    for row in rows:
        start = time.perf_counter()
        found = retriever.search(row["question"], top_k, method)
        result = answer_question(row["question"], found)
        abstained_results.append(int(result["abstained"]))
        latencies.append((time.perf_counter() - start) * 1000)
        expected = set(row.get("relevant_sources", []))
        actual = {e.source for e in found}
        if expected:
            recall.append(len(expected & actual) / len(expected))
            precision.append(len(expected & actual) / max(1, len(actual)))
        if row.get("answerable") is not None:
            abstentions.append(int(result["abstained"] == (not row["answerable"])))
        if row.get("expected_answer"):
            correctness.append(int(row["expected_answer"].casefold() in result["answer"].casefold()))
        if expected:
            citation.append(int(bool(result["citations"]) and result["citations"][0]["source"] in expected))
    mean = lambda xs: round(statistics.mean(xs), 4) if xs else None
    return {"questions": len(rows), "retrieval": method, "top_k": top_k, "recall_at_k": mean(recall), "precision_at_k": mean(precision), "citation_support_rate": mean(citation), "answer_correctness_exact_substring": mean(correctness), "abstention_decision_accuracy": mean(abstentions), "abstention_rate": mean(abstained_results), "latency_ms_mean": mean(latencies), "latency_ms_p95": round(sorted(latencies)[min(len(latencies)-1, int(len(latencies)*0.95))], 2) if latencies else None}


def main():
    parser = argparse.ArgumentParser(description="Ingest and evaluate the knowledge assistant")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--source", default="data/approved")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--dataset", default="eval/questions.jsonl")
    ev.add_argument("--corpus", default="data/approved")
    ev.add_argument("--retrieval", choices=["keyword", "semantic", "hybrid"], default="hybrid")
    ev.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if args.command == "ingest":
        chunks = load_directory(args.source)
        print(f"Loaded {len(chunks)} chunks from {args.source}")
    else:
        print(json.dumps(evaluate(Path(args.dataset), Path(args.corpus), args.retrieval, args.top_k), indent=2))


if __name__ == "__main__":
    main()

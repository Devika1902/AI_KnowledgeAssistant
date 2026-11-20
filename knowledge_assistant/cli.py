import argparse
import json
import math
import statistics
import time
from pathlib import Path

from .ingest import load_directory
from .qa import answer_question
from .retrieval import Retriever


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 4) if values else None


def evaluate(dataset: Path, corpus: Path, method: str, top_k: int, embedding_model: str | None = None,
             chunk_size: int = 350, chunk_overlap: int = 80) -> dict:
    chunks = load_directory(corpus, chunk_size, chunk_overlap)
    retriever = Retriever(chunks, embedding_model if method in {"semantic", "hybrid"} else None)
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError(f"Evaluation dataset is empty: {dataset}")
    recall, precision, citation, correctness, decision, latency, failures = [], [], [], [], [], [], []
    abstained_count = 0
    decision_scores: list[tuple[bool, float]] = []
    unsupported_accepts = 0
    unsupported_total = 0
    for row in rows:
        question = row["question"]
        start = time.perf_counter()
        found = retriever.search(question, top_k, method)
        default_threshold = {"keyword": 0.60, "semantic": 0.50, "hybrid": 0.50}[method]
        result = answer_question(question, found, float(row.get("abstain_threshold", default_threshold)))
        latency.append((time.perf_counter() - start) * 1000)
        abstained_count += int(result["abstained"])
        expected_sources = set(row.get("relevant_sources", []))
        expected_answer = row.get("expected_answer")
        answerable = row.get("answerable")
        if answerable is not None:
            decision_scores.append((bool(answerable), found[0].score if found else 0.0))
        if answerable is False:
            unsupported_total += 1
            unsupported_accepts += int(not result["abstained"])
        if expected_sources:
            relevant_phrases = [item for item in chunks if item.source in expected_sources and expected_answer
                                and expected_answer.casefold() in item.text.casefold()]
            relevant_ids = {item.chunk_id for item in relevant_phrases}
            retrieved_ids = {item.chunk_id for item in found}
            recall_value = len(relevant_ids & retrieved_ids) / max(1, len(relevant_ids))
            relevant_hits = sum(item.chunk_id in relevant_ids for item in found)
            precision_value = relevant_hits / max(1, top_k)
            recall.append(recall_value)
            precision.append(precision_value)
        if expected_answer:
            answer_ok = expected_answer.casefold() in result["answer"].casefold()
            correctness.append(int(answer_ok))
        else:
            answer_ok = None
        if answerable is not None:
            decision_ok = result["abstained"] == (not answerable)
            decision.append(int(decision_ok))
            cites = result["citations"]
            if answerable:
                citation_ok = bool(cites) and cites[0]["source"] in expected_sources
                if citation_ok and expected_answer:
                    lead = next((item for item in found if item.chunk_id == cites[0]["chunk_id"]), None)
                    citation_ok = bool(lead and expected_answer.casefold() in lead.text.casefold())
            else:
                citation_ok = not cites
            citation.append(int(citation_ok))
            if not decision_ok or (answerable and not citation_ok) or (answer_ok is False):
                failures.append({
                    "id": row.get("id"),
                    "question": question,
                    "answerable": answerable,
                    "abstained": result["abstained"],
                    "citation_ok": citation_ok,
                    "answer_ok": answer_ok,
                    "top_source": found[0].source if found else None,
                    "top_score": round(found[0].score, 4) if found else 0.0,
                })

    ordered_latency = sorted(latency)
    threshold_sweep = []
    for threshold in (0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60):
        tp = sum(answerable and score >= threshold for answerable, score in decision_scores)
        fn = sum(answerable and score < threshold for answerable, score in decision_scores)
        tn = sum(not answerable and score < threshold for answerable, score in decision_scores)
        fp = sum(not answerable and score >= threshold for answerable, score in decision_scores)
        threshold_sweep.append({
            "threshold": threshold,
            "decision_accuracy": round((tp + tn) / max(1, len(decision_scores)), 4),
            "unsupported_answer_rate": round(fp / max(1, fp + tn), 4),
            "answerable_abstention_rate": round(fn / max(1, fn + tp), 4),
        })
    return {
        "questions": len(rows), "corpus_chunks": len(chunks), "retrieval": method, "top_k": top_k,
        "recall_at_k": _mean(recall), "precision_at_k": _mean(precision),
        "citation_accuracy": _mean(citation), "answer_correctness_exact_substring": _mean(correctness),
        "abstention_decision_accuracy": _mean(decision), "abstention_rate": round(abstained_count / len(rows), 4),
        "unsupported_answer_rate": round(unsupported_accepts / max(1, unsupported_total), 4),
        "latency_ms_mean": _mean(latency),
        "latency_ms_p95": round(ordered_latency[min(len(ordered_latency) - 1, math.ceil(0.95 * len(ordered_latency)) - 1)], 2),
        "failure_count": len(failures), "threshold_sweep": threshold_sweep, "failures": failures,
    }


def main():
    parser = argparse.ArgumentParser(description="Ingest and evaluate the knowledge assistant")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest")
    ingest.add_argument("--source", default="data/approved")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--dataset", default="eval/questions.jsonl")
    ev.add_argument("--corpus", default="data/approved")
    ev.add_argument("--retrieval", choices=["keyword", "semantic", "hybrid", "compare"], default="compare")
    ev.add_argument("--top-k", type=int, default=5)
    ev.add_argument("--embedding-model", default="sentence-transformers/all-MiniLM-L6-v2")
    ev.add_argument("--chunk-size", type=int, default=350)
    ev.add_argument("--chunk-overlap", type=int, default=80)
    args = parser.parse_args()
    if args.command == "ingest":
        chunks = load_directory(args.source)
        print(f"Loaded {len(chunks)} chunks from {args.source}")
    else:
        methods = ["keyword", "semantic", "hybrid"] if args.retrieval == "compare" else [args.retrieval]
        results = {}
        failure_reports = {}
        for method in methods:
            try:
                results[method] = evaluate(Path(args.dataset), Path(args.corpus), method, args.top_k,
                                           args.embedding_model, args.chunk_size, args.chunk_overlap)
                failure_reports[method] = results[method].pop("failures", [])
            except RuntimeError as exc:
                results[method] = {"status": "unavailable", "reason": str(exc)}
        Path("eval/results").mkdir(parents=True, exist_ok=True)
        out = Path("eval/results/comparison.json")
        out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        (out.parent / "failures.json").write_text(json.dumps(failure_reports, indent=2), encoding="utf-8")
        print(json.dumps(results, indent=2))
        print(f"Saved comparison to {out}")


if __name__ == "__main__":
    main()

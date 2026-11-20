from .models import Evidence


def answer_question(question: str, evidence: list[Evidence], threshold: float = 0.12) -> dict:
    if not evidence or evidence[0].score < threshold:
        return {"answer": "I could not find enough evidence in the approved documents to answer this question.", "abstained": True, "citations": [], "evidence": [e.as_dict() for e in evidence]}
    # Extractive prototype: return source passage verbatim, avoiding unsupported synthesis.
    lead = evidence[0]
    citation = {"source": lead.source, "page": lead.page, "chunk_id": lead.chunk_id}
    return {"answer": lead.text, "abstained": False, "citations": [citation], "evidence": [e.as_dict() for e in evidence]}

from .models import Evidence

ABSTENTION = "I could not find enough evidence in the approved documents to answer this question."


def answer_question(question: str, evidence: list[Evidence], threshold: float = 0.28) -> dict:
    """Return only quoted source text, or abstain below an absolute score threshold."""
    if not evidence or evidence[0].score < threshold:
        return {
            "answer": ABSTENTION,
            "abstained": True,
            "confidence": evidence[0].score if evidence else 0.0,
            "citations": [],
            "evidence": [item.as_dict() for item in evidence],
        }
    lead = evidence[0]
    citation = {"source": lead.source, "page": lead.page, "chunk_id": lead.chunk_id}
    return {
        "answer": lead.text,
        "abstained": False,
        "confidence": lead.score,
        "citations": [citation],
        "evidence": [item.as_dict() for item in evidence],
    }

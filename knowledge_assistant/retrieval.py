import math
import re
from collections import Counter

from .models import Chunk, Evidence

TOKEN_RE = re.compile(r"[\w'-]+", re.UNICODE)


def tokens(text: str) -> list[str]:
    return [t.casefold() for t in TOKEN_RE.findall(text)]


class Retriever:
    def __init__(self, chunks: list[Chunk], embedding_model: str | None = None):
        self.chunks = chunks
        self._vectors = None
        self._model = None
        if embedding_model:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(embedding_model)
                self._vectors = self._model.encode([c.text for c in chunks], normalize_embeddings=True) if chunks else []
            except ImportError:
                pass

    @property
    def semantic_available(self) -> bool:
        return self._model is not None

    def search(self, query: str, top_k: int = 5, method: str = "hybrid") -> list[Evidence]:
        if method not in {"hybrid", "keyword", "semantic"}:
            raise ValueError("retrieval must be hybrid, keyword, or semantic")
        if method == "semantic" and not self.semantic_available:
            method = "keyword"
        qtokens = set(tokens(query))
        docs = [set(tokens(c.text)) for c in self.chunks]
        df = Counter(t for doc in docs for t in doc)
        kw = []
        for doc in docs:
            overlap = qtokens & doc
            kw.append(sum(math.log(1 + len(docs) / (1 + df[t])) for t in overlap) / max(1, len(qtokens)))
        max_kw = max(kw, default=0) or 1
        kw = [v / max_kw for v in kw]
        sem = [0.0] * len(self.chunks)
        if self.semantic_available and self.chunks:
            import numpy as np
            query_vec = self._model.encode([query], normalize_embeddings=True)[0]
            sem = np.asarray(self._vectors) @ query_vec
            sem = [max(0.0, float(v)) for v in sem]
            max_sem = max(sem, default=0) or 1
            sem = [v / max_sem for v in sem]
        scored = []
        for i, chunk in enumerate(self.chunks):
            score = kw[i] if method == "keyword" or not self.semantic_available else sem[i] if method == "semantic" else 0.55 * sem[i] + 0.45 * kw[i]
            if score > 0:
                scored.append(Evidence(chunk.chunk_id, chunk.source, chunk.page, chunk.text, float(score)))
        return sorted(scored, key=lambda x: (-x.score, x.source, x.page or 0))[:max(1, top_k)]

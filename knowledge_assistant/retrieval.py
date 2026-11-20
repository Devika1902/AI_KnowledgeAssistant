import math
import re
from collections import Counter

from .models import Chunk, Evidence

TOKEN_RE = re.compile(r"[\w'-]+", re.UNICODE)


def tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text)]


class Retriever:
    """BM25 keyword search, embedding cosine search, and a fixed 50/50 hybrid.

    Scores are corpus-independent confidence proxies in [0, 1]; they are not
    probabilities. In particular, they are never divided by the best result
    in the current query, which used to make every query look confident.
    """

    def __init__(self, chunks: list[Chunk], embedding_model: str | None = None):
        self.chunks = chunks
        self._tokens = [tokens(chunk.text) for chunk in chunks]
        self._model = None
        self._vectors = None
        self.semantic_error: str | None = None
        if embedding_model:
            try:
                from sentence_transformers import SentenceTransformer
                import numpy as np

                self._model = SentenceTransformer(embedding_model)
                if chunks:
                    self._vectors = np.asarray(
                        self._model.encode([c.text for c in chunks], normalize_embeddings=True)
                    )
                else:
                    self._vectors = np.empty((0, 0))
            except Exception as exc:
                self.semantic_error = str(exc)

        self._df = Counter(token for document in self._tokens for token in set(document))
        self._avgdl = sum(map(len, self._tokens)) / max(1, len(self._tokens))

    @property
    def semantic_available(self) -> bool:
        return self._model is not None

    def _keyword_scores(self, query_tokens: list[str]) -> list[float]:
        if not query_tokens or not self.chunks:
            return [0.0] * len(self.chunks)
        n = len(self.chunks)
        k1, b = 1.5, 0.75
        scores = []
        for document in self._tokens:
            counts = Counter(document)
            length = len(document)
            score = 0.0
            for term in set(query_tokens):
                frequency = counts[term]
                if not frequency:
                    continue
                idf = math.log(1 + (n - self._df[term] + 0.5) / (self._df[term] + 0.5))
                denominator = frequency + k1 * (1 - b + b * length / max(1, self._avgdl))
                score += idf * frequency * (k1 + 1) / denominator
            # Saturation keeps the score bounded without query-relative scaling.
            scores.append(score / (score + 2.5) if score else 0.0)
        return scores

    def _semantic_scores(self, query: str) -> list[float]:
        if not self.semantic_available:
            reason = f": {self.semantic_error}" if self.semantic_error else ""
            raise RuntimeError("Semantic retrieval is unavailable; install the semantic extra and load the model" + reason)
        if not self.chunks:
            return []
        import numpy as np

        vector = self._model.encode([query], normalize_embeddings=True)[0]
        similarities = np.asarray(self._vectors) @ vector
        # Keep absolute cosine values: unrelated passages must not be shifted to 0.5.
        return [max(0.0, min(1.0, float(value))) for value in similarities]

    def search(self, query: str, top_k: int = 5, method: str = "hybrid") -> list[Evidence]:
        if method not in {"hybrid", "keyword", "semantic"}:
            raise ValueError("retrieval must be hybrid, keyword, or semantic")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        keyword = self._keyword_scores(tokens(query))
        semantic = self._semantic_scores(query) if method in {"semantic", "hybrid"} else [0.0] * len(self.chunks)
        if method == "keyword":
            scores = keyword
        elif method == "semantic":
            scores = semantic
        else:
            if not self.semantic_available:
                raise RuntimeError("Hybrid retrieval requires semantic embeddings; use keyword mode or install the semantic extra")
            scores = [0.5 * kw + 0.5 * sem for kw, sem in zip(keyword, semantic)]

        ranked = [
            Evidence(chunk.chunk_id, chunk.source, chunk.page, chunk.text, float(score))
            for chunk, score in zip(self.chunks, scores)
            if score > 0
        ]
        return sorted(ranked, key=lambda item: (-item.score, item.source, item.page or 0, item.chunk_id))[:top_k]

from pathlib import Path
import hashlib
import re

from .models import Chunk


def read_pages(path: Path) -> list[tuple[int | None, str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("Install the app extra to read PDFs: pip install -e '.[app]'") from exc
        with fitz.open(path) as document:
            return [(i + 1, page.get_text("text")) for i, page in enumerate(document)]
    if suffix in {".txt", ".md"}:
        return [(None, path.read_text(encoding="utf-8", errors="replace"))]
    return []


def split_text(text: str, size: int = 700, overlap: int = 100) -> list[str]:
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError("Require size > overlap >= 0")
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paras:
        # Long paragraphs are split on sentence/space boundaries instead of being dropped.
        pieces = [para[i:i + size] for i in range(0, len(para), size)] if len(para) > size else [para]
        for piece in pieces:
            candidate = f"{current} {piece}".strip()
            if current and len(candidate) > size:
                chunks.append(current)
                current = current[-overlap:] + " " + piece if overlap else piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def load_directory(directory: str | Path, size: int = 700, overlap: int = 100) -> list[Chunk]:
    root = Path(directory)
    if not root.exists():
        return []
    result: list[Chunk] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".pdf", ".txt", ".md"}:
            continue
        for page, text in read_pages(path):
            for index, part in enumerate(split_text(text, size, overlap)):
                key = f"{path.relative_to(root).as_posix()}:{page}:{index}:{part}"
                chunk_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
                result.append(Chunk(chunk_id, path.relative_to(root).as_posix(), page, part))
    return result

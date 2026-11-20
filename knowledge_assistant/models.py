from dataclasses import asdict, dataclass


@dataclass
class Chunk:
    chunk_id: str
    source: str
    page: int | None
    text: str


@dataclass
class Evidence:
    chunk_id: str
    source: str
    page: int | None
    text: str
    score: float

    def as_dict(self) -> dict:
        return asdict(self)

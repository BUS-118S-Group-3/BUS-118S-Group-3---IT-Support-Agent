"""Query interface over the ChromaDB index.

The retriever returns dicts of {text, source, section, score} so the
Knowledge Agent can surface citations with the same shape regardless of
which vector DB is behind it.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from langchain_openai import OpenAIEmbeddings

from config import settings, require_openai_key
from rag.ingest import get_chroma_client


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    source: str
    section: str
    score: float

    def cite(self) -> str:
        """Short citation string suitable for inline use."""
        return f"{self.source} § {self.section}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "section": self.section,
            "score": self.score,
        }


@lru_cache(maxsize=1)
def _embedder() -> OpenAIEmbeddings:
    require_openai_key()
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )


@lru_cache(maxsize=1)
def _collection():
    client = get_chroma_client()
    return client.get_or_create_collection(name=settings.collection_name)


def retrieve(query: str, k: int | None = None) -> list[RetrievedChunk]:
    """Return up to ``k`` most relevant chunks for ``query``."""
    if not query.strip():
        return []
    k = k or settings.top_k

    coll = _collection()
    if coll.count() == 0:
        raise RuntimeError(
            "Vector store is empty. Run `python -m rag.ingest` first."
        )

    [vec] = _embedder().embed_documents([query])
    res = coll.query(
        query_embeddings=[vec],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]

    chunks: list[RetrievedChunk] = []
    for text, meta, dist in zip(docs, metas, dists):
        chunks.append(
            RetrievedChunk(
                text=text,
                source=(meta or {}).get("source", "unknown"),
                section=(meta or {}).get("section", ""),
                # Chroma returns a distance; convert to a [0,1] similarity-ish score
                score=max(0.0, 1.0 - float(dist)),
            )
        )
    return chunks


def format_for_prompt(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks into a prompt-ready string with explicit citations."""
    if not chunks:
        return "(no policy chunks retrieved)"
    blocks = []
    for i, c in enumerate(chunks, start=1):
        blocks.append(
            f"[{i}] ({c.cite()})\n{c.text.strip()}"
        )
    return "\n\n".join(blocks)

"""Build (or rebuild) the ChromaDB index from the markdown knowledge base.

Run with:    python -m rag.ingest

We deliberately use a header-aware chunker: each markdown section becomes
its own chunk. This makes the citations the agent surfaces actually
useful — they line up with policy section numbers ("Rule SoX-1", etc.)
rather than arbitrary character windows.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings

from config import settings, require_openai_key


def _iter_chunks(text: str, source: str) -> Iterable[dict]:
    """Split a markdown document by H2/H3 headers; fall back to size-based
    chunking only if a section is huge."""
    # Split on H2 ("## ") and H3 ("### ") boundaries while keeping the heading
    sections = re.split(r"(?m)^(?=#{2,3}\s)", text)
    sections = [s.strip() for s in sections if s.strip()]
    chunk_size = settings.chunk_size

    for sec in sections:
        first_line = sec.splitlines()[0].strip()
        heading = first_line.lstrip("#").strip() or source
        if len(sec) <= chunk_size:
            yield {"text": sec, "source": source, "section": heading}
            continue
        # Long section: window it
        for i in range(0, len(sec), chunk_size - settings.chunk_overlap):
            piece = sec[i : i + chunk_size]
            yield {"text": piece, "source": source, "section": heading}


def load_corpus() -> list[dict]:
    docs: list[dict] = []
    for md_path in sorted(settings.kb_dir.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        docs.extend(_iter_chunks(text, source=md_path.name))
    return docs


def get_chroma_client() -> chromadb.api.client.Client:
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(settings.chroma_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def build_index(reset: bool = True) -> int:
    require_openai_key()
    client = get_chroma_client()

    if reset:
        try:
            client.delete_collection(settings.collection_name)
        except Exception:
            pass

    collection = client.get_or_create_collection(name=settings.collection_name)

    docs = load_corpus()
    if not docs:
        raise RuntimeError(
            f"No markdown files found in {settings.kb_dir!s}. "
            "Add policy files to knowledge_base/ and re-run."
        )

    embedder = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )
    vectors = embedder.embed_documents([d["text"] for d in docs])

    ids = [f"{d['source']}::{i}" for i, d in enumerate(docs)]
    metadatas = [{"source": d["source"], "section": d["section"]} for d in docs]
    collection.add(
        ids=ids,
        documents=[d["text"] for d in docs],
        embeddings=vectors,
        metadatas=metadatas,
    )
    return len(docs)


def main() -> int:
    try:
        n = build_index(reset=True)
    except Exception as exc:
        print(f"[ingest] failed: {exc}", file=sys.stderr)
        return 1
    print(f"[ingest] indexed {n} chunks into '{settings.collection_name}' "
          f"at {settings.chroma_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

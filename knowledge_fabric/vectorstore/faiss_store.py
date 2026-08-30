"""Persistent local vector store with safe UTF-8 JSON + NumPy serialization.

No pickle is used for persisted application state. FAISS remains an optional
in-memory accelerator; the portable source of truth is JSON metadata + NPZ
vectors.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from knowledge_fabric.types import Chunk, RankedChunk

try:
    import faiss  # type: ignore
except Exception:
    faiss = None


class FaissVectorStore:
    def __init__(self, dimension: int, index_path: str):
        self.dimension = dimension
        self.index_path = Path(index_path)
        self.meta_path = self.index_path.with_suffix(".meta.json")
        self.vector_path = self.index_path.with_suffix(".vectors.npz")
        self.index = None
        self.chunks: list[Chunk] = []
        self._vectors = np.empty((0, dimension), dtype="float32")
        self._id_to_pos: dict[str, int] = {}
        if self.meta_path.exists() and self.vector_path.exists():
            self.load()

    def replace_all(self, chunks, vectors):
        mat = np.asarray(vectors, dtype="float32")
        if len(chunks) and (mat.ndim != 2 or mat.shape[1] != self.dimension):
            raise ValueError(f"Expected vectors with dimension {self.dimension}, got {mat.shape}")
        self.chunks = list(chunks)
        self._vectors = _normalize(mat.copy()) if len(chunks) else np.empty((0, self.dimension), dtype="float32")
        self._rebuild_index()

    def upsert(self, chunks, vectors):
        if not chunks:
            return
        mat = np.asarray(vectors, dtype="float32")
        if mat.ndim != 2 or mat.shape[1] != self.dimension:
            raise ValueError(f"Expected vectors with dimension {self.dimension}, got {mat.shape}")
        mat = _normalize(mat)
        merged = {c.chunk_id: (c, self._vector_at(i)) for i, c in enumerate(self.chunks)}
        for c, v in zip(chunks, mat):
            merged[c.chunk_id] = (c, v)
        self.chunks = [x[0] for x in merged.values()]
        self._vectors = np.vstack([x[1] for x in merged.values()]).astype("float32") if merged else np.empty((0, self.dimension), dtype="float32")
        self._rebuild_index()

    def remove_items(self, item_ids):
        ids = set(item_ids)
        keep = [(c, self._vector_at(i)) for i, c in enumerate(self.chunks) if c.item_id not in ids]
        self.chunks = [x[0] for x in keep]
        self._vectors = np.vstack([x[1] for x in keep]).astype("float32") if keep else np.empty((0, self.dimension), dtype="float32")
        self._rebuild_index()

    def _vector_at(self, pos):
        return self._vectors[pos]

    def _rebuild_index(self):
        self._id_to_pos = {c.chunk_id: i for i, c in enumerate(self.chunks)}
        if faiss:
            self.index = faiss.IndexFlatIP(self.dimension)
            if len(self._vectors):
                self.index.add(_normalize(self._vectors.copy()))
        else:
            self.index = None

    def search(self, query_vector, top_k=10, allowed_chunk_ids=None):
        if not self.chunks:
            return []
        q = _normalize(np.asarray(query_vector, dtype="float32").reshape(1, -1))[0]
        limit = min(max(top_k * 3, top_k), len(self.chunks))
        if faiss and self.index is not None:
            scores, positions = self.index.search(q.reshape(1, -1), limit)
            ranked = [(int(pos), float(score)) for score, pos in zip(scores[0], positions[0]) if pos >= 0]
        else:
            scores = self._vectors @ q
            ranked = sorted(enumerate(scores.tolist()), key=lambda x: -x[1])[:limit]
        out, seen = [], set()
        for pos, score in ranked:
            c = self.chunks[pos]
            if allowed_chunk_ids is not None and c.chunk_id not in allowed_chunk_ids:
                continue
            if c.chunk_id in seen:
                continue
            seen.add(c.chunk_id)
            out.append(RankedChunk(c, score))
            if len(out) >= top_k:
                break
        return out

    def save(self):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = []
        for c in self.chunks:
            payload.append({
                "chunk_id": c.chunk_id, "source_id": c.source_id, "item_id": c.item_id,
                "text": c.text, "symbol": c.symbol, "language": c.language,
                "content_hash": c.content_hash, "sensitivity": c.sensitivity, "extra": c.extra,
            })
        tmp_meta = self.meta_path.with_suffix(".tmp")
        tmp_vec = self.vector_path.with_suffix(".tmp.npz")
        # Explicit UTF-8 is required on Windows, where the process default is
        # commonly cp1252 and GitHub repositories frequently contain Unicode.
        tmp_meta.write_text(
            json.dumps({"version": 2, "dimension": self.dimension, "chunks": payload}, ensure_ascii=False),
            encoding="utf-8",
        )
        np.savez_compressed(tmp_vec, vectors=self._vectors)
        tmp_meta.replace(self.meta_path)
        tmp_vec.replace(self.vector_path)
        self.index_path.write_text("Knowledge Fabric vector index v2\n", encoding="utf-8")

    def load(self):
        meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        if int(meta.get("dimension", self.dimension)) != self.dimension:
            raise ValueError("Vector index dimension does not match configured embedder")
        self.chunks = [Chunk(**x) for x in meta.get("chunks", [])]
        with np.load(self.vector_path, allow_pickle=False) as data:
            self._vectors = np.asarray(data["vectors"], dtype="float32")
        if len(self.chunks) != len(self._vectors):
            raise ValueError("Vector index metadata/vector count mismatch")
        self._rebuild_index()

    def all_content_hashes(self):
        out = {}
        for chunk in self.chunks:
            h = chunk.extra.get("parent_content_hash")
            if h:
                out[chunk.item_id] = h
        return out

    def chunk_hashes_by_id(self):
        return {c.chunk_id: c.content_hash for c in self.chunks}


def _normalize(mat):
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms

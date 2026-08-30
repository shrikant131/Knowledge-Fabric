"""Dependency-light local TF-IDF embedding backend.

This is lexical retrieval, not a semantic transformer. State is persisted as
JSON rather than pickle so a local index cannot execute arbitrary code when
loaded.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from knowledge_fabric.embeddings.base import Embedder

class LocalTfidfEmbedder(Embedder):
    def __init__(self, dimension=512, state_path=None):
        self.dimension = dimension
        self.state_path = Path(state_path) if state_path else None
        self._vectorizer = TfidfVectorizer(max_features=dimension, stop_words="english")
        self._fitted = False
        if self.state_path and self.state_path.exists():
            self._load()

    def fit(self, corpus):
        self._vectorizer.fit(corpus or ["empty knowledge base"])
        self._fitted = True
        self._save()

    def embed(self, texts):
        if not self._fitted:
            self.fit(texts)
        matrix = self._vectorizer.transform(texts).toarray().astype("float32")
        if matrix.shape[1] < self.dimension:
            matrix = np.pad(matrix, ((0, 0), (0, self.dimension - matrix.shape[1])))
        elif matrix.shape[1] > self.dimension:
            matrix = matrix[:, :self.dimension]
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    def _save(self):
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        vocab = {str(k): int(v) for k,v in self._vectorizer.vocabulary_.items()}
        idf = [float(x) for x in self._vectorizer.idf_] if self._fitted else []
        self.state_path.write_text(json.dumps({
            "version": 1, "dimension": self.dimension, "fitted": self._fitted,
            "vocabulary": vocab, "idf": idf,
            "token_pattern": self._vectorizer.token_pattern,
            "lowercase": self._vectorizer.lowercase,
            "stop_words": "english",
        }), encoding="utf-8")

    def _load(self):
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        if int(data.get("dimension", self.dimension)) != self.dimension:
            raise ValueError("Local embedding state dimension mismatch")
        vocab = {str(k): int(v) for k, v in (data.get("vocabulary") or {}).items()}
        self._vectorizer = TfidfVectorizer(max_features=self.dimension,
                                           stop_words=data.get("stop_words", "english"),
                                           token_pattern=data.get("token_pattern", r"(?u)\b\w\w+\b"),
                                           lowercase=bool(data.get("lowercase", True)),
                                           vocabulary=vocab)
        if data.get("fitted") and vocab:
            # Initialize sklearn internals with the exact vocabulary, then
            # restore the learned IDF values without executing serialized code.
            self._vectorizer.fit([" ".join(vocab.keys())])
            idf=np.asarray(data.get("idf") or [], dtype=float)
            if len(idf) != len(vocab):
                raise ValueError("Invalid persisted TF-IDF state")
            self._vectorizer._tfidf.idf_=idf
            self._vectorizer._tfidf._idf_diag=__import__("scipy").sparse.diags(idf, offsets=0)
            self._fitted=True
        else:
            self._fitted = False

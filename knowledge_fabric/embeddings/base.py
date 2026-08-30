from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class Embedder(ABC):
    dimension: int

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (N, dimension) float32 array of embeddings."""

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]

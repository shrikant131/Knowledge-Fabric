import numpy as np

from knowledge_fabric.cache.semantic_cache import CacheEntry, SemanticCache


def test_cache_miss_when_empty(tmp_path):
    cache = SemanticCache(dimension=4, cache_path=str(tmp_path / "cache.pkl"))
    result = cache.lookup(np.array([1.0, 0.0, 0.0, 0.0]), current_hashes={})
    assert result is None


def test_cache_hit_on_similar_vector(tmp_path):
    cache = SemanticCache(dimension=4, cache_path=str(tmp_path / "cache.pkl"), similarity_threshold=0.9)
    vec = np.array([1.0, 0.0, 0.0, 0.0])
    entry = CacheEntry(query="q", answer="a", retrieved=[], chunk_hashes={"c1": "hash1"})
    cache.write(vec, entry)

    # near-identical vector should hit
    similar = np.array([0.99, 0.01, 0.0, 0.0])
    result = cache.lookup(similar, current_hashes={"c1": "hash1"})
    assert result is not None
    assert result.answer == "a"


def test_cache_miss_on_dissimilar_vector(tmp_path):
    cache = SemanticCache(dimension=4, cache_path=str(tmp_path / "cache.pkl"), similarity_threshold=0.9)
    cache.write(np.array([1.0, 0.0, 0.0, 0.0]), CacheEntry(query="q", answer="a", retrieved=[], chunk_hashes={}))

    dissimilar = np.array([0.0, 1.0, 0.0, 0.0])
    result = cache.lookup(dissimilar, current_hashes={})
    assert result is None


def test_cache_invalidated_when_cited_chunk_changes(tmp_path):
    cache = SemanticCache(dimension=4, cache_path=str(tmp_path / "cache.pkl"), similarity_threshold=0.9)
    vec = np.array([1.0, 0.0, 0.0, 0.0])
    entry = CacheEntry(query="q", answer="a", retrieved=[], chunk_hashes={"c1": "old_hash"})
    cache.write(vec, entry)

    # chunk c1 has since changed content (different hash in "current_hashes")
    result = cache.lookup(vec, current_hashes={"c1": "new_hash"})
    assert result is None


def test_cache_persists_across_instances(tmp_path):
    path = str(tmp_path / "cache.pkl")
    cache1 = SemanticCache(dimension=4, cache_path=path, similarity_threshold=0.9)
    vec = np.array([1.0, 0.0, 0.0, 0.0])
    cache1.write(vec, CacheEntry(query="q", answer="persisted answer", retrieved=[], chunk_hashes={}))

    cache2 = SemanticCache(dimension=4, cache_path=path, similarity_threshold=0.9)
    result = cache2.lookup(vec, current_hashes={})
    assert result is not None
    assert result.answer == "persisted answer"

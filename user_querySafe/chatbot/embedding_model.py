"""
Singleton module for SentenceTransformer embedding model.
Loaded lazily on first use to avoid duplicate loading across modules.
"""
import threading

_model = None
_lock = threading.Lock()


def get_embedding_model():
    """Return the shared SentenceTransformer instance, loading it on first call."""
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model

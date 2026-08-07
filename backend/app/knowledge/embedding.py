"""Generate dense vector embeddings for text chunks."""

import logging
import time
from functools import lru_cache

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 384
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


@lru_cache(maxsize=1)
def _get_model():
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    return [list(vector) for vector in model.embed(texts)]


def warm_up() -> bool:
    """Load and initialize the embedding model before it is first needed.

    Without this, the model is constructed lazily on the first upload or RAG
    query. On a host that spins down when idle, that means a visitor's first
    grounded question pays the full download-and-initialize cost — measured at
    over four minutes on a cold Render instance, against ~2.3s once warm.

    A single throwaway embed is issued deliberately: constructing
    ``TextEmbedding`` does not build the ONNX inference session, so without it
    the first real call would still absorb that cost.

    Returns True when the model is ready. Never raises — an instance that
    cannot embed should still serve auth, chat, and observability, and the
    failure will resurface with a clear error at the actual call site.
    """
    started = time.perf_counter()
    try:
        model = _get_model()
        # Forces session creation and the first allocation.
        list(model.embed(["warmup"]))
    except Exception as exc:  # noqa: BLE001 — startup must never be fatal here
        elapsed = time.perf_counter() - started
        logger.warning(
            "Embedding model warm-up failed after %.1fs (%s: %s). "
            "Retrieval and document ingestion will retry on first use.",
            elapsed,
            type(exc).__name__,
            exc,
        )
        return False

    logger.info(
        "Embedding model '%s' warm and ready in %.1fs",
        EMBEDDING_MODEL,
        time.perf_counter() - started,
    )
    return True

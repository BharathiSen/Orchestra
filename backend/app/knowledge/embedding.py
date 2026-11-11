"""Generate dense vector embeddings for text chunks."""

import logging
import threading
import time

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 384
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

_model = None
_model_lock = threading.Lock()
# "lazy" until something asks for the model, then "warming" -> "ready" | "failed".
# Read by /health/ready; informational only.
status = "lazy"


def _get_model():
    """Return the embedding model, fully initialised, building it at most once.

    Warm-up runs in a background thread so the API can answer while the model
    downloads. A grounded request that arrives meanwhile waits on this lock for
    the same build instead of starting a second download.
    """
    global _model, status
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        status = "warming"
        try:
            from fastembed import TextEmbedding

            model = TextEmbedding(model_name=EMBEDDING_MODEL)
            # Constructing TextEmbedding does not build the ONNX inference
            # session; one throwaway embed does, so no caller pays for it.
            list(model.embed(["warmup"]))
        except Exception:
            status = "failed"
            raise
        _model = model
        status = "ready"
        return _model


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

    Runs in a background thread (see ``app.main.lifespan``): with an empty
    model cache, as on a free-tier instance waking from sleep, the download
    alone measured ~28s, and blocking startup on it kept even ``/health/live``
    unreachable for the whole time.

    Returns True when the model is ready. Never raises — an instance that
    cannot embed should still serve auth, chat, and observability, and the
    failure will resurface with a clear error at the actual call site.
    """
    started = time.perf_counter()
    try:
        _get_model()
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

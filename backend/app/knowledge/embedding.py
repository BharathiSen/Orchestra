"""Generate dense vector embeddings for text chunks."""

from functools import lru_cache

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

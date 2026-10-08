import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
_model = None

def get_model():
    global _model
    if _model is None:
        print(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def create_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    emb = get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return emb.tolist()

def create_embedding(text: str) -> list[float]:
    return create_embeddings([text])[0]
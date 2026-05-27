import os
import json
import time
import math
import re
from collections import Counter
import numpy as np
import pymongo
import requests
from bson import ObjectId
from sqlalchemy import create_engine, Column, Integer, DateTime, Enum
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import datetime
import enum

STORAGE_URL = os.getenv("STORAGE_URL", "mongodb://mongo_db:27017")
MONGO_DB_NAME = "collection_storage"
DATABASE_URL = os.environ["DATABASE_URL"]
RELEVANCE_PROVIDER = os.getenv("RELEVANCE_PROVIDER", "auto").strip().lower()
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "").rstrip("/")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY", ""))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("EMBEDDING_REQUEST_TIMEOUT_SECONDS", "120"))

mongo_client = pymongo.MongoClient(STORAGE_URL)
mongo_db = mongo_client[MONGO_DB_NAME]

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class SessionStatusEnum(str, enum.Enum):
    queued = "queued"
    starting = "starting"
    chunking = "chunking"
    extracting = "extracting"
    finished = "finished"
    canceled = "canceled"

class CerSession(Base):
    __tablename__ = "cer_sessions"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(Enum(SessionStatusEnum), default=SessionStatusEnum.queued, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

def update_session_status(session_id: int, new_status: SessionStatusEnum):
    """Werk de status van een sessie bij in PostgreSQL."""
    db: Session = SessionLocal()
    try:
        session_obj = db.query(CerSession).filter(CerSession.id == session_id).first()
        if session_obj:
            session_obj.status = new_status
            session_obj.updated_at = datetime.datetime.utcnow()
            db.commit()
            print(f"✅ Sessiestatus bijgewerkt naar '{new_status.value}' voor sessie {session_id}")
        else:
            print(f"❌ Geen sessie gevonden met ID {session_id}")
    except Exception as e:
        print(f"❌ Fout bij updaten sessiestatus: {e}")
    finally:
        db.close()

def fetch_chunks_from_collection(collection_id):
    """Haalt de chunks per document op uit MongoDB voor een gegeven collectie."""
    print(f"Ophalen van chunks voor collectie {collection_id}...")
    chunked_data = mongo_db["chunked_collections"].find_one({"collection_id": collection_id})

    if not chunked_data or "documents" not in chunked_data:
        raise ValueError(f"❌ Geen chunk data gevonden voor collectie {collection_id}")

    print(f"✅ Chunks opgehaald voor collectie {collection_id}.")
    return chunked_data["documents"]

def tokenize_text(text):
    """Tokenize text into lowercase word fragments for local relevance scoring."""
    return re.findall(r"[a-z0-9]+", text.lower())


def resolve_relevance_provider():
    """Use local scoring by default, unless embedding credentials/endpoint are configured."""
    if RELEVANCE_PROVIDER != "auto":
        return RELEVANCE_PROVIDER
    if EMBEDDING_BASE_URL or EMBEDDING_API_KEY:
        return "embeddings"
    return "local_tfidf"


def embed_texts(texts, model=EMBEDDING_MODEL):
    """Embed multiple texts using an OpenAI-compatible embeddings endpoint."""
    if not EMBEDDING_BASE_URL:
        raise ValueError("EMBEDDING_BASE_URL must be set when using the embeddings provider.")

    headers = {"Content-Type": "application/json"}
    if EMBEDDING_API_KEY:
        headers["Authorization"] = f"Bearer {EMBEDDING_API_KEY}"

    response = requests.post(
        f"{EMBEDDING_BASE_URL}/embeddings",
        json={"input": texts, "model": model},
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    return np.array([item["embedding"] for item in payload["data"]], dtype=np.float32)


def normalize_embeddings(embeddings):
    """Normalize embeddings to unit length for cosine similarity."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return embeddings / norms


def score_chunks_with_embeddings(all_chunks, key_events):
    """Rank chunks using embedding similarity through an OpenAI-compatible API."""
    chunk_embeddings = normalize_embeddings(embed_texts(all_chunks))
    key_event_embeddings = normalize_embeddings(embed_texts(key_events))
    similarity_matrix = np.matmul(key_event_embeddings, chunk_embeddings.T)
    return similarity_matrix


def build_idf_lookup(documents):
    """Compute a lightweight IDF table across chunk texts for local relevance scoring."""
    document_frequency = Counter()
    total_documents = 0

    for text in documents:
        tokens = set(tokenize_text(text))
        if not tokens:
            continue
        total_documents += 1
        document_frequency.update(tokens)

    if total_documents == 0:
        return {}

    return {
        token: math.log((1 + total_documents) / (1 + frequency)) + 1.0
        for token, frequency in document_frequency.items()
    }


def build_tfidf_vector(text, idf_lookup):
    """Build a sparse TF-IDF representation for a text snippet."""
    tokens = tokenize_text(text)
    if not tokens:
        return {}, 0.0

    counts = Counter(tokens)
    total_tokens = sum(counts.values()) or 1
    vector = {}
    norm = 0.0

    for token, count in counts.items():
        weight = (count / total_tokens) * idf_lookup.get(token, 1.0)
        vector[token] = weight
        norm += weight * weight

    return vector, math.sqrt(norm)


def cosine_similarity_sparse(left_vector, left_norm, right_vector, right_norm):
    """Compute cosine similarity for sparse TF-IDF vectors."""
    if left_norm == 0 or right_norm == 0:
        return 0.0

    shared_tokens = set(left_vector.keys()) & set(right_vector.keys())
    dot_product = sum(left_vector[token] * right_vector[token] for token in shared_tokens)
    return dot_product / (left_norm * right_norm)


def score_chunks_with_local_tfidf(all_chunks, key_events):
    """Rank chunks using a local TF-IDF cosine similarity fallback."""
    idf_lookup = build_idf_lookup(all_chunks + key_events)
    chunk_vectors = [build_tfidf_vector(chunk, idf_lookup) for chunk in all_chunks]
    key_event_vectors = [build_tfidf_vector(event, idf_lookup) for event in key_events]

    similarity_rows = []
    for key_vector, key_norm in key_event_vectors:
        row = [
            cosine_similarity_sparse(key_vector, key_norm, chunk_vector, chunk_norm)
            for chunk_vector, chunk_norm in chunk_vectors
        ]
        similarity_rows.append(row)

    return np.array(similarity_rows, dtype=np.float32)

# Verwerk de relevantie van chunks
def process_relevance(session_id, collection_id, key_events):
    """Berekent de relevantie-score van chunks op basis van key events en slaat het op in MongoDB."""
    print(f"Starten van relevance scoring voor collectie {collection_id}, sessie {session_id}...")

    # Update sessie status naar "starting"
    update_session_status(session_id, SessionStatusEnum.starting)

    # Haal de chunks per document op
    try:
        documents = fetch_chunks_from_collection(collection_id)
    except ValueError as e:
        print(f"❌ Error: {e}")
        update_session_status(session_id, SessionStatusEnum.canceled)
        return

    all_chunks = []
    chunk_doc_mapping = []  # Dit bewaart document_id en index van de chunk in all_chunks

    for doc in documents:
        document_id = doc["document_id"]
        for chunk in doc["chunks"]:
            chunk_id = str(ObjectId())
            all_chunks.append(chunk["chunk"])
            chunk_doc_mapping.append({
                "document_id": document_id,
                "chunk_index": len(all_chunks) - 1,
                "chunk": chunk,
                "chunk_id": chunk_id  # ✅ Voeg de gegenereerde ID toe
            })

    provider = resolve_relevance_provider()
    print(f"Using relevance provider: {provider}")

    try:
        if provider == "embeddings":
            similarity_matrix = score_chunks_with_embeddings(all_chunks, key_events)
        elif provider == "local_tfidf":
            similarity_matrix = score_chunks_with_local_tfidf(all_chunks, key_events)
        else:
            raise ValueError(f"Unknown relevance provider '{provider}'")
    except Exception as error:
        print(f"⚠️ Falling back to local_tfidf relevance scoring: {error}")
        similarity_matrix = score_chunks_with_local_tfidf(all_chunks, key_events)

    # Bereken de relevantie-score per chunk voor elk key event
    chunk_relevance_map = {
        chunk["chunk_index"]: {
            "document_id": chunk["document_id"],
            "chunk": chunk["chunk"],
            "chunk_id": chunk["chunk_id"],  # ✅ Voeg de chunk ID toe aan de mapping
            "scores": []
        }
        for chunk in chunk_doc_mapping
    }

    for i, key_event in enumerate(key_events):
        print(f"\n🔍 Bezig met zoeken naar relevante chunks voor key event: {key_event}")
        distances = similarity_matrix[i]
        indices = np.argsort(distances)[::-1]

        for idx in indices:
            dist = distances[idx]
            if idx in chunk_relevance_map:
                chunk_relevance_map[idx]["scores"].append(round(float(dist), 4))

    # Herstructureer de output naar per document met chunks en scores
    structured_documents = {}
    for chunk_data in chunk_relevance_map.values():
        document_id = chunk_data["document_id"]
        if document_id not in structured_documents:
            structured_documents[document_id] = {"document_id": document_id, "chunks": []}

        chunk_obj = {
            "chunk_id": chunk_data["chunk_id"],  # Unieke chunk ID wordt toegevoegd
            "chunk": chunk_data["chunk"]["chunk"],
            "heading": chunk_data["chunk"]["heading"],
            "document_id": document_id,
            "score": max(chunk_data["scores"]) if chunk_data["scores"] else 0  # Neem de hoogste score
        }
        structured_documents[document_id]["chunks"].append(chunk_obj)

    # Sla de verrijkte chunks met relevance scores op in MongoDB
    mongo_db["chunked_relevance"].insert_one({
        "session_id": session_id,
        "collection_id": collection_id,
        "processed_at": float(time.time()),
        "documents": list(structured_documents.values())
    })

    print(f"✅ Relevance scoring voltooid en opgeslagen in MongoDB voor sessie {session_id}.")

    # Update sessie status naar "chunking"
    update_session_status(session_id, SessionStatusEnum.chunking)

if __name__ == "__main__":
    session_id = int(os.getenv("SESSION_ID", "1"))
    collection_id = int(os.getenv("COLLECTION_ID", "1"))
    key_events = json.loads(os.getenv("KEY_EVENTS", "[]"))

    process_relevance(session_id, collection_id, key_events)

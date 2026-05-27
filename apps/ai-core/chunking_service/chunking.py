import os
import time
import pymongo

STORAGE_URL = os.getenv("STORAGE_URL", "mongodb://mongo_db:27017")
MONGO_DB_NAME = "collection_storage"
CHUNK_SIZE = 1000  # Grootte van de chunks

mongo_client = pymongo.MongoClient(STORAGE_URL)
mongo_db = mongo_client[MONGO_DB_NAME]

def fetch_preprocessed_data(collection_id):
    """Haalt de preprocessing-output op uit MongoDB."""
    print(f"🔄 Ophalen van preprocessing-output voor collectie {collection_id}...")
    preprocessed_data = mongo_db["processed_collections"].find_one({"collection_id": collection_id})

    if not preprocessed_data or "documents" not in preprocessed_data:
        raise ValueError(f"❌ Geen preprocessing data gevonden voor collectie {collection_id}")

    print(f"✅ Preprocessing-output opgehaald voor collectie {collection_id}.")
    return preprocessed_data["documents"]

def fixed_size_chunking(text, chunk_size):
    """Splits tekst in chunks van vaste grootte en verwijdert lege chunks."""
    if not text.strip():
        return []  # Voorkom lege chunks

    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

def process_chunking(collection_id):
    """Chunking-proces dat de preprocessing-output omzet naar chunks en opslaat in MongoDB."""
    print(f"Starten met chunking voor collectie {collection_id}...")

    try:
        documents = fetch_preprocessed_data(collection_id)
    except ValueError as e:
        print(f"❌ Error: {e}")
        return

    chunked_documents = []
    total_chunks_in_collection = 0  # Totaal aantal chunks in de collectie

    for doc in documents:
        document_id = doc["document_id"]
        extracted_data = doc["content"]

        # Verwerk elk document individueel
        chunks = []
        for item in extracted_data:
            text = item["Content"]
            heading = item.get("Heading", "Unknown")

            # Chunk de tekst
            document_chunks = fixed_size_chunking(text, CHUNK_SIZE)
            for chunk in document_chunks:
                chunks.append({"chunk": chunk, "heading": heading, "document_id": document_id})

        total_chunks = len(chunks)
        total_chunks_in_collection += total_chunks  # Update totaal aantal chunks in de collectie

        chunked_documents.append({
            "document_id": document_id,
            "total_chunks": total_chunks,
            "chunks": chunks
        })

        print(f"✅ Chunking voltooid voor document {document_id} (Totaal chunks: {total_chunks})")

    mongo_db["chunked_collections"].insert_one({
        "collection_id": collection_id,
        "chunked_at": float(time.time()),
        "total_chunks_in_collection": total_chunks_in_collection,
        "documents": chunked_documents
    })

    print(f"✅ Chunking opgeslagen in MongoDB voor collectie {collection_id} (Totaal chunks: {total_chunks_in_collection}).")

if __name__ == "__main__":
    collection_id = int(os.getenv("COLLECTION_ID", "1"))
    process_chunking(collection_id)

import os
import json
import pika
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from models import Base
from schemas import CollectionCreate, CollectionOut
from repository import CollectionRepository
from storage import get_mongo_client, get_gridfs
from typing import List
from bson import ObjectId
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]
STORAGE_URL = os.getenv("STORAGE_URL", "mongodb://mongo_db:27017")
MONGO_DB_NAME = "collection_storage"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

mongo_client = get_mongo_client(STORAGE_URL)
mongo_db = mongo_client[MONGO_DB_NAME]
fs = get_gridfs(MONGO_DB_NAME, STORAGE_URL)


# Endpoint om een nieuwe collectie aan te maken
@app.post("/collections", response_model=CollectionOut)
def create_collection(collection: CollectionCreate, db: Session = Depends(get_db)):
    repo = CollectionRepository(db)
    new_collection = repo.create_collection(collection)
    return new_collection


# Endpoint om alle collecties voor een gebruiker op te halen
@app.get("/collections", response_model=List[CollectionOut])
def get_user_collections(user_id: int = Query(..., description="De ID van de gebruiker"), db: Session = Depends(get_db)):
    repo = CollectionRepository(db)
    collections = repo.get_collections_by_user(user_id)

    # Voor elke collectie in PostgreSQL, haal `total_chunks_in_collection` uit MongoDB op
    for collection in collections:
        chunked_data = mongo_db["chunked_collections"].find_one({"collection_id": collection.id})
        collection.total_chunks = chunked_data.get("total_chunks_in_collection", 0) if chunked_data else 0

    return collections


# Endpoint om een PDF te uploaden in een collectie en deze te linken
@app.post("/collections/{collection_id}/upload")
def upload_pdf(collection_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    repo = CollectionRepository(db)
    collection = repo.get_collection_by_id(collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Lees de file data
    file_data = file.file.read()
    # Sla het bestand op in MongoDB met GridFS.
    # Maak een bestandsnaam die de collectie identificeert.
    file_id = fs.put(file_data, filename=f"collection_{collection_id}_{file.filename}", contentType=file.content_type)
    file_id_str = str(file_id)  # Zorg dat we een string opslaan

    # Voeg het file_id toe aan de collectie in PostgreSQL.
    # Als er al PDF's gekoppeld zijn, voegen we deze toe aan de lijst.
    if collection.pdf_ids is None:
        collection.pdf_ids = []
    collection.pdf_ids.append(file_id_str)

    db.commit()
    db.refresh(collection)

    return {"message": "File uploaded successfully", "file_id": file_id_str}


@app.delete("/collections/{collection_id}/pdfs/{file_id}")
def delete_pdf_from_collection(collection_id: int, file_id: str, db: Session = Depends(get_db)):
    repo = CollectionRepository(db)
    collection = repo.get_collection_by_id(collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Controleer of het opgegeven file_id bestaat in de collectie
    if not collection.pdf_ids or file_id not in collection.pdf_ids:
        raise HTTPException(status_code=404, detail="File not found in collection")

    # Verwijder het bestand uit MongoDB via GridFS
    try:
        fs.delete(ObjectId(file_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error deleting file from storage")

    # Verwijder de file_id uit de pdf_ids-lijst in de collectie
    collection.pdf_ids.remove(file_id)
    db.commit()
    db.refresh(collection)

    return {"message": "File deleted successfully", "collection_id": collection_id, "removed_file_id": file_id}


@app.post("/collections/{collection_id}/scan")
def scan_collection(collection_id: int, db: Session = Depends(get_db)):
    repo = CollectionRepository(db)
    collection = repo.get_collection_by_id(collection_id)

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    if collection.status == "scanned":
        raise HTTPException(status_code=400, detail="Collection has already been scanned.")

    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq_broker")
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue="preprocessing_queue", durable=True)

        message = json.dumps({"collection_id": collection_id})
        channel.basic_publish(
            exchange="",
            routing_key="preprocessing_queue",
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,
            )
        )

        repo.update_collection_status(collection_id, 'queued_preprocessing')
        connection.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish message: {e}")

    return {"message": "Scan task queued", "collection_id": collection_id}

from fastapi import FastAPI, Request, Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from bson import ObjectId
from schemas import CerSessionCreate, CerSessionOut
import repository
import os
import pika
import json
import pymongo
import datetime
from typing import List
from models import Base, CerSession, CerSessionLog, SessionStatusEnum

DATABASE_URL = os.environ["DATABASE_URL"]
RABBITMQ_HOST = os.getenv("MQ_HOST", "rabbitmq_broker")
STORAGE_URL = os.getenv("STORAGE_URL", "mongodb://mongo_db:27017")
BUDGET = os.getenv('BUDGET', 50)
MONGO_DB_NAME = "collection_storage"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_session_status_enum_values():
    expected_values = [status.value for status in SessionStatusEnum]
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            enum_exists = connection.execute(text("SELECT 1 FROM pg_type WHERE typname = 'sessionstatusenum'")).scalar()
            if not enum_exists:
                return

            existing_values = {
                row[0]
                for row in connection.execute(
                    text(
                        """
                        SELECT e.enumlabel
                        FROM pg_type t
                        JOIN pg_enum e ON t.oid = e.enumtypid
                        WHERE t.typname = 'sessionstatusenum'
                        """
                    )
                )
            }

            for value in expected_values:
                if value not in existing_values:
                    connection.execute(text(f"ALTER TYPE sessionstatusenum ADD VALUE IF NOT EXISTS '{value}'"))
                    print(f"✅ Added missing enum value '{value}' to sessionstatusenum")
    except Exception as exc:
        print(f"⚠️ Could not update sessionstatusenum on startup: {exc}")


Base.metadata.create_all(bind=engine)
ensure_session_status_enum_values()

app = FastAPI()

mongo_client = pymongo.MongoClient(STORAGE_URL)
mongo_db = mongo_client[MONGO_DB_NAME]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_telemetry(session_id: int):
    telemetry = mongo_db["session_telemetry"].find_one({"session_id": session_id})
    if not telemetry:
        return None

    telemetry.pop("_id", None)
    return telemetry


def get_owned_session_or_404(db: Session, session_id: int, user_id: int) -> CerSession:
    session_obj = repository.get_session_by_id_and_user(db, session_id, user_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_obj


def clear_session_runtime_data(session_id: int, keep_selected_chunks: bool = False):
    mongo_db["chunked_relevance"].delete_many({"session_id": session_id})
    mongo_db["extracted_causal_relations"].delete_many({"session_id": session_id})
    mongo_db["enriched_graphs"].delete_many({"session_id": session_id})
    mongo_db["session_telemetry"].delete_many({"session_id": session_id})

    if not keep_selected_chunks:
        mongo_db["selected_chunks"].delete_many({"session_id": session_id})


# Publiceer een bericht naar de `relevance_queue`
def publish_to_relevance_queue(session_id: int):
    """Stuur een bericht naar RabbitMQ relevance_queue na het aanmaken van een sessie."""
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue="relevance_queue", durable=True)

        message = json.dumps({"session_id": session_id})
        channel.basic_publish(
            exchange="",
            routing_key="relevance_queue",
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,
            )
        )
        connection.close()
        print(f"📩 Published session {session_id} to relevance_queue.")
    except Exception as e:
        print(f"❌ Error publishing to relevance_queue: {e}")


def publish_to_cre_queue(session_id: int):
    """Publiceert een bericht naar RabbitMQ cre_queue."""
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue="cre_queue", durable=True)

        message = json.dumps({"session_id": session_id})
        channel.basic_publish(
            exchange="",
            routing_key="cre_queue",
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,
            )
        )
        connection.close()
        print(f"📩 Published session {session_id} to cre_queue.")
    except Exception as e:
        print(f"❌ Error publishing to cre_queue: {e}")

def update_session_status(db: Session, session_id: int, new_status: SessionStatusEnum):
    """Werk de status van een sessie bij in de database."""
    session_obj = db.query(CerSession).filter(CerSession.id == session_id).first()
    if session_obj:
        session_obj.status = new_status
        session_obj.updated_at = datetime.datetime.utcnow()
        db.commit()
        print(f"✅ Sessiestatus bijgewerkt naar '{new_status.value}' voor sessie {session_id}")
    else:
        print(f"❌ Geen sessie gevonden met ID {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")


def log_session_status(db: Session, session_id: int, status: SessionStatusEnum):
    """Voegt een log entry toe voor de sessie."""
    log_entry = CerSessionLog(
        session_id=session_id,
        timestamp=datetime.datetime.utcnow(),
        status=status
    )
    db.add(log_entry)
    db.commit()
    print(f"📝 Log toegevoegd: '{status.value}' voor sessie {session_id}")

# Endpoint om een sessie aan te maken
@app.post("/sessions", response_model=CerSessionOut)
def create_session(session_data: CerSessionCreate, db: Session = Depends(get_db)):
    session_obj = repository.create_cer_session(db, session_data)

    # 🟢 Publiceer de sessie naar de relevance queue
    publish_to_relevance_queue(session_obj.id)

    return session_obj


# Endpoint om een specifieke sessie op te halen
@app.get("/sessions/{session_id}", response_model=CerSessionOut)
def get_session(session_id: int, db: Session = Depends(get_db)):
    session_obj = repository.get_session_by_id(db, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    session_data = CerSessionOut.model_validate(session_obj, from_attributes=True).model_dump()
    session_data["telemetry"] = get_session_telemetry(session_id)
    return session_data


# Endpoint om alle sessies van een gebruiker op te halen
@app.get("/sessions", response_model=List[CerSessionOut])
def get_sessions(user_id: int, db: Session = Depends(get_db)):
    sessions = repository.get_sessions_by_user(db, user_id)
    payload = []
    for session_obj in sessions:
        session_data = CerSessionOut.model_validate(session_obj, from_attributes=True).model_dump()
        session_data["telemetry"] = get_session_telemetry(session_obj.id)
        payload.append(session_data)
    return payload


# Endpoint om sessiegegevens + chunked_relevance uit MongoDB op te halen
@app.get("/sessions/{session_id}/chunks", response_model=CerSessionOut)
def get_session_with_chunks(session_id: int, db: Session = Depends(get_db)):
    """Haal een sessie op met de bijbehorende chunks en documentnamen uit MongoDB."""

    session_obj = repository.get_session_by_id(db, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    # Zet het SQLAlchemy-object correct om naar een Pydantic-schema
    session_data = CerSessionOut.model_validate(session_obj, from_attributes=True)

    # Haal de chunked_relevance documenten op uit MongoDB
    chunked_data = mongo_db["chunked_relevance"].find_one({"session_id": session_id})

    # Controleer of er data is, zo niet, geef een lege array terug
    documents = chunked_data["documents"] if chunked_data and "documents" in chunked_data else []

    for document in documents:
        document_id = document.get("document_id")
        if document_id:
            file_metadata = mongo_db["fs.files"].find_one({"_id": ObjectId(document_id)})
            document["name"] = file_metadata["filename"] if file_metadata else "Unknown Document"

    session_data = session_data.model_dump()  # Zet het Pydantic-object om naar een dictionary
    session_data["documents"] = documents
    session_data["telemetry"] = get_session_telemetry(session_id)

    return session_data


# Endpoint om geselecteerde documenten en chunks op te slaan
@app.post("/sessions/{session_id}/submit")
async def submit_selected_chunks(session_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Ontvangt en slaat de geselecteerde documenten en chunks op in MongoDB en publiceert een bericht naar cre_queue.
    """
    session_obj = repository.get_session_by_id(db, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        selected_documents = await request.json()
        if not isinstance(selected_documents, list):
            raise ValueError("Invalid data format: Expected a list of documents.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON format: {e}")

    for document in selected_documents:
        if "document_id" not in document or "chunks" not in document:
            raise HTTPException(status_code=400, detail="Missing required fields in document data.")

        if not isinstance(document["chunks"], list):
            raise HTTPException(status_code=400, detail="Chunks should be a list.")

    mongo_db["selected_chunks"].replace_one(
        {"session_id": session_id},
        {
            "session_id": session_id,
            "submitted_at": datetime.datetime.utcnow(),
            "documents": selected_documents
        },
        upsert=True
    )

    print(f"✅ Geselecteerde chunks opgeslagen voor sessie {session_id}.")

    update_session_status(db, session_id, SessionStatusEnum.waiting)
    log_session_status(db, session_id, SessionStatusEnum.waiting)

    publish_to_cre_queue(session_id)

    return {"message": "Selected chunks successfully saved", "session_id": session_id}


@app.post("/sessions/{session_id}/resubmit")
def resubmit_session(session_id: int, user_id: int, force: bool = False, db: Session = Depends(get_db)):
    session_obj = get_owned_session_or_404(db, session_id, user_id)

    if session_obj.status in {
        SessionStatusEnum.queued,
        SessionStatusEnum.starting,
        SessionStatusEnum.chunking,
        SessionStatusEnum.waiting,
        SessionStatusEnum.extracting,
    } and not force:
        raise HTTPException(status_code=409, detail="Session is already active")

    selected_chunks = mongo_db["selected_chunks"].find_one(
        {"session_id": session_id},
        sort=[("submitted_at", pymongo.DESCENDING)],
    )

    clear_session_runtime_data(session_id, keep_selected_chunks=selected_chunks is not None)

    if selected_chunks:
        update_session_status(db, session_id, SessionStatusEnum.waiting)
        log_session_status(db, session_id, SessionStatusEnum.waiting)
        publish_to_cre_queue(session_id)
        return {
            "message": "Session resubmitted for extraction",
            "session_id": session_id,
            "status": SessionStatusEnum.waiting.value,
        }

    update_session_status(db, session_id, SessionStatusEnum.queued)
    log_session_status(db, session_id, SessionStatusEnum.queued)
    publish_to_relevance_queue(session_id)
    return {
        "message": "Session resubmitted from relevance processing",
        "session_id": session_id,
        "status": SessionStatusEnum.queued.value,
    }


@app.delete("/sessions/{session_id}")
def delete_session(session_id: int, user_id: int, db: Session = Depends(get_db)):
    session_obj = get_owned_session_or_404(db, session_id, user_id)

    clear_session_runtime_data(session_id, keep_selected_chunks=False)
    repository.delete_session(db, session_obj)

    return {"message": "Session deleted", "session_id": session_id}

# Endpoint om het resultaat van een sessie op te halen
@app.get("/sessions/{session_id}/result")
def get_session_result(session_id: int, db: Session = Depends(get_db)):
    """
    Haalt de sessiegegevens op, inclusief de geselecteerde chunks en de geëxtraheerde causale relaties.
    """
    session_obj = repository.get_session_by_id(db, session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")

    # Zet het SQLAlchemy-object correct om naar een Pydantic-schema
    session_data = CerSessionOut.model_validate(session_obj, from_attributes=True)

    selected_chunks_data = mongo_db["selected_chunks"].find_one({"session_id": session_id})

    if not selected_chunks_data:
        raise HTTPException(status_code=404, detail="No selected chunks found for this session")

    selected_documents = selected_chunks_data.get("documents", [])

    for document in selected_documents:
        document_id = document.get("document_id")
        if document_id:
            file_metadata = mongo_db["fs.files"].find_one({"_id": ObjectId(document_id)})
            document["name"] = file_metadata["filename"] if file_metadata else "Unknown Document"
            reference_info = mongo_db["document_references"].find_one({"document_id": document_id})
            if reference_info:
                reference_info.pop("_id", None)
                document["reference"] = reference_info
            elif file_metadata:
                document["reference"] = {
                    "document_id": document_id,
                    "filename": file_metadata.get("filename"),
                    "title": file_metadata.get("filename"),
                    "authors": None,
                    "subject": None,
                    "keywords": None,
                    "doi": None,
                    "year": file_metadata.get("uploadDate").year if file_metadata.get("uploadDate") else None,
                    "upload_date": file_metadata.get("uploadDate"),
                    "content_type": file_metadata.get("contentType"),
                    "file_size_bytes": file_metadata.get("length"),
                    "page_count": None,
                }

    extracted_data_entry = mongo_db["extracted_causal_relations"].find_one({"session_id": session_id})
    extracted_data = extracted_data_entry.get("extracted_data", []) if extracted_data_entry else []
    enriched_graph_entry = mongo_db["enriched_graphs"].find_one({"session_id": session_id})
    enriched_graph = enriched_graph_entry.get("graph", None) if enriched_graph_entry else None

    result_data = {
        "session": session_data.model_dump(),  # Zet het Pydantic-object om naar een dictionary
        "selected_chunks": selected_documents,
        "extracted_causal_relations": extracted_data,
        "enriched_graph": enriched_graph,
    }

    result_data["session"]["telemetry"] = get_session_telemetry(session_id)

    return result_data

@app.get("/budget")
def get_budget():
    """
    Returns the remaining shared budget from the environment.
    """
    return {"budget": round(float(BUDGET), 2)}

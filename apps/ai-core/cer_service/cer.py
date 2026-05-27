import os
import json
import time
import requests
import pymongo
import pika
import enum
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Enum, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList
import datetime

base_url = os.getenv("CER_API_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
api_key = os.getenv("CER_API_KEY", os.getenv("OPENROUTER_API_KEY", ""))
request_timeout_seconds = float(os.getenv("CER_REQUEST_TIMEOUT_SECONDS", "300"))
RABBITMQ_HOST = os.getenv("MQ_HOST", "rabbitmq_broker")

headers = {"Content-Type": "application/json"}
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

# LLM Rate Limits (requests per minute)
rate_limits = {
    "qwen3_14b": None,
    "deepseek_r1_14b": None,
    "qwen3_8b": None,
    "gpt_oss": None,
}

# Models Mapping
models = {
    "qwen3_14b": os.getenv("CER_MODEL_QWEN3_14B", "qwen3:14b"),
    "deepseek_r1_14b": os.getenv("CER_MODEL_DEEPSEEK_R1_14B", "deepseek-r1:14b"),
    "qwen3_8b": os.getenv("CER_MODEL_QWEN3_8B", "qwen3:8b"),
    # Backward compatibility for older sessions.
    "gpt_oss": os.getenv("CER_MODEL_DEFAULT", os.getenv("CER_MODEL_QWEN3_14B", "qwen3:14b")),
}

MONGO_URI = os.getenv("STORAGE_URL", "mongodb://mongo_db:27017")
MONGO_DB_NAME = "collection_storage"
mongo_client = pymongo.MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DB_NAME]
telemetry_collection = mongo_db["session_telemetry"]

DATABASE_URL = os.environ["DATABASE_URL"]
Base = declarative_base()

class SessionStatusEnum(str, enum.Enum):
    queued = "queued"
    starting = "starting"
    chunking = "chunking"
    extracting = "extracting"
    enriching = "enriching"
    finished = "finished"
    canceled = "canceled"

class CerSession(Base):
    __tablename__ = "cer_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    collection_id = Column(Integer, index=True, nullable=False)
    title = Column(String, nullable=False)
    key_events = Column(MutableList.as_mutable(ARRAY(String)), default=[])
    model_name = Column(String, nullable=False)
    relevance_score_threshold = Column(Float, nullable=False)
    status = Column(Enum(SessionStatusEnum, native_enum=False), default=SessionStatusEnum.queued, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    logs = relationship("CerSessionLog", back_populates="session", cascade="all, delete-orphan")

class CerSessionLog(Base):
    __tablename__ = "cer_session_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("cer_sessions.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(Enum(SessionStatusEnum, native_enum=False), nullable=False)

    session = relationship("CerSession", back_populates="logs")

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


ensure_session_status_enum_values()


# ✅ **Functie om het gekozen model op te halen**
def get_model_for_session(session_id: int) -> str:
    """Haalt het model op uit de PostgreSQL database voor de gegeven sessie."""
    db: Session = SessionLocal()
    try:
        session = db.query(CerSession).filter(CerSession.id == session_id).first()
        if session and session.model_name in models:
            return session.model_name
        else:
            unknown_model_name = session.model_name if session else "<missing session>"
            print(f"⚠️ Model '{unknown_model_name}' niet gevonden, gebruik standaard 'qwen3_14b'")
            return "qwen3_14b"  # Fallback model
    except Exception as e:
        print(f"❌ Fout bij ophalen model voor sessie {session_id}: {e}")
        return "qwen3_14b"  # Fallback model
    finally:
        db.close()


def update_session_status(session_id: int, new_status: SessionStatusEnum):
    """Werk de status van een sessie bij in PostgreSQL."""
    db: Session = SessionLocal()
    try:
        session = db.query(CerSession).filter(CerSession.id == session_id).first()
        if session:
            session.status = new_status
            session.updated_at = datetime.datetime.utcnow()
            db.commit()
            print(f"✅ Updated session {session_id} status to '{new_status.value}'")
        else:
            print(f"❌ Session {session_id} not found!")
    except Exception as e:
        print(f"❌ Error updating session status: {e}")
    finally:
        db.close()


def publish_to_enrichment_queue(session_id: int):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue="enrichment_queue", durable=True)
        message = json.dumps({"session_id": session_id})
        channel.basic_publish(
            exchange="",
            routing_key="enrichment_queue",
            body=message,
            properties=pika.BasicProperties(delivery_mode=2),
        )
        connection.close()
        print(f"📩 Published session {session_id} to enrichment_queue.")
    except Exception as e:
        print(f"❌ Error publishing to enrichment_queue: {e}")
        raise

def log_session_status(session_id: int, status: SessionStatusEnum):
    """Voegt een log entry toe voor de sessie."""
    db: Session = SessionLocal()
    log_entry = CerSessionLog(
        session_id=session_id,
        timestamp=datetime.datetime.utcnow(),
        status=status
    )
    db.add(log_entry)
    db.commit()
    print(f"📝 Log toegevoegd: '{status.value}' voor sessie {session_id}")

def fetch_chunks(session_id: int):
    """Haalt alle geselecteerde chunks op uit MongoDB voor de opgegeven sessie."""
    selected_data = mongo_db["selected_chunks"].find_one({"session_id": session_id})

    if not selected_data or "documents" not in selected_data:
        print(f"❌ No selected chunks found for session {session_id}")
        return []

    chunks = []
    for document in selected_data["documents"]:
        for chunk in document["chunks"]:
            if chunk.get("selected", False):  # Alleen geselecteerde chunks verwerken
                chunks.append({
                    "id": chunk["id"],
                    "chunk": chunk["text"]
                })

    print(f"✅ Fetched {len(chunks)} selected chunks for session {session_id}")
    return chunks


def upsert_session_telemetry(session_id: int, payload: dict):
    telemetry_collection.update_one(
        {"session_id": session_id},
        {"$set": {"session_id": session_id, **payload}},
        upsert=True,
    )


def update_chunk_progress(
    session_id: int,
    model_key: str,
    total_chunks: int,
    processed_chunks: int,
    successful_chunks: int,
    failed_chunks: int,
    total_relationships: int,
    last_chunk_id: str,
    last_message: str,
    last_error: str = None,
):
    percent_complete = round((processed_chunks / total_chunks) * 100, 1) if total_chunks else 0
    upsert_session_telemetry(
        session_id,
        {
            "phase": "extracting",
            "model_name": model_key,
            "total_chunks": total_chunks,
            "processed_chunks": processed_chunks,
            "successful_chunks": successful_chunks,
            "failed_chunks": failed_chunks,
            "total_relationships": total_relationships,
            "percent_complete": percent_complete,
            "updated_at": datetime.datetime.utcnow(),
            "last_chunk_id": last_chunk_id,
            "last_message": last_message,
            "last_error": last_error,
        },
    )


def extract_causal_connections(chunks, model_key, session_id):
    """
    Extract causal connections from text chunks using the specified model.
    """
    if model_key not in models:
        raise ValueError(f"Model '{model_key}' not found. Available models: {', '.join(models.keys())}")

    model = models[model_key]
    print(f"Using model: {model_key} ({model})")

    # Bepaal de cooldown op basis van het model
    rate_limit = rate_limits.get(model_key)
    cooldown = 60 / rate_limit if rate_limit else 0  # Cooldown in seconden

    system_prompt = """You are an advanced information extraction assistant specialized in toxicological texts. Your task is to analyze the provided input text, identify key named entities, and extract relationships that represent causal connections. Only use direct quotes from the text for all extracted entities, relationships, and connecting verbs or phrases. Do not invent or infer any words or phrases.
    Key Requirements:
    1.	Use only exact phrases from the input text. Avoid rephrasing, summarizing, or making any assumptions beyond what is explicitly stated in the text.
    2.	Resolve co-referencing issues. If a sentence says ‘’this effect causes that’’ replace ‘this’ with that which is being referenced. Never use demonstratives as their own entity, always replace them with the actual entity being referenced. 
    3.	Extract causal relationships, specifying the subject, verb, and object of the relationship exactly as written in the text.
    4.	Classify each causal or contextual connection as one of the following: 
    o	Positive: The connection represents a facilitating or enabling relationship (e.g., "causes," "leads to").
    o	Negative: The connection represents an inhibitory or contradictory relationship (e.g., "prevents," "does not affect").
    o	Not existing: The text explicitly states that a relationship does not exist (e.g., "is not associated with," "has no effect on").
    5.	Ensure that the verb or connecting phrase is a valid action or linking word directly quoted from the text (e.g., "causes," "leads to," "is associated with"). Do not use prepositions like "in" or "of" as verbs.
    6.	Ignore references between brackets, such as (Friesema et al., 2003)
    7.	Represent the extracted information in the following JSON schema:
    {
      "relationships": [
        {
          "subject": "Entity Name",
          "verb": "Connecting Verb or Phrase",
          "object": "Entity Name",
          "causal_connection": "Positive/Negative/Not existing"
        }
      ]
    }
    Example Inputs and Outputs:
    Input Text:
    "Exposure to lead causes cognitive impairments in children. This is harmful to their development "
    Output JSON:
    {
      "relationships": [
        {
          "subject": "lead",
          "verb": "causes",
          "object": "cognitive impairments",
          "causal_connection": "Positive"
        },
        {
          "subject": "lead",
          "verb": "is harmful",
          "object": "children’s development",
          "causal_connection": "Positive"
        }
      ]
    }
    Input Text:
    "Cadmium exposure is not associated with kidney damage in humans."
    Output JSON:
    {
      "relationships": [
        {
          "subject": "cadmium",
          "verb": "is not associated with",
          "object": "kidney damage",
          "causal_connection": "Not existing"
        }
      ]
    }
    Input Text:
    "Bisphenol A (BPA) inhibits the proliferation of cancer cells in vitro."
    Output JSON:
    {
      "relationships": [
        {
          "subject": "Bisphenol A (BPA)",
          "verb": "inhibits",
          "object": "proliferation of cancer cells",
          "causal_connection": "Negative"
        }
      ]
    }
    Additional Guidelines:
    1.	Do not create new entities, verbs, or relationships beyond what is explicitly present in the text.
    2.	Ensure all verbs are valid actions or linking phrases directly quoted from the text (e.g., "causes," "leads to," "is associated with") and only indicate causal relationships.
    3.	If the text contains ambiguous or unclear relationships, only include what is explicitly stated without assumptions.
    4.	Clearly classify the causal connection as Positive, Negative, or Not existing, based on the explicit description in the input text.
    Now, proceed to extract causal relationships and output the information in the specified JSON format based on the provided toxicology text.
    Text:
    """

    results = []
    successful_chunks = 0
    failed_chunks = 0
    total_relationships = 0
    total_chunks = len(chunks)

    for index, chunk in enumerate(chunks, start=1):
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Text: {chunk['chunk']}"}
                ]
            }

            response = requests.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=request_timeout_seconds,
            )
            response.raise_for_status()

            model_output = response.json()["choices"][0]["message"]["content"].strip()
            if model_output.startswith("```json"):
                model_output = model_output[7:]
            if model_output.endswith("```"):
                model_output = model_output[:-3]

            try:
                json_output = json.loads(model_output)

                # Zorg dat de output de juiste structuur heeft
                if not isinstance(json_output, dict) or "relationships" not in json_output:
                    raise ValueError("JSON heeft niet de verwachte structuur")

            except json.JSONDecodeError as e:
                print(f"❌ JSONDecodeError voor chunk {chunk['id']}: {e}")
                json_output = {"relationships": []}  # Fallback lege structuur

            results.append({
                "id": chunk["id"],
                "text": chunk["chunk"],
                "output": json_output
            })
            successful_chunks += 1
            total_relationships += len(json_output.get("relationships", []))
            update_chunk_progress(
                session_id=session_id,
                model_key=model_key,
                total_chunks=total_chunks,
                processed_chunks=index,
                successful_chunks=successful_chunks,
                failed_chunks=failed_chunks,
                total_relationships=total_relationships,
                last_chunk_id=chunk["id"],
                last_message=f"Processed chunk {index} of {total_chunks}.",
            )

            if cooldown > 0:
                time.sleep(cooldown)

        except Exception as e:
            print(f"❌ Error processing chunk ID {chunk['id']}: {e}")
            failed_chunks += 1
            results.append({
                "id": chunk["id"],
                "output": {"relationships": []}
            })
            update_chunk_progress(
                session_id=session_id,
                model_key=model_key,
                total_chunks=total_chunks,
                processed_chunks=index,
                successful_chunks=successful_chunks,
                failed_chunks=failed_chunks,
                total_relationships=total_relationships,
                last_chunk_id=chunk["id"],
                last_message=f"Chunk {index} of {total_chunks} failed.",
                last_error=str(e),
            )

    return results, successful_chunks, failed_chunks, total_relationships


# ✅ **Verwerk en sla de resultaten op**
def process_and_store(session_id: int):
    """Haalt chunks op, verwerkt ze en slaat de resultaten op in MongoDB."""

    # 🟢 Werk status bij naar "extracting"
    update_session_status(session_id, SessionStatusEnum.extracting)
    log_session_status(session_id, SessionStatusEnum.extracting)

    # Haal geselecteerde chunks op
    chunks = fetch_chunks(session_id)
    if not chunks:
        raise RuntimeError(f"No selected chunks found for session {session_id}")

    # Haal het juiste model op uit de database
    model_key = get_model_for_session(session_id)
    upsert_session_telemetry(
        session_id,
        {
            "phase": "extracting",
            "model_name": model_key,
            "total_chunks": len(chunks),
            "processed_chunks": 0,
            "successful_chunks": 0,
            "failed_chunks": 0,
            "total_relationships": 0,
            "percent_complete": 0,
            "started_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
            "last_message": f"Starting extraction for {len(chunks)} selected chunks.",
            "last_error": None,
        },
    )

    # Verwerk chunks en extract causal connections
    extracted_data, successful_chunks, failed_chunks, total_relationships = extract_causal_connections(chunks, model_key, session_id)

    if successful_chunks == 0:
        raise RuntimeError(
            f"CER extraction failed for every chunk in session {session_id}. "
            f"Check CER_API_BASE_URL ({base_url}) and model service availability."
        )

    # Sla de output op in MongoDB
    mongo_db["extracted_causal_relations"].insert_one({
        "session_id": session_id,
        "processed_at": datetime.datetime.utcnow(),
        "extracted_data": extracted_data,
        "meta": {
            "successful_chunks": successful_chunks,
            "failed_chunks": failed_chunks,
            "total_relationships": total_relationships,
        },
    })

    print(f"✅ Causal relationships stored for session {session_id}")
    if failed_chunks > 0:
        print(f"⚠️ CER extraction completed with {failed_chunks} failed chunks for session {session_id}")

    upsert_session_telemetry(
        session_id,
        {
            "phase": "enriching",
            "model_name": model_key,
            "total_chunks": len(chunks),
            "processed_chunks": len(chunks),
            "successful_chunks": successful_chunks,
            "failed_chunks": failed_chunks,
            "total_relationships": total_relationships,
            "percent_complete": 100,
            "updated_at": datetime.datetime.utcnow(),
            "last_message": "Raw extraction finished. Starting ontology and AOP enrichment.",
            "last_error": None,
        },
    )

    update_session_status(session_id, SessionStatusEnum.enriching)
    log_session_status(session_id, SessionStatusEnum.enriching)
    publish_to_enrichment_queue(session_id)


# ✅ **Start het proces als script wordt uitgevoerd**
if __name__ == "__main__":
    session_id = int(os.getenv("SESSION_ID", "1"))
    try:
        process_and_store(session_id)
    except Exception as e:
        print(f"❌ CER processing failed for session {session_id}: {e}")
        upsert_session_telemetry(
            session_id,
            {
                "phase": "canceled",
                "updated_at": datetime.datetime.utcnow(),
                "last_message": "Extraction stopped due to an error.",
                "last_error": str(e),
            },
        )
        update_session_status(session_id, SessionStatusEnum.canceled)
        log_session_status(session_id, SessionStatusEnum.canceled)
        raise

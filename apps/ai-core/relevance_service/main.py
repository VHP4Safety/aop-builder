import os
import json
import pika
import time
import subprocess
import datetime
import enum
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList

RABBITMQ_HOST = os.getenv("MQ_HOST", "rabbitmq_broker")
DATABASE_URL = os.environ["DATABASE_URL"]

Base = declarative_base()

class SessionStatusEnum(str, enum.Enum):
    queued = "queued"
    starting = "starting"
    chunking = "chunking"
    waiting = "waiting"
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

def fetch_session_data(session_id: int):
    """Haalt de sessiegegevens op uit PostgreSQL."""
    db: Session = SessionLocal()
    try:
        session_obj = db.query(CerSession).filter(CerSession.id == session_id).first()
        if not session_obj:
            print(f"❌ Geen sessie gevonden met ID {session_id}")
            return None
        return {
            "session_id": session_obj.id,
            "collection_id": session_obj.collection_id,
            "key_events": session_obj.key_events
        }
    except Exception as e:
        print(f"❌ Fout bij ophalen sessiegegevens: {e}")
        return None
    finally:
        db.close()

def update_session_status(session_id: int, new_status: SessionStatusEnum):
    """Werk de sessiestatus bij in PostgreSQL en voeg een log toe."""
    db: Session = SessionLocal()
    try:
        session_obj = db.query(CerSession).filter(CerSession.id == session_id).first()
        if session_obj:
            session_obj.status = new_status
            session_obj.updated_at = datetime.datetime.utcnow()

            session_log = CerSessionLog(session_id=session_id, status=new_status)
            db.add(session_log)

            db.commit()
            print(f"✅ Sessiestatus bijgewerkt naar '{new_status.value}' voor sessie {session_id}")
        else:
            print(f"❌ Geen sessie gevonden met ID {session_id}")
    except Exception as e:
        print(f"❌ Fout bij bijwerken sessiestatus: {e}")
    finally:
        db.close()

def start_relevance_processing(session_id: int, collection_id: int, key_events: list):
    """Start `relevance.py` als subproces met de juiste parameters."""
    print(f"Starten van relevance processing voor sessie {session_id}...")

    # Update status naar "starting"
    update_session_status(session_id, SessionStatusEnum.starting)

    try:
        env_vars = {
            **os.environ,
            "SESSION_ID": str(session_id),
            "COLLECTION_ID": str(collection_id),
            "KEY_EVENTS": json.dumps(key_events)
        }

        result = subprocess.run(["python", "relevance.py"], env=env_vars, check=True)

        if result.returncode == 0:
            print(f"✅ Relevance processing voltooid voor sessie {session_id}.")
            update_session_status(session_id, SessionStatusEnum.chunking)  # Update naar "chunking"
        else:
            print(f"❌ Relevance processing mislukt voor sessie {session_id}.")
            update_session_status(session_id, SessionStatusEnum.canceled)  # Update naar "canceled"

    except subprocess.CalledProcessError as e:
        print(f"❌ Error bij uitvoeren van relevance.py: {e}")
        update_session_status(session_id, SessionStatusEnum.canceled)

def callback(ch, method, properties, body):
    """Verwerkt berichten uit `relevance_queue` en start relevance processing."""
    print("📨 Received message for relevance processing:", body.decode())

    try:
        data = json.loads(body)
        session_id = data.get("session_id")

        if not session_id:
            print("❌ Geen session_id ontvangen in bericht.")
            return

        session_data = fetch_session_data(session_id)
        if session_data:
            start_relevance_processing(
                session_data["session_id"],
                session_data["collection_id"],
                session_data["key_events"]
            )

    except Exception as e:
        print("❌ Error processing relevance message:", e)

    ch.basic_ack(delivery_tag=method.delivery_tag)

def connect_to_rabbitmq(retries=5, delay=5):
    """Probeert verbinding te maken met RabbitMQ met retries."""
    for i in range(retries):
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            return connection
        except pika.exceptions.AMQPConnectionError as e:
            print(f"⚠️ RabbitMQ connection failed ({i + 1}/{retries}). Retrying in {delay} seconds...")
            time.sleep(delay)
    raise Exception("❌ Failed to connect to RabbitMQ after multiple attempts.")

def main():
    while True:
        try:
            print(f"Connecting to RabbitMQ at {RABBITMQ_HOST}...")
            connection = connect_to_rabbitmq()
            channel = connection.channel()
            channel.queue_declare(queue="relevance_queue", durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="relevance_queue", on_message_callback=callback)

            print("🎧 Waiting for messages on 'relevance_queue'. To exit press CTRL+C")
            channel.start_consuming()

        except (pika.exceptions.AMQPConnectionError, pika.exceptions.StreamLostError) as e:
            print(f"🔄 RabbitMQ connection lost: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("❌ Relevance-service stopped.")
            break

if __name__ == "__main__":
    print("🚀 Starting relevance service...")
    main()

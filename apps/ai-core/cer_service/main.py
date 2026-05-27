import os
import json
import pika
import time
import subprocess
import enum
import threading
import re
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple
import requests
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Enum, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList
import datetime

RABBITMQ_HOST = os.getenv("MQ_HOST", "rabbitmq_broker")
DATABASE_URL = os.environ["DATABASE_URL"]
CER_API_BASE_URL = os.getenv("CER_API_BASE_URL", "http://llm_service:11434/v1")
CER_MODEL_GPT_OSS = os.getenv(
    "CER_MODEL_DEFAULT",
    os.getenv("CER_MODEL_QWEN3_14B", "qwen3:14b"),
)
CER_MAX_CONCURRENT_SESSIONS_RAW = os.getenv("CER_MAX_CONCURRENT_SESSIONS", "auto")
CER_CONCURRENCY_HEADROOM_FACTOR = max(1.0, float(os.getenv("CER_CONCURRENCY_HEADROOM_FACTOR", "1.2")))
CER_CONCURRENCY_MAX_CAP = max(1, int(os.getenv("CER_CONCURRENCY_MAX_CAP", "4")))
REQUEST_TIMEOUT_SECONDS = 5

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
active_sessions_lock = threading.Lock()
active_sessions = set()


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


ensure_session_status_enum_values()


def _parse_model_parameter_billions(model_name: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*b", model_name.lower())
    if not match:
        return None
    return float(match.group(1))


def _infer_ollama_base_url(api_base_url: str) -> str:
    parsed = urlparse(api_base_url)
    path = parsed.path.rstrip("/")

    if path.endswith("/v1"):
        path = path[:-3]

    return f"{parsed.scheme}://{parsed.netloc}{path}" if path else f"{parsed.scheme}://{parsed.netloc}"


def _fetch_json(url: str) -> Optional[dict]:
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        print(f"⚠️ Could not read {url} while resolving CRE concurrency: {exc}")
        return None


def _get_model_memory_bytes_from_ollama(model_name: str) -> Tuple[Optional[int], Optional[str]]:
    base_url = _infer_ollama_base_url(CER_API_BASE_URL)

    ps_payload = _fetch_json(f"{base_url}/api/ps")
    if ps_payload:
        for model in ps_payload.get("models", []):
            if model.get("name") == model_name or model.get("model") == model_name:
                size_vram = model.get("size_vram") or model.get("size")
                if isinstance(size_vram, int) and size_vram > 0:
                    processor = model.get("processor")
                    processor_label = f" via Ollama ps ({processor})" if processor else " via Ollama ps"
                    return size_vram, processor_label

    tags_payload = _fetch_json(f"{base_url}/api/tags")
    if tags_payload:
        for model in tags_payload.get("models", []):
            if model.get("name") == model_name or model.get("model") == model_name:
                size_bytes = model.get("size")
                if isinstance(size_bytes, int) and size_bytes > 0:
                    return size_bytes, " via Ollama tags"

    return None, None


def _get_total_gpu_memory_bytes() -> Tuple[Optional[int], Optional[str]]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"⚠️ Could not read GPU memory with nvidia-smi while resolving CRE concurrency: {exc}")
        return None, None

    values = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            values.append(int(stripped))
        except ValueError:
            continue

    if not values:
        return None, None

    total_bytes = sum(values) * 1024 * 1024
    return total_bytes, f"{len(values)} GPU(s)"


def _resolve_auto_concurrency(model_name: str) -> Tuple[int, str]:
    model_size_bytes, model_size_source = _get_model_memory_bytes_from_ollama(model_name)
    gpu_memory_bytes, gpu_source = _get_total_gpu_memory_bytes()
    model_size_gb = round(model_size_bytes / (1024 ** 3), 1) if model_size_bytes else None

    if model_size_bytes and gpu_memory_bytes:
        effective_model_bytes = int(model_size_bytes * CER_CONCURRENCY_HEADROOM_FACTOR)
        resolved = max(1, min(CER_CONCURRENCY_MAX_CAP, gpu_memory_bytes // effective_model_bytes))
        gpu_memory_gb = round(gpu_memory_bytes / (1024 ** 3), 1)
        reason = (
            f"auto from model footprint {model_size_gb} GiB{model_size_source or ''} "
            f"and total GPU memory {gpu_memory_gb} GiB ({gpu_source}); "
            f"headroom factor {CER_CONCURRENCY_HEADROOM_FACTOR}"
        )
        return resolved, reason

    if model_size_bytes:
        if model_size_gb >= 12:
            return 1, f"auto from model footprint {model_size_gb} GiB{model_size_source or ''}"
        if model_size_gb >= 6:
            return min(2, CER_CONCURRENCY_MAX_CAP), f"auto from model footprint {model_size_gb} GiB{model_size_source or ''}"
        return min(3, CER_CONCURRENCY_MAX_CAP), f"auto from model footprint {model_size_gb} GiB{model_size_source or ''}"

    parameter_billions = _parse_model_parameter_billions(model_name)
    if parameter_billions is not None:
        if parameter_billions >= 18:
            return 1, f"auto fallback from model size hint {parameter_billions:.1f}B"
        if parameter_billions >= 10:
            return min(2, CER_CONCURRENCY_MAX_CAP), f"auto fallback from model size hint {parameter_billions:.1f}B"
        return min(3, CER_CONCURRENCY_MAX_CAP), f"auto fallback from model size hint {parameter_billions:.1f}B"

    return 1, "auto fallback because no model or GPU sizing data was available"


def resolve_max_concurrent_sessions() -> Tuple[int, str]:
    raw_value = CER_MAX_CONCURRENT_SESSIONS_RAW.strip().lower()

    if raw_value != "auto":
        try:
            return max(1, int(raw_value)), f"manual from CER_MAX_CONCURRENT_SESSIONS={CER_MAX_CONCURRENT_SESSIONS_RAW}"
        except ValueError:
            print(
                f"⚠️ Invalid CER_MAX_CONCURRENT_SESSIONS value '{CER_MAX_CONCURRENT_SESSIONS_RAW}'. "
                "Falling back to auto."
            )

    return _resolve_auto_concurrency(CER_MODEL_GPT_OSS)


MAX_CONCURRENT_SESSIONS, MAX_CONCURRENT_SESSIONS_REASON = resolve_max_concurrent_sessions()
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SESSIONS)


def get_session_status(session_id: int) -> str:
    """Haalt de huidige status van een sessie op uit PostgreSQL."""
    db: Session = SessionLocal()
    try:
        session = db.query(CerSession).filter(CerSession.id == session_id).first()
        return session.status if session else None
    except Exception as e:
        print(f"❌ Fout bij ophalen sessiestatus voor {session_id}: {e}")
        return None
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


def start_cre_processing(session_id: int):
    """Start `cer.py` als subproces en update de sessiestatus."""
    print(f"🚀 Starting CRE processing for session ID: {session_id}")

    current_status = get_session_status(session_id)
    if current_status in ["extracting", "finished"]:
        print(f"⚠️ Session {session_id} is already '{current_status}', skipping.")
        return  # Vermijd dubbele verwerking!

    # Werk de status bij naar 'extracting'
    update_session_status(session_id, SessionStatusEnum.extracting)

    try:
        print(f"🔄 CRE-processing gestart voor sessie {session_id}...")
        result = subprocess.run(["python", "cer.py"], env={**os.environ, "SESSION_ID": str(session_id)}, check=True)

        if result.returncode == 0:
            print(f"✅ CRE-processing voltooid voor sessie {session_id}.")
        else:
            print(f"❌ CRE-processing mislukt voor sessie {session_id}.")
            update_session_status(session_id, SessionStatusEnum.canceled)

    except subprocess.CalledProcessError as e:
        print(f"❌ Error bij uitvoeren van cer.py: {e}")
        update_session_status(session_id, SessionStatusEnum.canceled)


def process_session_in_background(session_id: int):
    """Voert CRE-processing uit binnen de worker pool en ruimt daarna de actieve sessie op."""
    try:
        start_cre_processing(session_id)
    finally:
        with active_sessions_lock:
            active_sessions.discard(session_id)
        print(f"🧹 Released worker slot for session {session_id}")


def callback(ch, method, properties, body):
    """Verwerkt RabbitMQ-berichten en start CRE-verwerking."""
    print("📨 Received message for CRE processing:", body.decode())
    try:
        data = json.loads(body)
        session_id = data.get("session_id")

        if session_id:
            with active_sessions_lock:
                if session_id in active_sessions:
                    print(f"⚠️ Session {session_id} is already scheduled or processing, skipping duplicate queue message.")
                else:
                    active_sessions.add(session_id)
                    queued_sessions = len(active_sessions)
                    print(
                        f"🧵 Scheduling session {session_id} in CRE worker pool "
                        f"({queued_sessions}/{MAX_CONCURRENT_SESSIONS} active or queued)"
                    )
                    executor.submit(process_session_in_background, session_id)

    except Exception as e:
        print("❌ Error processing CRE message:", e)

    ch.basic_ack(delivery_tag=method.delivery_tag)


def connect_to_rabbitmq():
    """Maakt verbinding met RabbitMQ en herstelt de verbinding zonder opnieuw te verwerken."""
    while True:
        try:
            print(f"🔌 Connecting to RabbitMQ at {RABBITMQ_HOST}...")
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue="cre_queue", durable=True)
            channel.basic_qos(prefetch_count=max(1, MAX_CONCURRENT_SESSIONS * 2))
            channel.basic_consume(queue="cre_queue", on_message_callback=callback)

            print(
                f"🎧 Waiting for messages on 'cre_queue' with up to "
                f"{MAX_CONCURRENT_SESSIONS} concurrent CRE session(s). To exit press CTRL+C"
            )
            channel.start_consuming()

        except (pika.exceptions.AMQPConnectionError, pika.exceptions.StreamLostError) as e:
            print(f"⚠️ RabbitMQ connection lost: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)  # Wacht 5 seconden en probeer opnieuw
        except KeyboardInterrupt:
            print("❌ CRE-service stopped.")
            break


if __name__ == "__main__":
    print("🚀 Starting CRE service...")
    print(
        f"⚙️ CRE concurrency resolved to {MAX_CONCURRENT_SESSIONS} "
        f"({MAX_CONCURRENT_SESSIONS_REASON})"
    )
    connect_to_rabbitmq()

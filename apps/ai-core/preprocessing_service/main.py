import os
import json
import pika
import time
import subprocess
from fastapi import FastAPI
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session, declarative_base

RABBITMQ_HOST = os.getenv("MQ_HOST", "rabbitmq_broker")
DATABASE_URL = os.environ["DATABASE_URL"]
Base = declarative_base()

class Collection(Base):
    __tablename__ = "collections"
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="unscanned", nullable=False)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def update_collection_status(collection_id: int, new_status: str, db: Session):
    """Update de status van een collectie in PostgreSQL."""
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if collection:
        collection.status = new_status
        db.commit()
        print(f"✅ Updated collection {collection_id} status to '{new_status}'")
    else:
        print(f"❌ Collection {collection_id} not found!")

def publish_to_chunking_queue(collection_id: int):
    """Stuur een bericht naar de chunking_queue na preprocessing."""
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue="chunking_queue", durable=True)

        message = json.dumps({"collection_id": collection_id})
        channel.basic_publish(
            exchange="",
            routing_key="chunking_queue",
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,
            )
        )
        connection.close()
        print(f"📩 Published collection {collection_id} to chunking_queue.")
    except Exception as e:
        print(f"❌ Error publishing to chunking_queue: {e}")


def start_preprocessing(collection_id: int):
    """Start `preprocessing.py` als een subproces en publiceert daarna naar de chunking_queue."""
    print(f"Checking if preprocessing should start for collection ID: {collection_id}")

    db: Session = SessionLocal()
    try:
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if collection:
            if collection.status in ["pre_processing", "chunking", "scanned"]:
                print(f"⚠️ Collection {collection_id} is already in status '{collection.status}'. Skipping preprocessing.")
                return

            collection.status = "pre_processing"
            db.commit()
            print(f"✅ Updated collection {collection_id} status to 'pre_processing'")

        else:
            print(f"❌ Collection {collection_id} not found!")
            return

    except Exception as e:
        print(f"❌ Error updating collection status: {e}")
        return
    finally:
        db.close()

    try:
        print(f"Preprocessing gestart voor collectie {collection_id}...")
        result = subprocess.run(["python", "preprocessing.py"], env={**os.environ, "COLLECTION_ID": str(collection_id)}, check=True)

        if result.returncode == 0:
            print(f"✅ Preprocessing voltooid voor collectie {collection_id}.")
            publish_to_chunking_queue(collection_id)  # Publiceer naar chunking queue
        else:
            print(f"❌ Preprocessing mislukt voor collectie {collection_id}, geen publicatie naar chunking.")

    except subprocess.CalledProcessError as e:
        print(f"❌ Error bij uitvoeren van preprocessing.py: {e}")


def callback(ch, method, properties, body):
    """Verwerkt RabbitMQ-berichten en start preprocessing."""
    print("📨 Received message:", body.decode())
    try:
        data = json.loads(body)
        collection_id = data.get("collection_id")

        if collection_id:
            start_preprocessing(collection_id)

    except Exception as e:
        print("❌ Error processing message:", e)

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
            print(f"🔌 Connecting to RabbitMQ at {RABBITMQ_HOST}...")
            connection = connect_to_rabbitmq()
            channel = connection.channel()
            channel.queue_declare(queue="preprocessing_queue", durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="preprocessing_queue", on_message_callback=callback)

            print("🎧 Waiting for messages on 'preprocessing_queue'. To exit press CTRL+C")
            channel.start_consuming()

        except (pika.exceptions.AMQPConnectionError, pika.exceptions.StreamLostError) as e:
            print(f"🔄 RabbitMQ connection lost: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("❌ Preprocessing-service stopped.")
            break


if __name__ == "__main__":
    print("🚀 Starting preprocessing service...")
    main()

import os
import json
import pika
import time
import subprocess
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

def update_collection_status(collection_id: int, new_status: str):
    """Update de status van een collectie in PostgreSQL."""
    db: Session = SessionLocal()
    try:
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if collection:
            collection.status = new_status
            db.commit()
            print(f"✅ Updated collection {collection_id} status to '{new_status}'")
        else:
            print(f"❌ Collection {collection_id} not found!")
    except Exception as e:
        print(f"❌ Error updating collection status: {e}")
    finally:
        db.close()

def start_chunking(collection_id: int):
    """Start `chunking.py` als een subproces en update de status."""
    print(f"🚀 Starting chunking for collection ID: {collection_id}")

    db: Session = SessionLocal()
    try:
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if collection:
            collection.status = "chunking"
            db.commit()
            print(f"✅ Updated collection {collection_id} status to 'chunking'")
        else:
            print(f"❌ Collection {collection_id} not found!")
            return  # Stop als de collectie niet bestaat
    except Exception as e:
        print(f"❌ Error updating collection status: {e}")
        return  # Stop bij een fout
    finally:
        db.close()

    try:
        print(f"🔄 Chunking gestart voor collectie {collection_id}...")
        result = subprocess.run(["python", "chunking.py"], env={**os.environ, "COLLECTION_ID": str(collection_id)}, check=True)

        if result.returncode == 0:
            print(f"✅ Chunking voltooid voor collectie {collection_id}.")
            update_collection_status(collection_id, "scanned")  # Update status naar 'scanned'
        else:
            print(f"❌ Chunking mislukt voor collectie {collection_id}, status blijft 'chunking'.")

    except subprocess.CalledProcessError as e:
        print(f"❌ Error bij uitvoeren van chunking.py: {e}")

def callback(ch, method, properties, body):
    """Verwerkt RabbitMQ-berichten en start chunking."""
    print("Received message for chunking:", body.decode())
    try:
        data = json.loads(body)
        collection_id = data.get("collection_id")

        if collection_id:
            start_chunking(collection_id)

    except Exception as e:
        print("❌ Error processing chunking message:", e)

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
    while True:  # Blijft draaien en herstelt de verbinding als deze verbreekt
        try:
            print(f"Connecting to RabbitMQ at {RABBITMQ_HOST}...")
            connection = connect_to_rabbitmq()
            channel = connection.channel()
            channel.queue_declare(queue="chunking_queue", durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="chunking_queue", on_message_callback=callback)

            print("🎧 Waiting for messages on 'chunking_queue'. To exit press CTRL+C")
            channel.start_consuming()

        except (pika.exceptions.AMQPConnectionError, pika.exceptions.StreamLostError) as e:
            print(f"🔄 RabbitMQ connection lost: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)  # Wacht 5 seconden en probeer opnieuw
        except KeyboardInterrupt:
            print("❌ Chunking-service stopped.")
            break

if __name__ == "__main__":
    print("🚀 Starting chunking service...")
    main()

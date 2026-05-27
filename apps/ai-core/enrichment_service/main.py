import json
import os
import time

import pika

from enrichment import mark_finished_with_warning, process_and_store

RABBITMQ_HOST = os.getenv("MQ_HOST", "rabbitmq_broker")


def callback(ch, method, properties, body):
    print("📨 Received message for enrichment processing:", body.decode())

    session_id = None
    try:
        data = json.loads(body)
        session_id = data.get("session_id")
        if not session_id:
            print("❌ No session_id received for enrichment.")
        else:
            process_and_store(session_id)
            print(f"✅ Enrichment completed for session {session_id}.")
    except Exception as exc:
        print(f"❌ Enrichment failed: {exc}")
        if session_id:
            mark_finished_with_warning(session_id, str(exc))

    ch.basic_ack(delivery_tag=method.delivery_tag)


def connect_to_rabbitmq(retries=5, delay=5):
    for i in range(retries):
        try:
            return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        except pika.exceptions.AMQPConnectionError:
            print(f"⚠️ RabbitMQ connection failed ({i + 1}/{retries}). Retrying in {delay} seconds...")
            time.sleep(delay)
    raise Exception("❌ Failed to connect to RabbitMQ after multiple attempts.")


def main():
    while True:
        try:
            print(f"Connecting to RabbitMQ at {RABBITMQ_HOST}...")
            connection = connect_to_rabbitmq()
            channel = connection.channel()
            channel.queue_declare(queue="enrichment_queue", durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue="enrichment_queue", on_message_callback=callback)

            print("🎧 Waiting for messages on 'enrichment_queue'. To exit press CTRL+C")
            channel.start_consuming()
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.StreamLostError) as exc:
            print(f"🔄 RabbitMQ connection lost: {exc}. Reconnecting in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("❌ Enrichment service stopped.")
            break


if __name__ == "__main__":
    print("🚀 Starting enrichment service...")
    main()

#!/usr/bin/env python3
"""
Kafka Producer - Replay CSV clickstream data to Kafka topic.
Simulates real-time event stream from historical data.
"""

import csv
import json
import time
import os
import sys
from datetime import datetime
from kafka import KafkaProducer
import yaml

def load_config():
    """Load configuration from YAML file."""
    config_path = os.environ.get('CONFIG_PATH', '/app/config/config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def create_producer(bootstrap_servers):
    """Create Kafka producer with retry logic."""
    max_retries = 30
    retry_interval = 5

    for attempt in range(max_retries):
        try:
            producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3,
                batch_size=16384,
                linger_ms=10
            )
            print(f"[OK] Connected to Kafka at {bootstrap_servers}")
            return producer
        except Exception as e:
            print(f"[RETRY {attempt + 1}/{max_retries}] Waiting for Kafka... ({e})")
            time.sleep(retry_interval)

    raise Exception("Failed to connect to Kafka after maximum retries")

def process_event(row, add_timestamp=True):
    """Process CSV row into event dictionary."""
    event = {
        'event_time': row.get('event_time', ''),
        'event_type': row.get('event_type', ''),
        'product_id': row.get('product_id', ''),
        'category_id': row.get('category_id', ''),
        'category_code': row.get('category_code', ''),
        'brand': row.get('brand', ''),
        'price': float(row.get('price', 0)) if row.get('price') else 0.0,
        'user_id': row.get('user_id', ''),
        'user_session': row.get('user_session', '')
    }

    if add_timestamp:
        event['ingestion_time'] = datetime.utcnow().isoformat()

    return event

def replay_csv(config):
    """Replay CSV file to Kafka topic."""
    kafka_config = config['kafka']
    producer_config = config['producer']

    bootstrap_servers = os.environ.get(
        'KAFKA_BOOTSTRAP_SERVERS',
        kafka_config['bootstrap_servers']
    )
    topic = os.environ.get('KAFKA_TOPIC', kafka_config['topic'])
    csv_path = producer_config['csv_path']
    message_delay = producer_config['message_delay']
    batch_size = producer_config['batch_size']
    add_timestamp = producer_config['add_timestamp']

    # Create producer
    producer = create_producer(bootstrap_servers)

    # Check if CSV exists
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV file not found: {csv_path}")
        print("[INFO] Please download the dataset and place it in data/raw/events.csv")
        print("[INFO] Dataset: https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop")
        sys.exit(1)

    print(f"[INFO] Starting replay from: {csv_path}")
    print(f"[INFO] Topic: {topic}")
    print(f"[INFO] Message delay: {message_delay}s")

    sent_count = 0
    start_time = time.time()

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                event = process_event(row, add_timestamp)

                # Use user_session as key for partitioning
                key = event.get('user_session', '')

                producer.send(topic, key=key, value=event)
                sent_count += 1

                # Flush periodically
                if sent_count % batch_size == 0:
                    producer.flush()
                    elapsed = time.time() - start_time
                    rate = sent_count / elapsed if elapsed > 0 else 0
                    print(f"[PROGRESS] Sent {sent_count:,} events ({rate:.1f} events/sec)")

                # Simulate real-time delay
                if message_delay > 0:
                    time.sleep(message_delay)

    except KeyboardInterrupt:
        print("\n[INFO] Producer stopped by user")

    finally:
        producer.flush()
        producer.close()

        elapsed = time.time() - start_time
        rate = sent_count / elapsed if elapsed > 0 else 0
        print(f"\n[COMPLETE] Sent {sent_count:,} events in {elapsed:.1f}s ({rate:.1f} events/sec)")

if __name__ == '__main__':
    config = load_config()
    replay_csv(config)

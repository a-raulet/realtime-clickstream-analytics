#!/usr/bin/env python3
"""
Spark Structured Streaming - Process clickstream events from Kafka and write to Delta Lake.
"""

import os
import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, window, count, sum as spark_sum,
    avg, approx_count_distinct, current_timestamp,
    when
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, TimestampType
)


def get_config():
    """Get configuration from environment variables with defaults."""
    delta_base = os.environ.get('DELTA_PATH', '/app/delta')

    return {
        'kafka': {
            'bootstrap_servers': os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9093'),
            'topic': os.environ.get('KAFKA_TOPIC', 'clickstream'),
        },
        'spark': {
            'app_name': 'ClickstreamAnalytics',
            'trigger_interval': '10 seconds',
            'watermark': '1 minute',
            'checkpoint_location': f'{delta_base}/checkpoints',
        },
        'delta': {
            'tables': {
                'events_raw': f'{delta_base}/events_raw',
                'events_1min': f'{delta_base}/aggregations/events_1min',
                'events_5min': f'{delta_base}/aggregations/events_5min',
                'products': f'{delta_base}/aggregations/products',
                'funnel': f'{delta_base}/aggregations/funnel',
            }
        }
    }


def create_spark_session(config):
    """Create Spark session with Delta Lake support."""
    spark = SparkSession.builder \
        .appName(config['spark']['app_name']) \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.sql.shuffle.partitions", "4") \
        .config("spark.sql.streaming.schemaInference", "true") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")
    return spark


def get_event_schema():
    """Define schema for clickstream events."""
    return StructType([
        StructField("event_time", StringType(), True),
        StructField("event_type", StringType(), True),
        StructField("product_id", StringType(), True),
        StructField("category_id", StringType(), True),
        StructField("category_code", StringType(), True),
        StructField("brand", StringType(), True),
        StructField("price", DoubleType(), True),
        StructField("user_id", StringType(), True),
        StructField("user_session", StringType(), True),
        StructField("ingestion_time", StringType(), True)
    ])


def read_kafka_stream(spark, config):
    """Read streaming data from Kafka."""
    bootstrap_servers = config['kafka']['bootstrap_servers']
    topic = config['kafka']['topic']

    print(f"[INFO] Connecting to Kafka at {bootstrap_servers}", flush=True)
    print(f"[INFO] Subscribing to topic: {topic}", flush=True)

    return spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", bootstrap_servers) \
        .option("subscribe", topic) \
        .option("startingOffsets", "earliest") \
        .option("failOnDataLoss", "false") \
        .load()


def parse_events(df, schema):
    """Parse JSON events from Kafka messages."""
    return df.select(
        from_json(col("value").cast("string"), schema).alias("data"),
        col("timestamp").alias("kafka_timestamp")
    ).select(
        col("data.*"),
        col("kafka_timestamp")
    ).withColumn(
        "event_timestamp",
        when(col("ingestion_time").isNotNull(),
             col("ingestion_time").cast(TimestampType()))
        .otherwise(current_timestamp())
    )


def write_raw_events(events_df, config):
    """Write raw events to Delta Lake."""
    delta_path = config['delta']['tables']['events_raw']
    checkpoint = f"{config['spark']['checkpoint_location']}/raw"

    return events_df.writeStream \
        .format("delta") \
        .outputMode("append") \
        .option("checkpointLocation", checkpoint) \
        .trigger(processingTime=config['spark']['trigger_interval']) \
        .start(delta_path)


def compute_1min_aggregations(events_df, config):
    """Compute 1-minute window aggregations."""
    agg_df = events_df \
        .withWatermark("event_timestamp", config['spark']['watermark']) \
        .groupBy(
            window(col("event_timestamp"), "1 minute", "30 seconds"),
            col("event_type")
        ).agg(
            count("*").alias("event_count"),
            approx_count_distinct("user_session").alias("unique_sessions"),
            approx_count_distinct("user_id").alias("unique_users"),
            spark_sum("price").alias("total_revenue"),
            avg("price").alias("avg_price")
        ).select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("event_type"),
            col("event_count"),
            col("unique_sessions"),
            col("unique_users"),
            col("total_revenue"),
            col("avg_price")
        )

    delta_path = config['delta']['tables']['events_1min']
    checkpoint = f"{config['spark']['checkpoint_location']}/1min"

    return agg_df.writeStream \
        .format("delta") \
        .outputMode("complete") \
        .option("checkpointLocation", checkpoint) \
        .trigger(processingTime=config['spark']['trigger_interval']) \
        .start(delta_path)


def compute_5min_aggregations(events_df, config):
    """Compute 5-minute window aggregations."""
    agg_df = events_df \
        .withWatermark("event_timestamp", config['spark']['watermark']) \
        .groupBy(
            window(col("event_timestamp"), "5 minutes", "1 minute"),
            col("event_type")
        ).agg(
            count("*").alias("event_count"),
            approx_count_distinct("user_session").alias("unique_sessions"),
            approx_count_distinct("user_id").alias("unique_users"),
            spark_sum("price").alias("total_revenue"),
            avg("price").alias("avg_price")
        ).select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("event_type"),
            col("event_count"),
            col("unique_sessions"),
            col("unique_users"),
            col("total_revenue"),
            col("avg_price")
        )

    delta_path = config['delta']['tables']['events_5min']
    checkpoint = f"{config['spark']['checkpoint_location']}/5min"

    return agg_df.writeStream \
        .format("delta") \
        .outputMode("complete") \
        .option("checkpointLocation", checkpoint) \
        .trigger(processingTime=config['spark']['trigger_interval']) \
        .start(delta_path)


def compute_top_products(events_df, config):
    """Compute top products by views and purchases."""
    products_df = events_df \
        .filter(col("event_type").isin("view", "purchase", "cart")) \
        .withWatermark("event_timestamp", config['spark']['watermark']) \
        .groupBy(
            window(col("event_timestamp"), "5 minutes", "1 minute"),
            col("product_id"),
            col("category_code"),
            col("brand")
        ).agg(
            count(when(col("event_type") == "view", 1)).alias("views"),
            count(when(col("event_type") == "cart", 1)).alias("add_to_cart"),
            count(when(col("event_type") == "purchase", 1)).alias("purchases"),
            spark_sum(when(col("event_type") == "purchase", col("price"))).alias("revenue")
        ).select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("product_id"),
            col("category_code"),
            col("brand"),
            col("views"),
            col("add_to_cart"),
            col("purchases"),
            col("revenue")
        )

    delta_path = config['delta']['tables']['products']
    checkpoint = f"{config['spark']['checkpoint_location']}/products"

    return products_df.writeStream \
        .format("delta") \
        .outputMode("complete") \
        .option("checkpointLocation", checkpoint) \
        .trigger(processingTime=config['spark']['trigger_interval']) \
        .start(delta_path)


def compute_funnel(events_df, config):
    """Compute conversion funnel metrics."""
    funnel_df = events_df \
        .withWatermark("event_timestamp", config['spark']['watermark']) \
        .groupBy(
            window(col("event_timestamp"), "5 minutes", "1 minute")
        ).agg(
            count(when(col("event_type") == "view", 1)).alias("views"),
            count(when(col("event_type") == "cart", 1)).alias("add_to_cart"),
            count(when(col("event_type") == "purchase", 1)).alias("purchases"),
            approx_count_distinct(
                when(col("event_type") == "view", col("user_session"))
            ).alias("users_viewed"),
            approx_count_distinct(
                when(col("event_type") == "cart", col("user_session"))
            ).alias("users_added_cart"),
            approx_count_distinct(
                when(col("event_type") == "purchase", col("user_session"))
            ).alias("users_purchased")
        ).select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("views"),
            col("add_to_cart"),
            col("purchases"),
            col("users_viewed"),
            col("users_added_cart"),
            col("users_purchased")
        )

    delta_path = config['delta']['tables']['funnel']
    checkpoint = f"{config['spark']['checkpoint_location']}/funnel"

    return funnel_df.writeStream \
        .format("delta") \
        .outputMode("complete") \
        .option("checkpointLocation", checkpoint) \
        .trigger(processingTime=config['spark']['trigger_interval']) \
        .start(delta_path)


def main():
    """Main entry point."""
    print("=" * 60, flush=True)
    print("  Clickstream Analytics - Spark Streaming Job", flush=True)
    print("=" * 60, flush=True)

    # Load configuration
    config = get_config()
    print(f"[INFO] Delta path: {os.environ.get('DELTA_PATH', '/app/delta')}", flush=True)

    # Create Spark session
    spark = create_spark_session(config)
    print("[OK] Spark session created", flush=True)

    # Read from Kafka
    kafka_df = read_kafka_stream(spark, config)
    print("[OK] Kafka stream connected", flush=True)

    # Parse events
    events_df = parse_events(kafka_df, get_event_schema())
    print("[OK] Event schema applied", flush=True)

    # Start streaming queries
    print("[INFO] Starting streaming queries...", flush=True)

    queries = []

    # Raw events
    queries.append(write_raw_events(events_df, config))
    print("[OK] Raw events query started", flush=True)

    # 1-minute aggregations
    queries.append(compute_1min_aggregations(events_df, config))
    print("[OK] 1-minute aggregations query started", flush=True)

    # 5-minute aggregations
    queries.append(compute_5min_aggregations(events_df, config))
    print("[OK] 5-minute aggregations query started", flush=True)

    # Top products
    queries.append(compute_top_products(events_df, config))
    print("[OK] Top products query started", flush=True)

    # Funnel metrics
    queries.append(compute_funnel(events_df, config))
    print("[OK] Funnel metrics query started", flush=True)

    print("\n" + "=" * 60, flush=True)
    print("  All streaming queries running!", flush=True)
    print("  Writing to Delta Lake tables:", flush=True)
    for table_name, table_path in config['delta']['tables'].items():
        print(f"    - {table_name}: {table_path}", flush=True)
    print("=" * 60 + "\n", flush=True)

    # Wait for all queries
    for query in queries:
        query.awaitTermination()


if __name__ == '__main__':
    main()

.PHONY: help start stop restart logs clean build status producer streaming dashboard all setup-topic test-kafka

# Docker Compose command (v2 syntax)
COMPOSE := docker compose

# Default target
help:
	@echo "========================================================================"
	@echo "     Real-time Clickstream Analytics - Available Commands"
	@echo "========================================================================"
	@echo ""
	@echo "  Infrastructure:"
	@echo "    make start       - Start Kafka + Zookeeper"
	@echo "    make stop        - Stop all services"
	@echo "    make restart     - Restart all services"
	@echo "    make status      - Show status of all containers"
	@echo "    make logs        - Follow logs of all services"
	@echo "    make clean       - Stop and remove all containers/volumes/data"
	@echo "    make build       - Build all Docker images"
	@echo ""
	@echo "  Applications:"
	@echo "    make producer    - Start the Kafka producer"
	@echo "    make streaming   - Start Spark Streaming job"
	@echo "    make dashboard   - Start Streamlit dashboard"
	@echo "    make pipeline    - Start full pipeline (streaming + producer + dashboard)"
	@echo ""
	@echo "  Utilities:"
	@echo "    make setup-topic - Create Kafka topic manually"
	@echo "    make test-kafka  - Test Kafka connectivity"
	@echo "    make consume     - Consume messages from topic (debug)"
	@echo "    make logs-kafka  - Follow Kafka logs only"
	@echo "    make logs-spark  - Follow Spark Streaming logs"
	@echo "    make shell-kafka - Open shell in Kafka container"
	@echo ""
	@echo "========================================================================"

# ============================================
# INFRASTRUCTURE COMMANDS
# ============================================

# Start base infrastructure (Zookeeper, Kafka)
start:
	@echo "Starting infrastructure (Zookeeper, Kafka)..."
	$(COMPOSE) up -d zookeeper kafka
	@echo "Infrastructure started!"
	@echo "  - Kafka: localhost:9092"
	@echo ""
	@echo "Waiting for Kafka to be ready..."
	@sleep 10
	@$(MAKE) status

# Stop all services
stop:
	@echo "Stopping all services..."
	$(COMPOSE) --profile producer --profile streaming --profile dashboard down
	@echo "All services stopped"

# Restart all services
restart: stop start

# Show status
status:
	@echo "Container Status:"
	@$(COMPOSE) ps -a

# Follow all logs
logs:
	$(COMPOSE) logs -f

# Clean everything
clean:
	@echo "Cleaning up..."
	$(COMPOSE) --profile producer --profile streaming --profile dashboard down -v --remove-orphans
	@echo "Removing Delta Lake data..."
	rm -rf delta/*
	@echo "Cleanup complete"

# Build all images
build:
	@echo "Building Docker images..."
	$(COMPOSE) --profile producer --profile streaming --profile dashboard build
	@echo "Build complete"

# ============================================
# APPLICATION COMMANDS
# ============================================

# Start Kafka producer
producer:
	@echo "Starting Kafka Producer..."
	$(COMPOSE) --profile producer up -d kafka-producer
	@echo "Producer started! Following logs..."
	$(COMPOSE) logs -f kafka-producer

# Start Kafka producer (detached, no logs)
producer-detached:
	@echo "Starting Kafka Producer (detached)..."
	$(COMPOSE) --profile producer up -d kafka-producer
	@echo "Producer started!"

# Start Spark Streaming
streaming:
	@echo "Starting Spark Streaming job..."
	$(COMPOSE) --profile streaming up -d spark-streaming
	@echo "Streaming job started!"
	@echo "  - Spark UI: http://localhost:4040"
	@echo "Following logs..."
	$(COMPOSE) logs -f spark-streaming

# Start Spark Streaming (detached, no logs)
streaming-detached:
	@echo "Starting Spark Streaming job (detached)..."
	$(COMPOSE) --profile streaming up -d spark-streaming
	@echo "Streaming job started!"
	@echo "  - Spark UI: http://localhost:4040"

# Start Streamlit Dashboard
dashboard:
	@echo "Starting Streamlit Dashboard..."
	$(COMPOSE) --profile dashboard up -d streamlit
	@echo "Dashboard started!"
	@echo "  - URL: http://localhost:8501"
	$(COMPOSE) logs -f streamlit

# Start Streamlit Dashboard (detached, no logs)
dashboard-detached:
	@echo "Starting Streamlit Dashboard (detached)..."
	$(COMPOSE) --profile dashboard up -d streamlit
	@echo "Dashboard started!"
	@echo "  - URL: http://localhost:8501"

# Start full pipeline
pipeline: start
	@echo "Waiting for Kafka to stabilize..."
	@sleep 5
	@$(MAKE) streaming-detached
	@echo "Waiting for Spark to initialize..."
	@sleep 10
	@$(MAKE) producer-detached
	@sleep 2
	@$(MAKE) dashboard-detached
	@echo ""
	@echo "========================================"
	@echo "  Pipeline started successfully!"
	@echo "========================================"
	@echo "  - Dashboard: http://localhost:8501"
	@echo "  - Spark UI:  http://localhost:4040"
	@echo "========================================"
	@$(MAKE) status

# ============================================
# UTILITY COMMANDS
# ============================================

# Create Kafka topic
setup-topic:
	@echo "Creating Kafka topic 'clickstream'..."
	$(COMPOSE) exec kafka kafka-topics.sh \
		--create \
		--bootstrap-server localhost:9092 \
		--replication-factor 1 \
		--partitions 3 \
		--topic clickstream \
		--if-not-exists
	@echo "Topic created!"

# Test Kafka
test-kafka:
	@echo "Testing Kafka connectivity..."
	@echo "Listing topics:"
	$(COMPOSE) exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092
	@echo ""
	@echo "Kafka is working!"

# Kafka logs only
logs-kafka:
	$(COMPOSE) logs -f kafka zookeeper

# Spark Streaming logs
logs-spark:
	$(COMPOSE) logs -f spark-streaming

# Dashboard logs
logs-dashboard:
	$(COMPOSE) logs -f streamlit

# Shell into Kafka container
shell-kafka:
	$(COMPOSE) exec kafka /bin/bash

# Consume messages from topic (for debugging)
consume:
	@echo "Consuming messages from 'clickstream' topic (Ctrl+C to stop)..."
	$(COMPOSE) exec kafka kafka-console-consumer.sh \
		--bootstrap-server localhost:9092 \
		--topic clickstream \
		--from-beginning

# Produce test message
test-produce:
	@echo "Sending test message..."
	$(COMPOSE) exec kafka /bin/bash -c "echo '{\"test\": \"message\"}' | kafka-console-producer.sh --bootstrap-server localhost:9092 --topic clickstream"
	@echo "Test message sent!"

# Show Kafka topic info
topic-info:
	@echo "Topic 'clickstream' info:"
	$(COMPOSE) exec kafka kafka-topics.sh \
		--describe \
		--bootstrap-server localhost:9092 \
		--topic clickstream

# Count messages in topic
topic-count:
	@echo "Message count per partition:"
	$(COMPOSE) exec kafka kafka-run-class.sh kafka.tools.GetOffsetShell \
		--broker-list localhost:9092 \
		--topic clickstream

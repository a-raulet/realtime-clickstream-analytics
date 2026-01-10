#!/bin/bash
#
# Real-time Clickstream Analytics - Deployment Script
# Usage: ./deploy.sh [--with-sample-data]
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/USERNAME/realtime-clickstream-analytics.git"
APP_DIR="/opt/clickstream"
APP_USER="clickstream"
SWAP_SIZE="4G"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

print_banner() {
    echo ""
    echo "========================================================"
    echo "   Real-time Clickstream Analytics - VPS Deployment"
    echo "========================================================"
    echo ""
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Please run as root (sudo ./deploy.sh)"
    fi
}

check_os() {
    if [ ! -f /etc/os-release ]; then
        log_error "Cannot detect OS. This script requires Ubuntu 20.04+"
    fi

    . /etc/os-release
    if [ "$ID" != "ubuntu" ]; then
        log_warn "This script is designed for Ubuntu. Your OS: $ID"
    fi
    log_success "OS: $PRETTY_NAME"
}

check_resources() {
    log_info "Checking system resources..."

    # Check RAM
    TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$TOTAL_RAM" -lt 3 ]; then
        log_warn "Low RAM detected (${TOTAL_RAM}GB). Minimum recommended: 4GB"
    else
        log_success "RAM: ${TOTAL_RAM}GB"
    fi

    # Check disk space
    FREE_DISK=$(df -BG / | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$FREE_DISK" -lt 15 ]; then
        log_warn "Low disk space (${FREE_DISK}GB free). Minimum recommended: 20GB"
    else
        log_success "Disk: ${FREE_DISK}GB free"
    fi

    # Check CPU
    CPU_CORES=$(nproc)
    log_success "CPU: ${CPU_CORES} cores"
}

install_dependencies() {
    log_info "Installing system dependencies..."

    apt-get update -qq
    apt-get install -y -qq curl git wget unzip htop

    log_success "Dependencies installed"
}

install_docker() {
    log_info "Installing Docker..."

    if command -v docker &> /dev/null; then
        log_success "Docker already installed: $(docker --version)"
    else
        curl -fsSL https://get.docker.com | sh
        log_success "Docker installed: $(docker --version)"
    fi

    # Install Docker Compose plugin if not present
    if ! docker compose version &> /dev/null; then
        apt-get install -y -qq docker-compose-plugin
    fi
    log_success "Docker Compose: $(docker compose version --short)"
}

setup_swap() {
    log_info "Setting up swap space..."

    if [ -f /swapfile ]; then
        log_success "Swap already configured"
        return
    fi

    fallocate -l $SWAP_SIZE /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab

    # Optimize swap
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
    sysctl -p > /dev/null 2>&1

    log_success "Swap configured: $SWAP_SIZE"
}

create_user() {
    log_info "Creating application user..."

    if id "$APP_USER" &>/dev/null; then
        log_success "User $APP_USER already exists"
    else
        useradd -m -s /bin/bash $APP_USER
        log_success "User $APP_USER created"
    fi

    usermod -aG docker $APP_USER
}

clone_project() {
    log_info "Setting up project directory..."

    if [ -d "$APP_DIR" ]; then
        log_warn "Directory $APP_DIR already exists. Pulling latest..."
        cd $APP_DIR
        git pull
    else
        mkdir -p $APP_DIR

        # Check if we're already in the repo
        if [ -f "docker-compose.yml" ]; then
            log_info "Copying local files..."
            cp -r . $APP_DIR/
        else
            log_info "Cloning from $REPO_URL..."
            git clone $REPO_URL $APP_DIR
        fi
    fi

    chown -R $APP_USER:$APP_USER $APP_DIR
    log_success "Project ready at $APP_DIR"
}

setup_sample_data() {
    log_info "Setting up sample data..."

    cd $APP_DIR
    mkdir -p data/raw

    # Create a sample CSV with fake data for demo
    cat > data/raw/sample.csv << 'CSVEOF'
event_time,event_type,product_id,category_id,category_code,brand,price,user_id,user_session
2019-10-01 00:00:00 UTC,view,5300797,2053013563424899933,appliances.kitchen.washer,bosch,399.99,520088904,a3c1d5e2-5c7f-4f1a-9c3d-2f5a6b7c8d9e
2019-10-01 00:00:01 UTC,view,5300798,2053013563424899933,appliances.kitchen.refrigerator,samsung,599.99,520088905,b4d2e6f3-6d8g-5g2b-0d4e-3g6b7c8d9e0f
2019-10-01 00:00:02 UTC,cart,5300797,2053013563424899933,appliances.kitchen.washer,bosch,399.99,520088904,a3c1d5e2-5c7f-4f1a-9c3d-2f5a6b7c8d9e
2019-10-01 00:00:03 UTC,view,5300799,2053013563424899934,electronics.smartphone,apple,999.99,520088906,c5e3f7g4-7e9h-6h3c-1e5f-4h7c8d9e0f1g
2019-10-01 00:00:04 UTC,view,5300800,2053013563424899934,electronics.smartphone,samsung,799.99,520088907,d6f4g8h5-8f0i-7i4d-2f6g-5i8d9e0f1g2h
2019-10-01 00:00:05 UTC,cart,5300799,2053013563424899934,electronics.smartphone,apple,999.99,520088906,c5e3f7g4-7e9h-6h3c-1e5f-4h7c8d9e0f1g
2019-10-01 00:00:06 UTC,purchase,5300797,2053013563424899933,appliances.kitchen.washer,bosch,399.99,520088904,a3c1d5e2-5c7f-4f1a-9c3d-2f5a6b7c8d9e
2019-10-01 00:00:07 UTC,view,5300801,2053013563424899935,computers.laptop,lenovo,699.99,520088908,e7g5h9i6-9g1j-8j5e-3g7h-6j9e0f1g2h3i
2019-10-01 00:00:08 UTC,view,5300802,2053013563424899935,computers.laptop,apple,1299.99,520088909,f8h6i0j7-0h2k-9k6f-4h8i-7k0f1g2h3i4j
2019-10-01 00:00:09 UTC,cart,5300800,2053013563424899934,electronics.smartphone,samsung,799.99,520088907,d6f4g8h5-8f0i-7i4d-2f6g-5i8d9e0f1g2h
CSVEOF

    # Generate more sample data
    log_info "Generating 10,000 sample events..."

    python3 << 'PYEOF'
import csv
import random
from datetime import datetime, timedelta

events = ["view", "cart", "purchase", "remove_from_cart"]
brands = ["apple", "samsung", "bosch", "lenovo", "sony", "lg", "xiaomi", "huawei"]
categories = [
    ("electronics.smartphone", 799.99),
    ("electronics.tablet", 499.99),
    ("appliances.kitchen.washer", 399.99),
    ("appliances.kitchen.refrigerator", 599.99),
    ("computers.laptop", 999.99),
    ("computers.desktop", 699.99),
]

with open("data/raw/sample.csv", "a", newline="") as f:
    writer = csv.writer(f)

    base_time = datetime(2019, 10, 1, 0, 0, 10)

    for i in range(10000):
        event_time = base_time + timedelta(seconds=i)
        event_type = random.choices(events, weights=[60, 25, 10, 5])[0]
        product_id = random.randint(5300000, 5400000)
        category = random.choice(categories)
        brand = random.choice(brands)
        price = round(category[1] * random.uniform(0.8, 1.2), 2)
        user_id = random.randint(520000000, 530000000)
        session = f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}"

        writer.writerow([
            event_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            event_type,
            product_id,
            random.randint(2000000000000000000, 2100000000000000000),
            category[0],
            brand,
            price,
            user_id,
            session
        ])

print("Generated 10,000 sample events")
PYEOF

    # Update config to use sample data
    sed -i 's|csv_path:.*|csv_path: "/app/data/raw/sample.csv"|' config/config.yaml

    chown -R $APP_USER:$APP_USER data/
    log_success "Sample data created (10,000 events)"
}

build_images() {
    log_info "Building Docker images..."

    cd $APP_DIR
    sudo -u $APP_USER docker compose --profile producer --profile streaming --profile dashboard build

    log_success "Docker images built"
}

start_pipeline() {
    log_info "Starting the pipeline..."

    cd $APP_DIR
    sudo -u $APP_USER docker compose up -d zookeeper kafka

    log_info "Waiting for Kafka to be ready..."
    sleep 15

    sudo -u $APP_USER docker compose --profile streaming up -d spark-streaming
    sleep 10

    sudo -u $APP_USER docker compose --profile producer up -d kafka-producer
    sleep 5

    sudo -u $APP_USER docker compose --profile dashboard up -d streamlit

    log_success "Pipeline started"
}

setup_systemd() {
    log_info "Setting up systemd service..."

    cat > /etc/systemd/system/clickstream.service << EOF
[Unit]
Description=Clickstream Analytics Pipeline
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose --profile producer --profile streaming --profile dashboard up -d
ExecStop=/usr/bin/docker compose --profile producer --profile streaming --profile dashboard down

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable clickstream

    log_success "Systemd service created and enabled"
}

setup_firewall() {
    log_info "Configuring firewall..."

    if ! command -v ufw &> /dev/null; then
        apt-get install -y -qq ufw
    fi

    ufw --force reset > /dev/null
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8501/tcp  # Streamlit (remove after Nginx setup)
    ufw --force enable

    log_success "Firewall configured"
}

print_summary() {
    # Get server IP
    SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

    echo ""
    echo "========================================================"
    echo "            Deployment Complete!"
    echo "========================================================"
    echo ""
    echo "  Dashboard URL: http://${SERVER_IP}:8501"
    echo "  Spark UI:      http://${SERVER_IP}:4040"
    echo ""
    echo "  Project dir:   $APP_DIR"
    echo "  User:          $APP_USER"
    echo ""
    echo "  Useful commands:"
    echo "    cd $APP_DIR"
    echo "    make status      # Check container status"
    echo "    make logs        # View logs"
    echo "    make stop        # Stop all services"
    echo "    make restart     # Restart all services"
    echo ""
    echo "  Next steps:"
    echo "    1. Configure a domain name (optional)"
    echo "    2. Setup Nginx reverse proxy (see DEPLOY.md)"
    echo "    3. Enable HTTPS with Let's Encrypt"
    echo ""
    echo "========================================================"
}

# Main
main() {
    print_banner
    check_root
    check_os
    check_resources

    install_dependencies
    install_docker
    setup_swap
    create_user
    clone_project

    # Check for --with-sample-data flag
    if [[ "$1" == "--with-sample-data" ]] || [[ ! -f "$APP_DIR/data/raw/2019-Oct.csv" ]]; then
        setup_sample_data
    fi

    build_images
    start_pipeline
    setup_systemd
    setup_firewall

    print_summary
}

main "$@"

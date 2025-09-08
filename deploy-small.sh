#!/bin/bash

# Optimized deployment script for small servers (512MB RAM)
# Specifically designed for DigitalOcean droplets with limited resources

set -e

echo "🚀 Starting optimized deployment for small server..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check system resources
check_resources() {
    log_info "Checking system resources..."
    
    TOTAL_MEM=$(free -m | awk 'NR==2{printf "%.0f", $2}')
    AVAILABLE_MEM=$(free -m | awk 'NR==2{printf "%.0f", $7}')
    DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    echo "  Total Memory: ${TOTAL_MEM}MB"
    echo "  Available Memory: ${AVAILABLE_MEM}MB"
    echo "  Disk Usage: ${DISK_USAGE}%"
    
    if [ "$TOTAL_MEM" -lt 480 ]; then
        log_error "Insufficient memory! Need at least 512MB"
        exit 1
    fi
    
    if [ "$DISK_USAGE" -gt 80 ]; then
        log_warning "Disk usage is high (${DISK_USAGE}%). Consider cleaning up space."
    fi
}

# Optimize system for low memory
optimize_system() {
    log_info "Optimizing system for low memory..."
    
    # Create swap file if it doesn't exist
    if [ ! -f /swapfile ]; then
        log_info "Creating 1GB swap file..."
        fallocate -l 1G /swapfile
        chmod 600 /swapfile
        mkswap /swapfile
        swapon /swapfile
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
        log_success "Swap file created"
    else
        log_info "Swap file already exists"
    fi
    
    # Optimize swappiness
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
    sysctl vm.swappiness=10
    
    # Optimize memory overcommit
    echo 'vm.overcommit_memory=1' >> /etc/sysctl.conf
    sysctl vm.overcommit_memory=1
    
    log_success "System optimized for low memory"
}

# Install Docker with minimal footprint
install_docker_minimal() {
    log_info "Installing Docker (minimal)..."
    
    if ! command -v docker &> /dev/null; then
        # Install Docker CE without recommended packages to save space
        apt-get update
        apt-get install -y --no-install-recommends \
            apt-transport-https \
            ca-certificates \
            curl \
            gnupg \
            lsb-release
            
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        apt-get update
        apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io
        
        systemctl enable docker
        systemctl start docker
        log_success "Docker installed"
    else
        log_info "Docker already installed"
    fi
    
    # Install Docker Compose (standalone)
    if ! command -v docker-compose &> /dev/null; then
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        log_success "Docker Compose installed"
    else
        log_info "Docker Compose already installed"
    fi
}

# Clean up system to free space
cleanup_system() {
    log_info "Cleaning up system to free space..."
    
    # Remove unnecessary packages
    apt-get autoremove -y
    apt-get autoclean
    
    # Clean package cache
    apt-get clean
    
    # Remove old kernels (keep current and one backup)
    dpkg -l 'linux-*' | sed '/^ii/!d;/'"$(uname -r | sed "s/\(.*\)-\([^0-9]\+\)/\1/")"'/d;s/^[^ ]* [^ ]* \([^ ]*\).*/\1/;/[0-9]/!d' | head -n -1 | xargs apt-get -y purge 2>/dev/null || true
    
    # Clear logs older than 7 days
    journalctl --vacuum-time=7d
    
    log_success "System cleaned up"
}

# Deploy with small configuration
deploy_small() {
    log_info "Deploying with optimized configuration..."
    
    cd /opt/tg-news-summarizer || exit 1
    
    # Stop any running services
    docker-compose -f docker-compose.yml -f docker-compose.small.yml down --remove-orphans || true
    
    # Clean up old images and containers
    docker system prune -f
    
    # Build with minimal cache
    docker-compose -f docker-compose.yml -f docker-compose.small.yml build --no-cache --parallel
    
    # Start services one by one to manage memory usage
    log_info "Starting database..."
    docker-compose -f docker-compose.yml -f docker-compose.small.yml up -d db redis
    sleep 30
    
    log_info "Starting API server..."
    docker-compose -f docker-compose.yml -f docker-compose.small.yml up -d api
    sleep 20
    
    log_info "Running database migrations..."
    docker-compose -f docker-compose.yml -f docker-compose.small.yml exec -T api alembic upgrade head || {
        log_warning "Migration failed, retrying..."
        sleep 10
        docker-compose -f docker-compose.yml -f docker-compose.small.yml run --rm api alembic upgrade head
    }
    
    log_info "Starting background services..."
    docker-compose -f docker-compose.yml -f docker-compose.small.yml up -d worker scheduler
    
    log_success "Services deployed"
}

# Monitor resource usage
monitor_resources() {
    log_info "Monitoring resource usage..."
    
    sleep 30  # Wait for services to stabilize
    
    echo "Memory usage:"
    free -h
    echo
    echo "Docker container stats:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
    echo
    echo "Disk usage:"
    df -h /
}

# Main function for small server deployment
main_small() {
    log_info "Starting deployment for small server (512MB RAM)..."
    
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
    
    check_resources
    optimize_system
    install_docker_minimal
    cleanup_system
    
    # Clone repository if not exists
    if [ ! -d "/opt/tg-news-summarizer" ]; then
        git clone https://github.com/volontsevich/news-summarizer.git /opt/tg-news-summarizer
    fi
    
    deploy_small
    monitor_resources
    
    log_success "🎉 Small server deployment completed!"
    echo
    echo "Your application is running on a minimal configuration:"
    echo "  - API: http://$(curl -s ifconfig.me):8000"
    echo "  - Docs: http://$(curl -s ifconfig.me):8000/docs"
    echo
    echo "Important notes for small servers:"
    echo "  1. Monitor memory usage: free -h"
    echo "  2. Check container stats: docker stats"
    echo "  3. If services crash, restart them individually"
    echo "  4. Consider upgrading if you need better performance"
    echo
    echo "Management commands:"
    echo "  cd /opt/tg-news-summarizer"
    echo "  docker-compose -f docker-compose.yml -f docker-compose.small.yml [COMMAND]"
}

# Run main function
main_small "$@"

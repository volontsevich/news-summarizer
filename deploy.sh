#!/bin/bash

# Telegram News Summarizer - DigitalOcean Deployment Script
# This script automates the deployment process on a DigitalOcean droplet

set -e  # Exit on any error

echo "🚀 Starting Telegram News Summarizer deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/volontsevich/news-summarizer.git"
APP_DIR="/opt/tg-news-summarizer"
SERVICE_NAME="tg-news-summarizer"
DOMAIN=${DOMAIN:-"localhost"}  # Set via environment variable
EMAIL=${EMAIL:-"admin@example.com"}  # Set via environment variable

# Helper functions
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

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Update system packages
update_system() {
    log_info "Updating system packages..."
    apt-get update -y
    apt-get upgrade -y
}

# Install Docker and Docker Compose
install_docker() {
    log_info "Installing Docker and Docker Compose..."
    
    # Install Docker
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
        systemctl enable docker
        systemctl start docker
        log_success "Docker installed successfully"
    else
        log_info "Docker already installed"
    fi
    
    # Install Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        log_success "Docker Compose installed successfully"
    else
        log_info "Docker Compose already installed"
    fi
}

# Install additional tools
install_tools() {
    log_info "Installing additional tools..."
    apt-get install -y git curl jq make ufw nginx certbot python3-certbot-nginx
}

# Configure firewall
configure_firewall() {
    log_info "Configuring firewall..."
    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8000/tcp  # FastAPI
    ufw --force enable
    log_success "Firewall configured"
}

# Clone or update repository
setup_repository() {
    log_info "Setting up repository..."
    
    if [ -d "$APP_DIR" ]; then
        log_info "Repository exists, updating..."
        cd "$APP_DIR"
        git pull origin main
    else
        log_info "Cloning repository..."
        git clone "$REPO_URL" "$APP_DIR"
        cd "$APP_DIR"
    fi
    
    log_success "Repository ready"
}

# Setup environment configuration
setup_environment() {
    log_info "Setting up environment configuration..."
    
    cd "$APP_DIR"
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_info "Created .env from .env.example"
        else
            log_info "Creating basic .env file..."
            cat > .env << EOF
# Database Configuration
DATABASE_URL=postgresql://postgres:password@db:5432/tg_news_summarizer
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=tg_news_summarizer

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# API Configuration
SECRET_KEY=$(openssl rand -base64 32)
DEBUG=false
ALLOWED_HOSTS=localhost,127.0.0.1,$DOMAIN

# Email Configuration (Update with your SMTP settings)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_FROM_NAME=TG News Summarizer

# Telegram Configuration (Add your credentials)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=your_phone_number

# OpenAI Configuration (Add your API key)
OPENAI_API_KEY=your_openai_api_key

# Celery Configuration
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Scheduling (cron expressions)
ALERT_CRON_SCHEDULE=*/5 * * * *
DIGEST_CRON_SCHEDULE=0 * * * *
TIMEZONE=UTC

# Application Settings
LOG_LEVEL=INFO
MAX_POSTS_PER_DIGEST=50
DIGEST_DEFAULT_RECIPIENTS=$EMAIL
EOF
        fi
        
        log_warning "Please edit /opt/tg-news-summarizer/.env and add your API keys and configuration"
        log_warning "Required: TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE, OPENAI_API_KEY"
        log_warning "Optional: SMTP settings for email notifications"
    else
        log_info "Environment file already exists"
    fi
}

# Build and start services
deploy_services() {
    log_info "Building and starting services..."
    
    cd "$APP_DIR"
    
    # Build and start services
    docker-compose down --remove-orphans || true
    docker-compose build --no-cache
    docker-compose up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to start..."
    sleep 30
    
    # Run database migrations
    log_info "Running database migrations..."
    docker-compose exec -T api alembic upgrade head || {
        log_warning "Migration failed, trying alternative method..."
        docker-compose run --rm api alembic upgrade head
    }
    
    log_success "Services deployed successfully"
}

# Configure Nginx reverse proxy
configure_nginx() {
    log_info "Configuring Nginx reverse proxy..."
    
    cat > /etc/nginx/sites-available/$SERVICE_NAME << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        proxy_pass http://localhost:8000/static/;
    }

    location /docs {
        proxy_pass http://localhost:8000/docs;
    }

    location /api/ {
        proxy_pass http://localhost:8000/api/;
    }
}
EOF

    # Enable the site
    ln -sf /etc/nginx/sites-available/$SERVICE_NAME /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Test Nginx configuration
    nginx -t
    systemctl reload nginx
    
    log_success "Nginx configured successfully"
}

# Setup SSL with Let's Encrypt
setup_ssl() {
    if [ "$DOMAIN" != "localhost" ] && [ "$DOMAIN" != "127.0.0.1" ]; then
        log_info "Setting up SSL certificate..."
        certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "$EMAIL" --redirect
        log_success "SSL certificate configured"
    else
        log_info "Skipping SSL setup for localhost"
    fi
}

# Create systemd service for automatic startup
create_systemd_service() {
    log_info "Creating systemd service..."
    
    cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=Telegram News Summarizer
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable $SERVICE_NAME
    
    log_success "Systemd service created"
}

# Health check
health_check() {
    log_info "Performing health check..."
    
    # Wait a bit for services to fully start
    sleep 10
    
    # Check if services are running
    if docker-compose ps | grep -q "Up"; then
        log_success "Docker services are running"
    else
        log_error "Some Docker services are not running"
        docker-compose ps
        return 1
    fi
    
    # Check API health
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        log_success "API health check passed"
    else
        log_error "API health check failed"
        return 1
    fi
    
    # Check if landing page is accessible
    if curl -f http://localhost:8000/ >/dev/null 2>&1; then
        log_success "Landing page accessible"
    else
        log_warning "Landing page may not be accessible"
    fi
}

# Display completion message
show_completion() {
    log_success "🎉 Deployment completed successfully!"
    echo
    echo "Access your application:"
    echo "  Landing Page: http://$DOMAIN/"
    echo "  API Documentation: http://$DOMAIN/docs"
    echo "  API Health: http://$DOMAIN/health"
    echo "  API Status: http://$DOMAIN/status"
    echo
    echo "Next steps:"
    echo "  1. Edit $APP_DIR/.env with your API keys"
    echo "  2. Restart services: cd $APP_DIR && docker-compose restart"
    echo "  3. Check logs: cd $APP_DIR && docker-compose logs -f"
    echo
    echo "Management commands:"
    echo "  Start:   systemctl start $SERVICE_NAME"
    echo "  Stop:    systemctl stop $SERVICE_NAME"
    echo "  Restart: systemctl restart $SERVICE_NAME"
    echo "  Status:  systemctl status $SERVICE_NAME"
}

# Main deployment function
main() {
    log_info "Starting deployment with domain: $DOMAIN"
    
    check_root
    update_system
    install_docker
    install_tools
    configure_firewall
    setup_repository
    setup_environment
    deploy_services
    configure_nginx
    setup_ssl
    create_systemd_service
    health_check
    show_completion
}

# Run main function
main "$@"

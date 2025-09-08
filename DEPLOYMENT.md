# Deployment Guide

This guide covers deploying the Telegram News Summarizer to a DigitalOcean droplet with automated setup.

## Quick Start

### Option 1: Automated Deployment (Recommended)

Run the automated deployment script on your DigitalOcean droplet:

```bash
# Download and run deployment script
curl -fsSL https://raw.githubusercontent.com/volontsevich/news-summarizer/main/deploy.sh | sudo bash
```

Or clone the repository first:

```bash
git clone https://github.com/volontsevich/news-summarizer.git
cd news-summarizer
sudo ./deploy.sh
```

### Option 2: Manual Deployment

```bash
# 1. Update system and install Docker
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y docker.io docker-compose-plugin git curl jq

# 2. Clone repository
git clone https://github.com/volontsevich/news-summarizer.git
cd news-summarizer

# 3. Setup environment
cp .env.example .env
nano .env  # Edit with your configuration

# 4. Deploy with production settings
make deploy-local
```

## Environment Configuration

Edit the `.env` file with your settings:

### Required Settings
```env
# Telegram API (get from https://my.telegram.org)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=your_phone_number

# OpenAI API (get from https://platform.openai.com)
OPENAI_API_KEY=your_openai_api_key
```

### Optional Settings
```env
# Email notifications (for alerts and digests)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com

# Database (default values work for Docker)
DATABASE_URL=postgresql://postgres:password@db:5432/tg_news_summarizer
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=tg_news_summarizer

# Scheduling (cron expressions)
ALERT_CRON_SCHEDULE=*/5 * * * *  # Every 5 minutes
DIGEST_CRON_SCHEDULE=0 * * * *   # Every hour
```

## DigitalOcean Droplet Requirements

### Minimum Specifications
- **RAM**: 2GB (4GB recommended)
- **CPU**: 1 vCPU (2 vCPU recommended)
- **Storage**: 25GB SSD
- **OS**: Ubuntu 20.04 or 22.04 LTS

### Recommended Specifications
- **RAM**: 4GB
- **CPU**: 2 vCPU
- **Storage**: 50GB SSD
- **OS**: Ubuntu 22.04 LTS

## Deployment Process

The automated deployment script will:

1. ✅ Update system packages
2. ✅ Install Docker and Docker Compose
3. ✅ Configure firewall (UFW)
4. ✅ Clone/update repository
5. ✅ Setup environment configuration
6. ✅ Build and start all services
7. ✅ Run database migrations
8. ✅ Configure Nginx reverse proxy
9. ✅ Setup SSL certificate (if domain provided)
10. ✅ Create systemd service for auto-startup
11. ✅ Perform health checks

## Post-Deployment

### Access Your Application

After deployment, access your application at:

- **Landing Page**: `http://your-domain/` or `http://your-ip/`
- **API Documentation**: `http://your-domain/docs`
- **API Health**: `http://your-domain/health`
- **System Status**: `http://your-domain/status`

### Management Commands

```bash
# Check service status
systemctl status tg-news-summarizer

# Start/stop services
systemctl start tg-news-summarizer
systemctl stop tg-news-summarizer
systemctl restart tg-news-summarizer

# View logs
cd /opt/tg-news-summarizer
docker-compose logs -f

# Update application
cd /opt/tg-news-summarizer
git pull origin main
docker-compose build --no-cache
docker-compose up -d
```

### Using Make Commands

```bash
cd /opt/tg-news-summarizer

# Quick deployment
make deploy-local

# Check status
make status

# View logs
make logs

# Backup database
make backup

# Clean up
make clean
```

## SSL Certificate

If you provided a domain name during deployment, SSL will be automatically configured using Let's Encrypt.

To manually setup SSL later:

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
```

## Monitoring and Maintenance

### Health Checks

The application includes built-in health checks:

```bash
# API health
curl http://localhost:8000/health

# Service status
curl http://localhost:8000/status

# Docker services
docker-compose ps
```

### Log Monitoring

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f scheduler
```

### Database Backup

```bash
# Create backup
make backup

# Manual backup
docker-compose exec db pg_dump -U postgres tg_news_summarizer > backup.sql

# Restore backup
make restore
```

## Troubleshooting

### Common Issues

1. **Services not starting**: Check logs with `docker-compose logs`
2. **Database connection errors**: Ensure PostgreSQL is running and accessible
3. **API not responding**: Check if port 8000 is accessible and not blocked
4. **Email not working**: Verify SMTP settings in `.env` file

### Debugging Commands

```bash
# Check Docker status
docker-compose ps
docker-compose logs

# Check system resources
df -h  # Disk space
free -h  # Memory usage
top  # CPU usage

# Check network connectivity
curl -I http://localhost:8000/health
netstat -tlnp | grep 8000
```

### Restart Everything

```bash
cd /opt/tg-news-summarizer
docker-compose down
docker-compose up -d
```

## Security Considerations

### Firewall Configuration

The deployment script configures UFW with these rules:
- SSH (22): Allow
- HTTP (80): Allow
- HTTPS (443): Allow
- API (8000): Allow

### Environment Security

- Never commit `.env` files to version control
- Use strong passwords for database
- Regularly update system packages
- Consider using Docker secrets for production

### API Security

- The API includes CORS middleware
- Input validation on all endpoints
- Rate limiting can be added if needed

## Scaling

### Horizontal Scaling

To scale workers:

```bash
# Scale up workers
docker-compose up -d --scale worker=3

# Scale down workers
docker-compose up -d --scale worker=1
```

### Vertical Scaling

Upgrade your DigitalOcean droplet to higher specifications:
1. Power off droplet
2. Resize in DigitalOcean control panel
3. Power on and verify services

## Support

If you encounter issues:

1. Check the logs: `docker-compose logs -f`
2. Verify configuration: `cat .env`
3. Check health endpoints: `curl http://localhost:8000/health`
4. Review this guide for troubleshooting steps

For additional support, check the main README.md file for detailed API documentation and feature descriptions.

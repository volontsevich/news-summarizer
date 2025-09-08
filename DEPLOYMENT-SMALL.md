# Deployment Guide for Small DigitalOcean Droplet (512MB RAM)

This guide is specifically optimized for deploying the Telegram News Summarizer on a DigitalOcean droplet with 1 vCPU, 512MB RAM, and 10GB storage.

## 🚨 Important Considerations

**Memory Constraints**: 512MB is very limited. The application will use:
- PostgreSQL: ~150MB
- Redis: ~50MB  
- FastAPI: ~150MB
- Celery Worker: ~100MB
- Celery Scheduler: ~50MB
- **Total: ~500MB** (very tight!)

## 📋 Prerequisites

1. **DigitalOcean Droplet**: ubuntu-s-1vcpu-512mb-10gb-nyc1-01
2. **Required API Keys**:
   - Telegram API ID & Hash (from https://my.telegram.org/auth)
   - OpenAI API Key (from https://platform.openai.com/api-keys)
   - Optional: SMTP credentials for email notifications

## 🚀 Quick Deployment (Recommended)

### Step 1: Connect to Your Droplet

```bash
ssh root@your-droplet-ip
```

### Step 2: Download and Run the Optimized Deployment Script

```bash
# Download the repository
git clone https://github.com/volontsevich/news-summarizer.git /opt/tg-news-summarizer
cd /opt/tg-news-summarizer

# Run the optimized deployment script
sudo bash deploy-small.sh
```

### Step 3: Configure Environment Variables

```bash
# Edit the environment file
nano /opt/tg-news-summarizer/.env

# Add your API credentials:
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
OPENAI_API_KEY=your_openai_api_key

# Optional email configuration:
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
```

### Step 4: Restart Services

```bash
cd /opt/tg-news-summarizer
docker-compose -f docker-compose.yml -f docker-compose.small.yml restart
```

## 🔧 Manual Deployment (Advanced)

If you prefer manual control or the automated script fails:

### 1. System Preparation

```bash
# Update system
apt update && apt upgrade -y

# Create swap file (essential for 512MB RAM)
fallocate -l 1G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Optimize memory settings
echo 'vm.swappiness=10' >> /etc/sysctl.conf
echo 'vm.overcommit_memory=1' >> /etc/sysctl.conf
sysctl -p
```

### 2. Install Docker (Minimal)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Start Docker
systemctl enable docker
systemctl start docker
```

### 3. Deploy Application

```bash
# Clone repository
git clone https://github.com/volontsevich/news-summarizer.git /opt/tg-news-summarizer
cd /opt/tg-news-summarizer

# Create environment file
cp .env.example .env
# Edit .env with your credentials (see Step 3 above)

# Deploy with small configuration
docker-compose -f docker-compose.yml -f docker-compose.small.yml up -d

# Run migrations
docker-compose -f docker-compose.yml -f docker-compose.small.yml exec api alembic upgrade head
```

## 📊 Monitoring & Management

### Check Resource Usage

```bash
# Memory usage
free -h

# Container stats
docker stats

# Disk usage
df -h
```

### Service Management

```bash
cd /opt/tg-news-summarizer

# View logs
docker-compose -f docker-compose.yml -f docker-compose.small.yml logs -f

# Restart specific service
docker-compose -f docker-compose.yml -f docker-compose.small.yml restart api

# Stop all services
docker-compose -f docker-compose.yml -f docker-compose.small.yml down

# Start all services
docker-compose -f docker-compose.yml -f docker-compose.small.yml up -d
```

## 🔍 Access Your Application

Once deployed, access your application at:

- **Landing Page**: `http://your-droplet-ip:8000/`
- **API Documentation**: `http://your-droplet-ip:8000/docs`
- **Health Check**: `http://your-droplet-ip:8000/health`
- **Status**: `http://your-droplet-ip:8000/status`

## ⚠️ Troubleshooting

### Common Issues on Small Servers

1. **Out of Memory Errors**
   ```bash
   # Check memory usage
   free -h
   
   # Restart services individually
   docker-compose -f docker-compose.yml -f docker-compose.small.yml restart db
   sleep 30
   docker-compose -f docker-compose.yml -f docker-compose.small.yml restart api
   ```

2. **Services Won't Start**
   ```bash
   # Check container logs
   docker-compose -f docker-compose.yml -f docker-compose.small.yml logs api
   
   # Clean up and restart
   docker system prune -f
   docker-compose -f docker-compose.yml -f docker-compose.small.yml down
   docker-compose -f docker-compose.yml -f docker-compose.small.yml up -d
   ```

3. **Disk Space Issues**
   ```bash
   # Clean Docker
   docker system prune -af --volumes
   
   # Clean system
   apt autoremove -y
   apt autoclean
   journalctl --vacuum-time=3d
   ```

### Performance Optimization Tips

1. **Reduce Log Levels**: Set `LOG_LEVEL=WARNING` in `.env`
2. **Limit Workers**: The small config uses only 1 Celery worker
3. **Monitor Regularly**: Check `docker stats` and `free -h` frequently
4. **Consider Upgrade**: If you need better performance, upgrade to a larger droplet

## 💰 Cost Considerations

- **Monthly Cost**: ~$4-6/month for the basic droplet
- **Upgrade Path**: Consider upgrading to 1GB RAM droplet (~$12/month) for better stability
- **Alternative**: Use DigitalOcean's App Platform for easier scaling

## 🔄 Upgrading

To upgrade to a larger droplet:

1. Create a snapshot of your current droplet
2. Create a new larger droplet from the snapshot
3. Update DNS/IP references
4. Use the regular `deploy.sh` script instead of `deploy-small.sh`

## 📞 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review container logs: `docker-compose logs`
3. Monitor system resources: `htop` or `free -h`
4. Consider upgrading to a larger server if performance is insufficient

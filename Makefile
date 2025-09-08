# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# ...existing code...

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

revision:
	docker compose exec api poetry run alembic revision --autogenerate -m "auto"

migrate:
	docker compose exec api poetry run alembic upgrade head

format:
	docker compose exec api poetry run black app tests
	docker compose exec api poetry run isort app tests

test:
	docker compose exec api poetry run pytest

# Deployment commands
deploy-local:
	@echo "🚀 Deploying locally..."
	docker compose down --remove-orphans || true
	docker compose build --no-cache
	docker compose up -d
	@echo "⏳ Waiting for services to start..."
	sleep 15
	docker compose exec api poetry run alembic upgrade head
	@echo "✅ Local deployment complete!"
	@echo "Access: http://localhost:8000"

deploy-production:
	@echo "🚀 Starting production deployment..."
	@echo "⚠️  This will deploy to your DigitalOcean droplet"
	@read -p "Enter your droplet domain/IP: " domain; \
	read -p "Enter your email for SSL: " email; \
	export DOMAIN=$$domain EMAIL=$$email; \
	sudo ./deploy.sh

quick-deploy:
	@echo "🚀 Quick local deployment (no rebuild)..."
	docker compose up -d
	@echo "✅ Services started!"

status:
	@echo "📊 Service Status:"
	docker compose ps
	@echo ""
	@echo "🏥 Health Check:"
	curl -s http://localhost:8000/health | jq . || echo "API not responding"
	@echo ""
	@echo "📈 System Status:"
	curl -s http://localhost:8000/status | jq . || echo "Status endpoint not responding"

clean:
	@echo "🧹 Cleaning up..."
	docker compose down --remove-orphans
	docker system prune -f
	docker volume prune -f

backup:
	@echo "💾 Creating backup..."
	mkdir -p backups
	docker compose exec db pg_dump -U postgres tg_news_summarizer > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup created in backups/ directory"

restore:
	@echo "📥 Restoring from backup..."
	@read -p "Enter backup file path: " backup_file; \
	docker compose exec -T db psql -U postgres -d tg_news_summarizer < $$backup_file

dev-setup:
	@echo "🛠️  Setting up development environment..."
	cp .env.example .env
	@echo "📝 Please edit .env file with your configuration"
	@echo "⚠️  Required: TELEGRAM_API_ID, TELEGRAM_API_HASH, OPENAI_API_KEY"

help:
	@echo "📚 Available commands:"
	@echo "  up              - Start services"
	@echo "  down            - Stop services"
	@echo "  logs            - View logs"
	@echo "  build           - Build containers"
	@echo "  migrate         - Run database migrations"
	@echo "  test            - Run tests"
	@echo "  deploy-local    - Full local deployment with rebuild"
	@echo "  deploy-production - Deploy to DigitalOcean droplet"
	@echo "  quick-deploy    - Quick local start (no rebuild)"
	@echo "  status          - Check service status and health"
	@echo "  clean           - Clean up containers and volumes"
	@echo "  backup          - Create database backup"
	@echo "  restore         - Restore from database backup"
	@echo "  dev-setup       - Setup development environment"
	@echo "  help            - Show this help"

.PHONY: up down logs build revision migrate format test deploy-local deploy-production quick-deploy status clean backup restore dev-setup help

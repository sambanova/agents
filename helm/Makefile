# Variables
ENV ?= dev

# Try to determine version from Git
# Uses `git describe` which gives:
#   - latest tag (e.g., v1.2.3)
#   - latest tag + commits since + short hash (e.g., v1.2.3-4-gabcdef)
#   - short hash prefixed with 'g' if no tags (e.g., gabcdef0)
#   - appends '-dirty' if there are uncommitted changes
# Falls back to a date-based version if Git info is unavailable.
GIT_VERSION_RAW = $(shell git describe --tags --always --dirty --abbrev=7 2>/dev/null)
FALLBACK_VERSION = unknown-$(shell date '+%Y%m%d%H%M%S')

# APP_VERSION will be the Git version if available, otherwise the fallback.
APP_VERSION = $(if $(GIT_VERSION_RAW),$(GIT_VERSION_RAW),$(FALLBACK_VERSION))

# TAG is now ENV-APP_VERSION. User can override with `make ... TAG=custom-tag`
TAG ?= $(ENV)-$(APP_VERSION)

# Environment-specific file paths
VALUES_FILE = ./aiskagents/values.$(ENV).yaml

# Extract backend repository from values file
BACKEND_REPO = $(shell grep -A3 "backend:" $(VALUES_FILE) | grep "repository:" | sed 's/.*repository: *//')
FRONTEND_REPO = $(shell grep -A3 "frontend:" $(VALUES_FILE) | grep "repository:" | sed 's/.*repository: *//')
ORCHESTRATOR_REPO = $(shell grep -A3 "orchestrator:" $(VALUES_FILE) | grep "repository:" | sed 's/.*repository: *//')

# Extract frontend environment variables from values file
VITE_API_URL = $(shell grep -A20 "frontend:" $(VALUES_FILE) | grep "VITE_API_URL:" | sed 's/.*VITE_API_URL: *//;s/"//g')
VITE_CLERK_PUBLISHABLE_KEY = $(shell grep -A20 "frontend:" $(VALUES_FILE) | grep "VITE_CLERK_PUBLISHABLE_KEY:" | sed 's/.*VITE_CLERK_PUBLISHABLE_KEY: *//;s/"//g')

# Common variables
BACKEND_DOCKER_IMAGE = $(BACKEND_REPO)
FRONTEND_DOCKER_IMAGE = $(FRONTEND_REPO)
CHART_PATH = ./aiskagents

# Extract base URL for docker login
BACKEND_BASE_URL = $(shell echo $(BACKEND_REPO) | cut -d/ -f1)
FRONTEND_BASE_URL = $(shell echo $(FRONTEND_REPO) | cut -d/ -f1)

# MLflow-related variables
MLFLOW_HELM_REPO_NAME = community-charts
MLFLOW_HELM_REPO_URL = https://community-charts.github.io/helm-charts
MLFLOW_CHART_NAME = mlflow
MLFLOW_RELEASE_NAME = mlflow-$(ENV)
MLFLOW_NAMESPACE = default

# OpenEBS variables
OPENEBS_NAMESPACE = openebs

# Redis variables
REDIS_HELM_REPO_NAME = bitnami
REDIS_HELM_REPO_URL = https://charts.bitnami.com/bitnami
REDIS_CHART_NAME = redis
REDIS_RELEASE_NAME = redis-$(ENV)
REDIS_NAMESPACE = redis-$(ENV)


# Phony targets
.PHONY: build-backend build-frontend push-backend push-frontend build push deploy install upgrade uninstall clean help install-postgres install-mlflow uninstall-mlflow install-redis uninstall-redis

# Build the backend Docker image
build-backend:
	@echo "Building backend Docker image $(BACKEND_DOCKER_IMAGE):$(TAG) ($(ENV) environment)..."
	cd ../backend && docker build --platform linux/amd64 -t $(BACKEND_DOCKER_IMAGE):$(TAG) .

# Build the orchestrator Docker image
build-orchestrator:
	@echo "Building orchestrator Docker image $(ORCHESTRATOR_REPO):$(TAG) ($(ENV) environment)..."
	cd ../backend && docker build --platform linux/amd64 -f Dockerfile-orchestrator -t $(ORCHESTRATOR_REPO):$(TAG) .

# Push the orchestrator Docker image
push-orchestrator: build-orchestrator
	@echo "Logging in to Docker registry..."
	docker login $(shell echo $(ORCHESTRATOR_REPO) | cut -d/ -f1)
	@echo "Pushing orchestrator Docker image $(ORCHESTRATOR_REPO):$(TAG)..."
	docker push $(ORCHESTRATOR_REPO):$(TAG)

# Build the frontend Docker image
build-frontend:
	@echo "Building frontend Docker image $(FRONTEND_DOCKER_IMAGE):$(TAG) ($(ENV) environment)..."
	@echo "Using VITE_API_URL: $(VITE_API_URL)"
	@echo "Using VITE_CLERK_PUBLISHABLE_KEY: $(VITE_CLERK_PUBLISHABLE_KEY)"
	cd ../frontend/sales-agent-crew && docker build \
		--platform=linux/amd64 \
		--build-arg VITE_API_URL=$(VITE_API_URL) \
		--build-arg VITE_CLERK_PUBLISHABLE_KEY=$(VITE_CLERK_PUBLISHABLE_KEY) \
		-t $(FRONTEND_DOCKER_IMAGE):$(TAG) .

# Push the backend Docker image
push-backend: build-backend
	@echo "Logging in to Docker registry..."
	docker login $(BACKEND_BASE_URL)
	@echo "Pushing backend Docker image $(BACKEND_DOCKER_IMAGE):$(TAG)..."
	docker push $(BACKEND_DOCKER_IMAGE):$(TAG)

# Push the frontend Docker image
push-frontend: build-frontend
	@echo "Logging in to Docker registry..."
	docker login $(FRONTEND_BASE_URL)
	@echo "Pushing frontend Docker image $(FRONTEND_DOCKER_IMAGE):$(TAG)..."
	docker push $(FRONTEND_DOCKER_IMAGE):$(TAG)

# Build all Docker images
build: build-backend build-orchestrator build-frontend

# Push all Docker images
push: push-backend push-orchestrator push-frontend

# Install the Helm chart
install:
	@echo "Installing Helm chart using $(VALUES_FILE) ($(ENV) environment)..."
	helm install aiskagents-$(ENV) $(CHART_PATH) \
		--values $(VALUES_FILE) \
		--set backend.image.tag=$(TAG) \
		--set frontend.image.tag=$(TAG) \
		--set orchestrator.image.tag=$(TAG)

# Upgrade the Helm chart
upgrade:
	@echo "Upgrading Helm chart using $(VALUES_FILE) ($(ENV) environment)..."
	helm upgrade aiskagents-$(ENV) $(CHART_PATH) \
		--values $(VALUES_FILE) \
		--set backend.image.tag=$(TAG) \
		--set frontend.image.tag=$(TAG) \
		--set orchestrator.image.tag=$(TAG)

# Uninstall the Helm chart
uninstall:
	@echo "Uninstalling Helm chart ($(ENV) environment)..."
	helm uninstall aiskagents-$(ENV) --namespace aiskagents-$(ENV)

# Deploy to Kubernetes using Helm
deploy: push install

# Install mlflow
install-mlflow: 
	@if [ -z "$(PG_PASSWORD)" ]; then \
		echo "PG_PASSWORD is required. Please run: make install-mlflow PG_PASSWORD=your_secure_password ADMIN_PASSWORD=your_admin_password"; \
		exit 1; \
	fi
	@if [ -z "$(ADMIN_PASSWORD)" ]; then \
		echo "ADMIN_PASSWORD is required. Please run: make install-mlflow PG_PASSWORD=your_secure_password ADMIN_PASSWORD=your_admin_password"; \
		exit 1; \
	fi
	@echo "Creating mlflow artifacts PVC..."
	@kubectl apply -f ./mlflow/templates/artifacts-pvc.yaml -n $(MLFLOW_NAMESPACE)
	@helm repo add $(MLFLOW_HELM_REPO_NAME) $(MLFLOW_HELM_REPO_URL) || echo "Repo already exists."
	@helm repo update
	@echo "Installing mlflow..."
	@helm upgrade $(MLFLOW_RELEASE_NAME) $(MLFLOW_HELM_REPO_NAME)/$(MLFLOW_CHART_NAME) \
		--install \
		--namespace $(MLFLOW_NAMESPACE) \
		--set backendStore.postgres.password=$(PG_PASSWORD) \
		--set auth.postgres.password=$(PG_PASSWORD) \
		--set auth.adminPassword=$(ADMIN_PASSWORD) \
		-f ./mlflow/values/$(ENV).yaml


install-postgres: 
	@if [ -z "$(PG_PASSWORD)" ]; then \
		echo "PG_PASSWORD is required. Please run: make install-postgres PG_PASSWORD=your_secure_password"; \
		exit 1; \
	fi
	helm repo add bitnami https://charts.bitnami.com/bitnami || true && \
	helm repo update && \
	kubectl create namespace postgres --dry-run=client -o yaml | kubectl apply -f - && \
	helm upgrade --install postgres bitnami/postgresql \
		--set auth.postgresPassword=$(PG_PASSWORD) \
		--namespace postgres \
		-f ./postgres/values/$(ENV).yaml

install-openebs: ## Install OpenEBS storage engine
	helm repo add openebs https://openebs.github.io/openebs || true
	helm repo update
	helm upgrade --install openebs openebs/openebs \
		--create-namespace \
		--namespace $(OPENEBS_NAMESPACE) \
		-f ./openebs/values/$(ENV).yaml

install-redis:
	helm repo add $(REDIS_HELM_REPO_NAME) $(REDIS_HELM_REPO_URL) || true
	helm repo update
	kubectl create namespace $(REDIS_NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	helm upgrade --install $(REDIS_RELEASE_NAME) $(REDIS_HELM_REPO_NAME)/$(REDIS_CHART_NAME) \
		--namespace $(REDIS_NAMESPACE) \
		--set global.security.allowInsecureImages=true \
		-f ./redis/values/$(ENV).yaml

uninstall-redis:
	helm uninstall $(REDIS_RELEASE_NAME) --namespace $(REDIS_NAMESPACE)
	kubectl delete namespace $(REDIS_NAMESPACE) || true

# Help message
help:
	@echo "Usage: make [target] [ENV=dev|prod] [TAG=custom-tag]"
	@echo ""
	@echo "Current environment: $(ENV)"
	@echo "Current tag: $(TAG)"
	@echo "Using values file: $(VALUES_FILE)"
	@echo "Backend repository: $(BACKEND_REPO)"
	@echo "Frontend repository: $(FRONTEND_REPO)"
	@echo "Orchestrator repository: $(ORCHESTRATOR_REPO)"
	@echo "VITE_API_URL: $(VITE_API_URL)"
	@echo "VITE_CLERK_PUBLISHABLE_KEY: $(VITE_CLERK_PUBLISHABLE_KEY)"
	@echo ""
	@echo "Targets:"
	@echo "  build-backend   Build the backend Docker image"
	@echo "  build-orchestrator Build the orchestrator Docker image"
	@echo "  build-frontend  Build the frontend Docker image"
	@echo "  build           Build all Docker images"
	@echo "  push-backend    Push the backend Docker image"
	@echo "  push-orchestrator  Push the orchestrator Docker image"
	@echo "  push-frontend   Push the frontend Docker image"
	@echo "  push            Push all Docker images"
	@echo "  install         Install the Helm chart"
	@echo "  upgrade         Upgrade the Helm chart"
	@echo "  uninstall       Uninstall the Helm chart"
	@echo "  deploy          Build, push, and deploy using Helm"
	@echo "  install-mlflow  Install the mlflow chart"
	@echo "  uninstall-mlflow Uninstall the mlflow chart"
	@echo "  upgrade-mlflow  Upgrade the mlflow chart"
	@echo "  install-redis   Install the redis chart"
	@echo "  uninstall-redis Uninstall the redis chart"
	@echo "  clean           Clean up Docker images"
	@echo "  help            Display this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make deploy                           # Deploy to dev environment with auto-generated tag"
	@echo "  make deploy ENV=prod                  # Deploy to production environment with auto-generated tag"
	@echo "  make build ENV=prod TAG=v1.0.0        # Build images for production with custom tag"
	@echo "  make deploy ENV=dev TAG=feature-123   # Deploy to dev with custom tag"
	@echo ""

# Default target
default: help 
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
BACKEND_REPO = $(shell grep -A4 "backend:" $(VALUES_FILE) | grep "repository:" | sed 's/.*repository: *//')
FRONTEND_REPO = $(shell grep -A4 "frontend:" $(VALUES_FILE) | grep "repository:" | sed 's/.*repository: *//')

# Extract frontend environment variables from values file
VITE_API_URL = $(shell grep -A25 "frontend:" $(VALUES_FILE) | grep "VITE_API_URL:" | sed 's/.*VITE_API_URL: *//;s/"//g')
VITE_AUTH0_DOMAIN = $(shell grep -A25 "frontend:" $(VALUES_FILE) | grep "VITE_AUTH0_DOMAIN:" | sed 's/.*VITE_AUTH0_DOMAIN: *//;s/"//g')
VITE_AUTH0_CLIENT_ID = $(shell grep -A25 "frontend:" $(VALUES_FILE) | grep "VITE_AUTH0_CLIENT_ID:" | sed 's/.*VITE_AUTH0_CLIENT_ID: *//;s/"//g')
VITE_AUTH0_SCOPES = $(shell grep -A25 "frontend:" $(VALUES_FILE) | grep "VITE_AUTH0_SCOPES:" | sed 's/.*VITE_AUTH0_SCOPES: *//;s/"//g')
VITE_SHOW_ADMIN_PANEL = $(shell grep -A25 "frontend:" $(VALUES_FILE) | grep "VITE_SHOW_ADMIN_PANEL:" | sed 's/.*VITE_SHOW_ADMIN_PANEL: *//;s/"//g')

# Common variables
BACKEND_DOCKER_IMAGE = $(BACKEND_REPO)
FRONTEND_DOCKER_IMAGE = $(FRONTEND_REPO)

# Extract base URL for docker login
BACKEND_BASE_URL = $(shell echo $(BACKEND_REPO) | cut -d/ -f1)
FRONTEND_BASE_URL = $(shell echo $(FRONTEND_REPO) | cut -d/ -f1)

# MLflow-related variables
MLFLOW_HELM_REPO_NAME = community-charts
MLFLOW_HELM_REPO_URL = https://community-charts.github.io/helm-charts
MLFLOW_CHART_NAME = mlflow
MLFLOW_RELEASE_NAME = mlflow-$(ENV)
MLFLOW_NAMESPACE = default



# Phony targets
.PHONY: build-backend build-frontend push-backend push-frontend build push deploy install upgrade uninstall clean help 

# Build the backend Docker image
build-backend:
	@echo "Building backend Docker image $(BACKEND_DOCKER_IMAGE):$(TAG) ($(ENV) environment)..."
	cd ../backend && docker build --platform linux/amd64 -t $(BACKEND_DOCKER_IMAGE):$(TAG) .

# Build the frontend Docker image
build-frontend:
	@echo "Building frontend Docker image $(FRONTEND_DOCKER_IMAGE):$(TAG) ($(ENV) environment)..."
	@echo "Using VITE_API_URL: '$(VITE_API_URL)'"
	@echo "Using VITE_AUTH0_DOMAIN: '$(VITE_AUTH0_DOMAIN)'"
	@echo "Using VITE_AUTH0_CLIENT_ID: '$(VITE_AUTH0_CLIENT_ID)'"
	@echo "Using VITE_AUTH0_SCOPES: '$(VITE_AUTH0_SCOPES)'"
	@echo "Using VITE_SHOW_ADMIN_PANEL: '$(VITE_SHOW_ADMIN_PANEL)'"
	cd ../frontend/sales-agent-crew && docker build \
		--platform=linux/amd64 \
		--build-arg VITE_API_URL="$(VITE_API_URL)" \
		--build-arg VITE_AUTH0_DOMAIN="$(VITE_AUTH0_DOMAIN)" \
		--build-arg VITE_AUTH0_CLIENT_ID="$(VITE_AUTH0_CLIENT_ID)" \
		--build-arg VITE_AUTH0_SCOPES="$(VITE_AUTH0_SCOPES)" \
		--build-arg VITE_SHOW_ADMIN_PANEL="$(VITE_SHOW_ADMIN_PANEL)" \
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
build: build-backend build-frontend

# Push all Docker images
push: push-backend push-frontend

# Upgrade the Helm chart
upgrade:
	@echo "Adding required Helm repositories..."
	helm repo add openebs https://openebs.github.io/openebs
	helm repo add postgresql https://charts.bitnami.com/bitnami
	helm repo add redis https://charts.bitnami.com/bitnami

	@echo "Building Helm chart dependencies..."
	helm dep update

	@echo "Upgrading Helm chart using $(VALUES_FILE) ($(ENV) environment)..."
	helm upgrade \
		--install \
		--namespace default \
		--create-namespace \
		--values $(VALUES_FILE) \
		--set backend.image.tag=$(TAG) \
		--set frontend.image.tag=$(TAG) \
		aiskagents \
		.

# Uninstall the Helm chart
uninstall:
	@echo "Uninstalling Helm chart ($(ENV) environment)..."
	helm uninstall aiskagents-$(ENV) --namespace aiskagents-$(ENV)

# Deploy to Kubernetes using Helm
deploy: push install

# Help message
help:
	@echo "Usage: make [target] [ENV=dev|prod] [TAG=custom-tag]"
	@echo ""
	@echo "Current environment: $(ENV)"
	@echo "Current tag: $(TAG)"
	@echo "Using values file: $(VALUES_FILE)"
	@echo "Backend repository: $(BACKEND_REPO)"
	@echo "Frontend repository: $(FRONTEND_REPO)"
	@echo "VITE_API_URL: $(VITE_API_URL)"
	@echo "VITE_AUTH0_DOMAIN: $(VITE_AUTH0_DOMAIN)"
	@echo "VITE_AUTH0_CLIENT_ID: $(VITE_AUTH0_CLIENT_ID)"
	@echo "VITE_AUTH0_SCOPES: $(VITE_AUTH0_SCOPES)"
	@echo "VITE_SHOW_ADMIN_PANEL: $(VITE_SHOW_ADMIN_PANEL)"
	@echo ""
	@echo "Targets:"
	@echo "  build-backend   Build the backend Docker image"
	@echo "  build-frontend  Build the frontend Docker image"
	@echo "  build           Build all Docker images"
	@echo "  push-backend    Push the backend Docker image"
	@echo "  push-frontend   Push the frontend Docker image"
	@echo "  push            Push all Docker images"
	@echo "  upgrade         Upgrade the Helm chart"
	@echo "  uninstall       Uninstall the Helm chart"
	@echo "  deploy          Build, push, and deploy using Helm"
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
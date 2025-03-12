# Variables
ENV ?= dev

# Environment-specific file paths
VALUES_FILE = ./aiskagents/values.$(ENV).yaml

# Extract repository information from values file
BACKEND_REPO = $(shell grep -A2 "backend:" $(VALUES_FILE) | grep "repository:" | awk '{print $$2}')
FRONTEND_REPO = $(shell grep -A2 "frontend:" $(VALUES_FILE) | grep "repository:" | awk '{print $$2}')

# Common variables
BACKEND_IMAGE_NAME ?= aiskagents-backend
FRONTEND_IMAGE_NAME ?= aiskagents-frontend
BACKEND_BASE_URL ?= $(shell echo $(BACKEND_REPO) | sed 's/\/$(BACKEND_IMAGE_NAME)$$//')
FRONTEND_BASE_URL ?= $(shell echo $(FRONTEND_REPO) | sed 's/\/$(FRONTEND_IMAGE_NAME)$$//')
TAG ?= $(ENV)-$(shell date '+%Y%m%d')
BACKEND_DOCKER_IMAGE = $(BACKEND_BASE_URL)/$(BACKEND_IMAGE_NAME)
FRONTEND_DOCKER_IMAGE = $(FRONTEND_BASE_URL)/$(FRONTEND_IMAGE_NAME)
CHART_PATH = ./aiskagents

# Phony targets
.PHONY: build-backend build-frontend push-backend push-frontend build push deploy install upgrade uninstall clean help

# Build the backend Docker image
build-backend:
	@echo "Building backend Docker image $(BACKEND_DOCKER_IMAGE):$(TAG) ($(ENV) environment)..."
	cd ../backend && docker build --platform linux/amd64 -t $(BACKEND_DOCKER_IMAGE):$(TAG) .

# Build the frontend Docker image
build-frontend:
	@echo "Building frontend Docker image $(FRONTEND_DOCKER_IMAGE):$(TAG) ($(ENV) environment)..."
	cd ../frontend/sales-agent-crew && docker build \
		--platform=linux/amd64 \
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

# Install the Helm chart
install:
	@echo "Installing Helm chart using $(VALUES_FILE) ($(ENV) environment)..."
	helm install aiskagents-$(ENV) $(CHART_PATH) \
		--namespace aiskagents-$(ENV) \
		--create-namespace \
		--values $(VALUES_FILE) \
		--set backend.image.tag=$(TAG) \
		--set frontend.image.tag=$(TAG)

# Upgrade the Helm chart
upgrade:
	@echo "Upgrading Helm chart using $(VALUES_FILE) ($(ENV) environment)..."
	helm upgrade aiskagents-$(ENV) $(CHART_PATH) \
		--namespace aiskagents-$(ENV) \
		--values $(VALUES_FILE) \
		--set backend.image.tag=$(TAG) \
		--set frontend.image.tag=$(TAG)

# Uninstall the Helm chart
uninstall:
	@echo "Uninstalling Helm chart ($(ENV) environment)..."
	helm uninstall aiskagents-$(ENV) --namespace aiskagents-$(ENV)

# Deploy to Kubernetes using Helm
deploy: push install

# Clean up
clean:
	@echo "Cleaning up ($(ENV) environment)..."
	docker rmi -f $(BACKEND_DOCKER_IMAGE):$(TAG) || true
	docker rmi -f $(FRONTEND_DOCKER_IMAGE):$(TAG) || true

# Help message
help:
	@echo "Usage: make [target] [ENV=dev|prod]"
	@echo ""
	@echo "Current environment: $(ENV)"
	@echo "Using values file: $(VALUES_FILE)"
	@echo "Backend repository: $(BACKEND_REPO)"
	@echo "Frontend repository: $(FRONTEND_REPO)"
	@echo ""
	@echo "Targets:"
	@echo "  build-backend   Build the backend Docker image"
	@echo "  build-frontend  Build the frontend Docker image"
	@echo "  build           Build all Docker images"
	@echo "  push-backend    Push the backend Docker image"
	@echo "  push-frontend   Push the frontend Docker image"
	@echo "  push            Push all Docker images"
	@echo "  install         Install the Helm chart"
	@echo "  upgrade         Upgrade the Helm chart"
	@echo "  uninstall       Uninstall the Helm chart"
	@echo "  deploy          Build, push, and deploy using Helm"
	@echo "  clean           Clean up Docker images"
	@echo "  help            Display this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make deploy               # Deploy to dev environment (default)"
	@echo "  make deploy ENV=prod      # Deploy to production environment"
	@echo "  make build ENV=prod       # Build images for production"
	@echo ""

# Default target
default: help 
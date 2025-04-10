# Variables
ENV ?= dev
TAG ?= $(ENV)-$(shell date '+%Y%m%d')

# Environment-specific file paths
VALUES_FILE = ./aiskagents/values.$(ENV).yaml

# Extract backend repository from values file
BACKEND_REPO = $(shell grep -A3 "backend:" $(VALUES_FILE) | grep "repository:" | sed 's/.*repository: *//')
FRONTEND_REPO = $(shell grep -A3 "frontend:" $(VALUES_FILE) | grep "repository:" | sed 's/.*repository: *//')

# Extract frontend environment variables from values file
VITE_API_URL = $(shell grep -A20 "frontend:" $(VALUES_FILE) | grep "VITE_API_URL:" | sed 's/.*VITE_API_URL: *//;s/"//g')
VITE_CLERK_PUBLISHABLE_KEY = $(shell grep -A20 "frontend:" $(VALUES_FILE) | grep "VITE_CLERK_PUBLISHABLE_KEY:" | sed 's/.*VITE_CLERK_PUBLISHABLE_KEY: *//;s/"//g')
VITE_MIXPANEL_TOKEN = $(shell grep -A20 "frontend:" $(VALUES_FILE) | grep "VITE_MIXPANEL_TOKEN:" | sed 's/.*VITE_MIXPANEL_TOKEN: *//;s/"//g')

# Common variables
BACKEND_DOCKER_IMAGE = $(BACKEND_REPO)
FRONTEND_DOCKER_IMAGE = $(FRONTEND_REPO)
CHART_PATH = ./aiskagents

# Extract base URL for docker login
BACKEND_BASE_URL = $(shell echo $(BACKEND_REPO) | cut -d/ -f1)
FRONTEND_BASE_URL = $(shell echo $(FRONTEND_REPO) | cut -d/ -f1)

# Phony targets
.PHONY: build-backend build-frontend push-backend push-frontend build push deploy install upgrade uninstall clean help

# Build the backend Docker image
build-backend:
	@echo "Building backend Docker image $(BACKEND_DOCKER_IMAGE):$(TAG) ($(ENV) environment)..."
	cd ../backend && docker build --platform linux/amd64 -t $(BACKEND_DOCKER_IMAGE):$(TAG) .

# Build the frontend Docker image
build-frontend:
	@echo "Building frontend Docker image $(FRONTEND_DOCKER_IMAGE):$(TAG) ($(ENV) environment)..."
	@echo "Using VITE_API_URL: $(VITE_API_URL)"
	@echo "Using VITE_CLERK_PUBLISHABLE_KEY: $(VITE_CLERK_PUBLISHABLE_KEY)"
	@echo "Using VITE_MIXPANEL_TOKEN: $(VITE_MIXPANEL_TOKEN)"
	cd ../frontend/sales-agent-crew && docker build \
		--platform=linux/amd64 \
		--build-arg VITE_API_URL=$(VITE_API_URL) \
		--build-arg VITE_CLERK_PUBLISHABLE_KEY=$(VITE_CLERK_PUBLISHABLE_KEY) \
		--build-arg VITE_MIXPANEL_TOKEN=$(VITE_MIXPANEL_TOKEN) \
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
		--values $(VALUES_FILE) \
		--set backend.image.tag=$(TAG) \
		--set frontend.image.tag=$(TAG)

# Upgrade the Helm chart
upgrade:
	@echo "Upgrading Helm chart using $(VALUES_FILE) ($(ENV) environment)..."
	helm upgrade aiskagents-$(ENV) $(CHART_PATH) \
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
	@echo "Usage: make [target] [ENV=dev|prod] [TAG=custom-tag]"
	@echo ""
	@echo "Current environment: $(ENV)"
	@echo "Current tag: $(TAG)"
	@echo "Using values file: $(VALUES_FILE)"
	@echo "Backend repository: $(BACKEND_REPO)"
	@echo "Frontend repository: $(FRONTEND_REPO)"
	@echo "VITE_API_URL: $(VITE_API_URL)"
	@echo "VITE_CLERK_PUBLISHABLE_KEY: $(VITE_CLERK_PUBLISHABLE_KEY)"
	@echo "VITE_MIXPANEL_TOKEN: $(VITE_MIXPANEL_TOKEN)"
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
	@echo "  make deploy                           # Deploy to dev environment with auto-generated tag"
	@echo "  make deploy ENV=prod                  # Deploy to production environment with auto-generated tag"
	@echo "  make build ENV=prod TAG=v1.0.0        # Build images for production with custom tag"
	@echo "  make deploy ENV=dev TAG=feature-123   # Deploy to dev with custom tag"
	@echo ""

# Default target
default: help 
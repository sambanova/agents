# Variables
BASE_URL ?= us-west2-docker.pkg.dev/acp-starterkits-development-57/oci-us-west2-starerkits
IMAGE_NAME ?= aiskagents-frontend
TAG ?= 0.0.1-$(shell date '+%Y%m%d')
DOCKER_IMAGE := $(BASE_URL)/$(IMAGE_NAME)
PLATFORMS ?= linux/amd64,linux/arm64

# Load environment variables from .env file
include .env
export

# Phony targets (targets that are not actual files)
.PHONY: build push deploy clean local deploy-secrets

# Build the Docker image
build:
	@echo "Building Docker image $(DOCKER_IMAGE):$(TAG)..."
	docker build \
		--platform=linux/amd64 \
		--build-arg VITE_API_URL=$(VITE_API_URL) \
		--build-arg VITE_CLERK_PUBLISHABLE_KEY=$(VITE_CLERK_PUBLISHABLE_KEY) \
		-t $(DOCKER_IMAGE):$(TAG) .

# Push the Docker image to Docker Hub
push: build
	@echo "**** Please Loggin in to Docker Hub..."
	docker login $(BASE_URL)

	@echo "Pushing Docker image $(DOCKER_IMAGE):$(TAG) to Docker Hub..."
	docker push $(DOCKER_IMAGE):$(TAG)

# Deploy to Kubernetes (assuming you have kubectl configured)
deploy: push
	@echo "Deploying application to Kubernetes..."
	cat ../../k8s/frontend_deployment.yaml | \
		sed 's@{{DOCKER_IMAGE}}@$(DOCKER_IMAGE):$(TAG)@g' | \
		kubectl apply -f -

# Run the application locally
local:
	@echo "Running application locally..."
	npm run start

# Clean up
clean:
	@echo "Cleaning up..."
	docker rmi -f $(DOCKER_IMAGE):$(TAG) || true

# Help message
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build          Build the Docker image"
	@echo "  push           Push the Docker image to Docker Hub"
	@echo "  deploy         Deploy the application to Kubernetes"
	@echo "  deploy-secrets Deploy secrets to Kubernetes"
	@echo "  local          Run the application locally"
	@echo "  clean          Clean up the Docker image"
	@echo "  help           Display this help message"
	@echo ""

# Default target
default: help
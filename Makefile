# Makefile for AISKAgents project

# Phony targets
.PHONY: deploy build push clean help

# Deploy to Kubernetes using Helm
deploy:
	@echo "Deploying AISKAgents to Kubernetes using Helm..."
	$(MAKE) -C helm deploy

# Build Docker images
build:
	@echo "Building Docker images..."
	$(MAKE) -C helm build

# Push Docker images
push:
	@echo "Pushing Docker images..."
	$(MAKE) -C helm push

# Clean up
clean:
	@echo "Cleaning up..."
	$(MAKE) -C helm clean

# Help message
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build    Build Docker images"
	@echo "  push     Push Docker images"
	@echo "  deploy   Deploy to Kubernetes using Helm"
	@echo "  clean    Clean up"
	@echo "  help     Display this help message"
	@echo ""
	@echo "For more detailed options, use: make -C helm help"
	@echo ""

# Default target
default: help

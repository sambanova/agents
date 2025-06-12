TOOLS_VERSION ?= 0.0.7
DOCKER_HOST := unix:///Users/$(USER)/.colima/default/docker.sock

.PHONY: push-finance
push-finance:
	DOCKER_HOST=$(DOCKER_HOST) docker buildx create --name multiplatform-builder --driver docker-container --use 2>/dev/null || true
	DOCKER_HOST=$(DOCKER_HOST) docker buildx build --platform linux/amd64 --load --tag data-analysis:$(TOOLS_VERSION) --file ./Dockerfile-finance .
	DOCKER_HOST=$(DOCKER_HOST) daytona image push data-analysis:$(TOOLS_VERSION)
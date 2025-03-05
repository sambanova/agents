
# Deploy to Kubernetes (assuming you have kubectl configured)
deploy:
	@echo "Deploying agents to Kubernetes..."
	make -C backend deploy
	
	@echo "Deploying backend to Kubernetes..."
	make -C frontend/sales-agent-crew deploy
ing application to Kubernetes..."
	cat k8s/ingress.yaml | kubectl apply -f -
	

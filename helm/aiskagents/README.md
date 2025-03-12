# AISKAgents Helm Chart

This Helm chart deploys the AISKAgents application, which consists of a backend, frontend, and Redis components.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- Ingress controller (e.g., NGINX Ingress Controller)
- Cert-manager (for TLS certificates)

## Installation

```bash
# Add the repository (if applicable)
# helm repo add aiskagents https://your-repo-url.com
# helm repo update

# Install the chart
helm install aiskagents ./aiskagents
```

## Configuration

The following table lists the configurable parameters of the AISKAgents chart and their default values.

### Global Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.namespace` | Namespace where the application will be deployed | `default` |
| `global.imagePullSecrets` | Image pull secrets | `[{name: regcred}]` |

### Backend Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `backend.name` | Name of the backend component | `aiskagents-backend` |
| `backend.image.repository` | Backend image repository | `us-west2-docker.pkg.dev/acp-starterkits-development-57/oci-us-west2-starerkits/aiskagents-backend` |
| `backend.image.tag` | Backend image tag | `0.0.1` |
| `backend.image.pullPolicy` | Backend image pull policy | `Always` |
| `backend.replicas` | Number of backend replicas | `4` |
| `backend.resources` | Backend resource requests and limits | See `values.yaml` |
| `backend.service.type` | Backend service type | `ClusterIP` |
| `backend.service.port` | Backend service port | `80` |
| `backend.service.targetPort` | Backend container port | `8000` |
| `backend.service.sessionAffinity` | Backend service session affinity | `ClientIP` |
| `backend.service.sessionAffinityTimeout` | Backend service session affinity timeout | `10800` |
| `backend.env` | Backend environment variables | See `values.yaml` |
| `backend.volumes.logs.hostPath` | Host path for logs volume | `/data/aiskagents-logs` |
| `backend.volumes.logs.mountPath` | Container mount path for logs volume | `/app/logs` |
| `backend.probes` | Backend liveness and readiness probes | See `values.yaml` |
| `backend.secrets.name` | Backend secrets name | `aiskagents-backend-secrets` |
| `backend.secrets.data` | Backend secrets data | See `values.yaml` |

### Frontend Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `frontend.name` | Name of the frontend component | `aiskagents-frontend` |
| `frontend.image.repository` | Frontend image repository | `us-west2-docker.pkg.dev/acp-starterkits-development-57/oci-us-west2-starerkits/aiskagents-frontend` |
| `frontend.image.tag` | Frontend image tag | `0.0.1` |
| `frontend.image.pullPolicy` | Frontend image pull policy | `Always` |
| `frontend.replicas` | Number of frontend replicas | `1` |
| `frontend.service.type` | Frontend service type | `ClusterIP` |
| `frontend.service.port` | Frontend service port | `80` |
| `frontend.service.targetPort` | Frontend container port | `80` |
| `frontend.env` | Frontend environment variables | See `values.yaml` |
| `frontend.secrets.name` | Frontend secrets name | `aiskagents-frontend-secrets` |
| `frontend.secrets.data` | Frontend secrets data | See `values.yaml` |

### Ingress Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `true` |
| `ingress.className` | Ingress class name | `nginx` |
| `ingress.annotations` | Ingress annotations | See `values.yaml` |
| `ingress.host` | Ingress host | `aiskagents.cloud.snova.ai` |
| `ingress.tls.secretName` | TLS secret name | `cloud-snova-ai-tls` |
| `ingress.paths` | Ingress paths | See `values.yaml` |

### Redis Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `redis.enabled` | Enable Redis | `true` |
| `redis.namespace` | Redis namespace | `redis` |
| `redis.image.repository` | Redis image repository | `redis` |
| `redis.image.tag` | Redis image tag | `7.2-alpine` |
| `redis.image.pullPolicy` | Redis image pull policy | `IfNotPresent` |
| `redis.replicas` | Number of Redis replicas | `1` |
| `redis.resources` | Redis resource requests and limits | See `values.yaml` |
| `redis.service.type` | Redis service type | `ClusterIP` |
| `redis.service.port` | Redis service port | `6379` |
| `redis.service.targetPort` | Redis container port | `6379` |
| `redis.args` | Redis container arguments | See `values.yaml` |
| `redis.volumes.data.hostPath` | Host path for Redis data volume | `/data/redis` |
| `redis.volumes.data.mountPath` | Container mount path for Redis data volume | `/data` |
| `redis.probes` | Redis liveness and readiness probes | See `values.yaml` |

## Upgrading

```bash
helm upgrade aiskagents ./aiskagents
```

## Uninstalling

```bash
helm uninstall aiskagents
``` 
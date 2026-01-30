# Kubernetes Manifests

This directory contains Kubernetes manifests for deploying the Mikrom API application.

## 📁 Files

| File | Description |
|------|-------------|
| `configmap.yaml` | Application configuration (non-sensitive) |
| `secrets.yaml` | Application secrets (DATABASE_URL, SECRET_KEY) |
| `postgres-deployment.yaml` | PostgreSQL database deployment + PVC |
| `postgres-service.yaml` | PostgreSQL service (ClusterIP) |
| `deployment.yaml` | Mikrom API application deployment (2 replicas) |
| `service.yaml` | Mikrom API service (ClusterIP) |
| `ingress.yaml` | Ingress configuration (NGINX) |

## 🚀 Quick Start

### Prerequisites

1. Kubernetes cluster (v1.24+)
2. `kubectl` configured
3. NGINX Ingress Controller installed

### Deploy

```bash
# Create namespace
kubectl create namespace mikrom-dev

# Apply all manifests
kubectl apply -f k8s/ -n mikrom-dev

# Check status
kubectl get all -n mikrom-dev
```

### Access Application

```bash
# Get ingress URL
kubectl get ingress -n mikrom-dev

# Port forward for local testing
kubectl port-forward svc/mikrom-api-service 8000:8000 -n mikrom-dev

# Access: http://localhost:8000
```

## ⚙️ Configuration

### Update Secrets

**Important:** Update secrets before deploying to production!

```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Create secret manually
kubectl create secret generic mikrom-secrets \
  --from-literal=SECRET_KEY="your-secret-key-here" \
  --from-literal=DATABASE_URL="postgresql://user:pass@host:5432/db" \
  --from-literal=POSTGRES_PASSWORD="secure-password" \
  -n mikrom-dev --dry-run=client -o yaml | kubectl apply -f -
```

### Update ConfigMap

```bash
# Edit configuration
kubectl edit configmap mikrom-config -n mikrom-dev

# Or update the file and reapply
kubectl apply -f k8s/configmap.yaml -n mikrom-dev
```

### Update Image

```bash
# Update deployment image
kubectl set image deployment/mikrom-api \
  mikrom-api=registry.gitlab.com/your-group/mikrom-py:v1.0.0 \
  -n mikrom-dev

# Or edit deployment
kubectl edit deployment mikrom-api -n mikrom-dev
```

## 🔍 Monitoring

### Check Logs

```bash
# Application logs
kubectl logs -f deployment/mikrom-api -n mikrom-dev

# PostgreSQL logs
kubectl logs -f deployment/postgres -n mikrom-dev

# All pods
kubectl logs -f -l app=mikrom-api -n mikrom-dev
```

### Check Health

```bash
# Pod status
kubectl get pods -n mikrom-dev

# Deployment status
kubectl rollout status deployment/mikrom-api -n mikrom-dev

# Service endpoints
kubectl get endpoints -n mikrom-dev

# Health check (if port-forwarded)
curl http://localhost:8000/api/v1/health
```

### Debugging

```bash
# Describe pod
kubectl describe pod <pod-name> -n mikrom-dev

# Get events
kubectl get events -n mikrom-dev --sort-by='.lastTimestamp'

# Shell into pod
kubectl exec -it <pod-name> -n mikrom-dev -- /bin/sh

# Shell into postgres
kubectl exec -it deployment/postgres -n mikrom-dev -- psql -U postgres -d mikrom_db
```

## 🔄 Operations

### Scale Application

```bash
# Manual scaling
kubectl scale deployment/mikrom-api --replicas=3 -n mikrom-dev

# Auto-scaling (HPA)
kubectl autoscale deployment mikrom-api \
  --min=2 --max=10 \
  --cpu-percent=80 \
  -n mikrom-dev
```

### Rollback

```bash
# View history
kubectl rollout history deployment/mikrom-api -n mikrom-dev

# Rollback to previous version
kubectl rollout undo deployment/mikrom-api -n mikrom-dev

# Rollback to specific revision
kubectl rollout undo deployment/mikrom-api --to-revision=2 -n mikrom-dev
```

### Restart

```bash
# Rolling restart
kubectl rollout restart deployment/mikrom-api -n mikrom-dev

# Force delete and recreate pod
kubectl delete pod <pod-name> -n mikrom-dev
```

### Delete Resources

```bash
# Delete all resources
kubectl delete -f k8s/ -n mikrom-dev

# Delete namespace (removes everything)
kubectl delete namespace mikrom-dev
```

## 📊 Resource Requirements

### Application (per pod)

- **Requests:** 100m CPU, 128Mi memory
- **Limits:** 500m CPU, 512Mi memory
- **Replicas:** 2 (development)

### PostgreSQL

- **Storage:** 5Gi PersistentVolumeClaim
- **Replicas:** 1 (use StatefulSet for production)

### Total (Development)

- **CPU:** ~300m (3 pods)
- **Memory:** ~512Mi (3 pods)
- **Storage:** 5Gi

## 🔐 Security Notes

1. **Secrets:** Never commit actual secrets to Git
2. **RBAC:** Use least-privilege service accounts
3. **Network Policies:** Implement network segmentation
4. **TLS:** Enable TLS for ingress (cert-manager)
5. **Scanning:** Scan images for vulnerabilities

## 📝 Customization

### Change Namespace

Replace `mikrom-dev` with your namespace in all files:

```bash
# Using sed (Linux/Mac)
sed -i 's/mikrom-dev/your-namespace/g' k8s/*.yaml

# Or manually edit each file
```

### Change Domain

Update `ingress.yaml`:

```yaml
spec:
  rules:
  - host: your-domain.com  # Change this
```

### Add TLS

Uncomment TLS section in `ingress.yaml`:

```yaml
tls:
- hosts:
  - your-domain.com
  secretName: your-tls-secret
```

### Use External Database

Update `secrets.yaml`:

```yaml
stringData:
  DATABASE_URL: "postgresql://user:pass@external-db:5432/mikrom_db"
```

Then remove PostgreSQL deployment:

```bash
# Don't apply these files
# - postgres-deployment.yaml
# - postgres-service.yaml
```

## 🆘 Troubleshooting

### Pod Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n mikrom-dev

# Common issues:
# - ImagePullBackOff: Check registry credentials
# - CrashLoopBackOff: Check application logs
# - Pending: Check resource availability
```

### Database Connection Failed

```bash
# Test connection from pod
kubectl exec -it <api-pod-name> -n mikrom-dev -- /bin/sh
# Inside pod:
apk add postgresql-client
psql $DATABASE_URL

# Check PostgreSQL service
kubectl get svc postgres-service -n mikrom-dev
kubectl get endpoints postgres-service -n mikrom-dev
```

### Ingress Not Working

```bash
# Check ingress controller
kubectl get pods -n ingress-nginx

# Check ingress resource
kubectl describe ingress mikrom-api-ingress -n mikrom-dev

# Check service
kubectl get svc mikrom-api-service -n mikrom-dev
```

## 📚 Additional Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
- [cert-manager](https://cert-manager.io/docs/)

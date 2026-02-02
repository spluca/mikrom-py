# GitLab CI/CD Pipeline Documentation

## 🚀 Quick Start

**Before using the pipeline, complete these steps:**

1. **Configure GitLab CI/CD Variables** (Settings → CI/CD → Variables):
   - `KUBE_URL` - Your Kubernetes cluster API URL
   - `KUBE_TOKEN` - Service account token for deployment
   - `KUBE_NAMESPACE` - Target namespace (e.g., `mikrom-dev`)
   - `KUBE_INGRESS_BASE_DOMAIN` - Your domain (e.g., `example.com`)

2. **Set up Kubernetes secrets**:
   ```bash
   # Copy the example file
   cp k8s/secrets.example.yaml k8s/secrets.yaml
   
   # Generate a secure SECRET_KEY
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   
   # Edit k8s/secrets.yaml and replace placeholder values
   # DO NOT commit secrets.yaml (it's in .gitignore)
   ```

3. **Update Kubernetes manifests**:
   - `k8s/deployment.yaml` - Change image registry path to your GitLab project
   - `k8s/ingress.yaml` - Change host to your domain

4. **Deploy secrets to cluster**:
   ```bash
   kubectl apply -f k8s/secrets.yaml
   ```

5. **Push to GitLab** - Pipeline will run automatically on main branch

See detailed setup instructions below.

---

## 📋 Overview

This document describes the GitLab CI/CD pipeline for the Mikrom API project. The pipeline automates testing, security scanning, building, and deployment to Kubernetes.

## 🎯 Pipeline Architecture

### Stages

The pipeline consists of 5 stages:

1. **Validate** - Code quality checks (linting, formatting)
2. **Test** - Run test suite with coverage reporting
3. **Security** - Dependency scanning and SAST
4. **Build** - Build and push Docker image
5. **Deploy** - Deploy to Kubernetes cluster

### Pipeline Flow

```
┌─────────────┐
│  Validate   │  → Lint + Format Check
└──────┬──────┘
       │
┌──────▼──────┐
│    Test     │  → 70 Tests + Coverage
└──────┬──────┘
       │
┌──────▼──────┐
│  Security   │  → Dependency Scan + SAST
└──────┬──────┘
       │
┌──────▼──────┐
│    Build    │  → Docker Build + Push
└──────┬──────┘
       │
┌──────▼──────┐
│   Deploy    │  → Kubernetes Dev (Auto)
└─────────────┘
```

## 🔧 Prerequisites

### 1. GitLab CI/CD Variables

Configure these variables in GitLab: **Settings → CI/CD → Variables**

#### Required Variables

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `KUBE_URL` | Variable | Kubernetes API URL | `https://k8s.example.com:6443` |
| `KUBE_TOKEN` | Variable (Masked) | Kubernetes service account token | `eyJhbGc...` |
| `KUBE_NAMESPACE` | Variable | Kubernetes namespace | `mikrom-dev` |
| `KUBE_INGRESS_BASE_DOMAIN` | Variable | Base domain for ingress | `example.com` |

#### Optional Variables

| Variable | Type | Description | Default |
|----------|------|-------------|---------|
| `CI_REGISTRY_USER` | Built-in | GitLab registry username | Auto-configured |
| `CI_REGISTRY_PASSWORD` | Built-in | GitLab registry password | Auto-configured |
| `SECRET_KEY` | Variable (Masked) | JWT secret key | Generated in K8s secret |
| `DATABASE_URL` | Variable (Masked) | PostgreSQL connection | In K8s secret |

### 2. Kubernetes Service Account

Create a service account with appropriate permissions:

```bash
# Create service account
kubectl create serviceaccount gitlab-deploy -n mikrom-dev

# Create role
kubectl create role gitlab-deploy \
  --verb=get,list,watch,create,update,patch,delete \
  --resource=deployments,services,ingress,configmaps,secrets,pods,jobs \
  -n mikrom-dev

# Create role binding
kubectl create rolebinding gitlab-deploy \
  --role=gitlab-deploy \
  --serviceaccount=mikrom-dev:gitlab-deploy \
  -n mikrom-dev

# Get token (Kubernetes 1.24+)
kubectl create token gitlab-deploy -n mikrom-dev --duration=8760h
```

### 3. GitLab Container Registry

Enable Container Registry in your GitLab project:
- **Settings → General → Visibility, project features, permissions**
- Enable **Container Registry**

## 📦 Stage Details

### Stage 1: Validate

**Jobs:** `lint`, `format-check`

Ensures code quality standards:

```yaml
lint:
  - ruff check mikrom tests
  
format-check:
  - ruff format --check mikrom tests
```

**Runs on:**
- Merge requests
- Main branch pushes

### Stage 2: Test

**Job:** `test`

Executes the complete test suite:

```yaml
test:
  - pytest -v --cov=mikrom --cov-report=xml
  - 70 tests passing
  - Coverage report uploaded to GitLab
```

**Features:**
- PostgreSQL service container
- Coverage reporting (XML + HTML)
- Test result artifacts (30 days retention)
- Coverage badge in README

**Runs on:**
- Merge requests
- Main branch pushes

### Stage 3: Security

**Jobs:** `dependency-scanning`, `sast`

Security analysis:

```yaml
dependency-scanning:
  - safety check (Python vulnerability scanner)
  
sast:
  - bandit (Static Application Security Testing)
```

**Features:**
- Dependency vulnerability detection
- Security issue reporting
- Non-blocking (allows pipeline to continue)

**Runs on:**
- Merge requests
- Main branch pushes

### Stage 4: Build

**Job:** `build`

Builds and pushes Docker image:

```yaml
build:
  - docker build --tag $IMAGE_NAME:$IMAGE_TAG
  - docker push to GitLab Container Registry
```

**Image Tags:**
- `latest` - Latest build from main
- `$CI_COMMIT_SHORT_SHA` - Specific commit
- `$CI_COMMIT_REF_SLUG` - Branch/tag name

**Runs on:**
- Main branch pushes (automatic)
- Merge requests (manual trigger)

### Stage 5: Deploy

**Job:** `deploy-dev`

Deploys to Kubernetes development environment:

```yaml
deploy-dev:
  1. Create namespace (mikrom-dev)
  2. Create registry secret
  3. Apply ConfigMap + Secrets
  4. Deploy PostgreSQL
  5. Run database migrations
  6. Deploy application
  7. Apply service + ingress
  8. Wait for rollout
```

**Features:**
- Automatic deployment on main branch
- Database migration execution
- Health check verification
- Rollout status monitoring
- Manual stop job available

**Runs on:**
- Main branch pushes (automatic)

## 🚀 Deployment Configuration

### Kubernetes Resources

The deployment creates these resources:

```
mikrom-dev/
├── ConfigMap (mikrom-config)
├── Secret (mikrom-secrets)
├── PersistentVolumeClaim (postgres-pvc - 5Gi)
├── Deployment (postgres - 1 replica)
├── Service (postgres-service)
├── Deployment (mikrom-api - 2 replicas)
├── Service (mikrom-api-service)
└── Ingress (mikrom-api-ingress)
```

### Resource Limits

**Application Pods:**
```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

**Replicas:**
- Development: 2 replicas
- PostgreSQL: 1 replica (StatefulSet recommended for production)

### Health Checks

**Liveness Probe:**
```yaml
httpGet:
  path: /api/v1/health
  port: 8000
initialDelaySeconds: 30
periodSeconds: 10
```

**Readiness Probe:**
```yaml
httpGet:
  path: /api/v1/health
  port: 8000
initialDelaySeconds: 10
periodSeconds: 5
```

## 🔐 Security Configuration

### 1. Secrets Management

**Important:** The provided `k8s/secrets.yaml` contains placeholder values. Update them before deployment:

```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Update secrets.yaml or use GitLab CI/CD variables
kubectl create secret generic mikrom-secrets \
  --from-literal=SECRET_KEY="your-generated-key" \
  --from-literal=DATABASE_URL="postgresql://..." \
  -n mikrom-dev
```

### 2. Registry Access

GitLab automatically creates registry credentials using:
- `$CI_REGISTRY_USER`
- `$CI_REGISTRY_PASSWORD`

The pipeline creates a Kubernetes secret:
```bash
kubectl create secret docker-registry gitlab-registry \
  --docker-server=$CI_REGISTRY \
  --docker-username=$CI_REGISTRY_USER \
  --docker-password=$CI_REGISTRY_PASSWORD \
  -n mikrom-dev
```

### 3. RBAC Permissions

Minimum required permissions for deployment:
- `get`, `list`, `watch` - Read access
- `create`, `update`, `patch` - Modify resources
- `delete` - Remove old resources

## 📊 Monitoring & Observability

### Pipeline Metrics

View pipeline performance:
- **CI/CD → Pipelines**
- Average duration
- Success rate
- Failed jobs

### Coverage Reporting

Coverage badge in README:
```markdown
![Coverage](https://gitlab.com/your-group/mikrom-py/badges/main/coverage.svg)
```

### Application Monitoring

Monitor deployed application:

```bash
# Pod logs
kubectl logs -f deployment/mikrom-api -n mikrom-dev

# Pod status
kubectl get pods -n mikrom-dev

# Service endpoints
kubectl get svc -n mikrom-dev

# Ingress status
kubectl get ingress -n mikrom-dev
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Pipeline Fails at Test Stage

**Error:** `Database connection failed`

**Solution:**
```bash
# Check PostgreSQL service in CI
# Ensure DATABASE_URL is correct
# Wait for PostgreSQL to be ready before tests
```

#### 2. Docker Build Fails

**Error:** `denied: access forbidden`

**Solution:**
```bash
# Verify registry access
docker login $CI_REGISTRY -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD

# Check project permissions
# Settings → Repository → Deploy tokens
```

#### 3. Kubernetes Deployment Fails

**Error:** `Unauthorized`

**Solution:**
```bash
# Verify Kubernetes token
kubectl --token=$KUBE_TOKEN --server=$KUBE_URL get nodes

# Check service account permissions
kubectl auth can-i create deployments --as=system:serviceaccount:mikrom-dev:gitlab-deploy -n mikrom-dev
```

#### 4. Database Migration Fails

**Error:** `Job failed`

**Solution:**
```bash
# Check migration logs
kubectl logs job/migrations-xxx -n mikrom-dev

# Verify DATABASE_URL
kubectl get secret mikrom-secrets -n mikrom-dev -o jsonpath='{.data.DATABASE_URL}' | base64 -d

# Run migration manually
kubectl run migrations-manual \
  --image=$IMAGE_NAME:latest \
  --restart=Never \
  --namespace=mikrom-dev \
  --env="DATABASE_URL=$DATABASE_URL" \
  --command -- uv run alembic upgrade head
```

#### 5. Application Not Accessible

**Error:** `502 Bad Gateway`

**Solution:**
```bash
# Check pod status
kubectl get pods -n mikrom-dev
kubectl describe pod <pod-name> -n mikrom-dev

# Check logs
kubectl logs <pod-name> -n mikrom-dev

# Check service endpoints
kubectl get endpoints mikrom-api-service -n mikrom-dev

# Verify ingress
kubectl describe ingress mikrom-api-ingress -n mikrom-dev
```

## 🔄 Manual Operations

### Trigger Deployment Manually

```bash
# From GitLab UI
CI/CD → Pipelines → Run Pipeline → Select branch → Run

# Or retrigger specific job
CI/CD → Pipelines → Select pipeline → Retry job
```

### Rollback Deployment

```bash
# View deployment history
kubectl rollout history deployment/mikrom-api -n mikrom-dev

# Rollback to previous version
kubectl rollout undo deployment/mikrom-api -n mikrom-dev

# Rollback to specific revision
kubectl rollout undo deployment/mikrom-api --to-revision=2 -n mikrom-dev
```

### Scale Application

```bash
# Scale replicas
kubectl scale deployment/mikrom-api --replicas=3 -n mikrom-dev

# Auto-scaling (HPA)
kubectl autoscale deployment mikrom-api \
  --min=2 --max=10 \
  --cpu-percent=80 \
  -n mikrom-dev
```

### Update Configuration

```bash
# Update ConfigMap
kubectl edit configmap mikrom-config -n mikrom-dev

# Update Secret
kubectl edit secret mikrom-secrets -n mikrom-dev

# Restart pods to apply changes
kubectl rollout restart deployment/mikrom-api -n mikrom-dev
```

## 📚 Best Practices

### 1. Branch Strategy

- `main` - Production-ready code, auto-deploys to dev
- `feature/*` - Feature branches, manual deployment
- `hotfix/*` - Emergency fixes, manual deployment

### 2. Merge Request Workflow

1. Create feature branch
2. Push changes
3. Pipeline runs automatically (validate + test + security)
4. Create merge request
5. Review + approval
6. Merge to main
7. Automatic deployment to dev

### 3. Security

- Never commit secrets to Git
- Use GitLab CI/CD variables for sensitive data
- Rotate credentials regularly
- Use Kubernetes secrets for application secrets
- Enable SAST and dependency scanning

### 4. Testing

- Maintain test coverage above 80%
- Fix failing tests before merging
- Review security scan results
- Test migrations before deployment

### 5. Monitoring

- Set up log aggregation (ELK, Loki)
- Configure alerting (Prometheus + Alertmanager)
- Monitor resource usage
- Track deployment metrics

## 📝 Customization

### Adding Staging Environment

Add to `.gitlab-ci.yml`:

```yaml
deploy-staging:
  stage: deploy
  extends: .deploy_template
  variables:
    KUBE_NAMESPACE: mikrom-staging
    ENVIRONMENT: staging
  environment:
    name: staging
    url: https://mikrom-staging.$KUBE_INGRESS_BASE_DOMAIN
  rules:
    - if: $CI_COMMIT_TAG
      when: manual
```

### Adding Production Environment

```yaml
deploy-production:
  stage: deploy
  extends: .deploy_template
  variables:
    KUBE_NAMESPACE: mikrom-prod
    ENVIRONMENT: production
  environment:
    name: production
    url: https://mikrom.$KUBE_INGRESS_BASE_DOMAIN
  rules:
    - if: $CI_COMMIT_TAG
      when: manual
  only:
    - tags
```

### Slack Notifications

Add to `.gitlab-ci.yml`:

```yaml
notify-slack:
  stage: .post
  image: alpine:latest
  script:
    - apk add --no-cache curl
    - |
      curl -X POST $SLACK_WEBHOOK_URL \
        -H 'Content-Type: application/json' \
        -d "{\"text\":\"Pipeline $CI_PIPELINE_STATUS: $CI_PROJECT_NAME ($CI_COMMIT_REF_NAME)\"}"
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: on_failure
```

## 🎓 Additional Resources

- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [GitLab Container Registry](https://docs.gitlab.com/ee/user/packages/container_registry/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)

## 📞 Support

For issues or questions:
1. Check pipeline logs in GitLab
2. Review Kubernetes pod logs
3. Check this documentation
4. Contact DevOps team

# Kubernetes Deployment Guide

Deploy the Thoughts Dashboard to OpenShift/Kubernetes in the `thoughts-app` namespace.

## What's Included

The `deployment.yaml` file contains:
- ✅ **Namespace**: `thoughts-app`
- ✅ **ConfigMap**: Non-sensitive configuration
- ✅ **Secret**: Database password and Flask secret key
- ✅ **Deployment**: Dashboard application
- ✅ **Service**: ClusterIP service (port 80 → 5000)
- ✅ **Route**: OpenShift route with TLS

## Prerequisites

1. **Image built and pushed** to Quay.io:
   ```
   quay.io/redhat_na_ssa/thoughts-vibe-dashboard:latest
   ```

2. **Image pull secret** exists:
   ```bash
   # Verify it exists
   kubectl get secret quay-auth-secret
   
   # If not, create it in thoughts-app namespace:
   kubectl create secret docker-registry quay-auth-secret \
     --docker-server=quay.io \
     --docker-username=<username> \
     --docker-password=<password> \
     -n thoughts-app
   ```

3. **PostgreSQL database** accessible at:
   ```
   postgresql.thoughts-app.svc.cluster.local:5432
   ```

## Quick Deploy

### Deploy Everything

```bash
kubectl apply -f deployment.yaml
```

This creates all resources in the `thoughts-app` namespace.

### Check Status

```bash
# Check all resources
kubectl get all -n thoughts-app

# Check deployment status
kubectl get deployment thought-vibe-dashboard -n thoughts-app

# Check pod status
kubectl get pods -n thoughts-app

# Check route
kubectl get route thought-vibe-dashboard -n thoughts-app
```

### View Logs

```bash
# Get pod name
kubectl get pods -n thoughts-app

# View logs
kubectl logs -f <pod-name> -n thoughts-app
```

### Access the Application

```bash
# Get the route URL
kubectl get route thought-vibe-dashboard -n thoughts-app -o jsonpath='{.spec.host}'

# Or use OpenShift console
oc get route thought-vibe-dashboard -n thoughts-app
```

Then open the URL in your browser.

## Configuration

### Update Environment Variables

Edit the ConfigMap in `deployment.yaml`:

```yaml
data:
  FLASK_ENV: "production"
  DB_HOST: "postgresql.thoughts-app.svc.cluster.local"
  DB_NAME: "thoughts"
  DB_PORT: "5432"
  DB_USER: "thoughts"
```

### Update Secrets

**⚠️ IMPORTANT:** Change the default passwords!

Edit the Secret in `deployment.yaml`:

```yaml
stringData:
  DB_PASSWORD: "your-secure-password-here"
  SECRET_KEY: "your-random-secret-key-here"
```

Generate a secure secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Update Image

Change the image version in the Deployment:

```yaml
containers:
- name: dashboard
  image: quay.io/redhat_na_ssa/thoughts-vibe-dashboard:v1.0  # Change tag
```

## Scaling

### Scale Replicas

```bash
# Scale to 3 replicas
kubectl scale deployment thought-vibe-dashboard --replicas=3 -n thoughts-app

# Or edit deployment.yaml and change:
spec:
  replicas: 3
```

### Auto-scaling (HPA)

```bash
kubectl autoscale deployment thought-vibe-dashboard \
  --cpu-percent=70 \
  --min=1 \
  --max=5 \
  -n thoughts-app
```

## Resource Limits

Current limits in deployment.yaml:

```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

Adjust based on your load testing.

## Troubleshooting

### Pod Not Starting

```bash
# Describe pod to see events
kubectl describe pod <pod-name> -n thoughts-app

# Check for image pull errors
kubectl get events -n thoughts-app --sort-by='.lastTimestamp'
```

### Database Connection Issues

```bash
# Check if PostgreSQL service exists
kubectl get svc postgresql -n thoughts-app

# Test connection from pod
kubectl exec -it <pod-name> -n thoughts-app -- bash
# Inside pod:
nc -zv postgresql.thoughts-app.svc.cluster.local 5432
```

### Image Pull Errors

```bash
# Check if secret exists
kubectl get secret quay-auth-secret -n thoughts-app

# Check if secret is referenced in deployment
kubectl get deployment thought-vibe-dashboard -n thoughts-app -o yaml | grep imagePullSecrets
```

### View Application Logs

```bash
# Stream logs
kubectl logs -f deployment/thought-vibe-dashboard -n thoughts-app

# View recent logs
kubectl logs --tail=100 deployment/thought-vibe-dashboard -n thoughts-app

# View logs from all pods
kubectl logs -l app=thought-vibe-dashboard -n thoughts-app
```

## Update Deployment

### Rolling Update

```bash
# Update image
kubectl set image deployment/thought-vibe-dashboard \
  dashboard=quay.io/redhat_na_ssa/thoughts-vibe-dashboard:v2.0 \
  -n thoughts-app

# Watch rollout status
kubectl rollout status deployment/thought-vibe-dashboard -n thoughts-app
```

### Rollback

```bash
# View rollout history
kubectl rollout history deployment/thought-vibe-dashboard -n thoughts-app

# Rollback to previous version
kubectl rollout undo deployment/thought-vibe-dashboard -n thoughts-app

# Rollback to specific revision
kubectl rollout undo deployment/thought-vibe-dashboard --to-revision=2 -n thoughts-app
```

## Clean Up

### Delete Everything

```bash
# Delete all resources
kubectl delete -f deployment.yaml

# Or delete namespace (removes everything inside)
kubectl delete namespace thoughts-app
```

### Delete Specific Resources

```bash
# Delete just the deployment
kubectl delete deployment thought-vibe-dashboard -n thoughts-app

# Delete just the route
kubectl delete route thought-vibe-dashboard -n thoughts-app
```

## Health Checks

The deployment includes:

**Liveness Probe:**
- Checks if app is running
- Restarts pod if failing

**Readiness Probe:**
- Checks if app is ready to serve traffic
- Removes from service endpoints if failing

## Next Steps

1. **Set up monitoring** - Add Prometheus metrics
2. **Configure alerts** - Set up alerting rules
3. **Add backup** - Database backup strategy
4. **Implement GitOps** - ArgoCD/Flux for automated deployments
5. **Add ingress** - If not using OpenShift Routes

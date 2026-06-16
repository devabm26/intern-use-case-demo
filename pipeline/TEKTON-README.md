# Tekton Pipeline for Building Container Images

This pipeline builds a container image from a Containerfile in the repository.

## Prerequisites

1. **Tekton Pipelines installed** on your OpenShift/Kubernetes cluster
2. **Tekton Hub ClusterTasks** installed:
   ```bash
   # Install git-clone task
   kubectl apply -f https://raw.githubusercontent.com/tektoncd/catalog/main/task/git-clone/0.9/git-clone.yaml
   
   # Install buildah task
   kubectl apply -f https://raw.githubusercontent.com/tektoncd/catalog/main/task/buildah/0.6/buildah.yaml
   ```
3. **Registry authentication secret** (already exists as `quay-auth-secret`):
   - The pipeline uses this secret to authenticate with Quay.io
   - To create one (if needed):
     ```bash
     kubectl create secret docker-registry quay-auth-secret \
       --docker-server=quay.io \
       --docker-username=<your-username> \
       --docker-password=<your-password>
     ```
4. **Trustification credentials secret** (already exists):
   - The pipeline uses existing `trustification-secret` for SBOM upload to Bombastic
   - **Verify the secret exists:**
     ```bash
     kubectl get secret trustification-secret
     ```
   - **Expected secret keys (lowercase):**
     - `bombastic_api_url` - Bombastic API endpoint
     - `oidc_issuer_url` - OIDC provider URL
     - `oidc_client_id` - OAuth2 client ID
     - `oidc_client_secret` - OAuth2 client secret
   - If you need to update the secret:
     ```bash
     kubectl create secret generic trustification-secret \
       --from-literal=bombastic_api_url=https://sbom.trustification.dev \
       --from-literal=oidc_issuer_url=https://sso.redhat.com/auth/realms/redhat-external \
       --from-literal=oidc_client_id=your-client-id \
       --from-literal=oidc_client_secret=your-client-secret \
       --dry-run=client -o yaml | kubectl apply -f -
     ```
5. **RHACS credentials secret** (for image scanning):
   - The pipeline uses `rhacs-secret` for RHACS Central authentication
   - **Create the secret:**
     ```bash
     # Get RHACS Central endpoint and API token from RHACS Console
     # Console: Platform Configuration → Integrations → API Token
     
     # Option 1: Internal cluster endpoint (recommended for in-cluster access)
     kubectl create secret generic rhacs-secret \
       --from-literal=rox_central_endpoint=central.stackrox.svc:443 \
       --from-literal=rox_api_token=your-api-token \
       --dry-run=client -o yaml | kubectl apply -f -
     
     # Option 2: External route endpoint (if using OpenShift route)
     kubectl create secret generic rhacs-secret \
       --from-literal=rox_central_endpoint=central-stackrox.apps.cluster-xxxx.example.com:443 \
       --from-literal=rox_api_token=your-api-token \
       --dry-run=client -o yaml | kubectl apply -f -
     
     # Option 3: With full URL (pipeline will normalize and add port)
     kubectl create secret generic rhacs-secret \
       --from-literal=rox_central_endpoint=https://central-stackrox.apps.cluster-xxxx.example.com \
       --from-literal=rox_api_token=your-api-token \
       --dry-run=client -o yaml | kubectl apply -f -
     ```
   - **Expected secret keys:**
     - `rox_central_endpoint` - RHACS Central endpoint
       - **Recommended format:** `central-stackrox.apps.cluster.example.com:443` (hostname:port)
       - Also accepts: `https://central-stackrox.apps.cluster.example.com` (pipeline adds `:443`)
       - Also accepts: `central.stackrox.svc:443` (internal cluster service)
       - **Important:** Port `:443` is required for gRPC connections (auto-added if missing)
     - `rox_api_token` - API token with image scanning permissions
   - **Get RHACS API token:**
     1. Login to RHACS Central console
     2. Go to Platform Configuration → Integrations
     3. Scroll to "Authentication Tokens" section
     4. Click "API Token"
     5. Generate new token with role: `Continuous Integration`
     6. Copy the token and use in secret above

## Quick Start

### 1. Apply the Pipeline

```bash
kubectl apply -f tekton-pipeline.yaml
```

This creates:
- ✅ PersistentVolumeClaim for shared workspace
- ✅ Pipeline definition
- ✅ PipelineRun to execute immediately

### 2. Watch the Pipeline Run

```bash
# Watch the pipeline
tkn pipelinerun logs build-containerfile-run -f

# Or using kubectl
kubectl logs -f <pod-name>
```

### 3. Check Status

```bash
# Check pipeline run status
tkn pipelinerun describe build-containerfile-run

# List all pipeline runs
tkn pipelinerun list
```

### 4. View Vulnerability Results in OpenShift Console

The pipeline exports vulnerability metrics that are visible in the OpenShift Console:

**Access Pipeline Results:**
1. Open OpenShift Console
2. Navigate to: **Pipelines → PipelineRuns**
3. Filter by label: `security-scan=rhacs` or `app=thoughts-vibe-dashboard`
4. Click on `build-containerfile-run`
5. Go to **"Results"** tab

**Available Results:**
- `CRITICAL_CVES` - Number of critical severity CVEs
- `HIGH_CVES` - Number of high severity CVEs
- `MEDIUM_CVES` - Number of medium severity CVEs
- `LOW_CVES` - Number of low severity CVEs
- `POLICY_VIOLATIONS` - Total RHACS policy violations
- `CRITICAL_VIOLATIONS` - Critical policy violations

**Notes:** 
- The built image URL is available in the pipeline parameters (`image-name`), not as a result.
- Full scan output (JSON) is available in task logs, not as a result (to avoid 4096 byte limit).
- To view detailed CVE information, check the `scan-image-rhacs` task logs.

**View Logs:**
1. Click on the PipelineRun
2. Go to **"Logs"** tab
3. Select task: `scan-image-rhacs`
4. View detailed CVE and policy violation output

**View in Topology View:**
1. Navigate to: **Topology**
2. Find the pipeline decorator on your application
3. Click to see last pipeline run status
4. Hover over tasks to see results

**CLI Method:**
```bash
# Get all pipeline results
tkn pipelinerun describe build-containerfile-run -o json | \
  jq '.status.pipelineResults'

# Get specific vulnerability counts
tkn pipelinerun describe build-containerfile-run -o json | \
  jq -r '.status.pipelineResults[] | select(.name | contains("CVE")) | "\(.name): \(.value)"'

# Example output:
# CRITICAL_CVES: 5
# HIGH_CVES: 23
# MEDIUM_CVES: 45
# LOW_CVES: 12

# Get image name from pipeline parameters
tkn pipelinerun describe build-containerfile-run -o json | \
  jq -r '.spec.params[] | select(.name=="image-name") | .value'

# Example output:
# quay.io/redhat_na_ssa/thoughts-vibe-dashboard:latest
```

**Filter PipelineRuns by Security Scan:**
```bash
# List all pipeline runs with RHACS scans
kubectl get pipelinerun -l security-scan=rhacs

# List all pipeline runs for this app
kubectl get pipelinerun -l app=thoughts-vibe-dashboard

# Get latest vulnerability counts
kubectl get pipelinerun build-containerfile-run -o json | \
  jq '.status.pipelineResults'
```

## Pipeline Parameters

You can customize the pipeline by editing the PipelineRun parameters:

```yaml
params:
  - name: git-url
    value: https://github.com/devabm26/intern-use-case-demo.git
  - name: git-revision
    value: main  # branch, tag, or commit SHA
  - name: image-name
    value: quay.io/redhat_na_ssa/thoughts-vibe-dashboard:latest
  - name: containerfile-path
    value: ./Containerfile  # or ./Dockerfile
```

## Pipeline Labels and Annotations

The pipeline includes labels and annotations for better visibility in OpenShift Console:

**Labels:**
```yaml
labels:
  app: thoughts-vibe-dashboard                    # Application name
  app.kubernetes.io/name: thoughts-vibe-dashboard # Standard k8s app label
  app.kubernetes.io/component: pipeline           # Component type
  pipeline.openshift.io/type: kubernetes          # Pipeline type
  tekton.dev/pipeline: build-containerfile-pipeline
  security-scan: rhacs                            # Indicates RHACS scanning
  sbom-generation: enabled                        # Indicates SBOM generation
```

**Annotations:**
```yaml
annotations:
  pipeline.openshift.io/started-by: "tekton-pipeline"
  description: "Build container image, scan with RHACS, generate SBOM, upload to Trustification"
  image: "quay.io/redhat_na_ssa/thoughts-vibe-dashboard:latest"
```

**Using Labels for Filtering:**

In OpenShift Console:
- Navigate to **Pipelines → PipelineRuns**
- Use label selectors to filter:
  - `security-scan=rhacs` - Show only pipelines with security scanning
  - `sbom-generation=enabled` - Show only pipelines with SBOM generation
  - `app=thoughts-vibe-dashboard` - Show only this application's pipelines

In CLI:
```bash
# List pipeline runs with RHACS scanning
kubectl get pipelinerun -l security-scan=rhacs

# List pipeline runs with SBOM generation
kubectl get pipelinerun -l sbom-generation=enabled

# List all runs for this application
kubectl get pipelinerun -l app=thoughts-vibe-dashboard

# Combine multiple labels
kubectl get pipelinerun -l app=thoughts-vibe-dashboard,security-scan=rhacs
```

**Benefits:**
- ✅ Easy to find security-scanned builds in console
- ✅ Filter pipelines by application
- ✅ Track SBOM generation status
- ✅ Integrate with monitoring and alerting
- ✅ Support GitOps workflows with label selectors

## Run Pipeline Again

Create a new PipelineRun:

```bash
cat <<EOF | kubectl apply -f -
apiVersion: tekton.dev/v1beta1
kind: PipelineRun
metadata:
  generateName: build-containerfile-run-
spec:
  pipelineRef:
    name: build-containerfile-pipeline
  params:
    - name: git-url
      value: https://github.com/devabm26/intern-use-case-demo.git
    - name: git-revision
      value: main
    - name: image-name
      value: quay.io/redhat_na_ssa/thoughts-vibe-dashboard:v1.0
  workspaces:
    - name: shared-data
      persistentVolumeClaim:
        claimName: shared-workspace-pvc
    - name: dockerconfig
      secret:
        secretName: quay-auth-secret
    - name: trustification-secret
      secret:
        secretName: trustification-secret
EOF
```

## Pipeline Workspaces

The pipeline uses four workspaces:

1. **shared-data** (PVC)
   - Stores source code and build artifacts
   - Shared across all tasks
   - Persisted between pipeline runs

2. **dockerconfig** (Secret: `quay-auth-secret`)
   - Registry authentication credentials
   - Used by buildah to push images
   - Used by syft to pull images for scanning

3. **rhacs-secret** (Secret: `rhacs-secret`)
   - RHACS Central endpoint and API token
   - Used for image vulnerability scanning and policy checks
   - Requires "Continuous Integration" role in RHACS

4. **trustification-secret** (Secret: `trustification-secret`)
   - Bombastic API and OIDC credentials
   - Used for SBOM upload to RHTPA

## Pipeline Steps

1. **fetch-repository**
   - Clones the git repository
   - Uses: `git-clone` ClusterTask
   - Output: Source code in shared workspace

2. **build-image**
   - Builds container image from Containerfile
   - Uses: `buildah` ClusterTask
   - Authenticates with registry via dockerconfig workspace
   - Storage driver: VFS (works in unprivileged mode)
   - Output: Container image pushed to registry

3. **scan-image-rhacs**
   - Scans container image for vulnerabilities and policy violations
   - Uses: Red Hat Advanced Cluster Security (RHACS) `roxctl` CLI
   - Authenticates with RHACS Central using rhacs-secret
   - Performs two checks:
     - **Image Scan**: Detects CVEs in image layers and packages
     - **Policy Check**: Validates against RHACS security policies
   - Reports: Critical, High, Medium, Low severity findings
   - Output: Scan results displayed in pipeline logs
   - **Note:** Can optionally block builds with critical violations (disabled by default)

4. **generate-sbom**
   - Generates Software Bill of Materials (SBOM)
   - Uses: `syft` to scan container image from registry
   - Authenticates with registry using dockerconfig workspace
   - Format: SPDX 2.3 JSON (required by Bombastic API)
   - Post-processing: Deduplicates license references to fix parser errors
   - Output: SBOM file saved to `/workspace/source/sbom.json`

5. **upload-sbom**
   - Attests SBOM to image using `cosign` (keyless mode)
   - Authenticates with OIDC to obtain access token
   - Uploads SBOM to RHTPA Bombastic API
   - Uses: trustification-secret for credentials
   - Output: SBOM uploaded to Trustification platform
   - **Note:** RHTPA performs vulnerability matching server-side against VEX database

## Troubleshooting

### Pipeline Fails with "ClusterTask not found"

Install the required ClusterTasks:
```bash
kubectl apply -f https://raw.githubusercontent.com/tektoncd/catalog/main/task/git-clone/0.9/git-clone.yaml
kubectl apply -f https://raw.githubusercontent.com/tektoncd/catalog/main/task/buildah/0.6/buildah.yaml
```

### Build Fails with Permission Errors

The pipeline uses `vfs` storage driver which works in unprivileged mode. If you still get errors, you may need to:
- Check SecurityContextConstraints (OpenShift)
- Ensure the buildah task has proper permissions

### SBOM Generation Fails with UNAUTHORIZED

If syft fails to scan the image with registry authentication errors:
```
failed to get image descriptor from registry: UNAUTHORIZED
```

This means syft can't pull the image from the registry. The pipeline is configured to:
- Mount the `dockerconfig` workspace (same as build-image task uses)
- Copy registry credentials to `~/.docker/config.json` for syft to use

**Verify:**
```bash
# Check that quay-auth-secret exists and is valid
kubectl get secret quay-auth-secret

# Check the secret has the right format
kubectl get secret quay-auth-secret -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d
```

The secret should contain authentication for `quay.io`.

### SBOM Upload Fails

If the `upload-sbom` task fails but you want to keep the generated SBOM:

```bash
# The SBOM is still available in the workspace PVC
# You can access it from another pod or manually upload it

# Create a debug pod to access the workspace
kubectl run -it --rm debug-sbom \
  --image=registry.access.redhat.com/ubi9/ubi-minimal \
  --overrides='
  {
    "spec": {
      "containers": [{
        "name": "debug-sbom",
        "image": "registry.access.redhat.com/ubi9/ubi-minimal",
        "command": ["sleep", "3600"],
        "volumeMounts": [{
          "name": "workspace",
          "mountPath": "/workspace"
        }]
      }],
      "volumes": [{
        "name": "workspace",
        "persistentVolumeClaim": {
          "claimName": "shared-workspace-pvc"
        }
      }]
    }
  }' -- bash

# Inside the pod:
cat /workspace/sbom.json
```

### RHACS Image Scan Fails

If the `scan-image-rhacs` task fails with authentication errors:

**Error: "Failed to download roxctl CLI" or "Failed to authenticate with RHACS Central"**

```bash
# Verify the rhacs-secret exists and has correct keys
kubectl get secret rhacs-secret

# Check secret has required keys
kubectl get secret rhacs-secret -o jsonpath='{.data}' | jq 'keys'
# Should show: ["rox_api_token", "rox_central_endpoint"]

# Verify RHACS Central endpoint is accessible
ROX_CENTRAL=$(kubectl get secret rhacs-secret -o jsonpath='{.data.rox_central_endpoint}' | base64 -d)
echo "Endpoint: $ROX_CENTRAL"

# Test connectivity (add https:// if not already present)
if [[ "$ROX_CENTRAL" == https://* ]]; then
  curl -k ${ROX_CENTRAL}/v1/ping
else
  curl -k https://${ROX_CENTRAL}/v1/ping
fi
```

**Error: "missing port in address"**

```
ERROR: could not get endpoint: invalid arguments: address central-stackrox.apps.cluster.example.com: missing port in address
```

This occurs when the endpoint doesn't include a port number. RHACS gRPC connections require a port.

**Fix:** The pipeline now automatically adds `:443` if no port is present. If you see this error with an older version of the pipeline, update your secret:

```bash
# Add :443 to the endpoint
kubectl create secret generic rhacs-secret \
  --from-literal=rox_central_endpoint=central-stackrox.apps.cluster-xxxx.example.com:443 \
  --from-literal=rox_api_token=your-api-token \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Error: Results showing as "-" (dash) in OpenShift Console**

If the pipeline runs successfully but results show as "-" in the OpenShift Console Results tab:

```
CRITICAL_CVES: -
HIGH_CVES: -
MEDIUM_CVES: -
```

This indicates the results aren't being propagated from the task to the pipeline level.

**Diagnosis:**

Run the diagnostic script to check Tekton version and result propagation:

```bash
./check-tekton-version.sh
```

**Common causes:**

1. **Tekton Pipelines version incompatibility**
   - Some older Tekton versions don't support inline `taskSpec` results properly
   - Results from inline tasks may not propagate to pipeline results

2. **Result files not being created**
   - Check the task logs for the "Final verification of all result files" section
   - Should show files like: `CRITICAL_CVSS_COUNT: '2'`

3. **TaskRun results exist but Pipeline results don't**
   - TaskRun has results: ✅ Task wrote results correctly
   - PipelineRun missing results: ❌ Pipeline not referencing task results

**Fix Option 1: Verify debug output**

After applying the latest pipeline, check task logs for:
```
DEBUG: Scan results file exists, checking structure...
DEBUG: Writing CVE counts to /tekton/results/
DEBUG: Verifying written results:
  CRITICAL_CVSS_COUNT: 2
  HIGH_CVSS_COUNT: 11

Final verification of all result files:
  CRITICAL_CVSS_COUNT: '2'
  HIGH_CVSS_COUNT: '11'
  ...
```

If these show correct values but OpenShift Console shows "-", it's a result propagation issue.

**Fix Option 2: Check Tekton version compatibility**

```bash
# Check OpenShift Pipelines version
kubectl get csv -n openshift-operators | grep pipelines

# Expected: Red Hat OpenShift Pipelines 1.12+ or newer
```

If using an older version, results from inline taskSpec might not propagate. You may need to:
- Upgrade OpenShift Pipelines operator
- Or convert inline taskSpec to a separate Task resource

**Fix Option 3: Verify TaskRun and PipelineRun results**

```bash
# Get latest pipeline run
PIPELINERUN=$(kubectl get pipelinerun -l app=thoughts-vibe-dashboard --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')

# Check TaskRun results (should have values)
kubectl get pipelinerun $PIPELINERUN -o json | \
  jq -r '.status.childReferences[] | select(.pipelineTaskName == "scan-image-rhacs") | .name' | \
  xargs -I {} kubectl get taskrun {} -o json | \
  jq -r '.status.results[]? | "  \(.name): \(.value)"'

# Check Pipeline results (should reference task results)
kubectl get pipelinerun $PIPELINERUN -o json | \
  jq -r '.status.results[]? | "  \(.name): \(.value)"'
```

**Expected output:**
```
TaskRun results:
  CRITICAL_CVSS_COUNT: 2
  HIGH_CVSS_COUNT: 11
  ...

Pipeline results:
  CRITICAL_CVES: 2
  HIGH_CVES: 11
  ...
```

If TaskRun results exist but Pipeline results are empty, the issue is with result propagation.

**Error: "Termination message is above max allowed size 4096"**

```
Error while handling results: Termination message is above max allowed size 4096, 
caused by large task result.
```

This occurs when task results exceed Tekton's 4096 byte limit. This can happen if the RHACS scan output is too large.

**Fix:** The pipeline has been updated to store only metric counts (not full JSON output) as results:
- ✅ Stored as results: CVE counts, policy violation counts (small, always fits)
- ❌ NOT stored as results: Full scan JSON (too large)
- ✅ Available in logs: Full scan output, detailed CVE information

**To view full scan details:**
```bash
# View scan-image-rhacs task logs (contains full output)
tkn pipelinerun logs build-containerfile-run -t scan-image-rhacs

# Or in OpenShift Console:
# Pipelines → build-containerfile-run → Logs → scan-image-rhacs
```

**Error: "jq: error: Cannot iterate over null"**

```
jq: error (at <stdin>:75): Cannot iterate over null (null)
```

This occurs when parsing RHACS policy check results that have no violations (`.alerts` is null).

**Fix:** The pipeline has been updated with null-safe jq parsing:
```bash
# Old (fails on null):
jq '[.alerts[] | select(...)]'

# New (null-safe):
jq '[.alerts // [] | .[] | select(...)]'
```

The `// []` operator means "use empty array if alerts is null".

**Error: "unsupported output format used"**

```
ERROR: could not create printer for image scan result: unsupported output format used: "/tmp/scan-results.json"
```

This is a roxctl CLI version issue. The newer roxctl uses `-o format` instead of `--format format --output file`.

**Fix:** The pipeline has been updated to use the new roxctl syntax:
- Old: `--format json --output /tmp/file.json`
- New: `-o json > /tmp/file.json`

**Supported endpoint formats:**

The pipeline accepts and normalizes these formats:
- ✅ `central-stackrox.apps.cluster.example.com:443` (recommended - hostname:port)
- ✅ `central.stackrox.svc:443` (internal cluster service)
- ✅ `https://central-stackrox.apps.cluster.example.com` (auto-adds `:443`)
- ✅ `central-stackrox.apps.cluster.example.com` (auto-adds `:443`)

The pipeline automatically:
1. Removes `https://` protocol if present
2. Adds `:443` port if missing
3. Uses normalized endpoint for all roxctl commands

**Fix: Regenerate API Token**

1. Login to RHACS Central Console
2. Go to **Platform Configuration → Integrations**
3. Scroll to **Authentication Tokens** → **API Token**
4. Click **Generate Token**
5. Name: `tekton-pipeline`
6. Role: **Continuous Integration** (required for image scanning)
7. Copy token and update secret:
   ```bash
   kubectl create secret generic rhacs-secret \
     --from-literal=rox_central_endpoint=central.stackrox.svc:443 \
     --from-literal=rox_api_token=<new-token> \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

**Error: "Could not depsolve transaction; problem with curl-minimal"**

This occurs when trying to install the full `curl` package in UBI minimal images:

```
error: Could not depsolve transaction; 1 problem detected:
 Problem: problem with installed package curl-minimal-7.76.1-40.el9.x86_64
  - package curl-minimal-7.76.1-40.el9.x86_64 from @System conflicts with curl
```

**Fix:** The pipeline has been updated to skip installing `curl` since `curl-minimal` is already present in the UBI base image and provides the same functionality. If you see this error:

```bash
# Verify the pipeline uses this package list (without curl):
grep "microdnf install" tekton-pipeline.yaml
# Should show: microdnf install -y tar gzip jq

# curl-minimal is already available:
kubectl run test --rm -it --image=registry.access.redhat.com/ubi9/ubi-minimal:latest -- curl --version
```

**Error: "Policy check failed with X violations"**

This is expected behavior when RHACS detects security issues:

```bash
# View the pipeline logs to see specific violations
tkn pipelinerun logs build-containerfile-run -t scan-image-rhacs

# Example output:
# ❌ Fixable Severity at least Important (CRITICAL_SEVERITY)
# ❌ Red Hat Package Manager in Image (HIGH_SEVERITY)
# ❌ Ubuntu Package Manager in Image (HIGH_SEVERITY)
```

**To block builds on critical violations:**

Uncomment these lines in the pipeline YAML:

```yaml
# Optional: Fail build if critical violations found (commented out by default)
# if [ "$CRITICAL_COUNT" -gt 0 ]; then
#   echo ""
#   echo "❌ Build blocked: $CRITICAL_COUNT critical policy violations found"
#   exit 1
# fi
```

**Understanding RHACS Scan Results:**

| Severity | Description | Action |
|----------|-------------|--------|
| CRITICAL | Remote code execution, privilege escalation | Block deployment |
| HIGH | Significant vulnerabilities, insecure configs | Review and fix |
| MEDIUM | Moderate risk issues | Review if time permits |
| LOW | Minor issues, informational | Optional review |

**View detailed scan results in RHACS Console:**

1. Login to RHACS Central
2. Go to **Vulnerability Management → Images**
3. Search for your image: `quay.io/redhat_na_ssa/thoughts-vibe-dashboard:latest`
4. Click image to see:
   - All CVEs with CVSS scores
   - Fixable vs unfixable vulnerabilities
   - Component details (OS packages, language libraries)
   - Policy violations

**Common Policy Violations:**

| Policy | Why It Triggers | How to Fix |
|--------|----------------|------------|
| Fixable Severity at least Important | Image has CVEs with fixes available | Update base image or rebuild |
| Ubuntu/Debian Package Manager | Using non-Red Hat base image | Use Red Hat UBI base images |
| Red Hat Package Manager Execution | Image runs yum/dnf commands | Use multi-stage build, cleanup in same layer |
| No resource requests or limits | Deployment missing resource constraints | Add to deployment YAML |
| Latest tag | Using `:latest` instead of digest | Use specific version tags or SHA digests |

**Disable RHACS scan for testing:**

If you want to skip RHACS scanning temporarily:

```bash
# Comment out the scan task in tekton-pipeline.yaml
# Or create a separate pipeline without the scan-image-rhacs task
```

### Clean Up Old SBOMs

Delete old SBOMs from Bombastic to save space:

```bash
# Get credentials from secret
export BOMBASTIC_API_URL=$(kubectl get secret trustification-secret -o jsonpath='{.data.bombastic_api_url}' | base64 -d)
export OIDC_ISSUER_URL=$(kubectl get secret trustification-secret -o jsonpath='{.data.oidc_issuer_url}' | base64 -d)
export OIDC_CLIENT_ID=$(kubectl get secret trustification-secret -o jsonpath='{.data.oidc_client_id}' | base64 -d)
export OIDC_CLIENT_SECRET=$(kubectl get secret trustification-secret -o jsonpath='{.data.oidc_client_secret}' | base64 -d)

# Get access token
ACCESS_TOKEN=$(curl -s -X POST "${OIDC_ISSUER_URL}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=${OIDC_CLIENT_ID}" \
  -d "client_secret=${OIDC_CLIENT_SECRET}" | jq -r '.access_token')

# List all SBOMs for an image
curl -s -X GET "${BOMBASTIC_API_URL}/api/v1/sbom" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | \
  jq -r '.[] | select(.id | startswith("thoughts-vibe-dashboard-")) | .id' | sort

# Delete specific SBOM by ID
SBOM_ID="thoughts-vibe-dashboard-20260615-142530-a7b3f9e2"
curl -X DELETE "${BOMBASTIC_API_URL}/api/v1/sbom?id=${SBOM_ID}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -w "\nHTTP Status: %{http_code}\n"

# Delete all SBOMs older than a specific date (e.g., before June 14, 2026)
curl -s -X GET "${BOMBASTIC_API_URL}/api/v1/sbom" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | \
  jq -r '.[] | select(.id | startswith("thoughts-vibe-dashboard-")) | select(.id | contains("-202606") | not) | .id' | \
  while read SBOM_ID; do
    echo "Deleting old SBOM: $SBOM_ID"
    curl -X DELETE "${BOMBASTIC_API_URL}/api/v1/sbom?id=${SBOM_ID}" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}"
    sleep 1
  done
```

### Skip SBOM Upload for Testing

To run the pipeline without uploading to Bombastic (useful for testing):

You can't skip individual tasks in Tekton, but you can:
1. Comment out the `upload-sbom` task in the pipeline definition
2. Or modify the upload task to skip on certain conditions
3. Or create a separate pipeline without the upload step

### View Vulnerability Data in RHTPA

Vulnerability data is available in the RHTPA web interface after SBOM upload:

1. **Access RHTPA Dashboard:**
   ```
   https://sbom-trusted-profile-analyzer.apps.<your-cluster>.com
   ```

2. **Search for your SBOM:**
   - Use the SBOM ID from pipeline logs
   - Or search by image name/component

3. **View Dependency Report:**
   - RHTPA matches SBOM against VEX database
   - Shows CVEs for each component
   - Displays severity, CVSS scores, remediation

**Note:** Vulnerability matching happens **server-side** in RHTPA:
- No need to scan in pipeline
- RHTPA uses Vexination (VEX database) for vulnerability data
- Updates automatically as new CVEs are published

### Bombastic Dependency Report Parse Errors

If Bombastic reports "Object URI already exists" or similar parse errors:

**Issue:** Syft sometimes generates duplicate license references in SPDX output

**Solution:** The pipeline includes automatic deduplication:
- Groups `hasExtractedLicensingInfos` by `licenseId`
- Removes duplicates before upload
- Logs how many duplicates were removed

**Verify the fix worked:**
```bash
# Check the pipeline logs for deduplication message
tkn pipelinerun logs <run-name> -t generate-sbom

# Look for:
# "License refs: X (removed Y duplicates)"
```

**Manual verification:**
```bash
# Extract SBOM from workspace and check for duplicates
cat sbom.json | jq '.hasExtractedLicensingInfos | group_by(.licenseId) | map(select(length > 1))'

# Should return empty array: []
```

### View Logs

```bash
# View logs for a specific task
tkn pipelinerun logs build-containerfile-run -t fetch-repository
tkn pipelinerun logs build-containerfile-run -t generate-sbom
tkn pipelinerun logs build-containerfile-run -t upload-sbom

# View all logs
tkn pipelinerun logs build-containerfile-run -f

# Get the SBOM ID from upload-sbom logs
tkn pipelinerun logs build-containerfile-run -t upload-sbom | grep "SBOM ID:"
# Output: Generated unique SBOM ID: thoughts-vibe-dashboard-20260615-142530-a7b3f9e2
```

### Delete and Retry

```bash
# Delete the pipeline run
kubectl delete pipelinerun build-containerfile-run

# Reapply
kubectl apply -f tekton-pipeline.yaml
```

## Registry Authentication

The pipeline is already configured to use the `quay-auth-secret` for pushing images to Quay.io.

**What's configured:**
- ✅ Secret workspace: `dockerconfig` → `quay-auth-secret`
- ✅ TLS verification enabled
- ✅ Retry on push failures (3 attempts)

**Verify the secret exists:**
```bash
kubectl get secret quay-auth-secret
```

**Image will be pushed to:**
```
quay.io/redhat_na_ssa/thoughts-vibe-dashboard:latest
```

**Change the image repository** by updating the `image-name` parameter in the PipelineRun.

## Why SBOM Shows Zero Vulnerabilities in Bombastic

**Important:** An SBOM (Software Bill of Materials) is a **component inventory**, not a vulnerability report.

**What SBOM contains:**
- ✅ List of all software packages in the image
- ✅ Package versions
- ✅ License information
- ✅ Dependencies

**What SBOM does NOT contain:**
- ❌ Vulnerability information (CVEs)
- ❌ Security advisories
- ❌ Exploit data

**How RHTPA/Trustification Works:**

RHTPA performs vulnerability matching **server-side** against its VEX (Vulnerability Exploitability eXchange) database:

1. **Pipeline uploads SBOM** → Bombastic API stores the component list
2. **RHTPA matches components** → Against Vexination (VEX database)
3. **Dependency report shows vulnerabilities** → Based on VEX data

**Why you might see zero vulnerabilities:**
- ✅ VEX database may not have data for your components yet
- ✅ Components may genuinely have no known CVEs
- ✅ VEX data needs to be uploaded separately (by security team)
- ✅ Matching happens asynchronously after SBOM upload

**To populate vulnerability data:**
- Upload VEX documents to RHTPA Vexination API
- Or wait for RHTPA to sync with upstream CVE databases
- Or use RHTPA's scanning features (if enabled)

## SBOM and RHTPA Configuration

The pipeline automatically generates SBOM (Software Bill of Materials) using Syft and uploads to RHTPA Bombastic API:

**Task 1: generate-sbom**
- ✅ Generates SBOM with Syft (SPDX 2.3 JSON format)
- ✅ Scans container image from registry
- ✅ Uses dockerconfig for registry authentication
- ✅ Deduplicates license references (fixes Bombastic parser errors)
- ✅ Saves SBOM to shared workspace

**Task 2: upload-sbom**
- ✅ Attests SBOM to image with cosign
- ✅ OIDC authentication with client credentials flow
- ✅ Generates unique SBOM ID: `<image-name>-<timestamp>-<random>`
- ✅ Uploads to Bombastic API with unique SBOM ID
- ✅ Uses existing `trustification-secret` for credentials
- ✅ RHTPA performs vulnerability matching server-side against VEX database

**Benefits of separate tasks:**
- Can retry SBOM upload without regenerating
- Can skip upload for testing/development
- Better visibility into which step fails
- Independent success/failure tracking
- Vulnerability matching happens server-side in RHTPA (no pipeline overhead)

**Authentication Flow:**
1. Pipeline loads OIDC credentials from secret
2. Exchanges client ID/secret for access token at OIDC issuer
3. Uses access token to authenticate with Bombastic API
4. Uploads SBOM to Bombastic

**Verify existing Trustification credentials:**

The pipeline uses the existing `trustification-secret`. Verify it has the required keys:
```bash
# Check secret exists
kubectl get secret trustification-secret

# View secret keys (not values)
kubectl get secret trustification-secret -o jsonpath='{.data}' | jq 'keys'
```

If you need to update the existing secret:
```bash
kubectl create secret generic trustification-secret \
  --from-literal=bombastic_api_url=https://sbom.trustification.dev \
  --from-literal=oidc_issuer_url=https://sso.redhat.com/auth/realms/redhat-external \
  --from-literal=oidc_client_id=your-client-id \
  --from-literal=oidc_client_secret=your-client-secret \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Required credentials (case-sensitive lowercase keys):**
- **bombastic_api_url**: Bombastic API endpoint (e.g., https://sbom.trustification.dev)
- **oidc_issuer_url**: OIDC provider URL (e.g., https://sso.redhat.com/auth/realms/chicken)
- **oidc_client_id**: OAuth2 client ID
- **oidc_client_secret**: OAuth2 client secret

**SBOM output:**
- **Format:** SPDX 2.3 JSON (required by Bombastic - also accepts SPDX 2.2)
- **Location:** Saved to `/workspace/source/sbom.json` in shared-data workspace
- **Attestation:** Attached to container image with cosign
- **Upload:** Sent to Bombastic API via OIDC-authenticated request with unique ID
- **Persistence:** Available in PVC until next pipeline run overwrites it
- **Version verification:** Pipeline verifies SPDX version after generation

## SBOM ID Format

Each SBOM uploaded to Bombastic gets a unique identifier:

**Format:** `<image-name>-<timestamp>-<random-suffix>`

**Example:** `thoughts-vibe-dashboard-20260615-142530-a7b3f9e2`

**Components:**
- **image-name**: Base image name (without registry/tag)
- **timestamp**: UTC timestamp in `YYYYMMDD-HHMMSS` format
- **random-suffix**: 8-character random alphanumeric string

**Benefits:**
- ✅ Unique across all pipeline runs
- ✅ Sortable by time (timestamp in name)
- ✅ Human-readable (includes image name)
- ✅ Collision-resistant (random suffix)

**Track SBOMs:**
```bash
# List all SBOMs for an image
curl -X GET "${BOMBASTIC_API_URL}/api/v1/sbom?query=thoughts-vibe-dashboard" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | jq -r '.[] | .id'

# Find SBOMs created on a specific date
curl -X GET "${BOMBASTIC_API_URL}/api/v1/sbom" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | \
  jq -r '.[] | select(.id | contains("20260615")) | .id'
```

**Test OIDC authentication:**
```bash
# Get access token
curl -X POST "https://your-oidc-issuer/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=your-client-id" \
  -d "client_secret=your-client-secret"
```

## Common Bombastic/RHTPA Endpoints

**Red Hat Trustification (Production):**
- Bombastic API: `https://sbom.trustification.dev`
- OIDC Issuer: `https://sso.redhat.com/auth/realms/redhat-external`

**Red Hat Trustification (Staging):**
- Bombastic API: `https://sbom.staging.trustification.dev`
- OIDC Issuer: `https://sso.stage.redhat.com/auth/realms/redhat-external`

**Self-Hosted:**
- Check with your RHTPA administrator for endpoints

## Verify SBOM Upload

After pipeline runs, verify SBOM was uploaded:

```bash
# Get access token
TOKEN=$(curl -s -X POST "${OIDC_ISSUER_URL}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=${OIDC_CLIENT_ID}" \
  -d "client_secret=${OIDC_CLIENT_SECRET}" | jq -r '.access_token')

# Query Bombastic API
curl -X GET "${BOMBASTIC_API_URL}/api/v1/sbom" \
  -H "Authorization: Bearer ${TOKEN}"
```

## Understanding Vulnerability Results

### Pipeline Results Explained

The pipeline exports several results that are visible in OpenShift Console:

**CVE Counts (from RHACS Image Scan):**
- `CRITICAL_CVES` - CVEs with CVSS score 9.0-10.0
- `HIGH_CVES` - CVEs with CVSS score 7.0-8.9
- `MEDIUM_CVES` - CVEs with CVSS score 4.0-6.9
- `LOW_CVES` - CVEs with CVSS score 0.1-3.9

**Policy Violations (from RHACS Policy Check):**
- `POLICY_VIOLATIONS` - Total violations of RHACS security policies
- `CRITICAL_VIOLATIONS` - Violations requiring immediate action
- Examples:
  - Privileged containers
  - Containers running as root
  - Using latest image tag
  - Missing resource limits
  - Fixable critical CVEs

### Viewing Results Across Multiple Runs

**Compare vulnerability trends:**
```bash
# Get CVE counts from last 5 pipeline runs
kubectl get pipelinerun -l app=thoughts-vibe-dashboard \
  --sort-by=.metadata.creationTimestamp \
  -o json | jq -r '
  .items[-5:] | .[] | 
  {
    name: .metadata.name,
    created: .metadata.creationTimestamp,
    critical: (.status.pipelineResults[] | select(.name=="CRITICAL_CVES") | .value),
    high: (.status.pipelineResults[] | select(.name=="HIGH_CVES") | .value),
    violations: (.status.pipelineResults[] | select(.name=="POLICY_VIOLATIONS") | .value)
  }'
```

**Track vulnerability remediation:**
```bash
# Compare current run vs previous run
CURRENT=$(kubectl get pipelinerun build-containerfile-run -o json | \
  jq -r '.status.pipelineResults[] | select(.name=="CRITICAL_CVES") | .value')

PREVIOUS=$(kubectl get pipelinerun -l app=thoughts-vibe-dashboard \
  --sort-by=.metadata.creationTimestamp -o json | \
  jq -r '.items[-2].status.pipelineResults[] | select(.name=="CRITICAL_CVES") | .value')

echo "Critical CVEs: $PREVIOUS → $CURRENT"
```

### Integration with OpenShift Security Features

**1. OpenShift Container Security Operator:**

If you have the Container Security Operator installed, you can correlate pipeline results with cluster-wide vulnerability reports:

```bash
# View image vulnerabilities from Container Security Operator
kubectl get imagemanifestvuln -n thoughts-app

# Compare with pipeline results
tkn pipelinerun describe build-containerfile-run | grep CVE
```

**2. OpenShift Compliance Operator:**

Pipeline results can inform compliance posture:
- Track CVE remediation progress
- Enforce security baselines
- Generate compliance reports

**3. RHACS Integration:**

The pipeline integrates directly with RHACS:
- Scan results visible in RHACS Console
- Policy violations tracked over time
- Deployment blocking based on scan results

### Setting Up Alerts

**Prometheus Alerts for High Vulnerability Counts:**

Create a PrometheusRule to alert on high CVE counts:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: pipeline-vulnerability-alerts
  namespace: thoughts-app
spec:
  groups:
  - name: pipeline-security
    interval: 30s
    rules:
    - alert: CriticalCVEsFound
      expr: |
        kube_tekton_pipelinerun_result{name="CRITICAL_CVES"} > 0
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "Critical CVEs found in pipeline run"
        description: "Pipeline {{ $labels.pipelinerun }} found {{ $value }} critical CVEs"
    
    - alert: HighPolicyViolations
      expr: |
        kube_tekton_pipelinerun_result{name="CRITICAL_VIOLATIONS"} > 0
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "Critical policy violations found"
        description: "Pipeline {{ $labels.pipelinerun }} has {{ $value }} critical violations"
```

**Slack/Email Notifications:**

Use Tekton EventListeners to send notifications when vulnerabilities are found:

```yaml
apiVersion: triggers.tekton.dev/v1beta1
kind: EventListener
metadata:
  name: vulnerability-notifier
spec:
  triggers:
  - name: high-cve-notification
    interceptors:
    - cel:
        filter: |
          body.pipelineRun.status.pipelineResults.exists(r, 
            r.name == "CRITICAL_CVES" && int(r.value) > 0)
    bindings:
    - ref: send-slack-notification
    template:
      ref: slack-notification-template
```

### Dashboard Visualization

**Grafana Dashboard for Pipeline Metrics:**

Import pipeline results into Grafana to track:
- CVE trends over time
- Policy violation history
- Scan success/failure rates
- Time to remediate vulnerabilities

**Example PromQL queries:**
```promql
# Critical CVEs over time
kube_tekton_pipelinerun_result{name="CRITICAL_CVES"}

# Total CVEs by severity
sum(kube_tekton_pipelinerun_result{name=~".*_CVES"}) by (name)

# Pipeline success rate
rate(kube_tekton_pipelinerun_status{status="Succeeded"}[1h])
```

### Best Practices

**1. Set Security Gates:**

Uncomment the build-blocking code in the pipeline to fail builds with critical vulnerabilities:
```yaml
if [ "$CRITICAL_COUNT" -gt 0 ]; then
  echo "❌ Build blocked: $CRITICAL_COUNT critical policy violations found"
  exit 1
fi
```

**2. Regular Baseline Scans:**

Run the pipeline on a schedule to track vulnerability drift:
```yaml
apiVersion: tekton.dev/v1beta1
kind: TriggerTemplate
metadata:
  name: scheduled-scan
spec:
  resourcetemplates:
  - apiVersion: tekton.dev/v1beta1
    kind: PipelineRun
    metadata:
      generateName: scheduled-scan-
      labels:
        scan-type: baseline
```

**3. Correlate with SBOM:**

Use SBOM results from Trustification to understand:
- Which components have CVEs
- Dependency chain vulnerabilities
- License compliance issues

**4. Track Remediation:**

Monitor vulnerability counts across pipeline runs to ensure:
- Critical CVEs are fixed quickly
- High CVEs are addressed in sprint cycles
- Vulnerability debt doesn't accumulate

## Next Steps

- Add VEX (Vulnerability Exploitability eXchange) generation and upload to Vexination
- Add signing with cosign keyless mode (currently skipped if no keys)
- Add notifications (Slack, email) on SBOM upload
- Implement GitOps deployment after build (ArgoCD/Flux)
- Integrate RHTPA policy enforcement via webhook (block builds with CRITICAL CVEs)
- Add SBOM quality checks (completeness, accuracy validation)

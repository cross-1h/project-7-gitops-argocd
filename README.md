# Project 7: GitOps Delivery with ArgoCD

In every project so far, your pipeline deployed by pushing into the cluster. In this one, it stops.
You will move to **GitOps**: git becomes the single source of truth for what should be running, and
ArgoCD, living inside the cluster, continuously makes reality match git.

**Read `PRIMER.md` first.** GitOps is a genuinely new idea and the tooling makes no sense until the
idea does. `architecture.svg` shows the shape: notice there is no arrow from Jenkins to the cluster.

You will reuse the ShopFlow system from Project 6, so there is no new application to learn. The only
thing that changes is how it gets deployed, which is exactly the lesson.

---

## Prerequisites

- Project 6 Phase 1 is working: the EKS cluster, RDS, SQS, ECR images, and the AWS Load Balancer
  Controller all exist, and you can place an order.
- `kubectl` and `helm` installed, and your kubeconfig points at the cluster.
- A GitHub account where you can create a second, separate repository.

Cost warning: the cluster, database, and load balancer bill by the hour. ArgoCD itself is cheap, but
the platform under it is not. Tear down when you finish (see Cleanup).

---

## What is in this folder

```
PRIMER.md                read this first
architecture.svg         the push-to-pull picture (the core idea)
aws-architecture.png     the full AWS architecture for this project
COMMANDS.md              the ArgoCD CLI and operations lab (do this after Step 5)
argocd/                  the ArgoCD Application definitions
gitops-repo/             the manifests that become YOUR GitOps repository
Jenkinsfile.gitops       the pipeline that commits instead of deploying
ASSIGNMENT.md            what to submit
```

---

## Step 1: Install ArgoCD in the cluster

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl get pods -n argocd -w      # wait until all pods are Running
```

Get the admin password and open the UI:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo

kubectl port-forward svc/argocd-server -n argocd 8090:443
```

Open `https://localhost:8090` (accept the certificate warning) and log in as `admin`.
The UI will be empty — that is correct. ArgoCD does not know about anything yet.

---

### Issues Encountered in Step 1

#### Issue 1 — ArgoCD pods not fully ready

**What happened:**
After running the installation command, the pods did not all come up cleanly. One controller pod kept
restarting and showing errors during startup.

**Root cause:**
The ApplicationSet Custom Resource Definition (CRD) was not fully established before the
ApplicationSet controller tried to start. The controller crashed because the resource type it manages
did not yet exist in the cluster's API.

**Fix:**
Re-apply the installation manifest using server-side apply with `--force-conflicts`, which safely
reconciles all CRD objects, then explicitly wait for the CRD to reach `Established` state before
proceeding.

```bash
kubectl apply --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

kubectl wait --for=condition=Established crd/applicationsets.argoproj.io --timeout=180s
```

**Verification:**
```bash
kubectl get pods -n argocd                   # all controllers should be Running
kubectl get crd applicationsets.argoproj.io  # should show ESTABLISHED=True
```

---

#### Issue 2 — ApplicationSet controller continued crash-looping

**What happened:**
Even after the initial pods appeared Running, the ApplicationSet controller kept restarting with
errors stating it could not find the ApplicationSet resource in the cluster.

**Root cause:**
Same underlying cause as Issue 1 — the CRD registration race. The controller started before the CRD
was fully registered, and the previous apply had not fully resolved this.

**Fix:**
The same server-side apply command from Issue 1 resolved both issues together. After the
`kubectl wait` completed, the controller stabilised permanently.

```bash
kubectl apply --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

kubectl wait --for=condition=Established crd/applicationsets.argoproj.io --timeout=180s

kubectl get pods -n argocd   # confirm all pods Running and stable
```

---

## Step 2: Create your GitOps repository

This is the heart of the project. Create a **new, separate** GitHub repository (for example
`shopflow-gitops`). It holds only manifests — no application code.

Copy the `gitops-repo/` contents into it:

```bash
cp -r gitops-repo/* /path/to/your/shopflow-gitops/
cd /path/to/your/shopflow-gitops
```

Fill in your own values before the first commit:

- In `apps/shopflow/config.yaml`, set your RDS endpoint host.
- In each of `catalog.yaml`, `orders.yaml`, `notifications.yaml`, `storefront.yaml`, replace
  `REPLACE_REGISTRY` with your ECR registry URL (`<account>.dkr.ecr.<region>.amazonaws.com`).

Then push:

```bash
git init && git add . && git commit -m "initial desired state"
git branch -M main
git remote add origin https://github.com/<you>/shopflow-gitops.git
git push -u origin main
```

---

### Issues Encountered in Step 2

#### Issue 3 — GitOps repository setup required careful initialisation

**What happened:**
The manifests in `gitops-repo/` contained placeholder values (`REPLACE_REGISTRY` and a template RDS
host). Pushing these placeholders without replacement would cause ArgoCD to attempt deploying
workloads pointing at non-existent image tags and database endpoints.

**Resolution:**
All placeholder values were replaced before the first commit. Only after all replacements were
confirmed was the repository initialised, committed, and pushed.

```bash
mkdir -p ~/shopflow-gitops
cp -r /path/to/project-7-gitops-argocd/gitops-repo/* ~/shopflow-gitops/

# Edit apps/shopflow/config.yaml — set SPRING_DATASOURCE_URL to actual RDS host
# Edit catalog.yaml, orders.yaml, notifications.yaml, storefront.yaml
#   Replace REPLACE_REGISTRY with: <account>.dkr.ecr.us-east-1.amazonaws.com

cd ~/shopflow-gitops
git init
git add .
git commit -m "initial desired state"
```

**Verification:**
```bash
git status   # should show nothing uncommitted
```

---

#### Issue 4 — Environment-specific config values needed before first push

**What happened:**
The `config.yaml` file required the actual RDS endpoint hostname from the Terraform output. Without
this, all backend pods would fail to connect to the database immediately after ArgoCD first synced.

**Resolution:**
Retrieved the RDS endpoint from Terraform output and set it directly in `config.yaml` before
committing. No shell scripting was required — direct file edit was used to ensure accuracy.

```bash
cd infra
terraform output rds_endpoint   # copy the host part (before :5432)

# Set SPRING_DATASOURCE_URL in apps/shopflow/config.yaml:
# jdbc:postgresql://<rds-host>:5432/shopflow
```

---

## Step 3: Carry over the database secret

ArgoCD manages what is in git, and your database password must **never** be in git. Create it
directly in the target namespace, once:

```bash
kubectl create namespace shopflow

kubectl -n shopflow create secret generic db-credentials \
  --from-literal=username=shopflow \
  --from-literal=password='YOUR_DB_PASSWORD'
```

> **Design note:** This is a real design question, not a footnote. Git is the source of truth for
> everything *except* secrets. Where secrets should live is one of the questions you must answer in
> your report.

---

### Issues Encountered in Step 3

#### Issue 5 — Namespace and secret must exist before ArgoCD first sync

**What happened:**
If the `shopflow` namespace or the `db-credentials` secret did not exist at the time ArgoCD first
synced, pods would fail immediately with `CreateContainerConfigError` because their env var
references to the secret could not be resolved.

**Resolution:**
Created the namespace and secret in the correct order — namespace first, secret immediately after —
and verified both existed before proceeding to Step 4.

```bash
kubectl create namespace shopflow

kubectl -n shopflow create secret generic db-credentials \
  --from-literal=username=shopflow \
  --from-literal=password='YOUR_DB_PASSWORD'

kubectl -n shopflow get secret db-credentials   # verify secret is present
```

---

## Step 4: Point ArgoCD at your repository

Edit `argocd/application-shopflow.yaml` and set `repoURL` to your GitOps repository. Then:

```bash
kubectl apply -f argocd/application-shopflow.yaml
```

Watch the UI. ArgoCD will find your repo, see the manifests, notice the cluster does not match, and
(because `automated` sync is on) apply them. Within a minute or two the app should go **Synced** and
**Healthy**.

```bash
kubectl get application shopflow -n argocd
kubectl get pods -n shopflow
```

You just deployed without running a single `kubectl apply` for the app. You committed, and the
cluster made itself match.

Confirm the store is reachable:

```bash
kubectl get ingress shopflow -n shopflow
```

---

### Issues Encountered in Step 4

#### Issue 6 — Initial sync showed Synced but Degraded (storefront port mismatch)

**What happened:**
Immediately after ArgoCD performed its first sync, the application status showed **Synced** (the
manifests were applied correctly) but **Degraded** (the workload health check was failing). The
storefront pods were Running but not Ready. The ArgoCD UI correctly distinguished between these two
independent states.

**What I first thought:**
I initially suspected an ingress or ALB routing problem.

**Root cause:**
The storefront container was listening on port **8080**, but the Deployment's `readinessProbe` and
the `Service.targetPort` were both pointing to port **80**. The readiness probe could never succeed
because it was hitting the wrong port.

**Why "Synced but Degraded" is not a contradiction:**
*Synced* means ArgoCD successfully applied the manifests as declared in Git — configuration
reconciliation succeeded. *Degraded* means the resulting workload is unhealthy at runtime. These are
independent concerns. A wrong port, a bad image tag, or a missing secret can all produce this
combination. Fixing it requires understanding the application failure, not the GitOps tooling.

**Fix:**
Updated the storefront manifest in the GitOps repository, committing the correction as a new desired
state. ArgoCD detected the new commit, applied the corrected manifest, and the pods became Ready.

```bash
# In apps/shopflow/storefront.yaml — change all three to port 8080:
#   spec.containers[0].ports[0].containerPort: 8080
#   spec.containers[0].readinessProbe.httpGet.port: 8080
#   Service.spec.ports[0].targetPort: 8080

git commit -am "fix storefront port alignment to 8080" && git push
```

**Verification:**
```bash
kubectl get pods -n shopflow                  # storefront pods should become Ready
kubectl get application shopflow -n argocd    # should return Synced + Healthy
```

---

## Step 5: Deploy by committing

Change something in git and watch the cluster follow. Edit `apps/shopflow/catalog.yaml` and change
`replicas: 2` to `replicas: 3`. Commit and push.

```bash
git commit -am "scale catalog to 3" && git push
kubectl get pods -n shopflow -w
```

A third catalog pod appears with nobody running a deploy. **That commit was the deploy.**

Roll it back the GitOps way:

```bash
git revert HEAD && git push
```

The pod goes away. Your deploy history and your rollback mechanism are just git.

---

### Issues Encountered in Step 5

#### Issue 7 — RDS connection exhaustion caused catalog CrashLoopBackOff

**What happened:**
While the replica scaling experiments were running, `catalog-service` pods began crashing with
`CrashLoopBackOff`. Pod logs showed JDBC connection failures; the PostgreSQL database was refusing
new connections because all connection slots were exhausted.

**What I first thought:**
I treated the first crash as an isolated pod restart and simply waited.

**Root cause:**
Multiple application pods were opening direct JDBC connections to the RDS instance simultaneously
during startup spikes. The small `db.t3.micro` instance hit its connection limit. Additionally, the
proxy IAM role trust policy was initially set to `rds-db.amazonaws.com` instead of the correct
`rds.amazonaws.com`, which prevented the proxy from authenticating.

**Fix:**
Added an AWS RDS Proxy to the Terraform configuration to pool and manage database connections.
A dedicated proxy security group, IAM role, and Secrets Manager secret were created. The IAM trust
policy was corrected.

```bash
cd infra
terraform plan -out=tfplan   # review all changes: proxy, SG, IAM role, Secrets Manager secret

TF_VAR_db_password='YOUR_DB_PASSWORD' terraform apply -auto-approve tfplan
```

**Verification:**
```bash
terraform output rds_proxy_endpoint   # note the proxy hostname for the next step
```

---

#### Issue 8 — GitOps config still pointing at the original RDS host

**What happened:**
After the RDS Proxy was created, the `config.yaml` in the GitOps repository still contained the
original direct RDS endpoint. ArgoCD kept deploying the old config, so the proxy infrastructure was
not being used by the application.

**Fix:**
Updated `SPRING_DATASOURCE_URL` in the GitOps config map to the new RDS Proxy endpoint, then
committed and pushed the change. ArgoCD detected the commit and applied the corrected config.

```bash
# In apps/shopflow/config.yaml — update SPRING_DATASOURCE_URL:
# jdbc:postgresql://<shopflow-db-proxy.proxy-...amazonaws.com>:5432/shopflow

git commit -am "route DB traffic through RDS Proxy" && git push
```

**Verification:**
```bash
kubectl get configmap shopflow-config -n shopflow -o yaml   # confirm proxy URL is live
kubectl get pods -n shopflow                                 # pods should stabilise
```

---

#### Issue 9 — RDS instance temporarily resized, then reverted

**What happened:**
As a short-term mitigation before the proxy was ready, the RDS instance was temporarily upgraded to
`db.t3.large` to ease connection pressure. Once the proxy was in place, the instance needed to be
returned to `db.t3.micro` to avoid unnecessary cost.

**Fix:**
Reverted `instance_class` in `infra/main.tf` from `db.t3.large` back to `db.t3.micro` and
re-applied. The proxy now absorbs connection spikes, so the instance no longer needed to be oversized.

```bash
# In infra/main.tf: instance_class = "db.t3.micro"

terraform plan -out=tfplan
TF_VAR_db_password='YOUR_DB_PASSWORD' terraform apply -auto-approve tfplan
```

---

#### Issue 10 — One catalog replica persisted in CrashLoopBackOff after proxy migration

**What happened:**
Even after the proxy was deployed and the config updated, one `catalog-service` replica continued
failing while the others recovered. The replica had already entered a crash cycle and was waiting
for proxy DNS and endpoint propagation to complete.

**Fix:**
Verified the `shopflow-config` ConfigMap and `db-credentials` Secret both contained correct values,
confirmed the proxy DNS resolved from within a pod, and waited for the failing replica to recover
once infrastructure changes propagated. No forced restart was required.

```bash
kubectl get pods -n shopflow                  # watch all replicas return to Running/Ready
kubectl get application shopflow -n argocd    # confirm Healthy status restored
```

---

## Step 5b: Learn the ArgoCD CLI and operations

Work through `COMMANDS.md`. It installs the `argocd` CLI and walks the commands you will actually
use at work: inspecting apps, diffing git against the cluster, syncing and refreshing, rolling back,
and patching. It also has you patch a live deployment and watch self-heal revert it, which teaches
the model better than any explanation.

---

## Step 6: Wire Jenkins to commit instead of deploy

Open `Jenkinsfile.gitops`. Everything up to `Push to ECR` is the pipeline you already know. The old
deploy stage is gone, replaced by `Update GitOps repo`, which clones the GitOps repo, rewrites the
image tag, and commits.

To use it:

1. Add a Jenkins credential `gitops-repo` (username + a GitHub token that can push to the GitOps
   repo).
2. Set `ECR_ACCOUNT` and `GITOPS_REPO` in the file.
3. Create a pipeline job for a service and run it.

Watch what happens: Jenkins finishes and reports success, having never touched the cluster. Then a
moment later, ArgoCD notices the commit and rolls out the new image. Two independent systems,
connected only by git.

**Remove the cluster credentials from Jenkins afterwards** and prove the pipeline still works. That
is the security payoff, and it is one of your deliverables.

---

### What this step proves

After the cluster credentials are removed from Jenkins:

- Jenkins can build, test, scan, push images to ECR, and commit image tag updates to the GitOps
  repo.
- Jenkins **cannot** read cluster secrets, apply manifests, or modify live workloads directly.
- The only path to a cluster change is a Git commit, which is auditable, reviewable, and
  revertable.

This is the **trust boundary**: ArgoCD is the sole deploy actor inside the cluster. A Jenkins
compromise cannot directly mutate production.

---

## Step 7 (optional): Manage the platform itself

Apply `argocd/application-monitoring.yaml` to have ArgoCD manage the Prometheus and Grafana stack
too. Now your monitoring tooling is also declared in git. Try uninstalling it by hand and watch
ArgoCD reinstall it.

---

## Troubleshooting Reference

| Symptom | Cause | Fix |
|---|---|---|
| Pods not all Running after ArgoCD install | ApplicationSet CRD not established | `kubectl apply --server-side --force-conflicts -f <url>` then `kubectl wait --for=condition=Established crd/applicationsets.argoproj.io` |
| App stuck `OutOfSync` and never syncs | `automated` sync off, or wrong `repoURL` | Check Application status in UI; verify `repoURL` and `path` |
| `Synced` but `Degraded` | Manifests applied but workload is unhealthy at runtime | `kubectl -n shopflow describe pod <pod>` and check logs — wrong port, bad image tag, or missing secret |
| Pods `CreateContainerConfigError` | `db-credentials` secret missing from namespace | Redo Step 3 — create namespace then secret before ArgoCD sync |
| Service `CrashLoopBackOff` with JDBC errors | DB connection pool exhausted on RDS instance | Add RDS Proxy via Terraform; update datasource URL in GitOps config |
| Change does not appear after push | ArgoCD polls every ~3 minutes by default | Hit Refresh in UI, or configure a webhook |
| Manual cluster edit snapped back | `selfHeal` is doing its job | Change git instead; disable self-heal only for controlled maintenance windows |

---

## Cleanup

```bash
kubectl delete -f argocd/application-shopflow.yaml   # removes the app and everything it created
kubectl delete namespace argocd
```

Then tear down the Project 6 infrastructure if you are finished with it:

```bash
cd infra
TF_VAR_db_password='YOUR_DB_PASSWORD' terraform destroy
```

---

## Deliverable

Complete the challenges in `ASSIGNMENT.md` and write the report. The report matters more than the
working cluster: this project is about understanding a model, and you will be asked to explain and
defend it, not just show a screenshot.
